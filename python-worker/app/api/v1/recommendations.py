"""
Recommendation API endpoints
Handles all recommendation requests from Shopify extension with context-based routing
"""

import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException, Header
from dataclasses import dataclass

from app.shared.helpers import now_utc

from app.core.logging import get_logger
from app.shared.gorse_api_client import GorseApiClient
from app.core.database.session import get_transaction_context
from app.core.config.settings import settings
from app.recommandations.models import RecommendationRequest, RecommendationResponse
from app.recommandations.category_detection import CategoryDetectionService
from app.recommandations.cache import RecommendationCacheService
from app.recommandations.hybrid import HybridRecommendationService
from app.recommandations.analytics import RecommendationAnalytics
from app.recommandations.enrichment import ProductEnrichment
from app.recommandations.exclusion_service import ProductExclusionService
from app.recommandations.session_service import SessionDataService
from app.recommandations.recommendation_executor import RecommendationExecutor
from app.recommandations.smart_selection_service import SmartSelectionService
from app.recommandations.shop_lookup_service import ShopLookupService
from app.recommandations.client_id_resolver import ClientIdResolver

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])


# --- Custom Exceptions for Core Logic ---
# These allow the core logic to be decoupled from FastAPI's HTTPException
class RecommendationLogicError(Exception):
    """Base exception for recommendation logic errors."""

    pass


class InvalidInputError(RecommendationLogicError):
    """Raised for invalid request parameters like context."""

    pass


class ShopNotFoundError(RecommendationLogicError):
    """Raised when a shop cannot be found."""

    pass


# --- Service Dependencies Container ---
# Using a dataclass to group services makes passing them around cleaner.
@dataclass
class RecommendationServices:
    shop_lookup: ShopLookupService
    category: CategoryDetectionService
    client_id_resolver: ClientIdResolver
    exclusion: ProductExclusionService
    cache: RecommendationCacheService
    session: SessionDataService
    hybrid: HybridRecommendationService
    smart_selection: SmartSelectionService
    executor: RecommendationExecutor
    enrichment: ProductEnrichment
    analytics: RecommendationAnalytics


# --- Initialize Services ---
# In a real application, you might use a dependency injection framework.
# For this example, we'll instantiate them here and bundle them.
gorse_client = GorseApiClient(
    base_url=settings.ml.GORSE_BASE_URL, api_key=settings.ml.GORSE_API_KEY
)
recommendation_executor = RecommendationExecutor(gorse_client)

services = RecommendationServices(
    shop_lookup=ShopLookupService(),
    category=CategoryDetectionService(),
    client_id_resolver=ClientIdResolver(),
    exclusion=ProductExclusionService(),
    cache=RecommendationCacheService(),
    session=SessionDataService(),
    hybrid=HybridRecommendationService(),
    smart_selection=SmartSelectionService(recommendation_executor),
    executor=recommendation_executor,
    enrichment=ProductEnrichment(),
    analytics=RecommendationAnalytics(),
)


