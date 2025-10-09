"""
Apollo API - Post-Purchase Extensions

This API handles interactions from the Apollo Post-Purchase extension.
Apollo can show recommendations and track interactions after purchase completion.
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
from app.recommandations.models import RecommendationRequest
from app.api.v1.recommendations import (
    fetch_recommendations_logic,
    services as recommendation_services,
)

logger = get_logger(__name__)

# Create router for Apollo API
router = APIRouter(prefix="/api/apollo", tags=["Apollo - Post-Purchase"])

# Initialize services
analytics_service = AnalyticsTrackingService()
session_service = UnifiedSessionService()


class ApolloCombinedRequest(BaseModel):
    """Request model for Apollo combined session + recommendations"""

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

    # Recommendation parameters
    order_id: Optional[str] = Field(
        None, description="Order ID for post-purchase context"
    )
    purchased_products: Optional[list] = Field(
        None, description="List of purchased products"
    )
    limit: int = Field(default=3, ge=1, le=10, description="Number of recommendations")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata"
    )


class ApolloCombinedResponse(BaseModel):
    """Response model for Apollo combined session + recommendations"""

    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    session_data: Optional[Dict[str, Any]] = Field(
        None, description="Session information"
    )
    recommendations: Optional[list] = Field(None, description="Product recommendations")
    recommendation_count: int = Field(
        default=0, description="Number of recommendations returned"
    )


@router.post("/get-session-and-recommendations", response_model=ApolloCombinedResponse)
async def get_session_and_recommendations(request: ApolloCombinedRequest):
    """
    Get or create session and fetch recommendations in a single API call

    This optimized endpoint combines session creation and recommendation retrieval
    to minimize API calls and improve performance for Apollo post-purchase extension.
    """
    try:
        logger.info(
            f"Apollo combined request: session + recommendations for customer {request.customer_id}"
        )

        # Step 1: Resolve shop domain to shop ID
        shop_id = await shop_resolver.get_shop_id_from_domain(request.shop_domain)
        if not shop_id:
            raise HTTPException(
                status_code=400,
                detail=f"Could not resolve shop ID for domain: {request.shop_domain}",
            )

        # Step 2: Get or create unified session
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

        logger.info(f"Apollo session created: {session.id}")

        # --- MODIFICATION: Call the reusable recommendation logic ---
        # Step 3: Get recommendations using the session
        recommendations = []
        recommendation_count = 0

        # 3.1. Create a RecommendationRequest object from the Apollo request
        rec_request = RecommendationRequest(
            shop_domain=request.shop_domain,
            user_id=request.customer_id,
            context="post_purchase",  # Hardcode the context for this endpoint
            product_ids=request.purchased_products,  # Use purchased products for context
            limit=request.limit,
            session_id=session.id,  # Link to the session we just created
            metadata=request.metadata,
        )

        # 3.2. Call the reusable logic function
        result_data = await fetch_recommendations_logic(
            request=rec_request, services=recommendation_services
        )

        # 3.3. Extract the results
        recommendations = result_data.get("recommendations", [])
        recommendation_count = result_data.get("count", 0)
        recommendation_source = result_data.get("source", "unknown")
        logger.info(
            f"✅ Successfully fetched {recommendation_count} recommendations for Apollo session {session.id}"
        )

        # Step 4: Track the initial post-purchase view interaction
        try:
            await analytics_service.track_interaction(
                session_id=session.id,
                extension_type=ExtensionType.APOLLO,
                interaction_type=InteractionType.RECOMMENDATION_READY,
                shop_id=shop_id,
                customer_id=request.customer_id,
                interaction_metadata={
                    "extension_type": "apollo",
                    "order_id": request.order_id,
                    "recommendation_count": recommendation_count,
                    "source": "apollo_post_purchase",
                    "context": "post_purchase",
                },
            )
        except Exception as track_error:
            logger.error(f"Error tracking initial interaction: {str(track_error)}")
            # Don't fail the request if tracking fails

        return ApolloCombinedResponse(
            success=True,
            message="Apollo session and recommendations retrieved successfully",
            session_data={
                "session_id": session.id,
                "customer_id": session.customer_id,
                "client_id": session.client_id,
                "created_at": session.created_at.isoformat(),
                "expires_at": (
                    session.expires_at.isoformat() if session.expires_at else None
                ),
            },
            recommendations=recommendations,
            recommendation_count=recommendation_count,
        )

    except Exception as e:
        logger.error(f"Error in Apollo combined request: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get session and recommendations: {str(e)}",
        )
