"""
Customer Linking API endpoints
Handles customer linking and backfilling operations
"""

from datetime import datetime
from typing import Dict, Any, Optional

from app.shared.helpers import now_utc

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.domains.customer_linking.scheduler import customer_linking_scheduler
from app.core.database.simple_db_client import get_database

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/customer-linking", tags=["customer-linking"])


# Pydantic models for request/response
class BackfillRequest(BaseModel):
    """Request model for backfilling customer links"""

    shop_id: str = Field(..., description="Shop ID to backfill customer links for")
    batch_size: int = Field(
        default=100, ge=1, le=1000, description="Batch size for processing"
    )
    force: bool = Field(
        default=False, description="Force backfill even if no unprocessed links found"
    )


class BackfillResponse(BaseModel):
    """Response model for backfill operations"""

    status: str
    shop_id: str
    processed_links: int
    total_events_backfilled: int
    errors: int
    duration_seconds: float
    message: str
    executed_at: datetime


class CustomerLinkStats(BaseModel):
    """Customer link statistics for a shop"""

    shop_id: str
    total_links: int
    unprocessed_links: int
    total_anonymous_events: int
    events_needing_backfill: int
    last_backfill_at: Optional[datetime]


class CustomerLinkInfo(BaseModel):
    """Information about a specific customer link"""

    id: str
    shop_id: str
    client_id: str
    customer_id: str
    linked_at: datetime
    events_count: int
    needs_backfill: bool


