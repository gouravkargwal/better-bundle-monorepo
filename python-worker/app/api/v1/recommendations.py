"""
Recommendation API endpoints
Handles all recommendation requests from Shopify extension with context-based routing
"""

import asyncio
from datetime import datetime
from fastapi import APIRouter, HTTPException

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

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])

# Initialize Gorse client
gorse_client = GorseApiClient(
    base_url=settings.ml.GORSE_BASE_URL, api_key=settings.ml.GORSE_API_KEY
)

# Initialize services
category_service = CategoryDetectionService()
cache_service = RecommendationCacheService()
hybrid_service = HybridRecommendationService()
analytics_service = RecommendationAnalytics()
enrichment_service = ProductEnrichment()
exclusion_service = ProductExclusionService()
session_service = SessionDataService()
recommendation_executor = RecommendationExecutor(gorse_client)
smart_selection_service = SmartSelectionService(recommendation_executor)
shop_lookup_service = ShopLookupService()


@router.post("/", response_model=RecommendationResponse)
async def get_recommendations(request: RecommendationRequest):
    """
    Get recommendations based on context with intelligent fallback system

    This endpoint provides context-aware recommendations using Gorse ML models
    with automatic fallbacks when Gorse is unavailable.

    Features:
    - Auto category detection from product_id
    - Context-specific caching with Redis
    - Performance optimization for checkout context
    """
    try:
        # Handle shop_domain: use provided value or lookup from customer_id
        shop_domain = request.shop_domain
        if not shop_domain and request.user_id:
            shop_domain = await shop_lookup_service.get_shop_domain_from_customer_id(
                request.user_id
            )
            if shop_domain:
                request.shop_domain = shop_domain
            else:
                logger.error(
                    f"❌ Could not find shop_domain for customer {request.user_id}"
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not determine shop domain for customer {request.user_id}. Please provide shop_domain in request.",
                )
        elif not shop_domain:
            logger.error("❌ No shop_domain or user_id provided")
            raise HTTPException(
                status_code=400,
                detail="Either shop_domain or user_id must be provided to determine the shop.",
            )

        # Post-purchase context handling
        if request.context == "post_purchase":
            logger.info(
                f"Processing post-purchase recommendations for shop {shop_domain}"
            )
            # Apply Shopify post-purchase restrictions
            request.metadata = request.metadata or {}
            request.metadata["post_purchase"] = True

        valid_contexts = [
            "product_page",
            "product_page_similar",
            "product_page_frequently_bought",
            "product_page_customers_viewed",
            "homepage",
            "cart",
            "collection_page",
            "profile",
            "checkout",
            "order_history",
            "order_status",
            "post_purchase",  # ✅ Apollo post-purchase extension support
        ]
        if request.context not in valid_contexts:
            logger.warning(
                f"❌ Invalid context '{request.context}' provided | valid_contexts={valid_contexts}"
            )
            raise HTTPException(
                status_code=400,
                detail=f"Invalid context. Must be one of: {valid_contexts}",
            )

        # Validate shop exists using SQLAlchemy
        logger.debug(
            f"🔍 Validating shop existence | shop_domain={request.shop_domain}"
        )

        shop = await shop_lookup_service.validate_shop_exists(request.shop_domain)
        if not shop:
            logger.error(f"❌ Shop not found | shop_domain={request.shop_domain}")
            raise HTTPException(
                status_code=404, detail=f"Shop {request.shop_domain} not found"
            )

        # Auto-detect category if missing and product_ids are provided
        category = request.category
        if not category and request.product_ids:
            # Detect categories across all provided products (up to 10)
            detected_categories = set()
            for pid in request.product_ids[:10]:
                try:
                    cat = await category_service.get_product_category(pid, shop.id)
                    if cat:
                        detected_categories.add(cat)
                except Exception as e:
                    logger.debug(f"⚠️ Category detection failed for product {pid}: {e}")
            if len(detected_categories) == 1:
                category = next(iter(detected_categories))
            elif len(detected_categories) > 1:
                # Mixed categories: avoid over-filtering
                category = None
            else:
                logger.debug("⚠️ No categories detected from provided product_ids")

        # Handle single product_id for product_page context
        if request.product_id and not request.product_ids:
            request.product_ids = [request.product_id]

        # Determine products to exclude from recommendations
        exclude_items = []

        # Always exclude products that are already in the context (cart, product page, etc.)
        if request.product_ids:
            exclude_items.extend(request.product_ids)
            logger.debug(
                f"🚫 Excluding context products from recommendations | context={request.context} | exclude_ids={request.product_ids}"
            )

        if request.user_id:
            try:
                async with get_transaction_context() as session:
                    # Get purchase history exclusions
                    purchase_exclusions = (
                        await exclusion_service.get_smart_purchase_exclusions(
                            session=session,
                            shop_id=shop.id,
                            user_id=request.user_id,
                            context=request.context,
                        )
                    )

                    if purchase_exclusions:
                        exclude_items.extend(purchase_exclusions)
                        logger.info(
                            f"✅ Added {len(purchase_exclusions)} purchased products to exclusion list | "
                            f"user_id={request.user_id} | context={request.context}"
                        )
            except Exception as e:
                logger.warning(
                    f"⚠️ Failed to get purchase exclusions for user {request.user_id}: {e}"
                )

        # Also exclude products that are already in the user's cart (with time decay)
        if request.user_id:
            try:
                async with get_transaction_context() as session:
                    time_decay_exclusions = (
                        await exclusion_service.get_cart_time_decay_exclusions(
                            session=session,
                            shop_id=shop.id,
                            user_id=request.user_id,
                        )
                    )

                if time_decay_exclusions:
                    exclude_items.extend(time_decay_exclusions)

            except Exception as e:
                logger.warning(
                    f"⚠️ Failed to get cart contents for user {request.user_id}: {e}"
                )

        # Remove duplicates and convert to set for efficient lookup
        exclude_items = list(set(exclude_items)) if exclude_items else None

        # Generate cache key (include exclude_items to ensure cart filtering is respected)
        logger.debug(
            f"🔑 Generating cache key | context={request.context} | product_ids={request.product_ids} | user_id={request.user_id} | exclude_items={exclude_items}"
        )
        cache_key = cache_service.generate_cache_key(
            shop_id=shop.id,
            context=request.context,
            product_ids=request.product_ids,
            user_id=request.user_id,
            session_id=request.session_id,
            category=category,
            limit=request.limit,
            exclude_items=exclude_items,  # Include cart contents in cache key
        )

        # Check cache first (skip for checkout context)
        logger.debug(
            f"💾 Checking cache for recommendations | cache_key={cache_key[:20]}..."
        )
        cached_result = await cache_service.get_cached_recommendations(
            cache_key, request.context
        )
        if cached_result:
            # Extract recommendations from cached result
            # The cached result has structure: {"recommendations": {"recommendations": [...], ...}, ...}
            cached_recommendations_data = cached_result.get("recommendations", {})
            recommendations = cached_recommendations_data.get("recommendations", [])

            # Apply exclusions to cached results
            if exclude_items:
                logger.debug(
                    f"🚫 Filtering cached recommendations | exclude_items={exclude_items} | before_count={len(recommendations)}"
                )
                # Filter out items that are already in cart
                filtered_recommendations = [
                    rec for rec in recommendations if rec.get("id") not in exclude_items
                ]
                recommendations = filtered_recommendations
                logger.debug(
                    f"✅ Cached recommendations filtered | after_count={len(recommendations)}"
                )

            # Filter out unavailable products
            available_recommendations = [
                rec
                for rec in recommendations
                if rec.get("available", True)  # Default to True if not specified
            ]
            recommendations = available_recommendations

            return RecommendationResponse(
                success=True,
                recommendations=recommendations,
                count=len(recommendations),
                source="cache",
                context=request.context,
                timestamp=datetime.now(),
            )

        logger.debug(
            f"💨 Cache miss, proceeding with fresh recommendations | context={request.context}"
        )

        # Performance optimization for checkout context
        if request.context == "checkout":
            # Limit recommendations for speed
            request.limit = min(request.limit, 3)

        # Try hybrid recommendations first (except for checkout which uses simple fallback)
        if request.context != "checkout":

            # Extract session data from behavioral events to enhance metadata
            enhanced_metadata = request.metadata or {}
            if request.user_id:
                session_data = (
                    await session_service.extract_session_data_from_behavioral_events(
                        request.user_id, shop.id
                    )
                )
                # Merge session data with existing metadata
                enhanced_metadata.update(session_data)

            # If the cart spans multiple categories, avoid over-filtering by category
            effective_category = session_service.get_effective_category_for_mixed_cart(
                category,
                enhanced_metadata.get("product_types", []) if enhanced_metadata else [],
            )

            # Fallback session_id from cart attributes if not provided
            effective_session_id = request.session_id
            if (
                not effective_session_id
                and enhanced_metadata
                and enhanced_metadata.get("cart_data")
            ):
                effective_session_id = (
                    session_service.extract_session_id_from_cart_data(
                        enhanced_metadata["cart_data"]
                    )
                )

            result = await hybrid_service.blend_recommendations(
                context=request.context,
                shop_id=shop.id,
                product_ids=request.product_ids,
                user_id=request.user_id,
                session_id=effective_session_id,
                category=effective_category,  # Mixed-category aware
                limit=request.limit,
                metadata=enhanced_metadata,
                exclude_items=exclude_items,
            )

            # If hybrid recommendations fail or return insufficient results, fall back to simple chain
            if (
                not result["success"]
                or len(result.get("items", [])) < request.limit // 2
            ):
                logger.warning(
                    f"⚠️ Hybrid recommendations insufficient | success={result['success']} | items_count={len(result.get('items', []))} | falling back to simple chain"
                )
                result = await recommendation_executor.execute_fallback_chain(
                    context=request.context,
                    shop_id=shop.id,
                    product_ids=request.product_ids,
                    user_id=request.user_id,
                    session_id=request.session_id,
                    category=category,
                    limit=request.limit,
                    metadata=request.metadata,
                    exclude_items=exclude_items,
                )

        else:
            # For product_page, use smart selection for optimal recommendations
            if request.context == "product_page":
                result = (
                    await smart_selection_service.get_smart_product_page_recommendation(
                        shop_id=shop.id,
                        product_ids=request.product_ids,
                        user_id=request.user_id,
                        limit=request.limit,
                    )
                )

            elif request.context == "homepage":
                result = (
                    await smart_selection_service.get_smart_homepage_recommendation(
                        shop_id=shop.id,
                        user_id=request.user_id,
                        limit=request.limit,
                    )
                )

            elif request.context == "collection_page":
                result = await smart_selection_service.get_smart_collection_page_recommendation(
                    shop_id=shop.id,
                    collection_id=request.collection_id,
                    category=category,
                    user_id=request.user_id,
                    limit=request.limit,
                )

            elif request.context == "cart":
                # For cart page, use smart selection with cart items for upsells/cross-sells
                result = await smart_selection_service.get_smart_cart_page_recommendation(
                    shop_id=shop.id,
                    cart_items=request.product_ids,  # Cart items passed as product_ids
                    user_id=request.user_id,
                    limit=request.limit,
                )

            else:
                # For other contexts, use simple fallback chain
                result = await recommendation_executor.execute_fallback_chain(
                    context=request.context,
                    shop_id=shop.id,
                    product_ids=request.product_ids,
                    user_id=request.user_id,
                    session_id=request.session_id,
                    category=category,
                    limit=request.limit,
                    metadata=request.metadata,
                    exclude_items=exclude_items,
                )

        if not result["success"] or not result["items"]:
            # No recommendations available - return empty results
            return RecommendationResponse(
                success=True,
                recommendations=[],
                count=0,
                source=result.get("source", "no_recommendations"),
                context=request.context,
                timestamp=datetime.now(),
            )

        # Enrich with Shopify product data
        item_ids = result["items"]
        enriched_items = await enrichment_service.enrich_items(
            shop.id, item_ids, request.context, result["source"]
        )

        # Filter out unavailable products
        available_items = [
            item
            for item in enriched_items
            if item.get("available", True)  # Default to True if not specified
        ]

        # Filter out excluded items (products already in cart/context)
        if exclude_items:
            logger.debug(
                f"🚫 Filtering out excluded items | exclude_items={exclude_items} | before_count={len(available_items)}"
            )
            filtered_items = [
                item for item in available_items if item.get("id") not in exclude_items
            ]
            available_items = filtered_items
            logger.debug(
                f"✅ Excluded items filtered | after_count={len(available_items)}"
            )

        # Use available items for the rest of the processing
        enriched_items = available_items

        # Centralized currency enhancement - apply consistent currency to all recommendations
        shop_currency = shop.currency_code if shop and shop.currency_code else "USD"
        enriched_items = enrichment_service.enhance_recommendations_with_currency(
            enriched_items, shop_currency
        )

        # Prepare response data
        response_data = {
            "recommendations": enriched_items,
            "count": len(enriched_items),
            "source": result["source"],
            "context": request.context,
            "shop_id": shop.id,
            "user_id": request.user_id,
            "timestamp": datetime.now().isoformat(),
            "category_detected": category if not request.category else None,
        }

        # Cache the results (skip for checkout context)
        logger.debug(
            f"💾 Caching recommendations | context={request.context} | count={len(enriched_items)}"
        )
        await cache_service.cache_recommendations(
            cache_key, response_data, request.context
        )

        # Log analytics (async, non-blocking)
        asyncio.create_task(
            analytics_service.log_recommendation_request(
                shop_id=shop.id,
                context=request.context,
                source=result["source"],
                count=len(enriched_items),
                user_id=request.user_id,
                product_ids=request.product_ids,
                category=category,
            )
        )

        return RecommendationResponse(
            success=True,
            recommendations=enriched_items,
            count=len(enriched_items),
            source=result["source"],
            context=request.context,
            timestamp=datetime.now(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"💥 Recommendation request failed | shop={request.shop_domain} | context={request.context} | error={str(e)}"
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to get recommendations: {str(e)}"
        )
