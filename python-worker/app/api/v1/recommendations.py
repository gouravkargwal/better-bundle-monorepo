"""
Recommendation API.

Serving is an indexed lookup over precomputed `product_edges` — no model
inference, no LLM call, no fan-out. Everything expensive happened in the install
pipeline and the nightly co-purchase miner.

Only two contexts are served, because only two surfaces exist: Mercury renders
in the checkout, Apollo after purchase. The previous implementation branched
across nine contexts (product_page, homepage, cart, collection_page and friends)
through a chain of hybrid blending, smart selection and retrieval fusion — none
of which had a storefront extension that could render the result. Those branches
are gone along with the services behind them.

The holdout and impression logic is unchanged and load-bearing: a held-out
shopper is shown nothing and recorded as control, and every offer shown writes
an impression row whose id goes back to the extension for the outcome callback.
That is what makes attributed revenue measurable rather than asserted.
"""

import asyncio
import time
import uuid
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, Header

from app.core.database.session import get_transaction_context
from app.core.logging import get_logger
from app.core.metrics import recommendations_served, recommendation_duration
from app.recommandations.analytics import RecommendationAnalytics
from app.recommandations.cache import RecommendationCacheService
from app.recommandations.edges.serving import EdgeRecommender
from app.recommandations.enrichment import ProductEnrichment
from app.recommandations.exclusion_service import ProductExclusionService
from app.recommandations.models import RecommendationRequest, RecommendationResponse
from app.recommandations.shop_lookup_service import ShopLookupService
from app.recommandations.client_id_resolver import ClientIdResolver
from app.services.holdout_service import HoldoutService
from app.shared.helpers import now_utc

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])


# Context -> surface. A context with no surface cannot be served, so the map is
# also the validation list.
# Context -> surface. A context with no extension to render it cannot be
# served, so this map doubles as the validation list.
#
# Plan reach, worst to best:
#   mercury    checkout UI block            SHOPIFY PLUS ONLY
#   apollo     post-purchase interstitial   all plans, only with a vaulted card
#   thank_you  Thank You page block         all plans, no gate
#   venus      customer account order status all plans
#   phoenix    theme app blocks             all plans — widest of all
CONTEXT_SURFACE = {
    # Checkout / post-purchase
    "checkout_page": "mercury",
    "post_purchase": "apollo",
    "thank_you_page": "thank_you",
    # Storefront (phoenix theme app extension). Product page only: the other
    # blocks were removed, and a context with no block to render it would just
    # be a 400 waiting to happen.
    "product_page": "phoenix",
    # Customer account (venus)
    "order_status": "venus",
}

# How many offers each surface shows. Checkout is a low-consideration moment and
# a long list reads as an interruption.
RETURN_LIMIT = {
    "mercury": 3,     # checkout: a long list reads as an interruption
    "apollo": 1,      # post-purchase interstitial shows a single offer
    "thank_you": 3,
    "phoenix": 4,     # a storefront carousel has room
    "venus": 2,
}


# --- Custom Exceptions for Core Logic ---
class RecommendationLogicError(Exception):
    """Base exception for recommendation logic errors."""


class InvalidInputError(RecommendationLogicError):
    """Raised for invalid request parameters like context."""


class ShopNotFoundError(RecommendationLogicError):
    """Raised when a shop cannot be found."""


@dataclass
class RecommendationServices:
    shop_lookup: ShopLookupService
    client_id_resolver: ClientIdResolver
    exclusion: ProductExclusionService
    cache: RecommendationCacheService
    edges: EdgeRecommender
    enrichment: ProductEnrichment
    analytics: RecommendationAnalytics


services = RecommendationServices(
    shop_lookup=ShopLookupService(),
    client_id_resolver=ClientIdResolver(),
    exclusion=ProductExclusionService(),
    cache=RecommendationCacheService(),
    edges=EdgeRecommender(),
    enrichment=ProductEnrichment(),
    analytics=RecommendationAnalytics(),
)


