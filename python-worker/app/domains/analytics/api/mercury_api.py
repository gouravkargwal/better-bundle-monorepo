"""
Mercury Analytics API

Handles analytics tracking for Mercury extension (Shopify Plus Checkout Extensions).
Mercury runs on checkout pages and requires Shopify Plus plan.
"""

from typing import Optional, Dict, Any
import time
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

# Create router for Mercury Analytics API
router = APIRouter(prefix="/api/mercury", tags=["Mercury Analytics"])

# Initialize services
session_service = UnifiedSessionService()
analytics_service = AnalyticsTrackingService()


class MercurySessionRequest(BaseModel):
    """Request model for Mercury session creation"""

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
    checkout_step: Optional[str] = Field(None, description="Current checkout step")
    cart_value: Optional[float] = Field(None, description="Total cart value")
    cart_items: Optional[list[str]] = Field(None, description="Product IDs in cart")


class MercuryInteractionRequest(BaseModel):
    """Request model for Mercury interaction tracking"""

    session_id: str = Field(..., description="Session identifier")
    shop_domain: str = Field(..., description="Shop domain")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    interaction_type: str = Field(..., description="Type of interaction")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata"
    )
    checkout_step: Optional[str] = Field(None, description="Current checkout step")
    cart_value: Optional[float] = Field(None, description="Cart value at interaction")
    product_id: Optional[str] = Field(None, description="Product ID if applicable")


class MercuryResponse(BaseModel):
    """Base response model for Mercury API"""

    success: bool
    message: str
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")
    # Session recovery information
    session_recovery: Optional[Dict[str, Any]] = Field(
        None, description="Session recovery details"
    )


async def validate_shopify_plus_store(shop_domain: str) -> bool:
    """
    Validate if the store is on Shopify Plus plan.
    This is a critical requirement for Mercury checkout extensions.
    Uses database check for optimal performance.
    """
    try:
        from app.core.database.session import get_session_context

        logger.info(f"🔍 Mercury: Validating Shopify Plus for {shop_domain}")

        # Check database for Shopify Plus status (fastest approach)
        async with get_session_context() as session:
            from sqlalchemy import select
            from app.core.database.models import Shop

            result = await session.execute(
                select(Shop.shopify_plus, Shop.plan_type)
                .where(Shop.shop_domain == shop_domain)
                .where(Shop.is_active == True)
            )
            shop_data = result.fetchone()

            if not shop_data:
                logger.warning(f"⚠️ Mercury: Shop {shop_domain} not found or inactive")
                return False

            is_plus = shop_data.shopify_plus or False
            plan_type = shop_data.plan_type or ""

            if not is_plus:
                logger.warning(
                    f"⚠️ Mercury: Store {shop_domain} is not on Shopify Plus plan (plan: {plan_type})"
                )
                return False

            logger.info(
                f"✅ Mercury: Store {shop_domain} validated as Shopify Plus (plan: {plan_type})"
            )
            return True

    except Exception as e:
        logger.error(
            f"❌ Mercury: Failed to validate Shopify Plus for {shop_domain}: {e}"
        )
        return False


@router.post("/get-or-create-session", response_model=MercuryResponse)
async def get_or_create_mercury_session(request: MercurySessionRequest):
    """
    Get or create unified session for Mercury extension

    Mercury runs on checkout pages where we have access to customer_id,
    but also supports anonymous sessions. Requires Shopify Plus plan.
    """
    try:
        # Validate Shopify Plus status first
        is_shopify_plus = await validate_shopify_plus_store(request.shop_domain)

        if not is_shopify_plus:
            logger.warning(
                f"⚠️ Mercury: Store {request.shop_domain} is not Shopify Plus - Mercury disabled"
            )
            return MercuryResponse(
                success=False,
                message="Mercury requires Shopify Plus plan",
                data={
                    "reason": "Shopify Plus required",
                    "shop_domain": request.shop_domain,
                    "mercury_enabled": False,
                },
            )

        shop_id = await shop_resolver.get_shop_id_from_domain(request.shop_domain)
        if not shop_id:
            raise HTTPException(status_code=404, detail="Shop not found")

        # Generate a browser session ID for Mercury if not provided
        browser_session_id = (
            request.browser_session_id
            or f"mercury_{request.customer_id}_{int(time.time())}"
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

        # Add Mercury to extensions used
        await session_service.add_extension_to_session(
            session.id, ExtensionType.MERCURY
        )

        if not session:
            raise HTTPException(status_code=500, detail="Failed to create session")

        return MercuryResponse(
            success=True,
            message="Mercury session started successfully",
            data={
                "session_id": session.id,
                "browser_session_id": session.browser_session_id,
                "client_id": session.client_id,
                "created_at": session.created_at.isoformat(),
                "expires_at": (
                    session.expires_at.isoformat() if session.expires_at else None
                ),
                "checkout_step": request.checkout_step,
                "cart_value": request.cart_value,
                "cart_items": request.cart_items,
                "mercury_enabled": True,
            },
        )

    except Exception as e:
        logger.error(f"Error starting Mercury session: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to start session: {str(e)}"
        )


@router.post("/track-interaction", response_model=MercuryResponse)
async def track_mercury_interaction(request: MercuryInteractionRequest):
    """
    Track user interaction from Mercury extension

    Mercury can track:
    - Recommendation views and clicks
    - Add to cart actions
    - Checkout step interactions
    - Product interactions during checkout
    - Cart value changes
    """
    try:
        # Add extension type to metadata
        enhanced_metadata = {
            **request.metadata,
            "extension_type": "mercury",
            "checkout_step": request.checkout_step,
            "cart_value": request.cart_value,
            "product_id": request.product_id,
        }

        # Resolve shop_id from domain
        shop_id = await shop_resolver.get_shop_id_from_domain(request.shop_domain)

        if not shop_id:
            raise HTTPException(status_code=404, detail="Shop not found")

        # Try to track interaction with the original session
        interaction = await analytics_service.track_interaction(
            session_id=request.session_id,
            extension_type=ExtensionType.MERCURY,
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
                        extension_type=ExtensionType.MERCURY,
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
                        extension_type=ExtensionType.MERCURY,
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

        return MercuryResponse(
            success=True,
            message="Mercury interaction tracked successfully",
            data={
                "interaction_id": interaction.id,
                "session_id": interaction.session_id,  # This will be the recovered session ID
                "interaction_type": request.interaction_type,
                "checkout_step": request.checkout_step,
                "cart_value": request.cart_value,
                "timestamp": interaction.created_at.isoformat(),
            },
            session_recovery=session_recovery_info,  # Frontend gets recovery info
        )

    except Exception as e:
        logger.error(f"Error tracking Mercury interaction: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to track interaction: {str(e)}"
        )
