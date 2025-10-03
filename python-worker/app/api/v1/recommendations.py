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
from app.core.database.session import get_transaction_context
from app.core.database.models.shop import Shop
from app.core.database.models.customer_data import CustomerData
from app.core.database.models.user_interaction import UserInteraction
from app.core.database.models.product_data import ProductData
from app.core.config.settings import settings
from app.core.redis_client import get_redis_client
from app.recommandations.models import RecommendationRequest, RecommendationResponse
from app.recommandations.category_detection import CategoryDetectionService
from app.recommandations.cache import RecommendationCacheService
from app.recommandations.hybrid import HybridRecommendationService
from app.recommandations.analytics import RecommendationAnalytics
from app.recommandations.user_neighbors import UserNeighborsService
from app.recommandations.enrichment import ProductEnrichment
from app.recommandations.purchase_history import PurchaseHistoryService
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendations"])

# Initialize Gorse client
gorse_client = GorseApiClient(
    base_url=settings.ml.GORSE_BASE_URL, api_key=settings.ml.GORSE_API_KEY
)


async def _get_purchase_exclusions(
    session: AsyncSession,
    shop_id: str,
    user_id: Optional[str],
    context: str,
) -> List[str]:
    """
    Get product IDs to exclude based on purchase history.

    Args:
        session: Database session
        shop_id: Shop ID
        user_id: User/Customer ID
        context: Recommendation context

    Returns:
        List of product IDs to exclude from recommendations
    """
    if not user_id:
        return []

    try:
        # Different exclusion strategies based on context
        if context in ["order_history", "order_status"]:
            # For order-related contexts, be less aggressive with exclusions
            # Only exclude very recent purchases (last 30 days)
            exclude_ids = (
                await PurchaseHistoryService.get_recently_purchased_product_ids(
                    session=session,
                    shop_id=shop_id,
                    customer_id=user_id,
                    days=30,
                )
            )
            logger.debug(
                f"📦 Excluding {len(exclude_ids)} recent purchases (30 days) for context '{context}'"
            )

        elif context in ["product_page", "homepage", "profile"]:
            # For main browsing contexts, exclude all-time purchases
            # This prevents showing already-owned products
            exclude_ids = await PurchaseHistoryService.get_purchased_product_ids(
                session=session,
                shop_id=shop_id,
                customer_id=user_id,
                exclude_refunded=True,
                exclude_cancelled=True,
            )
            logger.debug(
                f"📦 Excluding {len(exclude_ids)} all-time purchases for context '{context}'"
            )

        elif context == "cart":
            # For cart, only exclude very recent purchases (last 14 days)
            # Customer might want to buy again for someone else
            exclude_ids = (
                await PurchaseHistoryService.get_recently_purchased_product_ids(
                    session=session,
                    shop_id=shop_id,
                    customer_id=user_id,
                    days=14,
                )
            )
            logger.debug(
                f"📦 Excluding {len(exclude_ids)} recent purchases (14 days) for cart context"
            )

        else:
            # Default: exclude all-time purchases
            exclude_ids = await PurchaseHistoryService.get_purchased_product_ids(
                session=session,
                shop_id=shop_id,
                customer_id=user_id,
            )
            logger.debug(
                f"📦 Excluding {len(exclude_ids)} all-time purchases for context '{context}'"
            )

        return exclude_ids

    except Exception as e:
        logger.error(f"⚠️ Failed to get purchase exclusions for user {user_id}: {e}")
        return []


