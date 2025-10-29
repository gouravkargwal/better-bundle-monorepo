"""
Suspension management API endpoints
Handles cache invalidation and suspension status checks
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.middleware.suspension_middleware import suspension_middleware
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/suspension", tags=["suspension"])


class InvalidateCacheRequest(BaseModel):
    """Request model for cache invalidation"""

    shop_id: str = Field(..., description="Shop ID to invalidate cache for")


class SuspensionStatusRequest(BaseModel):
    """Request model for suspension status check"""

    shop_id: Optional[str] = Field(None, description="Shop ID to check")
    shop_domain: Optional[str] = Field(None, description="Shop domain to check")


class SuspensionStatusResponse(BaseModel):
    """Response model for suspension status"""

    is_suspended: bool = Field(..., description="Whether the shop is suspended")
    reason: str = Field(..., description="Reason for suspension")
    requires_billing_setup: bool = Field(
        default=False, description="Whether billing setup is required"
    )
    requires_cap_increase: bool = Field(
        default=False, description="Whether cap increase is required"
    )
    subscription_active: bool = Field(
        default=False, description="Whether subscription is active"
    )


@router.post("/invalidate-cache")
async def invalidate_suspension_cache(request: InvalidateCacheRequest):
    """
    Invalidate suspension cache for a specific shop

    This endpoint should be called when a shop's suspension status changes
    to ensure fresh data is fetched on next request.
    """
    try:
        await suspension_middleware.invalidate_cache(request.shop_id)
        logger.info(f"✅ Suspension cache invalidated for shop {request.shop_id}")

        return {
            "success": True,
            "message": f"Cache invalidated for shop {request.shop_id}",
            "shop_id": request.shop_id,
        }
    except Exception as e:
        logger.error(f"❌ Error invalidating cache for shop {request.shop_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to invalidate cache: {str(e)}"
        )


@router.post("/check-status", response_model=SuspensionStatusResponse)
async def check_suspension_status(request: SuspensionStatusRequest):
    """
    Check suspension status for a shop

    Can check by shop_id or shop_domain. Returns detailed suspension information.
    """
    try:
        if not request.shop_id and not request.shop_domain:
            raise HTTPException(
                status_code=400, detail="Either shop_id or shop_domain must be provided"
            )

        # Use shop_id if provided, otherwise resolve from domain
        shop_identifier = request.shop_id or request.shop_domain

        # Get suspension status (with caching)
        status = await suspension_middleware.check_shop_suspension(shop_identifier)

        return SuspensionStatusResponse(
            is_suspended=status.get("isSuspended", True),
            reason=status.get("reason", "unknown"),
            requires_billing_setup=status.get("requiresBillingSetup", False),
            requires_cap_increase=status.get("requiresCapIncrease", False),
            subscription_active=status.get("subscriptionActive", False),
        )

    except Exception as e:
        logger.error(f"❌ Error checking suspension status: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to check suspension status: {str(e)}"
        )


@router.get("/health")
async def suspension_health_check():
    """
    Health check for suspension middleware

    Verifies that the suspension middleware is working correctly.
    """
    try:
        # Test Redis connection by checking a dummy shop
        test_shop_id = "health-check-test"
        await suspension_middleware.check_shop_suspension(test_shop_id)

        return {
            "success": True,
            "message": "Suspension middleware is healthy",
            "cache_ttl": suspension_middleware.cache_ttl,
        }
    except Exception as e:
        logger.error(f"❌ Suspension middleware health check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Suspension middleware health check failed: {str(e)}",
        )
