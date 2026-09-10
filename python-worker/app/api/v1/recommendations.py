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
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

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
from app.recommandations.traffic import is_bot
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
    # Checkout renders one offer, in the order summary under the cart lines.
    # Three stacked cards made an ~800px block in the column the shopper is
    # scrolling to reach "Pay now", which reads as an obstacle rather than an
    # offer. The extension asks for 1; this is the ceiling if it ever asks for
    # more.
    "mercury": 2,
    "apollo": 1,  # post-purchase interstitial shows a single offer
    "thank_you": 3,
    "phoenix": 4,  # a storefront carousel has room
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
    request: RecommendationRequest,
    services: RecommendationServices,
    user_agent: Optional[str] = None,
) -> dict:
    """Resolve shop -> bucket holdout -> read edges -> enrich -> log impressions."""

    # Traffic that gets recommendations but is not a shopper seeing an offer.
    # `preview` is declared by the storefront (theme editor or preview link);
    # the bot check is server-side because a crawler will not volunteer it.
    if request.preview:
        skip_recording, skip_reason = True, "theme_preview"
    elif is_bot(user_agent):
        skip_recording, skip_reason = True, "bot"
    else:
        skip_recording, skip_reason = False, None

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

    # Merchant surface toggle (Settings). A disabled surface keeps its widget
    # in the theme but serves nothing — same mechanism as the holdout control
    # group, so the extension renders an empty widget without an error.
    shop_settings = shop.settings or {}
    surfaces = shop_settings.get("surfaces") or {}
    if surfaces.get(surface, True) is False:
        logger.info(
            f"🚫 Surface '{surface}' disabled by merchant for {request.shop_domain}"
        )
        return _empty(request, "surface_disabled")

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
    holdout_pct = HoldoutService.get_holdout_percent(shop, surface)
    if HoldoutService.is_held_out(
        shop_id=shop.id,
        customer_id=request.user_id,
        session_id=request.session_id,
        holdout_percent=holdout_pct,
    ):
        # A bot or a theme preview that lands in the control bucket must not be
        # logged either: control sessions are the counterfactual the billed lift
        # is measured against, so padding them understates the app's effect just
        # as recording fake impressions overstates the denominator.
        if skip_recording:
            logger.info(
                f"👻 Held-out {skip_reason} not recorded as control | surface={surface}"
            )
            return {
                "recommendations": [],
                "count": 0,
                "source": "holdout_control",
                "context": request.context,
                "timestamp": now_utc(),
                "holdout": {"is_control": True, "holdout_percent": holdout_pct},
            }

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
            lambda t: (
                logger.error(f"Control session logging failed: {t.exception()}")
                if t.exception()
                else None
            )
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
        request.metadata.get("cart_value") or request.metadata.get("order_value") or 0.0
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

    # Merchant-managed exclusions (Settings): products that must never be
    # offered, regardless of edges or purchase history.
    merchant_exclusions = shop_settings.get("excluded_product_ids") or []
    if merchant_exclusions:
        exclude_items.extend([str(p) for p in merchant_exclusions])
        logger.info(
            f"🚫 {len(merchant_exclusions)} merchant-excluded products for "
            f"{request.shop_domain} on {surface}"
        )

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

    # Offers this shopper has already answered. Without this the same product
    # comes back after an explicit decline — we recorded the refusal and then
    # recommended it seven more times.
    try:
        async with get_transaction_context() as session:
            answered = await services.exclusion.get_impression_exclusions(
                session=session,
                shop_id=shop.id,
                customer_id=effective_user_id,
                session_id=request.session_id,
            )
        exclude_items.extend(answered)
        if answered:
            logger.info(
                f"🚫 {len(answered)} already-answered offers excluded on {surface}"
            )
    except Exception as e:
        logger.warning(f"⚠️ Failed to get impression exclusions: {e}")

    exclude_items = list(dict.fromkeys(exclude_items))

    # 6. Cache
    #
    # exclude_items is part of the key. It was omitted, so two shoppers with the
    # same cart and no resolvable user id shared one cache entry — which would
    # have served each of them the other's excluded offers and quietly undone
    # every exclusion above.
    cache_key = services.cache.generate_cache_key(
        shop_id=shop.id,
        context=request.context,
        product_ids=context_ids,
        user_id=effective_user_id,
        category=None,
        limit=limit,
        exclude_items=exclude_items,
    )
    cached = await services.cache.get_cached_recommendations(cache_key, request.context)
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

    source = (
        "edges_observed"
        if any(c["source"] == "observed" for c in candidates)
        else "edges_prior"
    )

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
    #
    # Not written for a theme preview or a bot. Both still get real
    # recommendations — a merchant previewing their theme wants to see the
    # widget work, and a crawler should render a normal page — but neither is a
    # shopper being shown an offer. Recording them inflates the "offers shown"
    # denominator with impressions no human saw, which drags down the very
    # conversion rate the merchant is billed against.
    #
    # Guarded here rather than in each extension because every surface routes
    # through this function, so one check covers phoenix, mercury, apollo and
    # venus at once.
    if skip_recording:
        logger.info(
            f"👻 Serving {len(final_items)} recommendations without impressions "
            f"| reason={skip_reason} | surface={surface}"
        )

    for idx, item in enumerate([] if skip_recording else final_items):
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
            item["url"] = _tag_url(item.get("url"), iid, item.get("id"))

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
        lambda t: (
            logger.error(f"Analytics logging failed: {t.exception()}")
            if t.exception()
            else None
        )
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