# --- Reusable Core Logic Function ---
async def fetch_recommendations_logic(
    request: RecommendationRequest, services: RecommendationServices
) -> dict:
    """
    Core logic to fetch recommendations. Decoupled from the API layer.

    Args:
        request: The recommendation request data.
        services: A container with all necessary service clients.

    Returns:
        A dictionary containing the recommendation results.

    Raises:
        InvalidInputError: If the request contains invalid data (e.g., context).
        ShopNotFoundError: If the specified shop cannot be found.
        RecommendationLogicError: For other generic processing errors.
    """
    # 1. Resolve and Validate Shop Domain
    shop_domain = request.shop_domain
    if not shop_domain and request.user_id:
        shop_domain = await services.shop_lookup.get_shop_domain_from_customer_id(
            request.user_id
        )
        if shop_domain:
            request.shop_domain = shop_domain
        else:
            logger.error(
                f"❌ Could not find shop_domain for customer {request.user_id}"
            )
            raise InvalidInputError(
                f"Could not determine shop domain for customer {request.user_id}. Please provide shop_domain in request."
            )
    elif not shop_domain:
        logger.error("❌ No shop_domain or user_id provided")
        raise InvalidInputError(
            "Either shop_domain or user_id must be provided to determine the shop."
        )

    # 2. Context Handling & Validation
    if request.context == "post_purchase":
        logger.info(f"Processing post-purchase recommendations for shop {shop_domain}")
        request.metadata = request.metadata or {}
        request.metadata["post_purchase"] = True

    # Mercury checkout context handling
    if request.context == "checkout_page":
        logger.info(
            f"Processing Mercury checkout recommendations for shop {shop_domain}"
        )
        request.metadata = request.metadata or {}
        request.metadata["mercury_checkout"] = True
        request.metadata["checkout_type"] = "one_page"  # Default to one-page checkout
        # Add Mercury-specific metadata for checkout optimization
        if hasattr(request, "cart_value") and request.cart_value:
            request.metadata["cart_value"] = request.cart_value
        if hasattr(request, "cart_items") and request.cart_items:
            request.metadata["cart_items"] = request.cart_items
        if hasattr(request, "checkout_step") and request.checkout_step:
            request.metadata["checkout_step"] = request.checkout_step

    valid_contexts = [
        "product_page",
        "product_page_similar",
        "product_page_frequently_bought",
        "product_page_customers_viewed",
        "homepage",
        "cart",
        "collection_page",
        "profile",
        "checkout_page",
        "order_history",
        "order_status",
        "post_purchase",
    ]
    if request.context not in valid_contexts:
        raise InvalidInputError(f"Invalid context. Must be one of: {valid_contexts}")

    shop = await services.shop_lookup.validate_shop_exists(request.shop_domain)
    if not shop:
        raise ShopNotFoundError(f"Shop {request.shop_domain} not found")

    # 3. Auto-detect Category
    category = request.category
    if not category and request.product_ids:
        detected_categories = set()
        for pid in request.product_ids[:10]:
            try:
                cat = await services.category.get_product_category(pid, shop.id)
                if cat:
                    detected_categories.add(cat)
            except Exception as e:
                logger.debug(f"⚠️ Category detection failed for product {pid}: {e}")
        if len(detected_categories) == 1:
            category = next(iter(detected_categories))
        elif len(detected_categories) > 1:
            category = None

    if request.product_id and not request.product_ids:
        request.product_ids = [request.product_id]

    # 4. Resolve User ID and Determine Exclusions
    exclude_items = list(set(request.product_ids)) if request.product_ids else []
    logger.info(
        f"📦 Initial exclusion list from request.product_ids: {exclude_items} | context={request.context}"
    )
    effective_user_id = request.user_id

    # Resolve user_id from metadata or session if not present
    if not effective_user_id:
        try:
            async with get_transaction_context() as session:
                if request.metadata:
                    effective_user_id = (
                        await services.client_id_resolver.resolve_user_id_from_metadata(
                            session=session, shop_id=shop.id, metadata=request.metadata
                        )
                    )
                if not effective_user_id and request.session_id:
                    effective_user_id = await services.client_id_resolver.resolve_user_id_from_session_data(
                        session=session, shop_id=shop.id, session_id=request.session_id
                    )
        except Exception as e:
            logger.warning(f"⚠️ Failed to resolve user_id: {e}")

    # Gather purchase and cart exclusions for the user
    if effective_user_id:
        try:
            async with get_transaction_context() as session:
                purchase_exclusions = (
                    await services.exclusion.get_smart_purchase_exclusions(
                        session=session,
                        shop_id=shop.id,
                        user_id=effective_user_id,
                        context=request.context,
                    )
                )
                cart_exclusions = (
                    await services.exclusion.get_cart_time_decay_exclusions(
                        session=session,
                        shop_id=shop.id,
                        user_id=effective_user_id,
                    )
                )
                exclude_items.extend(purchase_exclusions)
                exclude_items.extend(cart_exclusions)
                logger.info(
                    f"🚫 Purchase exclusions: {len(purchase_exclusions)} items | cart exclusions: {len(cart_exclusions)} items | context={request.context}"
                )
                if purchase_exclusions:
                    logger.debug(f"   Purchase exclusions: {purchase_exclusions[:5]}")
                if cart_exclusions:
                    logger.debug(f"   Cart exclusions: {cart_exclusions[:5]}")
        except Exception as e:
            logger.warning(
                f"⚠️ Failed to get exclusions for user {effective_user_id}: {e}"
            )

    # Add current cart items to exclusion list (from request metadata)
    current_cart_items = (
        request.metadata.get("cart_items", []) if request.metadata else []
    )
    if current_cart_items:
        exclude_items.extend(current_cart_items)
        logger.info(f"🚫 Excluding current cart items: {current_cart_items}")

    final_exclude_items = list(set(exclude_items)) if exclude_items else None
    if final_exclude_items:
        logger.info(
            f"🚫 Final exclusion list: {len(final_exclude_items)} unique items | context={request.context} | excluded_ids={final_exclude_items}"
        )

    # 5. Cache Check
    cache_key = services.cache.generate_cache_key(
        shop_id=shop.id,
        context=request.context,
        product_ids=request.product_ids,
        user_id=effective_user_id,
        session_id=request.session_id,
        category=category,
        limit=request.limit,
        exclude_items=final_exclude_items,
    )
    cached_result = await services.cache.get_cached_recommendations(
        cache_key, request.context
    )
    if cached_result:
        recs = cached_result.get("recommendations", {}).get("recommendations", [])
        filtered_recs = [
            rec
            for rec in recs
            if rec.get("available", True)
            and (not final_exclude_items or rec.get("id") not in final_exclude_items)
        ]
        return {
            "recommendations": filtered_recs,
            "count": len(filtered_recs),
            "source": "cache",
            "context": request.context,
            "timestamp": now_utc(),
        }

    # 6. Fetch Fresh Recommendations
    logger.debug(
        f"💨 Cache miss, fetching fresh recommendations | context={request.context}"
    )
    result = None

    if result is None:
        if request.context == "product_page":
            result = (
                await services.smart_selection.get_smart_product_page_recommendation(
                    shop_id=shop.id,
                    product_ids=request.product_ids,
                    user_id=effective_user_id,
                    limit=request.limit,
                )
            )
        elif request.context == "homepage":
            result = await services.smart_selection.get_smart_homepage_recommendation(
                shop_id=shop.id, user_id=effective_user_id, limit=request.limit
            )
        elif request.context == "collection_page":
            result = (
                await services.smart_selection.get_smart_collection_page_recommendation(
                    shop_id=shop.id,
                    collection_id=request.collection_id,
                    category=category,
                    user_id=effective_user_id,
                    limit=request.limit,
                )
            )
        elif request.context == "cart":
            result = await services.smart_selection.get_smart_cart_page_recommendation(
                shop_id=shop.id,
                cart_items=request.product_ids,
                user_id=effective_user_id,
                limit=request.limit,
            )
        elif request.context == "checkout_page":
            # Mercury checkout-specific recommendations - FBT ONLY
            logger.info(
                f"🎯 Mercury: Generating FBT-only checkout recommendations for shop {shop_domain}"
            )

            # Use FBT directly for checkout recommendations
            from app.recommandations.frequently_bought_together import (
                FrequentlyBoughtTogetherService,
            )

            fbt_service = FrequentlyBoughtTogetherService()
            cart_items = request.product_ids or request.metadata.get("cart_items", [])
            cart_value = request.metadata.get("cart_value", 0.0)

            # For FBT, we need at least one product in cart
            if not cart_items:
                result = {
                    "success": False,
                    "items": [],
                    "source": "fbt_no_cart_items",
                    "error": "No cart items provided for FBT recommendations",
                }
            else:
                # Use the first cart item for FBT recommendations
                primary_product = cart_items[0]
                result = await fbt_service.get_frequently_bought_together(
                    shop_id=shop.id,
                    product_id=primary_product,
                    limit=request.limit,
                    cart_value=cart_value,
                )

                # Add Mercury-specific metadata
                if result.get("success"):
                    result["smart_selection"] = {
                        "selected_type": "frequently_bought_together",
                        "visitor_type": ("returning" if effective_user_id else "new"),
                        "checkout_context": "mercury_fbt_only",
                        "cart_value": cart_value,
                        "checkout_step": request.metadata.get("checkout_step"),
                        "reason": "fbt_complementary_upsells",
                        "primary_product": primary_product,
                    }

                # If FBT failed or returned no items, fallback to normal Gorse
                if not result.get("success") or not result.get("items"):
                    # Ensure session-based fallback can use cart contents
                    fallback_metadata = dict(request.metadata or {})
                    if cart_items:
                        fallback_metadata["cart_contents"] = cart_items

                    # Skip FBT in fallback to avoid retrying it; prefer session/user/popular
                    custom_levels = {
                        "checkout_page": [
                            "session_recommendations",
                            "user_recommendations",
                            "popular_category",
                            "popular",
                        ]
                    }

                    result = await services.executor.execute_fallback_chain(
                        context="checkout_page",
                        shop_id=shop.id,
                        product_ids=request.product_ids,
                        user_id=effective_user_id,
                        session_id=request.session_id,
                        category=category,
                        limit=request.limit,
                        metadata=fallback_metadata,
                        exclude_items=final_exclude_items,
                        fallback_levels=custom_levels,
                    )
        else:  # Default fallback for other contexts
            result = await services.executor.execute_fallback_chain(
                context=request.context,
                shop_id=shop.id,
                product_ids=request.product_ids,
                user_id=effective_user_id,
                session_id=request.session_id,
                category=category,
                limit=request.limit,
                metadata=request.metadata,
                exclude_items=final_exclude_items,
            )

    if not result["success"] or not result["items"]:
        logger.warning(
            f"⚠️ No recommendations from executor | context={request.context} | success={result.get('success')} | items_count={len(result.get('items', []))} | source={result.get('source')}"
        )
        return {
            "recommendations": [],
            "count": 0,
            "source": result.get("source", "no_recommendations"),
            "context": request.context,
            "timestamp": now_utc(),
        }

    logger.info(
        f"📦 Executor returned {len(result['items'])} items | context={request.context} | source={result.get('source')} | item_ids={result['items'][:5]}"
    )

    # 7. Enrich, Filter, and Finalize
    enriched_items = await services.enrichment.enrich_items(
        shop.id, result["items"], request.context, result["source"]
    )

    logger.info(
        f"✨ Enrichment returned {len(enriched_items)} items | context={request.context} | source={result.get('source')}"
    )

    available_items = [item for item in enriched_items if item.get("available", True)]

    logger.info(
        f"✅ {len(available_items)} items available after filtering | context={request.context}"
    )

    final_items = []
    excluded_by_id = []
    for item in available_items:
        item_id = item.get("id")
        if final_exclude_items and item_id in final_exclude_items:
            excluded_by_id.append(item_id)
        else:
            final_items.append(item)

    if excluded_by_id:
        logger.warning(
            f"🚫 Excluded {len(excluded_by_id)} items by ID | context={request.context} | excluded_ids={excluded_by_id}"
        )
    logger.info(
        f"🎯 Final {len(final_items)} recommendations after exclusions | context={request.context} | excluded={len(available_items) - len(final_items)}"
    )

    shop_currency = shop.currency_code if shop and shop.currency_code else "USD"
    final_items = services.enrichment.enhance_recommendations_with_currency(
        final_items, shop_currency
    )

    response_data = {
        "recommendations": final_items,
        "count": len(final_items),
        "source": result["source"],
        "context": request.context,
        "shop_id": shop.id,
        "user_id": request.user_id,
        "timestamp": now_utc().isoformat(),
        "category_detected": category if not request.category else None,
    }

    # 8. Cache and Log Side-effects
    await services.cache.cache_recommendations(
        cache_key, response_data, request.context
    )
    asyncio.create_task(
        services.analytics.log_recommendation_request(
            shop_id=shop.id,
            context=request.context,
            source=result["source"],
            count=len(final_items),
            user_id=effective_user_id,
            product_ids=request.product_ids,
            category=category,
        )
    )

    # Return only the data needed for the final response model
    return {
        "recommendations": final_items,
        "count": len(final_items),
        "source": result["source"],
        "context": request.context,
        "timestamp": now_utc(),
    }