async def get_shop_domain_from_customer_id(customer_id: str) -> Optional[str]:
    """
    Get shop domain from customer ID using SQLAlchemy
    """
    try:

        async with get_transaction_context() as session:
            # First, find the customer by customer_id
            result = await session.execute(
                select(CustomerData).where(CustomerData.customer_id == customer_id)
            )
            customer = result.scalar_one_or_none()

            if not customer:
                logger.warning(f"⚠️ Customer not found with customer_id: {customer_id}")
                return None

            # Get the shop_id from the customer
            shop_id = customer.shop_id
            if not shop_id:
                logger.warning(f"⚠️ No shop_id found for customer {customer_id}")
                return None

            # Now find the shop by shop_id to get shop_domain
            shop_result = await session.execute(select(Shop).where(Shop.id == shop_id))
            shop = shop_result.scalar_one_or_none()

            if shop and shop.shop_domain:
                shop_domain = shop.shop_domain
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
        from datetime import timezone

        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=24)

        async with get_transaction_context() as session:
            # Get recent cart interactions (last 24 hours) - both cart_viewed and individual cart events
            cart_events_result = await session.execute(
                select(UserInteraction)
                .where(
                    and_(
                        UserInteraction.customer_id == user_id,
                        UserInteraction.shop_id == shop_id,
                        UserInteraction.interaction_type.in_(
                            [
                                "cart_viewed",
                                "product_added_to_cart",
                                "product_removed_from_cart",
                            ]
                        ),
                        UserInteraction.created_at >= cutoff_time,
                    )
                )
                .order_by(desc(UserInteraction.created_at))
                .limit(20)
            )
            recent_cart_events = cart_events_result.scalars().all()

            # Get recent product_viewed events (last 24 hours)
            view_events_result = await session.execute(
                select(UserInteraction)
                .where(
                    and_(
                        UserInteraction.customer_id == user_id,
                        UserInteraction.shop_id == shop_id,
                        UserInteraction.interaction_type == "product_viewed",
                        UserInteraction.created_at >= cutoff_time,
                    )
                )
                .order_by(desc(UserInteraction.created_at))
                .limit(20)
            )
            recent_view_events = view_events_result.scalars().all()

            # Get recent add_to_cart events (last 24 hours)
            add_events_result = await session.execute(
                select(UserInteraction)
                .where(
                    and_(
                        UserInteraction.customer_id == user_id,
                        UserInteraction.shop_id == shop_id,
                        UserInteraction.interaction_type == "product_added_to_cart",
                        UserInteraction.created_at >= cutoff_time,
                    )
                )
                .order_by(desc(UserInteraction.created_at))
                .limit(10)
            )
            recent_add_events = add_events_result.scalars().all()

            # Extract cart contents from cart events
            cart_contents = []
            cart_data = None
            for event in recent_cart_events:
                metadata = event.metadata or {}

                # Handle cart_viewed events (full cart data)
                if event.interaction_type == "cart_viewed" and metadata.get(
                    "cart", {}
                ).get("lines"):
                    cart_data = metadata["cart"]
                    for line in metadata["cart"]["lines"]:
                        if line.get("merchandise", {}).get("product", {}).get("id"):
                            product_id = line["merchandise"]["product"]["id"]
                            if product_id not in cart_contents:
                                cart_contents.append(product_id)

                # Handle individual cart events (product_added_to_cart, product_removed_from_cart)
                elif event.interaction_type in [
                    "product_added_to_cart",
                    "product_removed_from_cart",
                ]:
                    product_id = None

                    # Try different metadata structures for product ID
                    if "product_id" in metadata:
                        product_id = metadata.get("product_id")
                    elif "data" in metadata and "cartLine" in metadata["data"]:
                        cart_line = metadata["data"]["cartLine"]
                        if (
                            "merchandise" in cart_line
                            and "product" in cart_line["merchandise"]
                        ):
                            product_id = cart_line["merchandise"]["product"].get("id")
                    elif "productId" in metadata:
                        product_id = metadata.get("productId")

                    if product_id:
                        if (
                            event.interaction_type == "product_added_to_cart"
                            and product_id not in cart_contents
                        ):
                            cart_contents.append(product_id)
                    elif (
                        event.interactionType == "product_removed_from_cart"
                        and product_id in cart_contents
                    ):
                        cart_contents.remove(product_id)

        # Extract recent views
        recent_views = []
        product_types = set()
        for event in recent_view_events:
            metadata = event.metadata or {}
            product_id = None

            # Try different metadata structures for product ID
            if "product_id" in metadata:
                product_id = metadata.get("product_id")
            elif "data" in metadata and "cartLine" in metadata["data"]:
                cart_line = metadata["data"]["cartLine"]
                if "merchandise" in cart_line and "product" in cart_line["merchandise"]:
                    product_id = cart_line["merchandise"]["product"].get("id")
            elif "productId" in metadata:
                product_id = metadata.get("productId")

            if product_id and product_id not in recent_views:
                recent_views.append(product_id)

            # Extract product type
            product_type = metadata.get("product_type")
            if product_type:
                product_types.add(product_type)

        # Extract recent adds to cart
        recent_adds = []
        for event in recent_add_events:
            metadata = event.metadata or {}
            product_id = None

            # Try different metadata structures for product ID
            if "product_id" in metadata:
                product_id = metadata.get("product_id")
            elif "data" in metadata and "cartLine" in metadata["data"]:
                cart_line = metadata["data"]["cartLine"]
                if "merchandise" in cart_line and "product" in cart_line["merchandise"]:
                    product_id = cart_line["merchandise"]["product"].get("id")
            elif "productId" in metadata:
                product_id = metadata.get("productId")

            if product_id and product_id not in recent_adds:
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
                    recent_cart_events[0].createdAt.isoformat()
                    if recent_cart_events
                    else None
                ),
            },
        }

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
            # Extract product ID from metadata
            metadata = interaction.metadata or {}
            product_id = None

            # Try different metadata structures for product ID
            if "product_id" in metadata:
                product_id = metadata.get("product_id")
            elif "data" in metadata and "cartLine" in metadata["data"]:
                cart_line = metadata["data"]["cartLine"]
                if "merchandise" in cart_line and "product" in cart_line["merchandise"]:
                    product_id = cart_line["merchandise"]["product"].get("id")
            elif "productId" in metadata:
                product_id = metadata.get("productId")

            if not product_id:
                continue

            if product_id not in product_interactions:
                product_interactions[product_id] = []

            # Ensure timestamp is timezone-aware
            timestamp = interaction.createdAt
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

            # Apply industry-standard time decay logic
            # Industry best practice: Only exclude items currently in cart or very recently purchased
            should_exclude = False
            reason = ""

            # Industry standard: Only exclude items that are currently in cart (very recent)
            if hours_ago < 0.01:  # Last ~36 seconds - likely current cart item
                should_exclude = True
                reason = f"current_cart_item_{hours_ago:.1f}h"
            else:
                # Don't exclude recently interacted items; handle recency in ranking, not filtering
                reason = f"included_{hours_ago:.1f}h"

            if should_exclude:
                excluded_products.append(product_id)
                logger.debug(
                    f"🚫 Excluding product {product_id} | reason={reason} | interactions={interaction_count} | hours_ago={hours_ago:.1f}"
                )
            else:
                logger.debug(
                    f"✅ Including product {product_id} | reason={reason} | interactions={interaction_count} | hours_ago={hours_ago:.1f}"
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
                timestamp = interaction.createdAt
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
                # Filter out empty or invalid recommendations
                valid_recommendations = [
                    item
                    for item in result["recommendations"]
                    if item and str(item).strip() and str(item).strip() != ""
                ]

                if valid_recommendations:
                    return {
                        "success": True,
                        "items": valid_recommendations,
                        "source": "gorse_user_recommendations",
                    }
                else:
                    logger.warning(
                        f"⚠️ User recommendations returned only empty items for user {user_id}"
                    )
                    return {
                        "success": False,
                        "items": [],
                        "source": "gorse_user_recommendations_empty",
                        "error": "All recommendations were empty",
                    }

        elif level == "session_recommendations":
            # Apply shop prefix for multi-tenancy
            prefixed_user_id = f"shop_{shop_id}_{user_id}" if user_id else None

            # Build session data as array of feedback objects
            feedback_objects = []
            effective_session_id = session_id or "auto"
            base_feedback = {
                "Comment": f"session_{effective_session_id}",
                "FeedbackType": "view",
                "ItemId": "",
                "Timestamp": datetime.now().isoformat(),
                "UserId": prefixed_user_id or "",
            }

            # Add cart contents if available
            if metadata and metadata.get("cart_contents"):
                for item_id in metadata["cart_contents"]:
                    cart_feedback = base_feedback.copy()
                    cart_feedback["ItemId"] = (
                        f"shop_{shop_id}_{item_id}"  # Apply shop prefix
                    )
                    cart_feedback["FeedbackType"] = "add_to_cart"
                    cart_feedback["Comment"] = f"cart_item_{item_id}"
                    feedback_objects.append(cart_feedback)

            # Add recent views if available
            if metadata and metadata.get("recent_views"):
                for item_id in metadata["recent_views"][:5]:  # Limit to 5 recent views
                    view_feedback = base_feedback.copy()
                    view_feedback["ItemId"] = (
                        f"shop_{shop_id}_{item_id}"  # Apply shop prefix
                    )
                    view_feedback["FeedbackType"] = "view"
                    view_feedback["Comment"] = f"recent_view_{item_id}"
                    feedback_objects.append(view_feedback)

            # If no specific items, create a general session feedback
            if not feedback_objects:
                feedback_objects.append(base_feedback)

            result = await gorse_client.get_session_recommendations(
                session_data=feedback_objects, n=limit, category=category
            )
            if result["success"]:
                # Handle case where recommendations is None
                recommendations = result.get("recommendations", [])
                if recommendations is None:
                    logger.warning(
                        f"⚠️ Session recommendations returned None in fallback chain"
                    )
                    return {
                        "success": False,
                        "items": [],
                        "source": "gorse_session_recommendations_none",
                        "error": "Gorse returned None recommendations",
                    }

                # Filter out empty or invalid recommendations
                valid_recommendations = [
                    item
                    for item in recommendations
                    if item and str(item).strip() and str(item).strip() != ""
                ]

                if valid_recommendations:
                    return {
                        "success": True,
                        "items": valid_recommendations,
                        "source": "gorse_session_recommendations",
                    }
                else:
                    logger.warning(
                        f"⚠️ Session recommendations returned only empty items"
                    )
                    return {
                        "success": False,
                        "items": [],
                        "source": "gorse_session_recommendations_empty",
                        "error": "All session recommendations were empty",
                    }

        elif level == "popular":
            result = await gorse_client.get_popular_items(n=limit, category=category)
            if result["success"]:
                # Filter out empty or invalid recommendations
                valid_items = [
                    item
                    for item in result["items"]
                    if item and str(item).strip() and str(item).strip() != ""
                ]

                if valid_items:
                    return {
                        "success": True,
                        "items": valid_items,
                        "source": "gorse_popular",
                    }
                else:
                    logger.warning(
                        f"⚠️ Popular recommendations returned only empty items"
                    )
                    return {
                        "success": False,
                        "items": [],
                        "source": "gorse_popular_empty",
                        "error": "All popular recommendations were empty",
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

        # Validate shop exists using SQLAlchemy
        logger.debug(
            f"🔍 Validating shop existence | shop_domain={request.shop_domain}"
        )

        async with get_transaction_context() as session:
            result = await session.execute(
                select(Shop).where(Shop.shop_domain == request.shop_domain)
            )
            shop = result.scalar_one_or_none()

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
                    purchase_exclusions = await _get_smart_purchase_exclusions(
                        session=session,
                        shop_id=shop.id,
                        user_id=request.user_id,
                        context=request.context,
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
                # Get cart interactions from the last 48 hours for time decay analysis
                async with get_transaction_context() as session:
                    cart_interactions_result = await session.execute(
                        select(UserInteraction)
                        .where(
                            and_(
                                UserInteraction.shop_id == shop.id,
                                UserInteraction.customer_id == request.user_id,
                                UserInteraction.interaction_type.in_(
                                    [
                                        "product_added_to_cart",
                                        "product_removed_from_cart",
                                    ]
                                ),
                                UserInteraction.created_at
                                >= datetime.utcnow() - timedelta(hours=48),
                            )
                        )
                        .order_by(desc(UserInteraction.created_at))
                        .limit(100)
                    )
                    cart_interactions = cart_interactions_result.scalars().all()

                # Apply time decay logic to determine which products to exclude
                time_decay_exclusions = _apply_time_decay_filtering(
                    cart_interactions, request.user_id
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
                session_data = await extract_session_data_from_behavioral_events(
                    request.user_id, shop.id
                )
                # Merge session data with existing metadata
                enhanced_metadata.update(session_data)

            # If the cart spans multiple categories, avoid over-filtering by category
            effective_category = category
            try:
                product_types = (
                    enhanced_metadata.get("product_types")
                    if enhanced_metadata
                    else None
                )
                if isinstance(product_types, list):
                    unique_types = {t for t in product_types if t}
                    if len(unique_types) > 1:
                        effective_category = None
            except Exception:
                # Non-fatal: fallback to original category
                pass

            # Fallback session_id from cart attributes if not provided
            effective_session_id = request.session_id
            try:
                if (
                    not effective_session_id
                    and enhanced_metadata
                    and enhanced_metadata.get("cart_data")
                ):
                    attributes = enhanced_metadata["cart_data"].get("attributes", [])
                    if isinstance(attributes, list):
                        for attr in attributes:
                            if (
                                isinstance(attr, dict)
                                and attr.get("key") == "bb_recommendation_session_id"
                                and attr.get("value")
                            ):
                                effective_session_id = attr["value"]
                                break
            except Exception:
                pass

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
            # For checkout, use simple fallback chain for speed
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


async def _get_smart_purchase_exclusions(
    session: AsyncSession,
    shop_id: str,
    user_id: Optional[str],
    context: str,
    product_ids_to_check: Optional[List[str]] = None,
) -> List[str]:
    """
    Smart purchase exclusions that consider product type.

    - Durable goods: Always exclude if purchased
    - Consumables: Only exclude recent purchases (last 60 days)
    """
    if not user_id:
        return []

    try:
        # Get all purchased products
        all_purchases = await PurchaseHistoryService.get_purchased_product_ids(
            session=session,
            shop_id=shop_id,
            customer_id=user_id,
        )

        # If we need to check specific products, fetch their types
        if product_ids_to_check:
            from app.core.database.models.product_data import ProductData

            result = await session.execute(
                select(ProductData.product_id, ProductData.product_type).where(
                    and_(
                        ProductData.shop_id == shop_id,
                        ProductData.product_id.in_(product_ids_to_check),
                    )
                )
            )
            product_types = {row.product_id: row.product_type for row in result}

            # Smart filtering
            exclude_ids = []
            for product_id in all_purchases:
                product_type = product_types.get(product_id, "")
                should_exclude = await PurchaseHistoryService.should_exclude_product(
                    session=session,
                    shop_id=shop_id,
                    customer_id=user_id,
                    product_id=product_id,
                    product_type=product_type,
                )
                if should_exclude:
                    exclude_ids.append(product_id)

            logger.debug(
                f"🧠 Smart exclusions: {len(exclude_ids)}/{len(all_purchases)} products excluded"
            )
            return exclude_ids

        # Default: exclude all purchases
        return all_purchases

    except Exception as e:
        logger.error(f"⚠️ Smart exclusions failed: {e}")
        # Fallback to basic exclusion
        return await _get_purchase_exclusions(session, shop_id, user_id, context)
