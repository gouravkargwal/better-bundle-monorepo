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

logger = get_logger(__name__)

# Create router for Phoenix API
router = APIRouter(prefix="/api/phoenix", tags=["Phoenix - Checkout UI"])

# Initialize services
analytics_service = AnalyticsTrackingService()
session_service = UnifiedSessionService()


class PhoenixInteractionRequest(BaseModel):
    """Request model for Phoenix interactions"""

    session_id: str = Field(..., description="Session identifier")
    shop_id: str = Field(..., description="Shop identifier")
    context: ExtensionContext = Field(
        ..., description="Context where interaction occurred"
    )
    interaction_type: InteractionType = Field(..., description="Type of interaction")

    # Optional user info
    customer_id: Optional[str] = Field(
        None, description="Customer identifier (if known)"
    )

    # Interaction details
    product_id: Optional[str] = Field(
        None, description="Product involved in interaction"
    )
    quantity: Optional[int] = Field(None, description="Quantity involved")
    value: Optional[float] = Field(None, description="Monetary value of interaction")

    # Recommendation specific
    recommendation_id: Optional[str] = Field(
        None, description="Recommendation identifier"
    )
    recommendation_position: Optional[int] = Field(
        None, description="Position of recommendation"
    )
    recommendation_algorithm: Optional[str] = Field(
        None, description="Algorithm used for recommendation"
    )

    # Checkout specific
    checkout_id: Optional[str] = Field(None, description="Checkout identifier")
    line_item_id: Optional[str] = Field(None, description="Line item identifier")

    # Metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional interaction metadata"
    )


class PhoenixRecommendationRequest(BaseModel):
    """Request model for Phoenix recommendations"""

    session_id: str = Field(..., description="Session identifier")
    shop_id: str = Field(..., description="Shop identifier")
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


@router.post("/track-interaction", response_model=PhoenixResponse)
async def track_phoenix_interaction(request: PhoenixInteractionRequest):
    """
    Track user interaction from Phoenix Checkout UI extension

    This endpoint is called by the Phoenix extension to track user interactions
    in the checkout flow (cart view, recommendations, etc.).
    """
    try:
        logger.info(
            f"Phoenix interaction tracking: {request.interaction_type} in {request.context}"
        )

        # Track the interaction
        interaction = await analytics_service.track_interaction(
            session_id=request.session_id,
            extension_type=ExtensionType.PHOENIX,
            context=request.context,
            interaction_type=request.interaction_type,
            customer_id=request.customer_id,
            shop_id=request.shop_id,
            product_id=request.product_id,
            quantity=request.quantity,
            value=request.value,
            recommendation_id=request.recommendation_id,
            recommendation_position=request.recommendation_position,
            recommendation_algorithm=request.recommendation_algorithm,
            metadata={
                **request.metadata,
                "checkout_id": request.checkout_id,
                "line_item_id": request.line_item_id,
                "source": "phoenix_checkout_ui",
            },
        )

        logger.info(f"Phoenix interaction tracked successfully: {interaction.id}")

        return PhoenixResponse(
            success=True,
            message="Phoenix interaction tracked successfully",
            data={
                "interaction_id": interaction.id,
                "session_id": request.session_id,
                "interaction_type": request.interaction_type,
                "context": request.context,
            },
        )

    except Exception as e:
        logger.error(f"Error tracking Phoenix interaction: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to track interaction: {str(e)}"
        )


@router.post("/track-cart-view", response_model=PhoenixResponse)
async def track_phoenix_cart_view(
    session_id: str,
    shop_id: str,
    checkout_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    cart_total: Optional[float] = None,
    item_count: Optional[int] = None,
):
    """
    Track cart view from Phoenix Checkout UI

    This endpoint tracks when users view their cart in the checkout flow.
    """
    try:
        logger.info(f"Phoenix cart view tracking for session: {session_id}")

        # Track cart view interaction
        interaction = await analytics_service.track_interaction(
            session_id=session_id,
            extension_type=ExtensionType.PHOENIX,
            context=ExtensionContext.CART_PAGE,
            interaction_type=InteractionType.CART_VIEW,
            customer_id=customer_id,
            shop_id=shop_id,
            metadata={
                "checkout_id": checkout_id,
                "cart_total": cart_total,
                "item_count": item_count,
                "source": "phoenix_checkout_ui",
            },
        )

        logger.info(f"Phoenix cart view tracked: {interaction.id}")

        return PhoenixResponse(
            success=True,
            message="Phoenix cart view tracked successfully",
            data={
                "interaction_id": interaction.id,
                "context": ExtensionContext.CART_PAGE,
                "checkout_id": checkout_id,
            },
        )

    except Exception as e:
        logger.error(f"Error tracking Phoenix cart view: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to track cart view: {str(e)}"
        )