# --- FastAPI Endpoint (Thin Wrapper) ---
@router.post("/", response_model=RecommendationResponse)
async def get_recommendations(
    request: RecommendationRequest, authorization: str = Header(None)
):
    """
    Get recommendations based on context with intelligent fallback system.

    This endpoint provides context-aware recommendations using JWT-based authorization.
    It uses stateless JWT validation instead of Redis/database checks for better performance.
    """
    try:
        # Extract JWT token from Authorization header
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "Missing or invalid authorization header",
                    "message": "Please provide a valid JWT token in Authorization header",
                    "required_format": "Bearer <jwt_token>",
                },
            )

        jwt_token = authorization.split(" ")[1]

        # Pass the request and the bundled services to the core logic function
        result_data = await fetch_recommendations_logic(request, services)

        return RecommendationResponse(success=True, **result_data)

    except HTTPException:
        # Re-raise HTTP exceptions (like 403 from suspension check) without modification
        raise
    except InvalidInputError as e:
        # Handle validation errors with a 400 Bad Request
        raise HTTPException(status_code=400, detail=str(e))
    except ShopNotFoundError as e:
        # Handle not found errors with a 404 Not Found
        raise HTTPException(status_code=404, detail=str(e))
    except (Exception, RecommendationLogicError) as e:
        # Handle all other logic or unexpected errors with a 500 Internal Server Error
        logger.error(
            f"💥 Recommendation request failed | shop={request.shop_domain} | context={request.context} | error={str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"An unexpected error occurred while fetching recommendations.",
        )
