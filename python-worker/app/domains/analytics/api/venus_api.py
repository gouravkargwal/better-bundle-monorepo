"""
Venus Analytics API

Handles analytics tracking for Venus extension (Customer Account Extensions).
Venus runs on customer profile pages, order status pages, and order index pages.
"""

from typing import Optional, Dict, Any
import time
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, Field

from app.domains.analytics.models.extension import ExtensionType, ExtensionContext
from app.domains.analytics.models.interaction import InteractionType
from app.domains.analytics.services.unified_session_service import UnifiedSessionService
from app.domains.analytics.services.analytics_tracking_service import (
    AnalyticsTrackingService,
)
from app.core.logging.logger import get_logger
from app.domains.analytics.services.shop_resolver import shop_resolver
from app.middleware.suspension_middleware import suspension_middleware

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
async def get_or_create_venus_session(
    request: VenusSessionRequest, authorization: str = Header(None)
):
    """
    Get or create unified session for Venus extension

    Venus runs on customer account pages where we have access to customer_id,
    but also supports anonymous sessions.
    """
    try:
        shop_id = await shop_resolver.get_shop_id_from_customer_id(request.customer_id)
        if not shop_id:
            raise HTTPException(status_code=404, detail="Shop not found for customer")

        # JWT-based suspension check (stateless - no Redis needed!)
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "Missing or invalid authorization header",
                    "message": "Please provide a valid JWT token in Authorization header",
                    "required_format": "Bearer <jwt_token>",
                },
            )

        jwt_token = authorization.split(" ")[1]
        if not await suspension_middleware.should_process_shop_from_jwt(jwt_token):
            message = await suspension_middleware.get_suspension_message_from_jwt(
                jwt_token
            )
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "Services suspended",
                    "message": message,
                    "shop_domain": request.shop_domain,
                },
            )

        # Generate a browser session ID for Venus if not provided
        # Venus doesn't have browser session tracking, so we create one
        browser_session_id = (
            request.browser_session_id
            or f"venus_{request.customer_id}_{int(time.time())}"
        )

        # Get or create unified session
        session = await session_service.get_or_create_session(
            shop_id=shop_id,
            customer_id=request.customer_id,
            browser_session_id=browser_session_id,
            client_id=request.client_id,
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

    except HTTPException:
        # Re-raise HTTP exceptions (like 403 from suspension check) without modification
        raise
    except Exception as e:
        logger.error(f"Error starting Venus session: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to start session: {str(e)}"
        )


@router.post("/track-interaction", response_model=VenusResponse)
async def track_venus_interaction(
    request: VenusInteractionRequest, authorization: str = Header(None)
):
    """
    Track user interaction from Venus extension with automatic session recovery

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

        # JWT-based suspension check (stateless - no Redis needed!)
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "Missing or invalid authorization header",
                    "message": "Please provide a valid JWT token in Authorization header",
                    "required_format": "Bearer <jwt_token>",
                },
            )

        jwt_token = authorization.split(" ")[1]
        if not await suspension_middleware.should_process_shop_from_jwt(jwt_token):
            message = await suspension_middleware.get_suspension_message_from_jwt(
                jwt_token
            )
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
            extension_type=ExtensionType.VENUS,
            interaction_type=request.interaction_type,
            shop_id=shop_id,
            customer_id=request.customer_id,
            interaction_metadata=enhanced_metadata,
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
                        extension_type=ExtensionType.VENUS,
                        interaction_type=request.interaction_type,
                        shop_id=shop_id,
                        customer_id=request.customer_id,
                        interaction_metadata=enhanced_metadata,
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
                        extension_type=ExtensionType.VENUS,
                        interaction_type=request.interaction_type,
                        shop_id=shop_id,
                        customer_id=request.customer_id,
                        interaction_metadata=enhanced_metadata,
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

        return VenusResponse(
            success=True,
            message="Venus interaction tracked successfully",
            data={
                "interaction_id": interaction.id,
                "session_id": interaction.session_id,  # This will be the recovered session ID
                "interaction_type": request.interaction_type,
                "timestamp": interaction.created_at.isoformat(),
            },
            session_recovery=session_recovery_info,  # Frontend gets recovery info
        )

    except HTTPException:
        # Re-raise HTTP exceptions (like 403 from suspension check) without modification
        raise
    except Exception as e:
        logger.error(f"Error tracking Venus interaction: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to track interaction: {str(e)}"
        )
