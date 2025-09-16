"""
Recommendation API endpoints
Handles all recommendation requests from Shopify extension with context-based routing
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, HTTPException, Query, Header, Request
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.shared.gorse_api_client import GorseApiClient
from app.core.database.simple_db_client import get_database
from app.core.config.settings import settings
from app.core.redis_client import get_redis_client
from app.recommandations.models import RecommendationRequest, RecommendationResponse
from app.recommandations.category_detection import CategoryDetectionService
from app.recommandations.cache import RecommendationCacheService
from app.recommandations.hybrid import HybridRecommendationService
from app.recommandations.analytics import RecommendationAnalytics
from app.recommandations.user_neighbors import UserNeighborsService
from app.recommandations.enrichment import ProductEnrichment

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])

# Initialize Gorse client
gorse_client = GorseApiClient(
    base_url=settings.ml.GORSE_BASE_URL, api_key=settings.ml.GORSE_API_KEY
)


async def get_shop_domain_from_customer_id(customer_id: str) -> Optional[str]:
    """
    Get shop domain from customer ID using Prisma ORM
    """
    try:
        db = await get_database()

        # First, find the customer by customerId (not id)
        customer = await db.customerdata.find_first(where={"customerId": customer_id})

        if not customer:
            logger.warning(f"⚠️ Customer not found with customerId: {customer_id}")
            return None

        # Get the shopId from the customer
        shop_id = customer.shopId
        if not shop_id:
            logger.warning(f"⚠️ No shopId found for customer {customer_id}")
            return None

        # Now find the shop by shopId to get shopDomain
        shop = await db.shop.find_unique(where={"id": shop_id})

        if shop and shop.shopDomain:
            shop_domain = shop.shopDomain
            logger.info(
                f"🔍 Found shop_domain for customer {customer_id}: {shop_domain}"
            )
            return shop_domain
        else:
            logger.warning(f"⚠️ No shop_domain found for shop {shop_id}")
            return None

    except Exception as e:
        logger.error(f"❌ Error looking up shop_domain for customer {customer_id}: {e}")
        return None


async def extract_session_data_from_behavioral_events(
    user_id: str, shop_id: str
) -> Dict[str, Any]:
    """Extract recent cart and browsing data from behavioral events for session recommendations"""
    try:
        db = await get_database()

        # Get recent cart_viewed events (last 30 minutes)
        from datetime import timezone

        now = datetime.now(timezone.utc)
        recent_cart_events = await db.behavioralevents.find_many(
            where={
                "customerId": user_id,
                "shopId": shop_id,
                "eventType": "cart_viewed",
                "timestamp": {"gte": now - timedelta(minutes=30)},
            },
            take=5,
            order={"timestamp": "desc"},
        )

        # Get recent product_viewed events (last 2 hours)
        recent_view_events = await db.behavioralevents.find_many(
            where={
                "customerId": user_id,
                "shopId": shop_id,
                "eventType": "product_viewed",
                "timestamp": {"gte": now - timedelta(hours=2)},
            },
            take=20,
            order={"timestamp": "desc"},
        )

        # Get recent add_to_cart events (last 1 hour)
        recent_add_events = await db.behavioralevents.find_many(
            where={
                "customerId": user_id,
                "shopId": shop_id,
                "eventType": "product_added_to_cart",
                "timestamp": {"gte": now - timedelta(hours=1)},
            },
            take=10,
            order={"timestamp": "desc"},
        )

        # Extract cart contents from cart_viewed events
        cart_contents = []
        cart_data = None
        for event in recent_cart_events:
            if event.eventData and event.eventData.get("cart", {}).get("lines"):
                cart_data = event.eventData["cart"]
                for line in event.eventData["cart"]["lines"]:
                    if line.get("merchandise", {}).get("product", {}).get("id"):
                        product_id = line["merchandise"]["product"]["id"]
                        if product_id not in cart_contents:
                            cart_contents.append(product_id)

        # Extract recent views
        recent_views = []
        product_types = set()
        for event in recent_view_events:
            if event.eventData and event.eventData.get("product", {}).get("id"):
                product_id = event.eventData["product"]["id"]
                if product_id not in recent_views:
                    recent_views.append(product_id)

                # Extract product type
                product_type = event.eventData["product"].get("type")
                if product_type:
                    product_types.add(product_type)

        # Extract recent adds to cart
        recent_adds = []
        for event in recent_add_events:
            if event.eventData and event.eventData.get("product", {}).get("id"):
                product_id = event.eventData["product"]["id"]
                if product_id not in recent_adds:
                    recent_adds.append(product_id)

        # Build session metadata
        session_metadata = {
            "cart_contents": cart_contents,
            "recent_views": recent_views,
            "recent_adds": recent_adds,
            "product_types": list(product_types),
            "cart_data": cart_data,  # Full cart data for detailed analysis
            "session_context": {
                "total_cart_items": len(cart_contents),
                "total_views": len(recent_views),
                "total_adds": len(recent_adds),
                "categories": list(product_types),
                "last_activity": (
                    recent_cart_events[0].timestamp.isoformat()
                    if recent_cart_events
                    else None
                ),
            },
        }

        logger.info(
            f"🔍 Extracted session data | user_id={user_id} | cart_items={len(cart_contents)} | views={len(recent_views)} | adds={len(recent_adds)}"
        )

        return session_metadata

    except Exception as e:
        logger.error(
            f"💥 Failed to extract session data from behavioral events: {str(e)}"
        )
        return {
            "cart_contents": [],
            "recent_views": [],
            "recent_adds": [],
            "product_types": [],
            "cart_data": None,
            "session_context": {},
        }


def _apply_time_decay_filtering(
    cart_interactions: List[Any], user_id: str
) -> List[str]:
    """
    Apply time decay logic to determine which products to exclude from recommendations

    Time Decay Rules:
    - Last 2 hours: Always exclude (weight = 1.0)
    - Last 6 hours: Usually exclude (weight = 0.8)
    - Last 24 hours: Maybe exclude (weight = 0.5)
    - Last 48 hours: Rarely exclude (weight = 0.2)

    Args:
        cart_interactions: List of cart interactions from database
        user_id: User ID for logging

    Returns:
        List of product IDs to exclude from recommendations
    """
    try:
        from datetime import timezone

        now = datetime.now(timezone.utc)
        product_interactions = {}  # product_id -> list of interactions

        # Group interactions by product ID
        for interaction in cart_interactions:
            if not interaction.productId:
                continue

            product_id = interaction.productId
            if product_id not in product_interactions:
                product_interactions[product_id] = []

            # Ensure timestamp is timezone-aware
            timestamp = interaction.timestamp
            if timestamp.tzinfo is None:
                # If timestamp is naive, assume it's UTC
                timestamp = timestamp.replace(tzinfo=timezone.utc)
            elif timestamp.tzinfo != timezone.utc:
                # Convert to UTC if it's in a different timezone
                timestamp = timestamp.astimezone(timezone.utc)

            product_interactions[product_id].append(
                {
                    "timestamp": timestamp,
                    "session_id": interaction.sessionId,
                }
            )

        logger.debug(
            f"🔍 Time decay analysis for {len(product_interactions)} unique products"
        )

        excluded_products = []

        for product_id, interactions in product_interactions.items():
            # Get the most recent interaction for this product
            most_recent = max(interactions, key=lambda x: x["timestamp"])
            hours_ago = (now - most_recent["timestamp"]).total_seconds() / 3600

            # Count total interactions for this product
            interaction_count = len(interactions)

            # Apply time decay logic
            should_exclude = False
            reason = ""

            if hours_ago < 2:
                # Very recent (last 2 hours) - always exclude
                should_exclude = True
                reason = f"very_recent_{hours_ago:.1f}h"
            elif hours_ago < 6:
                # Recent (last 6 hours) - usually exclude
                should_exclude = True
                reason = f"recent_{hours_ago:.1f}h"
            elif hours_ago < 24:
                # Yesterday - exclude if multiple interactions
                if interaction_count >= 2:
                    should_exclude = True
                    reason = f"yesterday_multiple_{interaction_count}times"
                else:
                    reason = f"yesterday_single_{hours_ago:.1f}h"
            elif hours_ago < 48:
                # Day before - exclude only if many interactions
                if interaction_count >= 3:
                    should_exclude = True
                    reason = f"day_before_many_{interaction_count}times"
                else:
                    reason = f"day_before_few_{hours_ago:.1f}h"
            else:
                # Too old - don't exclude
                reason = f"too_old_{hours_ago:.1f}h"

            if should_exclude:
                excluded_products.append(product_id)
                logger.debug(
                    f"🚫 Excluding product {product_id} | reason={reason} | interactions={interaction_count} | hours_ago={hours_ago:.1f}"
                )
            else:
                logger.debug(
                    f"✅ Including product {product_id} | reason={reason} | interactions={interaction_count} | hours_ago={hours_ago:.1f}"
                )

        logger.info(
            f"⏰ Time decay filtering complete | user_id={user_id} | total_products={len(product_interactions)} | excluded={len(excluded_products)} | included={len(product_interactions) - len(excluded_products)}"
        )

        return excluded_products

    except Exception as e:
        logger.error(f"💥 Time decay filtering failed: {str(e)}")
        # Fallback: exclude all products from last 24 hours
        fallback_exclusions = []
        from datetime import timezone

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        for interaction in cart_interactions:
            if interaction.productId:
                # Ensure timestamp is timezone-aware for comparison
                timestamp = interaction.timestamp
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                elif timestamp.tzinfo != timezone.utc:
                    timestamp = timestamp.astimezone(timezone.utc)

                if timestamp >= cutoff_time:
                    fallback_exclusions.append(interaction.productId)
        return list(set(fallback_exclusions))


# Initialize enrichment service
enrichment_service = ProductEnrichment()


# Initialize services
category_service = CategoryDetectionService()
cache_service = RecommendationCacheService()
hybrid_service = HybridRecommendationService()
analytics_service = RecommendationAnalytics()
user_neighbors_service = UserNeighborsService()


@router.get("/debug/check-products/{shop_id}")
async def debug_check_products(shop_id: str, limit: int = 10):
    """Debug endpoint to check what products exist in database"""
    try:
        db = await get_database()

        # Get sample products from database
        products = await db.productdata.find_many(where={"shopId": shop_id}, take=limit)

        # Get total count
        total_count = await db.productdata.count(where={"shopId": shop_id})

        # Get sample product IDs
        product_ids = [p.productId for p in products]

        return {
            "shop_id": shop_id,
            "total_products": total_count,
            "sample_products": [
                {
                    "id": p.id,
                    "productId": p.productId,
                    "title": p.title,
                    "handle": p.handle,
                    "price": p.price,
                    "status": p.status,
                }
                for p in products
            ],
            "sample_product_ids": product_ids,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to check products: {e}")
        return {"error": str(e), "shop_id": shop_id}


@router.get("/debug/check-missing-products/{shop_id}")
async def debug_check_missing_products(shop_id: str, product_ids: str):
    """Debug endpoint to check if specific product IDs exist in database"""
    try:
        db = await get_database()

        # Parse comma-separated product IDs
        missing_ids = [pid.strip() for pid in product_ids.split(",")]

        # Check which ones exist
        existing_products = await db.productdata.find_many(
            where={"shopId": shop_id, "productId": {"in": missing_ids}}
        )

        existing_ids = {p.productId for p in existing_products}
        actually_missing = [pid for pid in missing_ids if pid not in existing_ids]

        return {
            "shop_id": shop_id,
            "requested_ids": missing_ids,
            "existing_count": len(existing_products),
            "missing_count": len(actually_missing),
            "existing_products": [
                {"productId": p.productId, "title": p.title, "handle": p.handle}
                for p in existing_products
            ],
            "actually_missing": actually_missing,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to check missing products: {e}")
        return {"error": str(e), "shop_id": shop_id}


# Context-based routing logic
FALLBACK_LEVELS = {
    "product_page": [
        "item_neighbors",  # Level 1: Similar products
        "user_recommendations",  # Level 2: Personalized (if user_id)
        "popular_category",  # Level 3: Popular in category
    ],
    "homepage": [
        "user_recommendations",  # Level 1: Personalized
        "popular",  # Level 2: Popular items
        "latest",  # Level 3: Latest items
    ],
    "cart": [
        "session_recommendations",  # Level 1: Session-based
        "user_recommendations",  # Level 2: Personalized
        "popular",  # Level 3: Popular items
        "user_neighbors",  # Level 4: Neighbor-based
    ],
    "profile": [
        "user_recommendations",  # Level 1: Personalized
        "popular",  # Level 2: Popular items
    ],
    "checkout": ["popular"],  # Level 1: Popular items (fast)
    "order_history": [
        "user_recommendations",  # Level 1: Personalized based on order history
        "popular_category",  # Level 2: Popular in categories from order history
        "popular",  # Level 3: General popular items
    ],
    "order_status": [
        "item_neighbors",  # Level 1: Similar to ordered products
        "user_recommendations",  # Level 2: Personalized
        "popular_category",  # Level 3: Popular in same category
    ],
}


async def execute_recommendation_level(
    level: str,
    shop_id: str,
    product_ids: Optional[List[str]] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 6,
    metadata: Optional[Dict[str, Any]] = None,
    exclude_items: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Execute a specific recommendation level

    Args:
        level: Recommendation level to execute
        shop_id: Shop ID
        product_id: Product ID
        user_id: User ID
        session_id: Session ID
        category: Category filter
        limit: Number of recommendations
        metadata: Additional metadata

    Returns:
        Recommendation result
    """
    try:
        if level == "item_neighbors" and product_ids and len(product_ids) > 0:
            # Apply shop prefix for multi-tenancy - use first product for single item neighbors
            prefixed_item_id = f"shop_{shop_id}_{product_ids[0]}"
            # Convert exclude_items to Gorse format (with shop prefix)
            gorse_exclude_items = None
            if exclude_items:
                gorse_exclude_items = [
                    f"shop_{shop_id}_{item_id}" for item_id in exclude_items
                ]

            result = await gorse_client.get_item_neighbors(
                item_id=prefixed_item_id,
                n=limit,
                category=category,
                exclude_items=gorse_exclude_items,
            )
            if result["success"]:
                return {
                    "success": True,
                    "items": result["neighbors"],
                    "source": "gorse_item_neighbors",
                }

        elif level == "user_recommendations" and user_id:
            # Apply shop prefix for multi-tenancy
            prefixed_user_id = f"shop_{shop_id}_{user_id}"
            # Convert exclude_items to Gorse format (with shop prefix)
            gorse_exclude_items = None
            if exclude_items:
                gorse_exclude_items = [
                    f"shop_{shop_id}_{item_id}" for item_id in exclude_items
                ]

            result = await gorse_client.get_recommendations(
                user_id=prefixed_user_id,
                n=limit,
                category=category,
                exclude_items=gorse_exclude_items,
            )
            if result["success"]:
                return {
                    "success": True,
                    "items": result["recommendations"],
                    "source": "gorse_user_recommendations",
                }

        elif level == "session_recommendations" and session_id:
            # Apply shop prefix for multi-tenancy
            prefixed_user_id = f"shop_{shop_id}_{user_id}" if user_id else None

            # Build session data as array of feedback objects
            feedback_objects = []
            base_feedback = {
                "Comment": f"session_{session_id}",
                "FeedbackType": "view",
                "ItemId": "",
                "Timestamp": datetime.now().isoformat(),
                "UserId": prefixed_user_id or "",
            }

            # Add cart contents if available
            if metadata and metadata.get("cart_contents"):
                for item_id in metadata["cart_contents"]:
                    cart_feedback = base_feedback.copy()
                    cart_feedback["ItemId"] = item_id
                    cart_feedback["FeedbackType"] = "add_to_cart"
                    cart_feedback["Comment"] = f"cart_item_{item_id}"
                    feedback_objects.append(cart_feedback)

            # If no specific items, create a general session feedback
            if not feedback_objects:
                feedback_objects.append(base_feedback)

            result = await gorse_client.get_session_recommendations(
                session_data=feedback_objects, n=limit, category=category
            )
            if result["success"]:
                return {
                    "success": True,
                    "items": result["recommendations"],
                    "source": "gorse_session_recommendations",
                }

        elif level == "popular":
            result = await gorse_client.get_popular_items(n=limit, category=category)
            if result["success"]:
                return {
                    "success": True,
                    "items": result["items"],
                    "source": "gorse_popular",
                }

        elif level == "latest":
            result = await gorse_client.get_latest_items(n=limit, category=category)
            if result["success"]:
                return {
                    "success": True,
                    "items": result["items"],
                    "source": "gorse_latest",
                }

        elif level == "popular_category":
            # Use popular items with category filter
            result = await gorse_client.get_popular_items(n=limit, category=category)
            if result["success"]:
                return {
                    "success": True,
                    "items": result["items"],
                    "source": "gorse_popular_category",
                }

        return {"success": False, "items": [], "source": "none"}

    except Exception as e:
        logger.error(f"Failed to execute recommendation level {level}: {str(e)}")
        return {"success": False, "items": [], "source": "error"}


