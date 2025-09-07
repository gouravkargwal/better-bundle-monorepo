"""
Training API endpoints
Handles training job management and status monitoring
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.domains.ml.services.gorse_training_service import (
    GorseTrainingService,
    TrainingJobType,
    TrainingStatus,
)
from app.core.redis_client import get_redis_client

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/training", tags=["training"])


# Pydantic models for request/response
class TrainingJobRequest(BaseModel):
    """Request model for creating a training job"""

    shop_id: str = Field(..., description="Shop ID to train models for")
    job_type: str = Field(default="full_training", description="Type of training job")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata"
    )
    trigger_source: str = Field(
        default="api", description="Source that triggered the training"
    )


class TrainingJobResponse(BaseModel):
    """Response model for training job creation"""

    job_id: str
    shop_id: str
    job_type: str
    status: str
    message: str
    created_at: datetime


class TrainingJobStatus(BaseModel):
    """Training job status response"""

    job_id: str
    shop_id: str
    job_type: str
    status: str
    progress: float
    status_message: Optional[str]
    trigger_source: str
    metadata: Dict[str, Any]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime


class TrainingHistoryResponse(BaseModel):
    """Training history response"""

    shop_id: str
    jobs: list[Dict[str, Any]]
    total_count: int


class HealthCheckResponse(BaseModel):
    """Health check response"""

    status: str
    active_jobs: int
    max_concurrent_jobs: int
    consumer_health: Dict[str, Any]


@router.post("/jobs", response_model=TrainingJobResponse)
async def create_training_job(
    request: TrainingJobRequest,
    background_tasks: BackgroundTasks,
) -> TrainingJobResponse:
    """
    Create a new training job

    This endpoint creates a training job and queues it for processing.
    The job will be processed asynchronously by the training consumer.
    """
    try:
        # Validate job type
        try:
            job_type = TrainingJobType(request.job_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid job type: {request.job_type}. Valid types: {[t.value for t in TrainingJobType]}",
            )

        # Generate job ID
        job_id = f"training_{request.shop_id}_{job_type.value}_{int(datetime.now().timestamp())}"

        # Publish the Gorse training event to Redis stream
        from app.core.redis_client import streams_manager

        event_id = await streams_manager.publish_gorse_training_event(
            job_id=job_id,
            shop_id=request.shop_id,
            job_type=job_type.value,
            trigger_source=request.trigger_source,
            metadata=request.metadata or {},
        )

        logger.info(f"Created training job {job_id} for shop {request.shop_id}")

        return TrainingJobResponse(
            job_id=job_id,
            shop_id=request.shop_id,
            job_type=job_type.value,
            status="queued",
            message="Training job created and queued for processing",
            created_at=datetime.now(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create training job: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to create training job: {str(e)}"
        )


@router.get("/jobs/{job_id}", response_model=TrainingJobStatus)
async def get_training_job_status(job_id: str) -> TrainingJobStatus:
    """
    Get the status of a training job
    """
    try:
        training_service = GorseTrainingService()
        job_status = await training_service.get_training_job_status(job_id)

        if not job_status:
            raise HTTPException(
                status_code=404, detail=f"Training job {job_id} not found"
            )

        return TrainingJobStatus(**job_status)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get training job status: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get training job status: {str(e)}"
        )


@router.get("/shops/{shop_id}/history", response_model=TrainingHistoryResponse)
async def get_shop_training_history(
    shop_id: str,
    limit: int = Query(
        default=10, ge=1, le=100, description="Number of jobs to return"
    ),
) -> TrainingHistoryResponse:
    """
    Get training history for a shop
    """
    try:
        training_service = GorseTrainingService()
        history = await training_service.get_shop_training_history(shop_id, limit)

        return TrainingHistoryResponse(
            shop_id=shop_id,
            jobs=history,
            total_count=len(history),
        )

    except Exception as e:
        logger.error(f"Failed to get training history for shop {shop_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get training history: {str(e)}"
        )


@router.delete("/jobs/{job_id}")
async def cancel_training_job(job_id: str) -> Dict[str, Any]:
    """
    Cancel a running training job
    """
    try:
        training_service = GorseTrainingService()
        success = await training_service.cancel_training_job(job_id)

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Training job {job_id} not found or cannot be cancelled",
            )

        return {
            "job_id": job_id,
            "status": "cancelled",
            "message": "Training job cancelled successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel training job {job_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to cancel training job: {str(e)}"
        )


@router.post("/shops/{shop_id}/train")
async def trigger_shop_training(
    shop_id: str,
    job_type: str = Query(
        default="full_training", description="Type of training to trigger"
    ),
    background_tasks: BackgroundTasks = None,
) -> TrainingJobResponse:
    """
    Convenience endpoint to trigger training for a specific shop
    """
    try:
        # Validate job type
        try:
            TrainingJobType(job_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid job type: {job_type}. Valid types: {[t.value for t in TrainingJobType]}",
            )

        # Create training job request
        request = TrainingJobRequest(
            shop_id=shop_id,
            job_type=job_type,
            trigger_source="api",
        )

        # Create the training job
        return await create_training_job(request, background_tasks)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger training for shop {shop_id}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to trigger training: {str(e)}"
        )


@router.get("/health", response_model=HealthCheckResponse)
async def training_health_check() -> HealthCheckResponse:
    """
    Health check for the training system
    """
    try:
        # Get Redis client
        redis_client = await get_redis_client()

        # Check Redis connection
        redis_health = await redis_client.ping()

        # Get stream info
        stream_info = await redis_client.xinfo_stream("betterbundle:gorse-training")

        # Get consumer group info
        try:
            consumer_groups = await redis_client.xinfo_groups(
                "betterbundle:gorse-training"
            )
            active_consumers = len(consumer_groups)
        except:
            active_consumers = 0

        # Get pending messages count
        try:
            pending_info = await redis_client.xpending(
                "betterbundle:gorse-training", "gorse-training-consumer"
            )
            pending_messages = pending_info.get("pending", 0)
        except:
            pending_messages = 0

        return HealthCheckResponse(
            status="healthy" if redis_health else "unhealthy",
            active_jobs=0,  # This would need to be tracked separately
            max_concurrent_jobs=3,
            consumer_health={
                "redis_connected": redis_health,
                "stream_length": stream_info.get("length", 0),
                "active_consumers": active_consumers,
                "pending_messages": pending_messages,
            },
        )

    except Exception as e:
        logger.error(f"Training health check failed: {str(e)}")
        return HealthCheckResponse(
            status="unhealthy",
            active_jobs=0,
            max_concurrent_jobs=3,
            consumer_health={
                "error": str(e),
            },
        )


@router.get("/jobs")
async def list_training_jobs(
    shop_id: Optional[str] = Query(default=None, description="Filter by shop ID"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    limit: int = Query(
        default=20, ge=1, le=100, description="Number of jobs to return"
    ),
) -> Dict[str, Any]:
    """
    List training jobs with optional filtering
    """
    try:
        # This would need to be implemented in the training service
        # For now, return a placeholder response
        return {
            "jobs": [],
            "total_count": 0,
            "filters": {
                "shop_id": shop_id,
                "status": status,
                "limit": limit,
            },
        }

    except Exception as e:
        logger.error(f"Failed to list training jobs: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list training jobs: {str(e)}"
        )


# Webhook endpoint for Gorse to trigger training
@router.post("/webhooks/gorse")
async def gorse_webhook(
    payload: Dict[str, Any],
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """
    Webhook endpoint for Gorse to trigger training jobs
    This can be called by Gorse when certain events occur (e.g., data sync completed)
    """
    try:
        # Extract information from Gorse webhook payload
        event_type = payload.get("event_type")
        shop_id = payload.get("shop_id")
        metadata = payload.get("metadata", {})

        if not shop_id:
            raise HTTPException(
                status_code=400, detail="Missing shop_id in webhook payload"
            )

        # Determine job type based on event type
        job_type = "incremental_training"  # Default
        if event_type == "data_sync_completed":
            job_type = "incremental_training"
        elif event_type == "full_sync_completed":
            job_type = "full_training"
        elif event_type == "model_refresh_requested":
            job_type = "model_refresh"

        # Create training job request
        request = TrainingJobRequest(
            shop_id=shop_id,
            job_type=job_type,
            trigger_source="gorse_webhook",
            metadata={
                "webhook_event": event_type,
                "gorse_metadata": metadata,
            },
        )

        # Create the training job
        job_response = await create_training_job(request, background_tasks)

        logger.info(f"Created training job from Gorse webhook: {job_response.job_id}")

        return {
            "status": "success",
            "message": "Training job created from Gorse webhook",
            "job_id": job_response.job_id,
            "shop_id": job_response.shop_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process Gorse webhook: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to process webhook: {str(e)}"
        )
