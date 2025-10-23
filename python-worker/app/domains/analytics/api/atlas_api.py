"""
Atlas API - Web Pixels Extension

This API handles behavioral tracking from the Atlas Web Pixels extension.
Atlas tracks user behavior across the entire store (except checkout).
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.domains.analytics.services.analytics_tracking_service import (
    AnalyticsTrackingService,
)
from app.domains.analytics.services.unified_session_service import UnifiedSessionService
from app.domains.analytics.models.extension import ExtensionType
from app.domains.analytics.models.interaction import InteractionType
from app.core.logging.logger import get_logger
from app.domains.analytics.services.shop_resolver import shop_resolver

logger = get_logger(__name__)

# Create router for Atlas API
router = APIRouter(prefix="/api/atlas", tags=["Atlas - Web Pixels"])

# Initialize services
analytics_service = AnalyticsTrackingService()
session_service = UnifiedSessionService()


class AtlasInteractionRequest(BaseModel):
    """Request model for Atlas interactions"""

    session_id: str = Field(..., description="Session identifier")
    shop_domain: str = Field(..., description="Shop domain")
    interaction_type: InteractionType = Field(..., description="Type of interaction")
    customer_id: Optional[str] = Field(
        None, description="Customer identifier (if known)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional interaction metadata"
    )


class AtlasSessionRequest(BaseModel):
    """Request model for Atlas session management"""

    shop_domain: str = Field(..., description="Shop identifier")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    browser_session_id: Optional[str] = Field(
        None, description="Browser session identifier"
    )
    client_id: Optional[str] = Field(
        None, description="Shopify client ID for device tracking"
    )  # ✅ NEW
    user_agent: Optional[str] = Field(None, description="User agent string")
    ip_address: Optional[str] = Field(None, description="IP address")
    referrer: Optional[str] = Field(None, description="Referrer URL")
    page_url: Optional[str] = Field(None, description="Current page URL")


class AtlasResponse(BaseModel):
    """Response model for Atlas API"""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")


@router.post("/track-interaction", response_model=AtlasResponse)
async def track_atlas_interaction(request: AtlasInteractionRequest):
    """
    Track user interaction from Atlas Web Pixels extension

    This endpoint is called by the Atlas extension to track user behavior
    across the store (homepage, product pages, collection pages, etc.).
    """
    try:

        # Resolve shop_id from domain
        shop_id = await shop_resolver.get_shop_id_from_domain(request.shop_domain)

        if not shop_id:
            raise HTTPException(status_code=404, detail="Shop not found for domain")

        # Track the interaction
        interaction = await analytics_service.track_interaction(
            session_id=request.session_id,
            extension_type=ExtensionType.ATLAS,
            interaction_type=request.interaction_type,
            customer_id=request.customer_id,
            shop_id=shop_id,
            interaction_metadata={
                **request.metadata,
            },
        )

        if not interaction:
            logger.warning(
                f"Atlas interaction tracking failed for session {request.session_id}"
            )
            # Return success but with a warning - this is more graceful
            return AtlasResponse(
                success=True,
                message="Atlas interaction tracked (session may have expired)",
                data={
                    "interaction_id": None,
                    "session_id": request.session_id,
                    "warning": "Session not found or expired",
                },
            )

        # Feature computation is now automatically triggered in track_interaction method

        return AtlasResponse(
            success=True,
            message="Atlas interaction tracked successfully",
            data={
                "interaction_id": interaction.id,
                "session_id": request.session_id,
            },
        )

    except Exception as e:
        # Log full traceback and payload for better diagnostics
        try:
            payload = locals().get("data")
        except Exception:
            payload = None
        logger.exception(
            "Error tracking Atlas interaction",
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to track interaction: {e.__class__.__name__}: {str(e)}",
        )


@router.post("/get-or-create-session", response_model=AtlasResponse)
async def get_or_create_atlas_session(request: AtlasSessionRequest):
    """
    Get or create session for Atlas tracking

    This endpoint is called when Atlas needs to establish or retrieve
    a session for behavioral tracking.
    """
    try:

        shop_id = await shop_resolver.get_shop_id_from_domain(request.shop_domain)

        if not shop_id:
            raise HTTPException(
                status_code=400,
                detail=f"Could not resolve shop ID for domain: {request.shop_domain}",
            )

        # Get or create session
        session = await session_service.get_or_create_session(
            shop_id=shop_id,
            customer_id=request.customer_id,
            browser_session_id=request.browser_session_id,
            client_id=request.client_id,  # ✅ NEW
            user_agent=request.user_agent,
            ip_address=request.ip_address,
            referrer=request.referrer,
        )

        # Add Atlas to extensions used
        await session_service.add_extension_to_session(session.id, ExtensionType.ATLAS)

        return AtlasResponse(
            success=True,
            message="Atlas session created/retrieved successfully",
            data={
                "session_id": session.id,
                "customer_id": session.customer_id,
                "browser_session_id": session.browser_session_id,
                "client_id": session.client_id,  # ✅ NEW
                "expires_at": (
                    session.expires_at.isoformat() if session.expires_at else None
                ),
                "extensions_used": session.extensions_used,
            },
        )

    except Exception as e:
        # Log full traceback and request context
        try:
            ctx = request.model_dump()
        except Exception:
            ctx = None
        logger.exception("Error creating Atlas session")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create session: {e.__class__.__name__}: {str(e)}",
        )