async def execute_fallback_chain(
    context: str,
    shop_id: str,
    product_ids: Optional[List[str]] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 6,
    metadata: Optional[Dict[str, Any]] = None,
    exclude_items: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Execute the fallback chain for a given context

    Args:
        context: Recommendation context
        shop_id: Shop ID
        product_id: Product ID
        user_id: User ID
        session_id: Session ID
        category: Category filter
        limit: Number of recommendations
        metadata: Additional metadata

    Returns:
        Recommendation result with fallback information
    """
    levels = FALLBACK_LEVELS.get(context, ["popular"])
    logger.info(
        f"🔄 Starting fallback chain | context={context} | levels={levels} | limit={limit}"
    )

    for i, level in enumerate(levels, 1):
        try:
            logger.debug(
                f"🎯 Trying level {i}/{len(levels)}: {level} | context={context}"
            )
            result = await execute_recommendation_level(
                level,
                shop_id,
                product_ids,
                user_id,
                session_id,
                category,
                limit,
                metadata,
                exclude_items,
            )

            if result["success"] and result.get("items"):
                items = result["items"]
                logger.info(
                    f"✅ Level {level} succeeded | context={context} | items={len(items)} | source={result.get('source', 'unknown')}"
                )
                return result
            else:
                items = result.get("items", [])
                items_count = len(items) if items is not None else 0
                logger.warning(
                    f"⚠️ Level {level} returned no items | context={context} | success={result['success']} | items_count={items_count}"
                )

        except Exception as e:
            logger.error(
                f"💥 Level {level} failed | context={context} | error={str(e)}"
            )
            continue

    # All levels failed, return empty results
    logger.warning(
        f"❌ All recommendation levels failed | context={context} | returning empty results"
    )
    return {"success": False, "items": [], "source": "all_failed"}


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
            logger.info(
                f"🔍 Shop domain not provided, looking up from customer_id: {request.user_id}"
            )
            shop_domain = await get_shop_domain_from_customer_id(request.user_id)
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

        logger.info(
            f"📊 Recommendation request received | shop={request.shop_domain} | context={request.context} | user_id={request.user_id} | product_ids={request.product_ids} | limit={request.limit}"
        )

        # Validate context
        valid_contexts = [
            "product_page",
            "homepage",
            "cart",
            "profile",
            "checkout",
            "order_history",
            "order_status",
        ]
        if request.context not in valid_contexts:
            logger.warning(
                f"❌ Invalid context '{request.context}' provided | valid_contexts={valid_contexts}"
            )
            raise HTTPException(
                status_code=400,
                detail=f"Invalid context. Must be one of: {valid_contexts}",
            )

        # Validate shop exists
        logger.debug(
            f"🔍 Validating shop existence | shop_domain={request.shop_domain}"
        )
        db = await get_database()
        shop = await db.shop.find_unique(where={"shopDomain": request.shop_domain})
        if not shop:
            logger.error(f"❌ Shop not found | shop_domain={request.shop_domain}")
            raise HTTPException(
                status_code=404, detail=f"Shop {request.shop_domain} not found"
            )

        logger.info(
            f"✅ Shop validated | shop_id={shop.id} | shop_domain={request.shop_domain}"
        )

        # Auto-detect category if missing and product_ids are provided
        category = request.category
        if not category and request.product_ids and len(request.product_ids) > 0:
            # Use first product for category detection
            first_product_id = request.product_ids[0]
            logger.debug(f"🔍 Auto-detecting category for product {first_product_id}")
            category = await category_service.get_product_category(
                first_product_id, shop.id
            )
            if category:
                logger.info(
                    f"✅ Auto-detected category '{category}' for product {first_product_id}"
                )
            else:
                logger.debug(f"⚠️ No category detected for product {first_product_id}")

        # Determine products to exclude from recommendations
        exclude_items = []

        # Always exclude products that are already in the context (cart, product page, etc.)
        if request.product_ids:
            exclude_items.extend(request.product_ids)
            logger.debug(
                f"🚫 Excluding context products from recommendations | context={request.context} | exclude_ids={request.product_ids}"
            )

        # Also exclude products that are already in the user's cart (with time decay)
        if request.user_id:
            try:
                # Get cart interactions from the last 48 hours for time decay analysis
                cart_interactions = await db.recommendationinteraction.find_many(
                    where={
                        "session": {
                            "shopId": shop.id,
                            "userId": request.user_id,
                        },
                        "interactionType": "add_to_cart",
                        "timestamp": {
                            "gte": datetime.utcnow()
                            - timedelta(hours=48)  # Extended to 48 hours for time decay
                        },
                    },
                    order={"timestamp": "desc"},
                    take=100,  # Get more interactions for better time decay analysis
                )

                logger.info(
                    f"🔍 Found {len(cart_interactions)} cart interactions for user {request.user_id} in last 48 hours"
                )

                # Apply time decay logic to determine which products to exclude
                time_decay_exclusions = _apply_time_decay_filtering(
                    cart_interactions, request.user_id
                )

                if time_decay_exclusions:
                    exclude_items.extend(time_decay_exclusions)
                    logger.info(
                        f"🚫 Time decay exclusions | user_id={request.user_id} | excluded_products={len(time_decay_exclusions)} | products={time_decay_exclusions[:5]}{'...' if len(time_decay_exclusions) > 5 else ''}"
                    )
                else:
                    logger.info(
                        f"🔍 No time decay exclusions for user {request.user_id}"
                    )

            except Exception as e:
                logger.warning(
                    f"⚠️ Failed to get cart contents for user {request.user_id}: {e}"
                )

        # Remove duplicates and convert to set for efficient lookup
        exclude_items = list(set(exclude_items)) if exclude_items else None

        if exclude_items:
            logger.info(
                f"🚫 Total products to exclude: {len(exclude_items)} | exclude_ids={exclude_items[:5]}{'...' if len(exclude_items) > 5 else ''}"
            )

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

            logger.info(
                f"🎯 Cache hit! Returning filtered cached recommendations | context={request.context} | count={len(recommendations)}"
            )
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
            logger.info(
                f"⚡ Checkout optimization: limited to {request.limit} recommendations"
            )

        # Try hybrid recommendations first (except for checkout which uses simple fallback)
        if request.context != "checkout":
            logger.info(
                f"🔄 Attempting hybrid recommendations | context={request.context} | limit={request.limit}"
            )

            # Extract session data from behavioral events to enhance metadata
            enhanced_metadata = request.metadata or {}
            if request.user_id:
                session_data = await extract_session_data_from_behavioral_events(
                    request.user_id, shop.id
                )
                # Merge session data with existing metadata
                enhanced_metadata.update(session_data)
                logger.info(
                    f"📊 Enhanced metadata with session data | cart_items={len(session_data.get('cart_contents', []))} | views={len(session_data.get('recent_views', []))}"
                )

            result = await hybrid_service.blend_recommendations(
                context=request.context,
                shop_id=shop.id,
                product_ids=request.product_ids,
                user_id=request.user_id,
                session_id=request.session_id,
                category=category,  # Use auto-detected category
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
                result = await execute_fallback_chain(
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
                logger.info(
                    f"✅ Hybrid recommendations successful | items_count={len(result.get('items', []))} | source={result.get('source', 'unknown')}"
                )
        else:
            # For checkout, use simple fallback chain for speed
            logger.info(
                f"⚡ Using simple fallback chain for checkout | limit={request.limit}"
            )
            result = await execute_fallback_chain(
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
            logger.info(
                f"ℹ️ No recommendations available | success={result['success']} | items_count={len(result.get('items', []))} | source={result.get('source', 'unknown')}"
            )
            return RecommendationResponse(
                success=True,
                recommendations=[],
                count=0,
                source=result.get("source", "no_recommendations"),
                context=request.context,
                timestamp=datetime.now(),
            )

        # Enrich with Shopify product data
        logger.info(
            f"🎨 Enriching {len(result['items'])} items with Shopify data | source={result['source']}"
        )
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

        logger.info(
            f"✅ Enrichment complete | enriched_count={len(enriched_items)} | available_count={len(available_items)} | original_count={len(item_ids)}"
        )

        # Use available items for the rest of the processing
        enriched_items = available_items

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

        logger.info(
            f"🎉 Recommendation request completed successfully | shop={request.shop_domain} | context={request.context} | count={len(enriched_items)} | source={result['source']}"
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


# Analytics endpoints moved to separate service: /api/v1/analytics.py


@router.get("/health")
async def recommendations_health_check():
    """
    Health check for the recommendations system including cache and category services
    """
    try:
        logger.info("🏥 Starting recommendations health check")

        # Check Gorse health
        logger.debug("🔍 Checking Gorse health")
        gorse_health = await gorse_client.health_check()

        # Check database connection
        logger.debug("🔍 Checking database connection")
        db = await get_database()
        await db.shop.find_first()  # Simple query to test connection

        # Check Redis cache connection
        logger.debug("🔍 Checking Redis cache connection")
        redis_client = await get_redis_client()
        await redis_client.ping()  # Test Redis connection

        # Check cache TTL configuration
        cache_ttl_status = {
            context: f"{ttl}s" if ttl > 0 else "disabled"
            for context, ttl in cache_service.CACHE_TTL.items()
        }

        logger.info("✅ Recommendations health check passed | all services healthy")
        return {
            "success": True,
            "status": "healthy",
            "gorse": gorse_health,
            "database": "connected",
            "redis_cache": "connected",
            "cache_ttl_config": cache_ttl_status,
            "services": {
                "category_detection": "available",
                "recommendation_caching": "available",
                "product_enrichment": "available",
                "hybrid_recommendations": "available",
                "user_neighbors": "available",
                "analytics": "available",
            },
            "blending_ratios": hybrid_service.BLENDING_RATIOS,
            "timestamp": datetime.now(),
        }

    except Exception as e:
        logger.error(f"💥 Recommendations health check failed: {str(e)}")
        return {
            "success": False,
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(),
        }
