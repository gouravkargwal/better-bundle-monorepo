"""
Venus Analytics API

Handles analytics tracking for Venus extension (Customer Account Extensions).
Venus runs on customer profile pages, order status pages, and order index pages.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.domains.analytics.models.extension import ExtensionType, ExtensionContext
from app.domains.analytics.models.interaction import InteractionType
from app.domains.analytics.services.unified_session_service import UnifiedSessionService
from app.domains.analytics.services.analytics_tracking_service import (
    AnalyticsTrackingService,
)
from app.core.logging.logger import get_logger

logger = get_logger(__name__)

# Create router for Venus API
router = APIRouter(prefix="/api/venus", tags=["Venus Analytics"])

# Initialize services
session_service = UnifiedSessionService()
analytics_service = AnalyticsTrackingService()


class VenusSessionRequest(BaseModel):
    """Request model for Venus session creation"""

    shop_id: str = Field(..., description="Shop identifier")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    browser_session_id: Optional[str] = Field(
        None, description="Browser session identifier"
    )
    user_agent: Optional[str] = Field(None, description="User agent string")
    ip_address: Optional[str] = Field(None, description="IP address")
    referrer: Optional[str] = Field(None, description="Referrer URL")
    page_url: Optional[str] = Field(None, description="Current page URL")


class VenusInteractionRequest(BaseModel):
    """Request model for Venus interaction tracking"""

    session_id: str = Field(..., description="Unified session identifier")
    shop_id: str = Field(..., description="Shop identifier")
    interaction_type: InteractionType = Field(..., description="Type of interaction")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Raw interaction data as JSON"
    )


class VenusResponse(BaseModel):
    """Response model for Venus API"""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")


@router.post("/get-or-create-session", response_model=VenusResponse)
async def get_or_create_venus_session(request: VenusSessionRequest):
    """
    Get or create unified session for Venus extension

    Venus runs on customer account pages where we have access to customer_id,
    but also supports anonymous sessions.
    """
    try:
        # Get or create unified session
        session = await session_service.get_or_create_session(
            shop_id=request.shop_id,
            customer_id=request.customer_id,
            browser_session_id=request.browser_session_id,
            user_agent=request.user_agent,
            ip_address=request.ip_address,
            referrer=request.referrer,
        )

        # Add Venus to extensions used
        await session_service.add_extension_to_session(session.id, ExtensionType.VENUS)

        if not session:
            raise HTTPException(status_code=500, detail="Failed to create session")

        logger.info(
            f"Venus session started: {session.id} for customer {request.customer_id}"
        )

        return VenusResponse(
            success=True,
            message="Venus session started successfully",
            data={
                "session_id": session.id,
                "customer_id": session.customer_id,
                "created_at": session.created_at.isoformat(),
                "expires_at": (
                    session.expires_at.isoformat() if session.expires_at else None
                ),
            },
        )

    except Exception as e:
        logger.error(f"Error starting Venus session: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to start session: {str(e)}"
        )


@router.post("/track-interaction", response_model=VenusResponse)
async def track_venus_interaction(request: VenusInteractionRequest):
    """
    Track user interaction from Venus extension

    Venus can track:
    - Profile views
    - Order views
    - Order status views
    - Recommendation views and clicks
    - Product interactions
    - Shop now actions
    """
    try:
        # Add extension type to metadata
        enhanced_metadata = {
            **request.metadata,
            "extension_type": "venus",
        }

        # Track interaction using unified analytics
        interaction = await analytics_service.track_interaction(
            session_id=request.session_id,
            extension_type=ExtensionType.VENUS,
            interaction_type=request.interaction_type,
            shop_id=request.shop_id,
            customer_id=request.customer_id,
            metadata=enhanced_metadata,
        )

        if not interaction:
            raise HTTPException(status_code=500, detail="Failed to track interaction")

        logger.info(f"Venus interaction tracked: {request.interaction_type}")

        return VenusResponse(
            success=True,
            message="Venus interaction tracked successfully",
            data={
                "interaction_id": interaction.id,
                "session_id": interaction.session_id,
                "interaction_type": request.interaction_type,
                "timestamp": interaction.created_at.isoformat(),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tracking Venus interaction: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to track interaction: {str(e)}"
        )


@router.get("/session/{session_id}/interactions", response_model=VenusResponse)
async def get_venus_session_interactions(session_id: str):
    """Get all interactions for a Venus session"""
    try:
        interactions = await analytics_service.get_session_interactions(session_id)

        # Filter for Venus interactions only
        venus_interactions = [
            i for i in interactions if i.extension_type == ExtensionType.VENUS
        ]

        return VenusResponse(
            success=True,
            message="Venus interactions retrieved successfully",
            data={
                "session_id": session_id,
                "total_interactions": len(venus_interactions),
                "interactions": [
                    {
                        "id": i.id,
                        "interaction_type": i.interaction_type,
                        "context": i.context,
                        "product_id": i.product_id,
                        "order_id": i.order_id,
                        "timestamp": i.created_at.isoformat(),
                        "metadata": i.metadata,
                    }
                    for i in venus_interactions
                ],
            },
        )

    except Exception as e:
        logger.error(f"Error getting Venus session interactions: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get interactions: {str(e)}"
        )


@router.get("/customer/{customer_id}/interactions", response_model=VenusResponse)
async def get_venus_customer_interactions(customer_id: str, shop_id: str):
    """Get all Venus interactions for a specific customer"""
    try:
        interactions = await analytics_service.get_customer_interactions(
            customer_id=customer_id, shop_id=shop_id
        )

        # Filter for Venus interactions only
        venus_interactions = [
            i for i in interactions if i.extension_type == ExtensionType.VENUS
        ]

        return VenusResponse(
            success=True,
            message="Customer Venus interactions retrieved successfully",
            data={
                "customer_id": customer_id,
                "shop_id": shop_id,
                "total_interactions": len(venus_interactions),
                "interactions": [
                    {
                        "id": i.id,
                        "interaction_type": i.interaction_type,
                        "context": i.context,
                        "product_id": i.product_id,
                        "order_id": i.order_id,
                        "timestamp": i.created_at.isoformat(),
                        "metadata": i.metadata,
                    }
                    for i in venus_interactions
                ],
            },
        )

    except Exception as e:
        logger.error(f"Error getting customer Venus interactions: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get customer interactions: {str(e)}"
        )


@router.get("/performance", response_model=VenusResponse)
async def get_venus_performance(shop_id: str, days: int = 30):
    """Get Venus extension performance metrics"""
    try:
        performance = await analytics_service.get_extension_performance(
            extension_type=ExtensionType.VENUS, shop_id=shop_id, days=days
        )

        return VenusResponse(
            success=True,
            message="Venus performance metrics retrieved successfully",
            data=performance,
        )

    except Exception as e:
        logger.error(f"Error getting Venus performance: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get performance metrics: {str(e)}"
        )
