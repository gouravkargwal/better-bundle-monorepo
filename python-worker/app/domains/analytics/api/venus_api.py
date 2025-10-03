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
from app.domains.analytics.services.shop_resolver import shop_resolver

logger = get_logger(__name__)

# Create router for Venus API
router = APIRouter(prefix="/api/venus", tags=["Venus Analytics"])

# Initialize services
session_service = UnifiedSessionService()
analytics_service = AnalyticsTrackingService()


class VenusSessionRequest(BaseModel):
    """Request model for Venus session creation"""

    shop_domain: str = Field(..., description="Shop domain")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    browser_session_id: Optional[str] = Field(
        None, description="Browser session identifier"
    )
    client_id: Optional[str] = Field(
        None, description="Shopify client ID (optional)"
    )  # ✅ NEW (optional for Venus)
    user_agent: Optional[str] = Field(None, description="User agent string")
    ip_address: Optional[str] = Field(None, description="IP address")
    referrer: Optional[str] = Field(None, description="Referrer URL")
    page_url: Optional[str] = Field(None, description="Current page URL")


class VenusInteractionRequest(BaseModel):
    """Request model for Venus interaction tracking"""

    session_id: str = Field(..., description="Unified session identifier")
    shop_domain: str = Field(..., description="Shop domain")
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
        shop_id = await shop_resolver.get_shop_id_from_customer_id(request.customer_id)
        if not shop_id:
            raise HTTPException(status_code=404, detail="Shop not found for customer")

        # Get or create unified session
        session = await session_service.get_or_create_session(
            shop_id=shop_id,
            customer_id=request.customer_id,
            browser_session_id=None,  # Venus doesn't have this
            client_id=None,
            user_agent=request.user_agent,
            ip_address=request.ip_address,
            referrer=request.referrer,
        )

        # Add Venus to extensions used
        await session_service.add_extension_to_session(session.id, ExtensionType.VENUS)

        if not session:
            raise HTTPException(status_code=500, detail="Failed to create session")

        return VenusResponse(
            success=True,
            message="Venus session started successfully",
            data={
                "session_id": session.id,
                "browser_session_id": session.browser_session_id,  # May be null
                "client_id": session.client_id,  # May be null
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

        # Resolve shop_id from domain
        shop_id = await shop_resolver.get_shop_id_from_customer_id(request.customer_id)

        if not shop_id:
            raise HTTPException(status_code=404, detail="Shop not found for customer")

        # Track interaction using unified analytics
        interaction = await analytics_service.track_interaction(
            session_id=request.session_id,
            extension_type=ExtensionType.VENUS,
            interaction_type=request.interaction_type,
            shop_id=shop_id,
            customer_id=request.customer_id,
            interaction_metadata=enhanced_metadata,
        )

        if not interaction:
            raise HTTPException(status_code=500, detail="Failed to track interaction")

        # Feature computation is now automatically triggered in track_interaction method

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
