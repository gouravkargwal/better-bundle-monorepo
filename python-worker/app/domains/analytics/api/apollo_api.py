"""
Apollo API - Post-Purchase Extensions

This API handles interactions from the Apollo Post-Purchase extension.
Apollo can show recommendations and track interactions after purchase completion.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.domains.analytics.services.analytics_tracking_service import (
    AnalyticsTrackingService,
)
from app.domains.analytics.services.unified_session_service import UnifiedSessionService
from app.domains.analytics.models.extension import ExtensionType, ExtensionContext
from app.domains.analytics.models.interaction import InteractionType
from app.core.logging.logger import get_logger
from app.domains.analytics.services.shop_resolver import shop_resolver

logger = get_logger(__name__)

# Create router for Apollo API
router = APIRouter(prefix="/api/apollo", tags=["Apollo - Post-Purchase"])

# Initialize services
analytics_service = AnalyticsTrackingService()
session_service = UnifiedSessionService()


class ApolloSessionRequest(BaseModel):
    """Request model for Apollo session creation"""

    shop_domain: str = Field(..., description="Shop domain")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    browser_session_id: Optional[str] = Field(
        None, description="Browser session identifier"
    )
    client_id: Optional[str] = Field(None, description="Shopify client ID (optional)")
    user_agent: Optional[str] = Field(None, description="User agent string")
    ip_address: Optional[str] = Field(None, description="IP address")
    referrer: Optional[str] = Field(None, description="Referrer URL")
    page_url: Optional[str] = Field(None, description="Current page URL")


class ApolloInteractionRequest(BaseModel):
    """Request model for Apollo interactions"""

    session_id: str = Field(..., description="Session identifier")
    shop_domain: str = Field(..., description="Shop domain")
    interaction_type: InteractionType = Field(..., description="Type of interaction")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Raw interaction data as JSON"
    )


class ApolloResponse(BaseModel):
    """Response model for Apollo API"""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")


@router.post("/get-or-create-session", response_model=ApolloResponse)
async def get_or_create_apollo_session(request: ApolloSessionRequest):
    """
    Get or create unified session for Apollo extension

    Apollo is a post-purchase extension that runs after checkout completion
    and always has access to customer_id from the order context.
    """
    try:
        # Resolve shop domain to shop ID if needed
        shop_id = await shop_resolver.get_shop_id_from_domain(request.shop_domain)
        if not shop_id:
            raise HTTPException(
                status_code=400,
                detail=f"Could not resolve shop ID for domain: {request.shop_domain}",
            )

        # Get or create unified session
        session = await session_service.get_or_create_session(
            shop_id=shop_id,
            customer_id=request.customer_id,
            browser_session_id=request.browser_session_id,
            user_agent=request.user_agent,
            client_id=request.client_id,
            ip_address=request.ip_address,
            referrer=request.referrer,
        )

        # Add Apollo to extensions used
        await session_service.add_extension_to_session(session.id, ExtensionType.APOLLO)

        if not session:
            raise HTTPException(status_code=500, detail="Failed to create session")

        logger.info(
            f"Apollo session started: {session.id} for customer {request.customer_id}"
        )

        return ApolloResponse(
            success=True,
            message="Apollo session started successfully",
            data={
                "session_id": session.id,
                "customer_id": session.customer_id,
                "client_id": session.client_id,
                "created_at": session.created_at.isoformat(),
                "expires_at": (
                    session.expires_at.isoformat() if session.expires_at else None
                ),
            },
        )

    except Exception as e:
        logger.error(f"Error starting Apollo session: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to start session: {str(e)}"
        )


@router.post("/track-interaction", response_model=ApolloResponse)
async def track_apollo_interaction(request: ApolloInteractionRequest):
    """
    Track user interaction from Apollo Post-Purchase extension

    This endpoint is called by the Apollo extension to track user interactions
    in the post-purchase flow (recommendations, add to order, etc.).
    """
    try:
        logger.info(f"Apollo interaction tracking: {request.interaction_type}")

        # Resolve shop domain to shop ID if needed
        shop_id = await shop_resolver.get_shop_id_from_domain(request.shop_domain)
        if not shop_id:
            raise HTTPException(
                status_code=400,
                detail=f"Could not resolve shop ID for domain: {request.shop_domain}",
            )

        # Add extension type to metadata
        enhanced_metadata = {
            **request.metadata,
            "extension_type": "apollo",
        }

        # Track the interaction
        interaction = await analytics_service.track_interaction(
            session_id=request.session_id,
            extension_type=ExtensionType.APOLLO,
            interaction_type=request.interaction_type,
            shop_id=shop_id,
            customer_id=request.customer_id,
            interaction_metadata=enhanced_metadata,
        )

        if not interaction:
            raise HTTPException(status_code=500, detail="Failed to track interaction")

        # Feature computation is now automatically triggered in track_interaction method

        logger.info(f"Apollo interaction tracked successfully: {interaction.id}")

        return ApolloResponse(
            success=True,
            message="Apollo interaction tracked successfully",
            data={
                "interaction_id": interaction.id,
                "session_id": request.session_id,
                "interaction_type": request.interaction_type,
                "timestamp": interaction.created_at.isoformat(),
            },
        )

    except Exception as e:
        logger.error(f"Error tracking Apollo interaction: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to track interaction: {str(e)}"
        )
