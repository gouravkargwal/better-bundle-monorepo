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
from app.domains.analytics.services.analytics_tracking_service import AnalyticsTrackingService
from app.core.logging.logger import get_logger

logger = get_logger(__name__)

# Create router for Venus API
router = APIRouter(prefix="/api/venus", tags=["Venus Analytics"])

# Initialize services
session_service = UnifiedSessionService()
analytics_service = AnalyticsTrackingService()


class VenusSessionRequest(BaseModel):
    """Request model for Venus session creation"""
    shop_id: str = Field(..., description="Shop identifier")
    customer_id: str = Field(..., description="Customer identifier")
    browser_session_id: Optional[str] = Field(None, description="Browser session identifier")
    user_agent: Optional[str] = Field(None, description="User agent string")
    ip_address: Optional[str] = Field(None, description="IP address")
    referrer: Optional[str] = Field(None, description="Referrer URL")


class VenusInteractionRequest(BaseModel):
    """Request model for Venus interaction tracking"""
    session_id: str = Field(..., description="Unified session identifier")
    context: ExtensionContext = Field(..., description="Context where interaction occurred")
    interaction_type: InteractionType = Field(..., description="Type of interaction")
    product_id: Optional[str] = Field(None, description="Product involved in interaction")
    order_id: Optional[str] = Field(None, description="Order involved in interaction")
    recommendation_id: Optional[str] = Field(None, description="Recommendation identifier")
    recommendation_position: Optional[int] = Field(None, description="Position of recommendation")
    recommendation_algorithm: Optional[str] = Field(None, description="Algorithm used for recommendation")
    value: Optional[float] = Field(None, description="Monetary value of interaction")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")


class VenusResponse(BaseModel):
    """Response model for Venus API"""
    success: bool = Field(..., description="Whether the operation was successful")
    message: str = Field(..., description="Response message")
    data: Optional[Dict[str, Any]] = Field(None, description="Response data")


@router.post("/start-session", response_model=VenusResponse)
async def start_venus_session(request: VenusSessionRequest):
    """
    Start or resume a unified session for Venus extension
    
    Venus runs on customer account pages where we have access to customer_id,
    so we can create customer-specific sessions.
    """
    try:
        # Get or create unified session
        session = await session_service.get_or_create_session(
            shop_id=request.shop_id,
            customer_id=request.customer_id,
            browser_session_id=request.browser_session_id,
            user_agent=request.user_agent,
            ip_address=request.ip_address,
            referrer=request.referrer
        )
        
        if not session:
            raise HTTPException(status_code=500, detail="Failed to create session")
        
        logger.info(f"Venus session started: {session.id} for customer {request.customer_id}")
        
        return VenusResponse(
            success=True,
            message="Venus session started successfully",
            data={
                "session_id": session.id,
                "customer_id": session.customer_id,
                "created_at": session.created_at.isoformat(),
                "expires_at": session.expires_at.isoformat() if session.expires_at else None
            }
        )
        
    except Exception as e:
        logger.error(f"Error starting Venus session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")


@router.post("/track-interaction", response_model=VenusResponse)
async def track_venus_interaction(request: VenusInteractionRequest):
    """
    Track user interaction from Venus extension
    
    Venus can track:
    - Profile views
    - Order views
    - Order status views
    - Recommendation clicks
    - Product interactions
    """
    try:
        # Validate context for Venus
        valid_contexts = [
            ExtensionContext.CUSTOMER_PROFILE,
            ExtensionContext.ORDER_STATUS,
            ExtensionContext.ORDER_INDEX
        ]
        
        if request.context not in valid_contexts:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid context for Venus: {request.context}"
            )
        
        # Track interaction
        interaction = await analytics_service.track_interaction(
            session_id=request.session_id,
            extension_type=ExtensionType.VENUS,
            context=request.context,
            interaction_type=request.interaction_type,
            shop_id="",  # Will be extracted from session
            customer_id=None,  # Will be extracted from session
            product_id=request.product_id,
            order_id=request.order_id,
            recommendation_id=request.recommendation_id,
            recommendation_position=request.recommendation_position,
            recommendation_algorithm=request.recommendation_algorithm,
            value=request.value,
            metadata=request.metadata
        )
        
        if not interaction:
            raise HTTPException(status_code=500, detail="Failed to track interaction")
        
        logger.info(f"Venus interaction tracked: {request.interaction_type} in {request.context}")
        
        return VenusResponse(
            success=True,
            message="Interaction tracked successfully",
            data={
                "interaction_id": interaction.id,
                "interaction_type": interaction.interaction_type,
                "context": interaction.context,
                "timestamp": interaction.created_at.isoformat()
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tracking Venus interaction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to track interaction: {str(e)}")


@router.get("/session/{session_id}/interactions", response_model=VenusResponse)
async def get_venus_session_interactions(session_id: str):
    """Get all interactions for a Venus session"""
    try:
        interactions = await analytics_service.get_session_interactions(session_id)
        
        # Filter for Venus interactions only
        venus_interactions = [
            i for i in interactions 
            if i.extension_type == ExtensionType.VENUS
        ]
        
        return VenusResponse(
            success=True,
            message="Venus interactions retrieved successfully",
            data={
                "session_id": session_id,
                "total_interactions": len(venus_interactions),
                "interactions": [
                    {
                        "id": i.id,
                        "interaction_type": i.interaction_type,
                        "context": i.context,
                        "product_id": i.product_id,
                        "order_id": i.order_id,
                        "timestamp": i.created_at.isoformat(),
                        "metadata": i.metadata
                    }
                    for i in venus_interactions
                ]
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting Venus session interactions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get interactions: {str(e)}")


@router.get("/customer/{customer_id}/interactions", response_model=VenusResponse)
async def get_venus_customer_interactions(customer_id: str, shop_id: str):
    """Get all Venus interactions for a specific customer"""
    try:
        interactions = await analytics_service.get_customer_interactions(
            customer_id=customer_id,
            shop_id=shop_id
        )
        
        # Filter for Venus interactions only
        venus_interactions = [
            i for i in interactions 
            if i.extension_type == ExtensionType.VENUS
        ]
        
        return VenusResponse(
            success=True,
            message="Customer Venus interactions retrieved successfully",
            data={
                "customer_id": customer_id,
                "shop_id": shop_id,
                "total_interactions": len(venus_interactions),
                "interactions": [
                    {
                        "id": i.id,
                        "interaction_type": i.interaction_type,
                        "context": i.context,
                        "product_id": i.product_id,
                        "order_id": i.order_id,
                        "timestamp": i.created_at.isoformat(),
                        "metadata": i.metadata
                    }
                    for i in venus_interactions
                ]
            }
        )
        
    except Exception as e:
        logger.error(f"Error getting customer Venus interactions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get customer interactions: {str(e)}")


@router.get("/performance", response_model=VenusResponse)
async def get_venus_performance(shop_id: str, days: int = 30):
    """Get Venus extension performance metrics"""
    try:
        performance = await analytics_service.get_extension_performance(
            extension_type=ExtensionType.VENUS,
            shop_id=shop_id,
            days=days
        )
        
        return VenusResponse(
            success=True,
            message="Venus performance metrics retrieved successfully",
            data=performance
        )
        
    except Exception as e:
        logger.error(f"Error getting Venus performance: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get performance metrics: {str(e)}")
