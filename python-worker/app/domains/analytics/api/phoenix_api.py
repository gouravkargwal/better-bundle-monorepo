"""
Phoenix API - Checkout UI Extensions

This API handles interactions from the Phoenix Checkout UI extension.
Phoenix can show recommendations and track interactions in the checkout flow.
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

# Create router for Phoenix API
router = APIRouter(prefix="/api/phoenix", tags=["Phoenix - Checkout UI"])

# Initialize services
analytics_service = AnalyticsTrackingService()
session_service = UnifiedSessionService()


class PhoenixSessionRequest(BaseModel):
    """Request model for Phoenix session creation"""

    shop_domain: str = Field(..., description="Shop domain")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    browser_session_id: Optional[str] = Field(
        None, description="Browser session identifier"
    )
    client_id: Optional[str] = Field(
        None, description="Shopify client ID (optional)"
    )  # ✅ NEW (optional for Phoenix)
    user_agent: Optional[str] = Field(None, description="User agent string")
    ip_address: Optional[str] = Field(None, description="IP address")
    referrer: Optional[str] = Field(None, description="Referrer URL")
    page_url: Optional[str] = Field(None, description="Current page URL")


class PhoenixInteractionRequest(BaseModel):
    """Request model for Phoenix interactions"""

    session_id: str = Field(..., description="Session identifier")
    shop_domain: str = Field(..., description="Shop domain")
    interaction_type: InteractionType = Field(..., description="Type of interaction")
    customer_id: Optional[str] = Field(
        None, description="Customer identifier (if known)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Raw interaction data as JSON"
    )


class PhoenixRecommendationRequest(BaseModel):
    """Request model for Phoenix recommendations"""

    session_id: str = Field(..., description="Session identifier")
    shop_domain: str = Field(..., description="Shop domain")
    context: ExtensionContext = Field(
        ..., description="Context where recommendation is shown"
    )
    customer_id: Optional[str] = Field(None, description="Customer identifier")

    # Recommendation details
    recommendation_type: str = Field(..., description="Type of recommendation")
    algorithm: str = Field(..., description="Algorithm used for recommendation")
    products: list[Dict[str, Any]] = Field(..., description="Recommended products")

    # Context data
    current_cart: Optional[Dict[str, Any]] = Field(
        None, description="Current cart contents"
    )
    checkout_step: Optional[str] = Field(None, description="Current checkout step")


class PhoenixResponse(BaseModel):
    """Response model for Phoenix API"""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")


@router.post("/get-or-create-session", response_model=PhoenixResponse)
async def get_or_create_phoenix_session(request: PhoenixSessionRequest):
    """
    Get or create unified session for Phoenix extension

    Phoenix is a theme extension that runs on cart pages and can work with both
    anonymous users and identified customers.
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
            client_id=request.client_id,  # ✅ NEW
            ip_address=request.ip_address,
            referrer=request.referrer,
        )

        # Add Phoenix to extensions used
        await session_service.add_extension_to_session(
            session.id, ExtensionType.PHOENIX
        )

        if not session:
            raise HTTPException(status_code=500, detail="Failed to create session")

        logger.info(
            f"Phoenix session started: {session.id} for customer {request.customer_id}"
        )

        return PhoenixResponse(
            success=True,
            message="Phoenix session started successfully",
            data={
                "session_id": session.id,
                "customer_id": session.customer_id,
                "client_id": session.client_id,  # ✅ NEW
                "created_at": session.created_at.isoformat(),
                "expires_at": (
                    session.expires_at.isoformat() if session.expires_at else None
                ),
            },
        )

    except Exception as e:
        logger.error(f"Error starting Phoenix session: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to start session: {str(e)}"
        )


@router.post("/track-interaction", response_model=PhoenixResponse)
async def track_phoenix_interaction(request: PhoenixInteractionRequest):
    """
    Track user interaction from Phoenix theme extension

    This endpoint is called by the Phoenix extension to track user interactions
    in the cart flow (recommendations, clicks, etc.).
    """
    try:
        logger.info(f"Phoenix interaction tracking: {request.interaction_type}")

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
            "extension_type": "phoenix",
        }

        # Track the interaction
        interaction = await analytics_service.track_interaction(
            session_id=request.session_id,
            extension_type=ExtensionType.PHOENIX,
            interaction_type=request.interaction_type,
            shop_id=shop_id,
            customer_id=request.customer_id,
            metadata=enhanced_metadata,
        )

        if not interaction:
            raise HTTPException(status_code=500, detail="Failed to track interaction")

        # Feature computation is now automatically triggered in track_interaction method

        logger.info(f"Phoenix interaction tracked successfully: {interaction.id}")

        return PhoenixResponse(
            success=True,
            message="Phoenix interaction tracked successfully",
            data={
                "interaction_id": interaction.id,
                "session_id": request.session_id,
                "interaction_type": request.interaction_type,
                "timestamp": interaction.created_at.isoformat(),
            },
        )

    except Exception as e:
        logger.error(f"Error tracking Phoenix interaction: {str(e)}", exc_info=True)
        logger.error(f"Request data: {request.dict()}")
        raise HTTPException(
            status_code=500, detail=f"Failed to track interaction: {str(e)}"
        )