@router.post("/track-recommendation-view", response_model=PhoenixResponse)
async def track_phoenix_recommendation_view(
    session_id: str,
    shop_id: str,
    recommendation_id: str,
    recommendation_position: int,
    recommendation_algorithm: str,
    customer_id: Optional[str] = None,
    checkout_id: Optional[str] = None,
    context: ExtensionContext = ExtensionContext.CART_PAGE,
):
    """
    Track recommendation view from Phoenix Checkout UI

    This endpoint tracks when users view recommendations in the checkout flow.
    """
    try:
        logger.info(f"Phoenix recommendation view tracking: {recommendation_id}")

        # Track recommendation view interaction
        interaction = await analytics_service.track_interaction(
            session_id=session_id,
            extension_type=ExtensionType.PHOENIX,
            context=context,
            interaction_type=InteractionType.RECOMMENDATION_VIEW,
            customer_id=customer_id,
            shop_id=shop_id,
            recommendation_id=recommendation_id,
            recommendation_position=recommendation_position,
            recommendation_algorithm=recommendation_algorithm,
            metadata={"checkout_id": checkout_id, "source": "phoenix_checkout_ui"},
        )

        logger.info(f"Phoenix recommendation view tracked: {interaction.id}")

        return PhoenixResponse(
            success=True,
            message="Phoenix recommendation view tracked successfully",
            data={
                "interaction_id": interaction.id,
                "recommendation_id": recommendation_id,
                "position": recommendation_position,
                "context": context,
            },
        )

    except Exception as e:
        logger.error(f"Error tracking Phoenix recommendation view: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to track recommendation view: {str(e)}"
        )


@router.post("/track-recommendation-click", response_model=PhoenixResponse)
async def track_phoenix_recommendation_click(
    session_id: str,
    shop_id: str,
    recommendation_id: str,
    product_id: str,
    recommendation_position: int,
    recommendation_algorithm: str,
    customer_id: Optional[str] = None,
    checkout_id: Optional[str] = None,
    context: ExtensionContext = ExtensionContext.CART_PAGE,
):
    """
    Track recommendation click from Phoenix Checkout UI

    This endpoint tracks when users click on recommendations in the checkout flow.
    """
    try:
        logger.info(
            f"Phoenix recommendation click tracking: {recommendation_id} -> {product_id}"
        )

        # Track recommendation click interaction
        interaction = await analytics_service.track_interaction(
            session_id=session_id,
            extension_type=ExtensionType.PHOENIX,
            context=context,
            interaction_type=InteractionType.RECOMMENDATION_CLICK,
            customer_id=customer_id,
            shop_id=shop_id,
            product_id=product_id,
            recommendation_id=recommendation_id,
            recommendation_position=recommendation_position,
            recommendation_algorithm=recommendation_algorithm,
            metadata={"checkout_id": checkout_id, "source": "phoenix_checkout_ui"},
        )

        logger.info(f"Phoenix recommendation click tracked: {interaction.id}")

        return PhoenixResponse(
            success=True,
            message="Phoenix recommendation click tracked successfully",
            data={
                "interaction_id": interaction.id,
                "recommendation_id": recommendation_id,
                "product_id": product_id,
                "position": recommendation_position,
                "context": context,
            },
        )

    except Exception as e:
        logger.error(f"Error tracking Phoenix recommendation click: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to track recommendation click: {str(e)}"
        )


