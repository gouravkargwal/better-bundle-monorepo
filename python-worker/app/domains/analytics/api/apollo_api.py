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

logger = get_logger(__name__)

# Create router for Apollo API
router = APIRouter(prefix="/api/apollo", tags=["Apollo - Post-Purchase"])

# Initialize services
analytics_service = AnalyticsTrackingService()
session_service = UnifiedSessionService()


class ApolloSessionRequest(BaseModel):
    """Request model for Apollo session creation"""

    shop_id: str = Field(..., description="Shop identifier")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    browser_session_id: Optional[str] = Field(
        None, description="Browser session identifier"
    )
    client_id: Optional[str] = Field(
        None, description="Shopify client ID (optional)"
    )  # ✅ NEW (optional for Apollo)
    user_agent: Optional[str] = Field(None, description="User agent string")
    ip_address: Optional[str] = Field(None, description="IP address")
    referrer: Optional[str] = Field(None, description="Referrer URL")
    page_url: Optional[str] = Field(None, description="Current page URL")


class ApolloInteractionRequest(BaseModel):
    """Request model for Apollo interactions"""

    session_id: str = Field(..., description="Session identifier")
    shop_id: str = Field(..., description="Shop identifier")
    interaction_type: InteractionType = Field(..., description="Type of interaction")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Raw interaction data as JSON"
    )


