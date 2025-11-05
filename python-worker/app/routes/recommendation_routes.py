from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from app.core.dependencies import get_shop_authorization

from app.models.recommendation_models import (
    RecommendationRequest,
    CombinedRecommendationRequest,
    RecommendationResponse,
)
from app.controllers.recommendation_controller import recommendation_controller
from app.core.logging.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/recommendation", tags=["Recommendations"])


@router.post("/get", response_model=RecommendationResponse)
async def get_recommendations(
    request: RecommendationRequest,
    shop_info: Dict[str, Any] = Depends(get_shop_authorization),
):
    """
    Unified endpoint for fetching recommendations across all extensions.

    Requires an existing session. If session doesn't exist, use /api/session/get-or-create-session first.

    Used by: Venus, Atlas, Phoenix, Mercury

    Example payload:
    {
        "shop_domain": "example.myshopify.com",
        "extension_type": "phoenix",
        "session_id": "uuid-123",
        "context": "cart",
        "user_id": "customer_123",
        "limit": 4
    }
    """
    try:
        response = await recommendation_controller.get_recommendations(
            request, shop_info
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching recommendations: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch recommendations: {str(e)}"
        )


@router.post("/get-with-session", response_model=RecommendationResponse)
async def get_recommendations_with_session(
    request: CombinedRecommendationRequest,
    shop_info: Dict[str, Any] = Depends(get_shop_authorization),
):
    """
    Combined endpoint for creating session and fetching recommendations in one call.

    Optimized for Apollo post-purchase extension to minimize API calls.

    Used by: Apollo (primarily)

    Example payload:
    {
        "shop_domain": "example.myshopify.com",
        "extension_type": "apollo",
        "customer_id": "customer_123",
        "purchased_products": ["prod_1", "prod_2"],
        "order_id": "order_456",
        "limit": 3
    }
    """
    try:
        response = await recommendation_controller.get_recommendations_with_session(
            request, shop_info
        )
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching recommendations with session: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch recommendations with session: {str(e)}",
        )
