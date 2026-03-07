"""
Unified Gorse API endpoints
Provides endpoints for the unified sync and training service
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, Optional

from app.domains.ml.services.unified_gorse_service import UnifiedGorseService
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/gorse", tags=["unified-gorse"])


class SyncRequest(BaseModel):
    shop_id: str


class SyncResponse(BaseModel):
    model_config = {"extra": "ignore"}

    job_id: str
    shop_id: str
    sync_results: Dict[str, Any] = {}
    total_items_synced: int = 0
    training_triggered: bool = False
    duration_seconds: float = 0.0
    errors: list = []


@router.post("/sync", response_model=SyncResponse)
async def sync_and_train(request: SyncRequest, background_tasks: BackgroundTasks):
    """
    Sync data from feature tables directly to Gorse API and trigger training
    """
    try:
        service = UnifiedGorseService()

        # Run sync in background
        result = await service.sync_and_train(
            shop_id=request.shop_id,
        )

        return SyncResponse(**result)

    except Exception as e:
        logger.error(f"Failed to sync and train for shop {request.shop_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{shop_id}")
async def get_training_status(shop_id: str):
    """
    Get current training status for a shop
    """
    try:
        service = UnifiedGorseService()
        status = await service.get_training_status(shop_id)
        return status

    except Exception as e:
        logger.error(f"Failed to get training status for shop {shop_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train/{shop_id}")
async def trigger_manual_training(shop_id: str):
    """
    Manually trigger training for a shop
    """
    try:
        service = UnifiedGorseService()
        result = await service.trigger_manual_training(shop_id)
        return result

    except Exception as e:
        logger.error(f"Failed to trigger training for shop {shop_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
