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
    sync_type: str = "all"  # "all", "incremental", "users", "items", "feedback"
    since_hours: int = 24
    trigger_source: str = "api"


class SyncResponse(BaseModel):
    job_id: str
    shop_id: str
    sync_type: str
    users_synced: int
    items_synced: int
    feedback_synced: int
    training_triggered: bool
    duration_seconds: float
    errors: list


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
            sync_type=request.sync_type,
            since_hours=request.since_hours,
            trigger_source=request.trigger_source,
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