async def fetch_recommendations_logic(
    request: RecommendationRequest, services: RecommendationServices
) -> dict:
    """Resolve shop -> bucket holdout -> read edges -> enrich -> log impressions."""

    # 1. Resolve and validate the shop
    shop_domain = request.shop_domain
    if not shop_domain and request.user_id:
        shop_domain = await services.shop_lookup.get_shop_domain_from_customer_id(
            request.user_id
        )
        if not shop_domain:
            raise InvalidInputError(
                f"Could not determine shop domain for customer {request.user_id}. "
                f"Please provide shop_domain in request."
            )
        request.shop_domain = shop_domain
    elif not shop_domain:
        raise InvalidInputError(
            "Either shop_domain or user_id must be provided to determine the shop."
        )

    # 2. Context must map to a live surface
    surface = CONTEXT_SURFACE.get(request.context)
    if surface is None:
        raise InvalidInputError(
            f"Invalid context '{request.context}'. Must be one of: "
            f"{sorted(CONTEXT_SURFACE)}"
        )

    shop = await services.shop_lookup.validate_shop_exists(request.shop_domain)
    if not shop:
        raise ShopNotFoundError(f"Shop {request.shop_domain} not found")

    request.metadata = request.metadata or {}

    # 3. Holdout bucketing. A control shopper sees nothing and is recorded, so
    # their behaviour becomes the counterfactual the billing rests on.
    #
    # A shopper with no stable identity cannot be bucketed — most often because
    # they declined measurement consent, so the storefront sent no visitor id.
    # They still get recommendations, but they must be flagged: counting an
    # unbucketable shopper as treatment inflates that arm with people who could
    # never have landed in control, which biases the lift the merchant is
    # billed on.
    is_bucketable = bool(request.user_id or request.session_id)
    impression_group_id = str(uuid.uuid4())
    holdout_pct = HoldoutService.get_holdout_percent(shop)
    if HoldoutService.is_held_out(
        shop_id=shop.id,
        customer_id=request.user_id,
        session_id=request.session_id,
        holdout_percent=holdout_pct,
    ):
        task = asyncio.create_task(
            HoldoutService.log_control_session(
                shop_id=shop.id,
                surface=surface,
                session_id=request.session_id,
                customer_id=request.user_id,
                metadata={
                    "context": request.context,
                    "impression_group_id": impression_group_id,
                },
                impression_group_id=impression_group_id,
            )
        )
        task.add_done_callback(
            lambda t: logger.error(f"Control session logging failed: {t.exception()}")
            if t.exception()
            else None
        )
        return {
            "recommendations": [],
            "count": 0,
            "source": "holdout_control",
            "context": request.context,
            "timestamp": now_utc(),
            "holdout": {"is_control": True, "holdout_percent": holdout_pct},
        }

    # 4. The shopper's context products: cart contents at checkout, purchased
    # items post-purchase. Without them there is nothing to key an edge lookup on.
    context_ids = list(request.product_ids or []) or list(
        request.metadata.get("cart_items") or []
    )
    if request.product_id:
        context_ids.append(request.product_id)
    context_ids = [str(p) for p in dict.fromkeys(context_ids) if p]

    if not context_ids:
        logger.info(
            f"No context products for {request.context} on {request.shop_domain}"
        )
        return _empty(request, "no_context_products")

    context_value = float(
        request.metadata.get("cart_value")
        or request.metadata.get("order_value")
        or 0.0
    )
    limit = request.limit or RETURN_LIMIT.get(surface, 3)

    # 5. Exclusions: what this shopper already owns.
    effective_user_id = request.user_id
    if not effective_user_id:
        try:
            effective_user_id = await _resolve_user(request, shop.id)
        except Exception as e:
            logger.warning(f"⚠️ Failed to resolve user_id: {e}")

    exclude_items = list(context_ids)
    if effective_user_id:
        try:
            async with get_transaction_context() as session:
                purchased = await services.exclusion.get_smart_purchase_exclusions(
                    session=session,
                    shop_id=shop.id,
                    user_id=effective_user_id,
                    context=request.context,
                )
            exclude_items.extend(purchased)
            logger.info(
                f"🚫 {len(purchased)} purchase exclusions | context={request.context}"
            )
        except Exception as e:
            logger.warning(f"⚠️ Failed to get exclusions for {effective_user_id}: {e}")

    # 6. Cache
    cache_key = services.cache.generate_cache_key(
        shop_id=shop.id,
        context=request.context,
        product_ids=context_ids,
        user_id=effective_user_id,
        category=None,
        limit=limit,
    )
    cached = await services.cache.get_cached_recommendations(
        cache_key, request.context
    )
    if cached:
        logger.info(f"⚡ Cache hit | context={request.context}")
        return {
            "recommendations": cached.get("recommendations", []),
            "count": cached.get("count", 0),
            "source": cached.get("source", "cache"),
            "context": request.context,
            "timestamp": now_utc(),
            "holdout": {"is_control": False, "holdout_percent": holdout_pct},
        }

    # 7. The lookup itself
    candidates = await services.edges.recommend(
        shop_id=shop.id,
        context_product_ids=context_ids,
        surface=surface,
        context_value=context_value,
        limit=limit,
        exclude_product_ids=exclude_items,
    )
    if not candidates:
        return _empty(request, "no_edges", holdout_pct)

    source = "edges_observed" if any(
        c["source"] == "observed" for c in candidates
    ) else "edges_prior"

    # 8. Hydrate with product detail, drop anything unavailable
    enriched = await services.enrichment.enrich_items(
        shop.id, candidates, request.context, source
    )
    final_items = [i for i in enriched if i.get("available", True)]
    final_items = services.enrichment.enhance_recommendations_with_currency(
        final_items, shop.currency_code or "USD"
    )
    logger.info(
        f"🎯 {len(final_items)} recommendations | context={request.context} "
        f"| source={source}"
    )
    if not final_items:
        return _empty(request, "all_unavailable", holdout_pct)

    # 9. Impressions. Written before the response so the extension always has an
    # impression_id to report an outcome against.
    for idx, item in enumerate(final_items):
        iid = await HoldoutService.log_impression(
            shop_id=shop.id,
            surface=surface,
            offer_type="upsell" if surface == "apollo" else "cross_sell",
            is_control=False,
            session_id=request.session_id,
            customer_id=request.user_id,
            offer_id=str(item.get("id", "")),
            variant_id=str(item.get("variant_id", "")),
            metadata={
                "context": request.context,
                "position": idx,
                "source": source,
                "edge_type": item.get("edge_type"),
                "score": item.get("blended_score"),
                "price": item.get("price"),
                "impression_group_id": impression_group_id,
                # False when the shopper had no stable identity to bucket on.
                # Exclude these from any treatment-vs-control comparison.
                "bucketed": is_bucketable,
            },
            impression_group_id=impression_group_id,
        )
        if iid:
            item["impression_id"] = iid

    response_data = {
        "recommendations": final_items,
        "count": len(final_items),
        "source": source,
        "context": request.context,
        "shop_id": shop.id,
        "user_id": request.user_id,
        "timestamp": now_utc().isoformat(),
    }
    await services.cache.cache_recommendations(
        cache_key, response_data, request.context
    )

    analytics_task = asyncio.create_task(
        services.analytics.log_recommendation_request(
            shop_id=shop.id,
            context=request.context,
            source=source,
            count=len(final_items),
            user_id=effective_user_id,
            product_ids=context_ids,
            category=None,
        )
    )
    analytics_task.add_done_callback(
        lambda t: logger.error(f"Analytics logging failed: {t.exception()}")
        if t.exception()
        else None
    )

    return {
        "recommendations": final_items,
        "count": len(final_items),
        "source": source,
        "context": request.context,
        "timestamp": now_utc(),
        "holdout": {"is_control": False, "holdout_percent": holdout_pct},
    }


