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
from app.middleware.suspension_middleware import suspension_middleware

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
    # Session recovery information
    session_recovery: Optional[Dict[str, Any]] = Field(
        None, description="Session recovery details"
    )


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

        # Check if shop is suspended (with caching)
        if not await suspension_middleware.should_process_shop(shop_id):
            message = await suspension_middleware.get_suspension_message(shop_id)
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Services suspended",
                    "message": message,
                    "shop_domain": request.shop_domain,
                },
            )

        # Try to track interaction with the original session
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

        # Check if session recovery is needed
        session_recovery_info = None
        if not interaction:
            logger.warning(
                f"Session {request.session_id} not found, attempting recovery..."
            )

            # Try to find recent session for same customer
            if request.customer_id:
                recent_session = await session_service._find_recent_customer_session(
                    request.customer_id, shop_id, minutes_back=30
                )

                if recent_session:
                    logger.info(f"✅ Recovered recent session: {recent_session.id}")
                    session_recovery_info = {
                        "original_session_id": request.session_id,
                        "new_session_id": recent_session.id,
                        "recovery_reason": "recent_session_found",
                        "recovered_at": recent_session.last_active.isoformat(),
                    }

                    # Try tracking with recovered session
                    interaction = await analytics_service.track_interaction(
                        session_id=recent_session.id,
                        extension_type=ExtensionType.ATLAS,
                        interaction_type=request.interaction_type,
                        customer_id=request.customer_id,
                        shop_id=shop_id,
                        interaction_metadata={
                            **request.metadata,
                        },
                    )

            # If still no interaction, create new session
            if not interaction:
                logger.info("Creating new session as fallback...")
                new_session = await session_service.get_or_create_session(
                    shop_id=shop_id,
                    customer_id=request.customer_id,
                    browser_session_id=f"recovered_{request.session_id}",
                )

                if new_session:
                    session_recovery_info = {
                        "original_session_id": request.session_id,
                        "new_session_id": new_session.id,
                        "recovery_reason": "new_session_created",
                        "recovered_at": new_session.created_at.isoformat(),
                    }

                    # Try tracking with new session
                    interaction = await analytics_service.track_interaction(
                        session_id=new_session.id,
                        extension_type=ExtensionType.ATLAS,
                        interaction_type=request.interaction_type,
                        customer_id=request.customer_id,
                        shop_id=shop_id,
                        interaction_metadata={
                            **request.metadata,
                        },
                    )

        if not interaction:
            raise HTTPException(
                status_code=500,
                detail="Failed to track interaction even with session recovery",
            )

        # Log session recovery if it occurred
        if session_recovery_info:
            logger.info(
                f"🔄 Session recovered: {session_recovery_info['original_session_id']} → {session_recovery_info['new_session_id']}"
            )

        return AtlasResponse(
            success=True,
            message="Atlas interaction tracked successfully",
            data={
                "interaction_id": interaction.id,
                "session_id": interaction.session_id,  # This will be the recovered session ID
                "interaction_type": request.interaction_type,
                "timestamp": interaction.created_at.isoformat(),
            },
            session_recovery=session_recovery_info,  # Frontend gets recovery info
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

        # Check if shop is suspended (with caching)
        if not await suspension_middleware.should_process_shop(shop_id):
            message = await suspension_middleware.get_suspension_message(shop_id)
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Services suspended",
                    "message": message,
                    "shop_domain": request.shop_domain,
                },
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