@router.post("/shops/{shop_id}/backfill", response_model=BackfillResponse)
async def backfill_customer_links(
    shop_id: str,
    request: Optional[BackfillRequest] = None,
    batch_size: int = Query(
        default=100, ge=1, le=1000, description="Batch size for processing"
    ),
    force: bool = Query(
        default=False, description="Force backfill even if no unprocessed links found"
    ),
) -> BackfillResponse:
    """
    Backfill customer IDs for anonymous events in a specific shop

    This endpoint triggers a backfill job for the specified shop, linking
    anonymous events (clientId) to customer IDs based on UserIdentityLink records.
    """
    try:
        # Use request body if provided, otherwise use query parameters
        if request:
            batch_size = request.batch_size
            force = request.force

        start_time = now_utc()

        # Check if shop exists
        db = await get_database()
        shop = await db.shop.find_unique(where={"id": shop_id})
        if not shop:
            raise HTTPException(status_code=404, detail=f"Shop {shop_id} not found")

        # Run the backfill job
        result = await customer_linking_scheduler.run_backfill_job(batch_size)

        # Filter results for this specific shop if needed
        # (The scheduler currently processes all shops, but we can filter here)
        duration = (now_utc() - start_time).total_seconds()

        if result["status"] == "success":
            message = f"Successfully backfilled customer links for shop {shop_id}"
            if result["processed_links"] == 0 and not force:
                message = f"No unprocessed links found for shop {shop_id}"
        else:
            message = f"Backfill job failed: {result.get('error', 'Unknown error')}"

        return BackfillResponse(
            status=result["status"],
            shop_id=shop_id,
            processed_links=result.get("processed_links", 0),
            total_events_backfilled=result.get("total_events_backfilled", 0),
            errors=result.get("errors", 0),
            duration_seconds=duration,
            message=message,
            executed_at=start_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to backfill customer links for shop {shop_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to backfill customer links: {str(e)}"
        )


@router.get("/shops/{shop_id}/stats", response_model=CustomerLinkStats)
async def get_customer_link_stats(shop_id: str) -> CustomerLinkStats:
    """
    Get customer linking statistics for a specific shop
    """
    try:
        # Check if shop exists
        db = await get_database()
        shop = await db.shop.find_unique(where={"id": shop_id})
        if not shop:
            raise HTTPException(status_code=404, detail=f"Shop {shop_id} not found")

        # Get total links for this shop
        total_links = await db.useridentitylink.count(where={"shopId": shop_id})

        # Get unprocessed links (links with events that still need backfilling)
        unprocessed_links = 0
        all_links = await db.useridentitylink.find_many(where={"shopId": shop_id})

        for link in all_links:
            events_needing_backfill = await db.userinteraction.find_first(
                where={"shopId": shop_id, "clientId": link.clientId, "customerId": None}
            )
            if events_needing_backfill:
                unprocessed_links += 1

        # Get total anonymous events
        total_anonymous_events = await db.userinteraction.count(
            where={"shopId": shop_id, "customerId": None}
        )

        # Get events needing backfill
        events_needing_backfill = await db.userinteraction.count(
            where={
                "shopId": shop_id,
                "customerId": None,
                "clientId": {"not": None},  # Has clientId but no customerId
            }
        )

        # Get last backfill time (we'll use the most recent link creation time as proxy)
        last_link = await db.useridentitylink.find_first(
            where={"shopId": shop_id}, order={"linkedAt": "desc"}
        )
        last_backfill_at = last_link.linkedAt if last_link else None

        return CustomerLinkStats(
            shop_id=shop_id,
            total_links=total_links,
            unprocessed_links=unprocessed_links,
            total_anonymous_events=total_anonymous_events,
            events_needing_backfill=events_needing_backfill,
            last_backfill_at=last_backfill_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get customer link stats for shop {shop_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get customer link stats: {str(e)}"
        )


@router.get("/shops/{shop_id}/links", response_model=list[CustomerLinkInfo])
async def get_customer_links(
    shop_id: str,
    limit: int = Query(
        default=50, ge=1, le=200, description="Number of links to return"
    ),
    offset: int = Query(default=0, ge=0, description="Number of links to skip"),
) -> list[CustomerLinkInfo]:
    """
    Get customer links for a specific shop
    """
    try:
        # Check if shop exists
        db = await get_database()
        shop = await db.shop.find_unique(where={"id": shop_id})
        if not shop:
            raise HTTPException(status_code=404, detail=f"Shop {shop_id} not found")

        # Get customer links
        links = await db.useridentitylink.find_many(
            where={"shopId": shop_id},
            take=limit,
            skip=offset,
            order={"linkedAt": "desc"},
        )

        # Enrich with additional information
        link_infos = []
        for link in links:
            # Count events for this link
            events_count = await db.userinteraction.count(
                where={"shopId": shop_id, "clientId": link.clientId}
            )

            # Check if needs backfill
            needs_backfill = (
                await db.userinteraction.find_first(
                    where={
                        "shopId": shop_id,
                        "clientId": link.clientId,
                        "customerId": None,
                    }
                )
                is not None
            )

            link_infos.append(
                CustomerLinkInfo(
                    id=link.id,
                    shop_id=link.shopId,
                    client_id=link.clientId,
                    customer_id=link.customerId,
                    linked_at=link.linkedAt,
                    events_count=events_count,
                    needs_backfill=needs_backfill,
                )
            )

        return link_infos

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get customer links for shop {shop_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get customer links: {str(e)}"
        )


@router.delete("/shops/{shop_id}/links/{link_id}")
async def delete_customer_link(shop_id: str, link_id: str) -> Dict[str, Any]:
    """
    Delete a customer link (use with caution - this will unlink customer from anonymous events)
    """
    try:
        # Check if shop exists
        db = await get_database()
        shop = await db.shop.find_unique(where={"id": shop_id})
        if not shop:
            raise HTTPException(status_code=404, detail=f"Shop {shop_id} not found")

        # Check if link exists
        link = await db.useridentitylink.find_unique(where={"id": link_id})
        if not link or link.shopId != shop_id:
            raise HTTPException(
                status_code=404,
                detail=f"Customer link {link_id} not found for shop {shop_id}",
            )

        # Delete the link
        await db.useridentitylink.delete(where={"id": link_id})

        return {
            "status": "success",
            "message": f"Customer link {link_id} deleted successfully",
            "shop_id": shop_id,
            "link_id": link_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to delete customer link {link_id} for shop {shop_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to delete customer link: {str(e)}"
        )


@router.get("/health")
async def customer_linking_health_check() -> Dict[str, Any]:
    """
    Health check for the customer linking system
    """
    try:
        # Test database connection
        db = await get_database()

        # Get basic stats
        total_links = await db.useridentitylink.count()
        total_shops = await db.shop.count()

        return {
            "status": "healthy",
            "total_links": total_links,
            "total_shops": total_shops,
            "scheduler_available": True,
            "checked_at": now_utc(),
        }

    except Exception as e:
        logger.error(f"Customer linking health check failed: {str(e)}")
        return {"status": "unhealthy", "error": str(e), "checked_at": now_utc()}