# Query parameter carrying the impression a click came from.
#
# This is the only thing that survives a navigation out of an extension's
# sandbox. When a shopper follows a recommendation to the product's own page,
# they add it there with the *theme's* button — an add this app never observes,
# so no impression id can be stamped on the cart line. The parameter hands that
# id to Phoenix on arrival, which is what lets the click be joined to the
# eventual order.
#
# Deliberately an opaque impression UUID and nothing else. URLs get logged by
# proxies, pasted into chats and indexed by crawlers, so a customer id or email
# here would leak; a UUID that means nothing outside our own tables does not.
IMPRESSION_QUERY_PARAM = "_bb_imp"

# The product the impression was recommending, carried alongside it.
#
# Phoenix pairs the two on the cart so the eventual order can be checked against
# what was actually recommended. Without it a shopper who followed five
# recommendations and bought two would have all five credited — the claim has to
# name a product for the order to be able to refute it.
PRODUCT_QUERY_PARAM = "_bb_pid"


def _tag_url(
    url: Optional[str], impression_id: str, product_id: Optional[str] = None
) -> Optional[str]:
    """Append the impression id to a product URL, preserving existing params.

    Built with urlencode rather than string concatenation so a handle that
    already carries a query string or fragment survives intact — `?variant=123`
    is common on these links and a naive `+ "?_bb_imp="` would corrupt it.
    """
    if not url:
        return url

    try:
        parts = urlsplit(url)
        query = parse_qsl(parts.query, keep_blank_values=True)
        # Never duplicate the parameters if a URL somehow already carries them.
        query = [
            (k, v)
            for k, v in query
            if k not in (IMPRESSION_QUERY_PARAM, PRODUCT_QUERY_PARAM)
        ]
        query.append((IMPRESSION_QUERY_PARAM, str(impression_id)))
        if product_id:
            query.append((PRODUCT_QUERY_PARAM, str(product_id)))
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
        )
    except Exception as e:
        # A malformed URL must not cost the shopper their recommendation.
        logger.warning(f"⚠️ Could not tag url {url!r}: {e}")
        return url


def _empty(request: RecommendationRequest, reason: str, holdout_pct: int = 0) -> dict:
    return {
        "recommendations": [],
        "count": 0,
        "source": reason,
        "context": request.context,
        "timestamp": now_utc(),
        "holdout": {"is_control": False, "holdout_percent": holdout_pct},
    }


# "" and not "/": with a trailing slash the registered path becomes
# /api/v1/recommendations/ and every client posting to the unslashed path gets a
# 307. Behind the dev tunnel that redirect is emitted as http:// (uvicorn cannot
# see the original scheme), so the browser blocks it as mixed content — the POST
# never leaves the page, nothing reaches this worker, and the storefront sits on
# its loading skeleton forever with no failed request visible in the network tab.
# Every other route in this API is unslashed; this was the only exception.
@router.post("", response_model=RecommendationResponse)
async def get_recommendations(
    request: RecommendationRequest,
    authorization: str = Header(None),
    user_agent: str = Header(None),
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

        result_data = await fetch_recommendations_logic(
            request, services, user_agent=user_agent
        )

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