class ApolloRecommendationRequest(BaseModel):
    """Request model for Apollo recommendations"""

    session_id: str = Field(..., description="Session identifier")
    shop_id: str = Field(..., description="Shop identifier")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    order_id: str = Field(..., description="Order identifier")

    # Order context
    order_total: float = Field(..., description="Total order value")
    order_currency: str = Field(..., description="Order currency")
    purchased_products: list[Dict[str, Any]] = Field(
        ..., description="Products in the order"
    )

    # Recommendation details
    recommendation_type: str = Field(..., description="Type of recommendation")
    algorithm: str = Field(..., description="Algorithm used for recommendation")
    max_recommendations: int = Field(
        default=5, description="Maximum number of recommendations"
    )

    # Customer context
    customer_segment: Optional[str] = Field(None, description="Customer segment")
    customer_lifetime_value: Optional[float] = Field(
        None, description="Customer lifetime value"
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
        # Get or create unified session
        session = await session_service.get_or_create_session(
            shop_id=request.shop_id,
            customer_id=request.customer_id,
            browser_session_id=request.browser_session_id,
            client_id=request.client_id,  # ✅ NEW
            user_agent=request.user_agent,
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
                "client_id": session.client_id,  # ✅ NEW
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
            shop_id=request.shop_id,
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


@router.post("/track-post-purchase-view", response_model=ApolloResponse)
async def track_apollo_post_purchase_view(
    session_id: str,
    shop_id: str,
    order_id: str,
    customer_id: Optional[str] = None,
    order_total: Optional[float] = None,
    order_currency: Optional[str] = None,
    page_type: str = "thank_you_page",
):
    """
    Track post-purchase page view from Apollo

    This endpoint tracks when users view the post-purchase page.
    """
    try:
        logger.info(f"Apollo post-purchase view tracking: {order_id}")

        # Track post-purchase view interaction
        interaction = await analytics_service.track_interaction(
            session_id=session_id,
            extension_type=ExtensionType.APOLLO,
            context=ExtensionContext.POST_PURCHASE,
            interaction_type=InteractionType.POST_PURCHASE_VIEW,
            customer_id=customer_id,
            shop_id=shop_id,
            order_id=order_id,
            interaction_metadata={
                "order_total": order_total,
                "order_currency": order_currency,
                "page_type": page_type,
                "source": "apollo_post_purchase",
            },
        )

        logger.info(f"Apollo post-purchase view tracked: {interaction.id}")

        return ApolloResponse(
            success=True,
            message="Apollo post-purchase view tracked successfully",
            data={
                "interaction_id": interaction.id,
                "context": ExtensionContext.POST_PURCHASE,
                "order_id": order_id,
                "page_type": page_type,
            },
        )

    except Exception as e:
        logger.error(f"Error tracking Apollo post-purchase view: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to track post-purchase view: {str(e)}"
        )


@router.post("/track-recommendation-view", response_model=ApolloResponse)
async def track_apollo_recommendation_view(
    session_id: str,
    shop_id: str,
    order_id: str,
    recommendation_id: str,
    recommendation_position: int,
    recommendation_algorithm: str,
    customer_id: Optional[str] = None,
    recommendation_type: Optional[str] = None,
):
    """
    Track recommendation view from Apollo Post-Purchase

    This endpoint tracks when users view recommendations in the post-purchase flow.
    """
    try:
        logger.info(f"Apollo recommendation view tracking: {recommendation_id}")

        # Track recommendation view interaction
        interaction = await analytics_service.track_interaction(
            session_id=session_id,
            extension_type=ExtensionType.APOLLO,
            context=ExtensionContext.POST_PURCHASE,
            interaction_type=InteractionType.RECOMMENDATION_VIEW,
            customer_id=customer_id,
            shop_id=shop_id,
            order_id=order_id,
            recommendation_id=recommendation_id,
            recommendation_position=recommendation_position,
            recommendation_algorithm=recommendation_algorithm,
            interaction_metadata={
                "recommendation_type": recommendation_type,
                "source": "apollo_post_purchase",
            },
        )

        logger.info(f"Apollo recommendation view tracked: {interaction.id}")

        return ApolloResponse(
            success=True,
            message="Apollo recommendation view tracked successfully",
            data={
                "interaction_id": interaction.id,
                "recommendation_id": recommendation_id,
                "position": recommendation_position,
                "context": ExtensionContext.POST_PURCHASE,
            },
        )

    except Exception as e:
        logger.error(f"Error tracking Apollo recommendation view: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to track recommendation view: {str(e)}"
        )


@router.post("/track-recommendation-click", response_model=ApolloResponse)
async def track_apollo_recommendation_click(
    session_id: str,
    shop_id: str,
    order_id: str,
    recommendation_id: str,
    product_id: str,
    recommendation_position: int,
    recommendation_algorithm: str,
    customer_id: Optional[str] = None,
    recommendation_type: Optional[str] = None,
):
    """
    Track recommendation click from Apollo Post-Purchase

    This endpoint tracks when users click on recommendations in the post-purchase flow.
    """
    try:
        logger.info(
            f"Apollo recommendation click tracking: {recommendation_id} -> {product_id}"
        )

        # Track recommendation click interaction
        interaction = await analytics_service.track_interaction(
            session_id=session_id,
            extension_type=ExtensionType.APOLLO,
            context=ExtensionContext.POST_PURCHASE,
            interaction_type=InteractionType.RECOMMENDATION_CLICK,
            customer_id=customer_id,
            shop_id=shop_id,
            product_id=product_id,
            order_id=order_id,
            recommendation_id=recommendation_id,
            recommendation_position=recommendation_position,
            recommendation_algorithm=recommendation_algorithm,
            interaction_metadata={
                "recommendation_type": recommendation_type,
                "source": "apollo_post_purchase",
            },
        )

        logger.info(f"Apollo recommendation click tracked: {interaction.id}")

        return ApolloResponse(
            success=True,
            message="Apollo recommendation click tracked successfully",
            data={
                "interaction_id": interaction.id,
                "recommendation_id": recommendation_id,
                "product_id": product_id,
                "position": recommendation_position,
                "context": ExtensionContext.POST_PURCHASE,
            },
        )

    except Exception as e:
        logger.error(f"Error tracking Apollo recommendation click: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to track recommendation click: {str(e)}"
        )


@router.post("/track-upsell-purchase", response_model=ApolloResponse)
async def track_apollo_upsell_purchase(
    session_id: str,
    shop_id: str,
    order_id: str,
    product_id: str,
    quantity: int,
    value: float,
    recommendation_id: Optional[str] = None,
    recommendation_position: Optional[int] = None,
    recommendation_algorithm: Optional[str] = None,
    customer_id: Optional[str] = None,
    upsell_type: str = "post_purchase",
):
    """
    Track upsell purchase from Apollo Post-Purchase

    This endpoint tracks when users purchase additional items from post-purchase recommendations.
    """
    try:
        logger.info(f"Apollo upsell purchase tracking: {product_id} (value: {value})")

        # Track upsell purchase interaction
        interaction = await analytics_service.track_interaction(
            session_id=session_id,
            extension_type=ExtensionType.APOLLO,
            context=ExtensionContext.POST_PURCHASE,
            interaction_type=InteractionType.RECOMMENDATION_PURCHASE,
            customer_id=customer_id,
            shop_id=shop_id,
            product_id=product_id,
            order_id=order_id,
            quantity=quantity,
            value=value,
            recommendation_id=recommendation_id,
            recommendation_position=recommendation_position,
            recommendation_algorithm=recommendation_algorithm,
            interaction_metadata={
                "upsell_type": upsell_type,
                "source": "apollo_post_purchase",
            },
        )

        logger.info(f"Apollo upsell purchase tracked: {interaction.id}")

        return ApolloResponse(
            success=True,
            message="Apollo upsell purchase tracked successfully",
            data={
                "interaction_id": interaction.id,
                "product_id": product_id,
                "quantity": quantity,
                "value": value,
                "recommendation_id": recommendation_id,
                "upsell_type": upsell_type,
            },
        )

    except Exception as e:
        logger.error(f"Error tracking Apollo upsell purchase: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to track upsell purchase: {str(e)}"
        )


@router.post("/get-recommendations", response_model=ApolloResponse)
async def get_apollo_recommendations(request: ApolloRecommendationRequest):
    """
    Get recommendations for Apollo Post-Purchase

    This endpoint provides product recommendations for the post-purchase flow.
    """
    try:
        logger.info(
            f"Apollo recommendations request: {request.recommendation_type} for order {request.order_id}"
        )

        # For now, return mock recommendations based on order context
        # In a real implementation, you would call your recommendation engine

        # Generate mock recommendations based on purchased products
        mock_recommendations = []
        for i, product in enumerate(
            request.purchased_products[: request.max_recommendations]
        ):
            mock_recommendations.append(
                {
                    "product_id": f"recommended_{product.get('id', f'product_{i}')}",
                    "title": f"Recommended for {product.get('title', 'your purchase')}",
                    "price": request.order_total * 0.3,  # 30% of order value
                    "position": i + 1,
                    "reason": "Frequently bought together",
                }
            )

        recommendations = {
            "recommendation_id": f"apollo_{request.session_id}_{request.recommendation_type}",
            "recommendation_type": request.recommendation_type,
            "algorithm": request.algorithm,
            "products": mock_recommendations,
            "context": ExtensionContext.POST_PURCHASE,
            "session_id": request.session_id,
            "order_id": request.order_id,
            "order_total": request.order_total,
            "order_currency": request.order_currency,
        }

        logger.info(
            f"Apollo recommendations provided: {len(mock_recommendations)} products"
        )

        return ApolloResponse(
            success=True,
            message="Apollo recommendations retrieved successfully",
            data=recommendations,
        )

    except Exception as e:
        logger.error(f"Error getting Apollo recommendations: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get recommendations: {str(e)}"
        )


@router.post("/track-customer-feedback", response_model=ApolloResponse)
async def track_apollo_customer_feedback(
    session_id: str,
    shop_id: str,
    order_id: str,
    feedback_type: str,
    feedback_value: str,
    customer_id: Optional[str] = None,
    product_id: Optional[str] = None,
    rating: Optional[int] = None,
):
    """
    Track customer feedback from Apollo Post-Purchase

    This endpoint tracks customer feedback, ratings, and reviews.
    """
    try:
        logger.info(
            f"Apollo customer feedback tracking: {feedback_type} = {feedback_value}"
        )

        # Track customer feedback interaction
        interaction = await analytics_service.track_interaction(
            session_id=session_id,
            extension_type=ExtensionType.APOLLO,
            context=ExtensionContext.POST_PURCHASE,
            interaction_type=InteractionType.CUSTOM_EVENT,
            customer_id=customer_id,
            shop_id=shop_id,
            product_id=product_id,
            order_id=order_id,
            interaction_metadata={
                "feedback_type": feedback_type,
                "feedback_value": feedback_value,
                "rating": rating,
                "source": "apollo_post_purchase",
            },
        )

        logger.info(f"Apollo customer feedback tracked: {interaction.id}")

        return ApolloResponse(
            success=True,
            message="Apollo customer feedback tracked successfully",
            data={
                "interaction_id": interaction.id,
                "feedback_type": feedback_type,
                "feedback_value": feedback_value,
                "rating": rating,
                "context": ExtensionContext.POST_PURCHASE,
            },
        )

    except Exception as e:
        logger.error(f"Error tracking Apollo customer feedback: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to track customer feedback: {str(e)}"
        )


@router.post("/track-email-signup", response_model=ApolloResponse)
async def track_apollo_email_signup(
    session_id: str,
    shop_id: str,
    order_id: str,
    email: str,
    customer_id: Optional[str] = None,
    signup_type: str = "newsletter",
):
    """
    Track email signup from Apollo Post-Purchase

    This endpoint tracks when customers sign up for newsletters or updates.
    """
    try:

        # Track email signup interaction
        interaction = await analytics_service.track_interaction(
            session_id=session_id,
            extension_type=ExtensionType.APOLLO,
            context=ExtensionContext.POST_PURCHASE,
            interaction_type=InteractionType.CUSTOM_EVENT,
            customer_id=customer_id,
            shop_id=shop_id,
            order_id=order_id,
            interaction_metadata={
                "email": email,
                "signup_type": signup_type,
                "source": "apollo_post_purchase",
            },
        )

        return ApolloResponse(
            success=True,
            message="Apollo email signup tracked successfully",
            data={
                "interaction_id": interaction.id,
                "email": email,
                "signup_type": signup_type,
                "context": ExtensionContext.POST_PURCHASE,
            },
        )

    except Exception as e:
        logger.error(f"Error tracking Apollo email signup: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to track email signup: {str(e)}"
        )