async def _resolve_user(request: RecommendationRequest, shop_id: str):
    """Best-effort identity resolution from client or session id."""
    if request.client_id:
        return await services.client_id_resolver.resolve_user_id_from_client_id(
            client_id=request.client_id, shop_id=shop_id
        )
    if request.session_id:
        return await services.client_id_resolver.resolve_user_id_from_session_id(
            session_id=request.session_id, shop_id=shop_id
        )
    return None


def _empty(request: RecommendationRequest, reason: str, holdout_pct: int = 0) -> dict:
    return {
        "recommendations": [],
        "count": 0,
        "source": reason,
        "context": request.context,
        "timestamp": now_utc(),
        "holdout": {"is_control": False, "holdout_percent": holdout_pct},
    }


@router.post("/", response_model=RecommendationResponse)
async def get_recommendations(
    request: RecommendationRequest, authorization: str = Header(None)
):
    """Context-aware recommendations, served from precomputed edges."""
    start = time.time()
    try:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "Missing or invalid authorization header",
                    "message": "Please provide a valid JWT token in Authorization header",
                    "required_format": "Bearer <jwt_token>",
                },
            )

        result_data = await fetch_recommendations_logic(request, services)

        duration = time.time() - start
        labels = {
            "context": request.context,
            "source": result_data.get("source", "unknown"),
        }
        recommendations_served.add(result_data.get("count", 0), labels)
        recommendation_duration.record(duration, labels)

        return RecommendationResponse(success=True, **result_data)

    except HTTPException:
        raise
    except InvalidInputError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ShopNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except (Exception, RecommendationLogicError) as e:
        logger.error(
            f"💥 Recommendation request failed | shop={request.shop_domain} "
            f"| context={request.context} | error={e}"
        )
        recommendation_duration.record(
            time.time() - start,
            {"context": request.context, "source": "error", "error": "true"},
        )
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while fetching recommendations.",
        )