@router.post("/track-add-to-cart", response_model=PhoenixResponse)
async def track_phoenix_add_to_cart(
    session_id: str,
    shop_id: str,
    product_id: str,
    quantity: int,
    value: float,
    recommendation_id: Optional[str] = None,
    recommendation_position: Optional[int] = None,
    recommendation_algorithm: Optional[str] = None,
    customer_id: Optional[str] = None,
    checkout_id: Optional[str] = None,
    line_item_id: Optional[str] = None,
    context: ExtensionContext = ExtensionContext.CART_PAGE,
):
    """
    Track add to cart from Phoenix Checkout UI

    This endpoint tracks when users add items to cart from recommendations.
    """
    try:
        logger.info(f"Phoenix add to cart tracking: {product_id} (qty: {quantity})")

        # Track add to cart interaction
        interaction = await analytics_service.track_interaction(
            session_id=session_id,
            extension_type=ExtensionType.PHOENIX,
            context=context,
            interaction_type=InteractionType.RECOMMENDATION_ADD_TO_CART,
            customer_id=customer_id,
            shop_id=shop_id,
            product_id=product_id,
            quantity=quantity,
            value=value,
            recommendation_id=recommendation_id,
            recommendation_position=recommendation_position,
            recommendation_algorithm=recommendation_algorithm,
            metadata={
                "checkout_id": checkout_id,
                "line_item_id": line_item_id,
                "source": "phoenix_checkout_ui",
            },
        )

        logger.info(f"Phoenix add to cart tracked: {interaction.id}")

        return PhoenixResponse(
            success=True,
            message="Phoenix add to cart tracked successfully",
            data={
                "interaction_id": interaction.id,
                "product_id": product_id,
                "quantity": quantity,
                "value": value,
                "recommendation_id": recommendation_id,
                "context": context,
            },
        )

    except Exception as e:
        logger.error(f"Error tracking Phoenix add to cart: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to track add to cart: {str(e)}"
        )


@router.post("/track-cart-update", response_model=PhoenixResponse)
async def track_phoenix_cart_update(
    session_id: str,
    shop_id: str,
    checkout_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    cart_total: Optional[float] = None,
    item_count: Optional[int] = None,
    updated_items: Optional[list[Dict[str, Any]]] = None,
):
    """
    Track cart update from Phoenix Checkout UI

    This endpoint tracks when users update their cart (quantity changes, removals, etc.).
    """
    try:
        logger.info(f"Phoenix cart update tracking for session: {session_id}")

        # Track cart update interaction
        interaction = await analytics_service.track_interaction(
            session_id=session_id,
            extension_type=ExtensionType.PHOENIX,
            context=ExtensionContext.CART_PAGE,
            interaction_type=InteractionType.CART_UPDATE,
            customer_id=customer_id,
            shop_id=shop_id,
            metadata={
                "checkout_id": checkout_id,
                "cart_total": cart_total,
                "item_count": item_count,
                "updated_items": updated_items,
                "source": "phoenix_checkout_ui",
            },
        )

        logger.info(f"Phoenix cart update tracked: {interaction.id}")

        return PhoenixResponse(
            success=True,
            message="Phoenix cart update tracked successfully",
            data={
                "interaction_id": interaction.id,
                "context": ExtensionContext.CART_PAGE,
                "checkout_id": checkout_id,
            },
        )

    except Exception as e:
        logger.error(f"Error tracking Phoenix cart update: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to track cart update: {str(e)}"
        )


@router.post("/get-recommendations", response_model=PhoenixResponse)
async def get_phoenix_recommendations(request: PhoenixRecommendationRequest):
    """
    Get recommendations for Phoenix Checkout UI

    This endpoint provides product recommendations for the checkout flow.
    """
    try:
        logger.info(f"Phoenix recommendations request: {request.recommendation_type}")

        # For now, return the provided products as recommendations
        # In a real implementation, you would call your recommendation engine

        recommendations = {
            "recommendation_id": f"phoenix_{request.session_id}_{request.recommendation_type}",
            "recommendation_type": request.recommendation_type,
            "algorithm": request.algorithm,
            "products": request.products,
            "context": request.context,
            "session_id": request.session_id,
        }

        logger.info(
            f"Phoenix recommendations provided: {len(request.products)} products"
        )

        return PhoenixResponse(
            success=True,
            message="Phoenix recommendations retrieved successfully",
            data=recommendations,
        )

    except Exception as e:
        logger.error(f"Error getting Phoenix recommendations: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get recommendations: {str(e)}"
        )
