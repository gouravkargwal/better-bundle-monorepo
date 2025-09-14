"""
Analytics API for BetterBundle Python Worker

This service handles all analytics and attribution tracking separately from recommendations.
Follows proper separation of concerns and single responsibility principle.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from functools import lru_cache
import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from prisma import Json

from app.core.database.simple_db_client import get_database
from app.core.logging import get_logger
from app.domains.analytics.services.attribution_service import AttributionService

logger = get_logger(__name__)

# Create analytics router
router = APIRouter(prefix="/analytics", tags=["analytics"])

# Cache for shop lookups to improve performance
_shop_cache: Dict[str, str] = {}
_cache_lock = asyncio.Lock()


async def get_cached_shop_id_from_user_id(user_id: str) -> Optional[str]:
    """Get shop ID from user ID with caching to reduce database queries"""
    async with _cache_lock:
        # Check cache first
        if user_id in _shop_cache:
            logger.debug(f"🎯 Cache hit for user_id: {user_id}")
            return _shop_cache[user_id]

        # Cache miss - lookup from database
        try:
            from app.api.v1.recommendations import get_shop_domain_from_customer_id

            shop_domain = await get_shop_domain_from_customer_id(user_id)
            if shop_domain:
                db = await get_database()
                shop = await db.shop.find_unique(where={"shopDomain": shop_domain})
                if shop:
                    # Cache the result
                    _shop_cache[user_id] = shop.id
                    logger.debug(f"💾 Cached shop_id {shop.id} for user_id: {user_id}")
                    return shop.id

            # Cache negative result to avoid repeated lookups
            _shop_cache[user_id] = None
            return None

        except Exception as e:
            logger.error(f"Failed to lookup shop for user {user_id}: {e}")
            return None


def clear_shop_cache():
    """Clear the shop cache to prevent memory leaks"""
    global _shop_cache
    _shop_cache.clear()
    logger.info("🧹 Shop cache cleared")


def get_cache_stats() -> Dict[str, int]:
    """Get cache statistics for monitoring"""
    return {
        "cache_size": len(_shop_cache),
        "cached_users": len([k for k, v in _shop_cache.items() if v is not None]),
        "negative_cache_entries": len([k for k, v in _shop_cache.items() if v is None]),
    }


# ============= ANALYTICS MODELS =============


class ViewedProduct(BaseModel):
    """Model for viewed products in session"""

    product_id: str = Field(..., description="Product ID")
    position: int = Field(..., description="Position in recommendation list")


class RecommendationSessionData(BaseModel):
    """Model for creating recommendation sessions"""

    shop_id: Optional[str] = Field(
        None,
        description="Shop ID (optional - will be looked up from user_id if not provided)",
    )
    extension_type: str = Field(
        ..., description="Extension type (venus, mercury, phoenix, etc.)"
    )
    context: str = Field(
        ..., description="Context (profile, checkout, product_page, etc.)"
    )
    user_id: Optional[str] = Field(None, description="User ID if available")
    session_id: str = Field(..., description="Browser session ID")
    viewed_products: Optional[List[ViewedProduct]] = Field(
        default=None, description="Products viewed in this session"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata"
    )


class RecommendationInteractionData(BaseModel):
    """Model for tracking recommendation interactions"""

    session_id: str = Field(..., description="Recommendation session ID")
    product_id: str = Field(..., description="Product ID")
    interaction_type: str = Field(
        ...,
        description="Interaction type (view, click, add_to_cart, buy_now, purchase)",
    )
    position: Optional[int] = Field(None, description="Position in recommendation list")
    extension_type: str = Field(..., description="Extension type")
    context: str = Field(..., description="Context where interaction occurred")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata"
    )


class AttributionResponse(BaseModel):
    """Response model for attribution tracking"""

    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


# ============= ANALYTICS ENDPOINTS =============


@router.post("/session", response_model=AttributionResponse)
async def create_recommendation_session(session_data: RecommendationSessionData):
    """Create a new recommendation session for tracking"""
    try:
        db = await get_database()

        # Handle shop_id: use provided value or lookup from user_id (with caching)
        shop_id = session_data.shop_id
        if not shop_id and session_data.user_id:
            logger.info(
                f"🔍 Shop ID not provided, looking up from user_id: {session_data.user_id}"
            )

            # Use cached lookup for better performance
            shop_id = await get_cached_shop_id_from_user_id(session_data.user_id)

            if shop_id:
                logger.info(
                    f"✅ Found shop_id {shop_id} for user {session_data.user_id}"
                )
            else:
                logger.error(f"❌ Could not find shop for user {session_data.user_id}")
                return AttributionResponse(
                    success=False,
                    message=f"Could not determine shop for user {session_data.user_id}",
                )
        elif not shop_id:
            logger.error("❌ No shop_id or user_id provided")
            return AttributionResponse(
                success=False, message="Either shop_id or user_id must be provided"
            )

        # Create recommendation session in database using frontend session ID
        session = await db.recommendationsession.create(
            {
                "id": session_data.session_id,  # Use frontend session ID as primary key
                "shopId": shop_id,
                "extensionType": session_data.extension_type,
                "context": session_data.context,
                "userId": session_data.user_id,
                "sessionId": session_data.session_id,
                "expiresAt": datetime.utcnow() + timedelta(hours=24),
                "isActive": True,
            }
        )
        logger.info(f"Analytics session created: {session.id} for shop {shop_id}")

        # Create view interactions for viewed products (optimized batch operation)
        if session_data.viewed_products:
            # Use individual creates but with optimized data structure
            interaction_tasks = []
            for viewed_product in session_data.viewed_products:
                task = db.recommendationinteraction.create(
                    {
                        "sessionId": session.id,
                        "productId": viewed_product.product_id,
                        "interactionType": "view",
                        "position": viewed_product.position,
                        "extensionType": session_data.extension_type,
                        "context": session_data.context,
                        "metadata": Json({"batch_created": True}),
                    }
                )
                interaction_tasks.append(task)

            # Execute all creates concurrently for better performance
            await asyncio.gather(*interaction_tasks)

            logger.info(
                f"Created {len(session_data.viewed_products)} view interactions for session {session.id} (concurrent batch operation)"
            )

        return AttributionResponse(
            success=True,
            message="Recommendation session created successfully",
            data={"session_id": session.id},
        )

    except Exception as e:
        logger.error(f"Failed to create recommendation session: {e}")
        return AttributionResponse(
            success=False, message=f"Failed to create session: {str(e)}"
        )


@router.post("/interaction", response_model=AttributionResponse)
async def track_recommendation_interaction(
    interaction_data: RecommendationInteractionData,
):
    """Track a recommendation interaction (view, click, add_to_cart, etc.)"""
    try:
        db = await get_database()

        # Create recommendation interaction
        interaction = await db.recommendationinteraction.create(
            {
                "sessionId": interaction_data.session_id,
                "productId": interaction_data.product_id,
                "interactionType": interaction_data.interaction_type,
                "position": interaction_data.position,
                "extensionType": interaction_data.extension_type,
                "context": interaction_data.context,
                "metadata": (
                    Json(interaction_data.metadata)
                    if interaction_data.metadata
                    else None
                ),
            }
        )

        logger.info(
            f"Tracked recommendation interaction: {interaction.id} for product {interaction_data.product_id}"
        )

        return AttributionResponse(
            success=True,
            message="Recommendation interaction tracked successfully",
            data={"interaction_id": interaction.id},
        )

    except Exception as e:
        logger.error(f"Failed to track recommendation interaction: {e}")
        return AttributionResponse(
            success=False, message=f"Failed to track interaction: {str(e)}"
        )


@router.post("/interactions/batch", response_model=AttributionResponse)
async def track_recommendation_interactions_batch(
    interactions_data: List[RecommendationInteractionData],
):
    """Track multiple recommendation interactions in a single batch operation for better performance"""
    try:
        if not interactions_data:
            return AttributionResponse(
                success=False, message="No interactions provided"
            )

        db = await get_database()

        # Prepare concurrent tasks for better performance
        interaction_tasks = []
        for interaction in interactions_data:
            task = db.recommendationinteraction.create(
                {
                    "sessionId": interaction.session_id,
                    "productId": interaction.product_id,
                    "interactionType": interaction.interaction_type,
                    "position": interaction.position,
                    "extensionType": interaction.extension_type,
                    "context": interaction.context,
                    "metadata": (
                        Json(interaction.metadata) if interaction.metadata else None
                    ),
                }
            )
            interaction_tasks.append(task)

        # Execute all creates concurrently
        await asyncio.gather(*interaction_tasks)

        logger.info(
            f"Tracked {len(interactions_data)} recommendation interactions in batch"
        )

        return AttributionResponse(
            success=True,
            message=f"Successfully tracked {len(interactions_data)} interactions",
            data={"batch_size": len(interactions_data)},
        )

    except Exception as e:
        logger.error(f"Failed to track recommendation interactions batch: {e}")
        return AttributionResponse(
            success=False, message=f"Failed to track interactions: {str(e)}"
        )


@router.get("/cache/stats")
async def get_cache_statistics():
    """Get cache statistics for monitoring performance"""
    try:
        stats = get_cache_stats()
        return {
            "success": True,
            "data": stats,
            "message": "Cache statistics retrieved successfully",
        }
    except Exception as e:
        logger.error(f"Failed to get cache statistics: {e}")
        return {
            "success": False,
            "message": f"Failed to get cache statistics: {str(e)}",
        }


@router.post("/cache/clear")
async def clear_analytics_cache():
    """Clear the analytics cache to free memory"""
    try:
        clear_shop_cache()
        return {"success": True, "message": "Analytics cache cleared successfully"}
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        return {"success": False, "message": f"Failed to clear cache: {str(e)}"}


@router.get("/metrics/{shop_id}")
async def get_attribution_metrics(
    shop_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    extension_type: Optional[str] = None,
):
    """Get attribution metrics for a shop"""
    try:
        db = await get_database()

        # Parse dates
        start_dt = (
            datetime.fromisoformat(start_date)
            if start_date
            else datetime.utcnow() - timedelta(days=30)
        )
        end_dt = datetime.fromisoformat(end_date) if end_date else datetime.utcnow()

        # Build query filters
        where_filters = {
            "shopId": shop_id,
            "attributionDate": {"gte": start_dt, "lte": end_dt},
        }

        if extension_type:
            where_filters["extensionType"] = extension_type

        # Get attribution data
        attributions = await db.recommendationattribution.find_many(where=where_filters)

        # Calculate metrics
        total_revenue = sum(attr.revenue for attr in attributions)
        total_attributions = len(attributions)
        avg_confidence = (
            sum(attr.confidenceScore for attr in attributions) / total_attributions
            if total_attributions > 0
            else 0
        )

        # Group by extension type
        extension_breakdown = {}
        for attr in attributions:
            ext_type = attr.extensionType
            if ext_type not in extension_breakdown:
                extension_breakdown[ext_type] = {"count": 0, "revenue": 0}
            extension_breakdown[ext_type]["count"] += 1
            extension_breakdown[ext_type]["revenue"] += attr.revenue

        return {
            "success": True,
            "metrics": {
                "total_revenue": total_revenue,
                "total_attributions": total_attributions,
                "average_confidence": avg_confidence,
                "extension_breakdown": extension_breakdown,
                "date_range": {
                    "start": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                },
            },
        }

    except Exception as e:
        logger.error(f"Failed to get attribution metrics: {e}")
        return {"success": False, "error": str(e)}


@router.post("/attribution/event")
async def track_attribution_event(event_data: Dict[str, Any]):
    """
    Track attribution events from Atlas (product views, cart additions, etc.)
    This endpoint receives events from the Atlas Web Pixel Extension
    """
    try:
        db = await get_database()
        attribution_service = AttributionService(db)

        # Extract attribution parameters from the event
        recommendation_session = event_data.get("recommendation_session")
        recommendation_product = event_data.get("recommendation_product")
        recommendation_position = event_data.get("recommendation_position")

        # Only process if we have recommendation attribution data
        if not recommendation_session:
            return {"success": True, "message": "No attribution data to track"}

        # Extract customer ID and shop ID
        customer_id = event_data.get("customerId")
        if not customer_id:
            return {"success": False, "error": "Customer ID is required"}

        # Get shop ID from customer ID (you might need to implement this lookup)
        shop_id = await get_shop_id_from_customer_id(db, customer_id)
        if not shop_id:
            return {"success": False, "error": "Could not determine shop ID"}

        # Determine event type from the event data
        event_type = "unknown"
        if "event" in event_data:
            event_name = event_data["event"]
            if "product_viewed" in event_name:
                event_type = "product_viewed"
            elif "product_added_to_cart" in event_name:
                event_type = "add_to_cart"
            elif "checkout_started" in event_name:
                event_type = "checkout_started"
            elif "checkout_completed" in event_name:
                event_type = "checkout_completed"

        # Store attribution event
        attribution_event = await attribution_service.store_attribution_data(
            customer_id=customer_id,
            session_id=recommendation_session,
            product_id=recommendation_product or "unknown",
            position=int(recommendation_position) if recommendation_position else 0,
            event_type=event_type,
            event_data=event_data,
            shop_id=shop_id,
        )

        if attribution_event:
            logger.info(
                f"Tracked attribution event: {event_type} for customer {customer_id}"
            )
            return {"success": True, "attribution_event_id": attribution_event.id}
        else:
            return {"success": False, "error": "Failed to store attribution event"}

    except Exception as e:
        logger.error(f"Failed to track attribution event: {e}")
        return {"success": False, "error": str(e)}


async def get_shop_id_from_customer_id(db, customer_id: str) -> Optional[str]:
    """
    Get shop ID from customer ID
    This is a helper function - you might need to implement proper customer-to-shop mapping
    """
    try:
        # For now, we'll use a simple approach
        # You might need to implement proper customer-to-shop mapping based on your data structure
        customer_data = await db.customerdata.find_first(where={"id": customer_id})

        if customer_data and hasattr(customer_data, "shop_id"):
            return customer_data.shop_id

        # Fallback: try to get from any shop (this is not ideal but works for testing)
        shop = await db.shop.find_first()
        return shop.id if shop else None

    except Exception as e:
        logger.error(f"Failed to get shop ID for customer {customer_id}: {e}")
        return None


@router.post("/attribution/link-order")
async def link_attribution_to_order(order_data: Dict[str, Any]):
    """
    Link attribution events to an order when checkout completes
    This endpoint is called when an order is completed
    """
    try:
        db = await get_database()
        attribution_service = AttributionService(db)

        # Extract order information
        order_id = order_data.get("order_id")
        customer_id = order_data.get("customer_id")
        shop_id = order_data.get("shop_id")

        if not all([order_id, customer_id, shop_id]):
            return {
                "success": False,
                "error": "Missing required fields: order_id, customer_id, shop_id",
            }

        # Link attribution events to the order
        success = await attribution_service.link_attribution_to_order(
            order_id=order_id, customer_id=customer_id, shop_id=shop_id
        )

        if success:
            logger.info(f"Successfully linked attribution to order {order_id}")
            return {
                "success": True,
                "message": f"Attribution linked to order {order_id}",
            }
        else:
            return {"success": False, "error": "Failed to link attribution to order"}

    except Exception as e:
        logger.error(f"Failed to link attribution to order: {e}")
        return {"success": False, "error": str(e)}


@router.get("/attribution/stats")
async def get_attribution_stats():
    """Get attribution processing statistics"""
    try:
        db = await get_database()

        # Count attribution events
        attribution_count = await db.attributionevent.count()

        # Count linked attribution events
        linked_count = await db.attributionevent.count(
            where={"order_id": {"not": None}}
        )

        return {
            "success": True,
            "total_attribution_events": attribution_count,
            "linked_attribution_events": linked_count,
            "unlinked_attribution_events": attribution_count - linked_count,
        }

    except Exception as e:
        logger.error(f"Failed to get attribution stats: {e}")
        return {"success": False, "error": str(e)}


@router.get("/health")
async def analytics_health_check():
    """Health check for analytics service"""
    return {
        "status": "healthy",
        "service": "analytics",
        "timestamp": datetime.utcnow().isoformat(),
    }
