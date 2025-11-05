from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from app.core.dependencies import get_shop_authorization

from app.controllers.interaction_controller import interaction_controller
from app.models.interaction_models import InteractionRequest, InteractionResponse
from app.core.logging.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/interaction", tags=["Interaction Tracking"])


@router.post("/track", response_model=InteractionResponse)
async def track_interaction(
    request: InteractionRequest,
    shop_info: Dict[str, Any] = Depends(get_shop_authorization),
):
    """
    Unified endpoint for tracking interactions across all extensions.

    All extensions (Venus, Atlas, Phoenix, Apollo, Mercury) use this single endpoint
    with the same payload structure, differentiated by the extension_type field.

    Example payload:
    {
        "session_id": "uuid-123",
        "shop_domain": "example.myshopify.com",
        "extension_type": "phoenix",
        "interaction_type": "recommendation_clicked",
        "customer_id": "customer_123",
        "metadata": { "product_id": "prod_456", "context": "cart" }
    }
    """
    try:
        response = await interaction_controller.track_interaction(request, shop_info)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tracking interaction: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to track interaction: {str(e)}"
        )
