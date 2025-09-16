"""
Atlas API - Web Pixels Extension

This API handles behavioral tracking from the Atlas Web Pixels extension.
Atlas tracks user behavior across the entire store (except checkout).
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.domains.analytics.services.analytics_tracking_service import AnalyticsTrackingService
from app.domains.analytics.services.unified_session_service import UnifiedSessionService
from app.domains.analytics.models.extension import ExtensionType, ExtensionContext
from app.domains.analytics.models.interaction import InteractionType
from app.core.logging.logger import get_logger

logger = get_logger(__name__)

# Create router for Atlas API
router = APIRouter(prefix="/api/atlas", tags=["Atlas - Web Pixels"])

# Initialize services
analytics_service = AnalyticsTrackingService()
session_service = UnifiedSessionService()


class AtlasInteractionRequest(BaseModel):
    """Request model for Atlas interactions"""
    session_id: str = Field(..., description="Session identifier")
    shop_id: str = Field(..., description="Shop identifier")
    context: ExtensionContext = Field(..., description="Context where interaction occurred")
    interaction_type: InteractionType = Field(..., description="Type of interaction")
    
    # Optional user info
    customer_id: Optional[str] = Field(None, description="Customer identifier (if known)")
    
    # Interaction details
    product_id: Optional[str] = Field(None, description="Product involved in interaction")
    collection_id: Optional[str] = Field(None, description="Collection involved in interaction")
    search_query: Optional[str] = Field(None, description="Search query")
    
    # Behavioral data
    page_url: Optional[str] = Field(None, description="Page URL")
    referrer: Optional[str] = Field(None, description="Referrer URL")
    time_on_page: Optional[int] = Field(None, description="Time spent on page (seconds)")
    scroll_depth: Optional[float] = Field(None, description="Scroll depth percentage")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional interaction metadata")


class AtlasSessionRequest(BaseModel):
    """Request model for Atlas session management"""
    shop_id: str = Field(..., description="Shop identifier")
    customer_id: Optional[str] = Field(None, description="Customer identifier")
    browser_session_id: Optional[str] = Field(None, description="Browser session identifier")
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
        logger.info(f"Atlas interaction tracking: {request.interaction_type} in {request.context}")
        
        # Track the interaction
        interaction = await analytics_service.track_interaction(
            session_id=request.session_id,
            extension_type=ExtensionType.ATLAS,
            context=request.context,
            interaction_type=request.interaction_type,
            customer_id=request.customer_id,
            shop_id=request.shop_id,
            product_id=request.product_id,
            collection_id=request.collection_id,
            metadata={
                **request.metadata,
                "page_url": request.page_url,
                "referrer": request.referrer,
                "time_on_page": request.time_on_page,
                "scroll_depth": request.scroll_depth,
                "search_query": request.search_query,
                "source": "atlas_web_pixel"
            }
        )
        
        logger.info(f"Atlas interaction tracked successfully: {interaction.id}")
        
        return AtlasResponse(
            success=True,
            message="Atlas interaction tracked successfully",
            data={
                "interaction_id": interaction.id,
                "session_id": request.session_id,
                "interaction_type": request.interaction_type,
                "context": request.context
            }
        )
        
    except Exception as e:
        logger.error(f"Error tracking Atlas interaction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to track interaction: {str(e)}")


@router.post("/get-or-create-session", response_model=AtlasResponse)
async def get_or_create_atlas_session(request: AtlasSessionRequest):
    """
    Get or create session for Atlas tracking
    
    This endpoint is called when Atlas needs to establish or retrieve
    a session for behavioral tracking.
    """
    try:
        logger.info(f"Atlas session request for shop: {request.shop_id}")
        
        # Get or create session
        session = await session_service.get_or_create_session(
            shop_id=request.shop_id,
            customer_id=request.customer_id,
            browser_session_id=request.browser_session_id,
            user_agent=request.user_agent,
            ip_address=request.ip_address,
            referrer=request.referrer,
            metadata={
                "page_url": request.page_url,
                "source": "atlas_web_pixel"
            }
        )
        
        # Add Atlas to extensions used
        await session_service.add_extension_to_session(session.id, ExtensionType.ATLAS)
        
        logger.info(f"Atlas session created/retrieved: {session.id}")
        
        return AtlasResponse(
            success=True,
            message="Atlas session created/retrieved successfully",
            data={
                "session_id": session.id,
                "customer_id": session.customer_id,
                "browser_session_id": session.browser_session_id,
                "expires_at": session.expires_at.isoformat() if session.expires_at else None,
                "extensions_used": session.extensions_used
            }
        )
        
    except Exception as e:
        logger.error(f"Error creating Atlas session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@router.post("/track-page-view", response_model=AtlasResponse)
async def track_atlas_page_view(
    session_id: str,
    shop_id: str,
    page_url: str,
    page_title: Optional[str] = None,
    context: Optional[ExtensionContext] = None,
    customer_id: Optional[str] = None,
    time_on_page: Optional[int] = None,
    referrer: Optional[str] = None
):
    """
    Track page view from Atlas Web Pixels
    
    This is a convenience endpoint specifically for page view tracking.
    """
    try:
        logger.info(f"Atlas page view tracking: {page_url}")
        
        # Determine context from page URL if not provided
        if not context:
            if "/products/" in page_url:
                context = ExtensionContext.PRODUCT_PAGE
            elif "/collections/" in page_url:
                context = ExtensionContext.COLLECTION_PAGE
            elif "/cart" in page_url:
                context = ExtensionContext.CART_PAGE
            elif "/search" in page_url:
                context = ExtensionContext.SEARCH_PAGE
            elif "/account" in page_url:
                context = ExtensionContext.CUSTOMER_ACCOUNT
            else:
                context = ExtensionContext.HOMEPAGE
        
        # Track page view interaction
        interaction = await analytics_service.track_interaction(
            session_id=session_id,
            extension_type=ExtensionType.ATLAS,
            context=context,
            interaction_type=InteractionType.PAGE_VIEW,
            customer_id=customer_id,
            shop_id=shop_id,
            metadata={
                "page_url": page_url,
                "page_title": page_title,
                "time_on_page": time_on_page,
                "referrer": referrer,
                "source": "atlas_web_pixel"
            }
        )
        
        logger.info(f"Atlas page view tracked: {interaction.id}")
        
        return AtlasResponse(
            success=True,
            message="Atlas page view tracked successfully",
            data={
                "interaction_id": interaction.id,
                "context": context,
                "page_url": page_url
            }
        )
        
    except Exception as e:
        logger.error(f"Error tracking Atlas page view: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to track page view: {str(e)}")


@router.post("/track-product-view", response_model=AtlasResponse)
async def track_atlas_product_view(
    session_id: str,
    shop_id: str,
    product_id: str,
    product_title: Optional[str] = None,
    product_price: Optional[float] = None,
    product_variant_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    page_url: Optional[str] = None
):
    """
    Track product view from Atlas Web Pixels
    
    This endpoint tracks when users view product pages.
    """
    try:
        logger.info(f"Atlas product view tracking: {product_id}")
        
        # Track product view interaction
        interaction = await analytics_service.track_interaction(
            session_id=session_id,
            extension_type=ExtensionType.ATLAS,
            context=ExtensionContext.PRODUCT_PAGE,
            interaction_type=InteractionType.PRODUCT_VIEW,
            customer_id=customer_id,
            shop_id=shop_id,
            product_id=product_id,
            metadata={
                "product_title": product_title,
                "product_price": product_price,
                "product_variant_id": product_variant_id,
                "page_url": page_url,
                "source": "atlas_web_pixel"
            }
        )
        
        logger.info(f"Atlas product view tracked: {interaction.id}")
        
        return AtlasResponse(
            success=True,
            message="Atlas product view tracked successfully",
            data={
                "interaction_id": interaction.id,
                "product_id": product_id,
                "context": ExtensionContext.PRODUCT_PAGE
            }
        )
        
    except Exception as e:
        logger.error(f"Error tracking Atlas product view: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to track product view: {str(e)}")


@router.post("/track-search", response_model=AtlasResponse)
async def track_atlas_search(
    session_id: str,
    shop_id: str,
    search_query: str,
    results_count: Optional[int] = None,
    customer_id: Optional[str] = None,
    page_url: Optional[str] = None
):
    """
    Track search from Atlas Web Pixels
    
    This endpoint tracks when users perform searches.
    """
    try:
        logger.info(f"Atlas search tracking: {search_query}")
        
        # Track search interaction
        interaction = await analytics_service.track_interaction(
            session_id=session_id,
            extension_type=ExtensionType.ATLAS,
            context=ExtensionContext.SEARCH_PAGE,
            interaction_type=InteractionType.SEARCH,
            customer_id=customer_id,
            shop_id=shop_id,
            metadata={
                "search_query": search_query,
                "results_count": results_count,
                "page_url": page_url,
                "source": "atlas_web_pixel"
            }
        )
        
        logger.info(f"Atlas search tracked: {interaction.id}")
        
        return AtlasResponse(
            success=True,
            message="Atlas search tracked successfully",
            data={
                "interaction_id": interaction.id,
                "search_query": search_query,
                "context": ExtensionContext.SEARCH_PAGE
            }
        )
        
    except Exception as e:
        logger.error(f"Error tracking Atlas search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to track search: {str(e)}")


@router.post("/track-form-submission", response_model=AtlasResponse)
async def track_atlas_form_submission(
    session_id: str,
    shop_id: str,
    form_type: str,
    form_data: Optional[Dict[str, Any]] = None,
    customer_id: Optional[str] = None,
    page_url: Optional[str] = None
):
    """
    Track form submission from Atlas Web Pixels
    
    This endpoint tracks when users submit forms (newsletter, contact, etc.).
    """
    try:
        logger.info(f"Atlas form submission tracking: {form_type}")
        
        # Track form submission interaction
        interaction = await analytics_service.track_interaction(
            session_id=session_id,
            extension_type=ExtensionType.ATLAS,
            context=ExtensionContext.HOMEPAGE,  # Forms can be on any page
            interaction_type=InteractionType.SUBMIT,
            customer_id=customer_id,
            shop_id=shop_id,
            metadata={
                "form_type": form_type,
                "form_data": form_data,
                "page_url": page_url,
                "source": "atlas_web_pixel"
            }
        )
        
        logger.info(f"Atlas form submission tracked: {interaction.id}")
        
        return AtlasResponse(
            success=True,
            message="Atlas form submission tracked successfully",
            data={
                "interaction_id": interaction.id,
                "form_type": form_type,
                "context": ExtensionContext.HOMEPAGE
            }
        )
        
    except Exception as e:
        logger.error(f"Error tracking Atlas form submission: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to track form submission: {str(e)}")
