"""
Data jobs API endpoints
"""

import asyncio
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from app.core.config import settings
from app.core.redis_client import streams_manager
from app.services.data_processor import data_processor, DataJobRequest
from app.core.logging import get_logger, log_error, log_request_start, log_request_end
from app.services.transformations import run_transformations_for_shop

logger = get_logger(__name__)
router = APIRouter()


class DataJobRequestModel(BaseModel):
    """Data job request model for API"""

    shop_id: str
    shop_domain: str
    access_token: str
    job_type: str = "complete"  # complete or incremental
    days_back: Optional[int] = None


class DataJobResponse(BaseModel):
    """Data job response model"""

    success: bool
    job_id: str
    message: str
    shop_id: str
    status: str = "queued"


class StreamEventResponse(BaseModel):
    """Stream event response model"""

    success: bool
    event_id: str
    stream_name: str
    message: str


@router.post("/queue", response_model=DataJobResponse)
async def queue_data_job(request: DataJobRequestModel):
    """Queue a data collection job via Redis Streams"""

    start_time = asyncio.get_event_loop().time()
    job_id = f"data_job_{int(asyncio.get_event_loop().time())}_{uuid.uuid4().hex[:8]}"

    log_request_start(
        "POST", "/api/v1/data-jobs/queue", job_id=job_id, shop_id=request.shop_id
    )

    try:
        logger.info(
            "Received data job queue request",
            job_id=job_id,
            shop_id=request.shop_id,
            shop_domain=request.shop_domain,
            job_type=request.job_type,
        )

        # Initialize streams manager if needed
        if not streams_manager.redis:
            await streams_manager.initialize()

        # Create job record in database first
        from app.core.database import get_database

        db = await get_database()

        analysis_job = await db.analysisjob.create(
            data={
                "jobId": job_id,
                "shopId": request.shop_id,
                "status": "queued",
                "progress": 0,
            }
        )

        logger.info(
            "Job record created in database", job_id=job_id, db_id=analysis_job.id
        )

        # Publish job to Redis stream
        event_id = await streams_manager.publish_data_job_event(
            job_id=job_id,
            shop_id=request.shop_id,
            shop_domain=request.shop_domain,
            access_token=request.access_token,
            job_type=request.job_type,
        )

        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        log_request_end(
            "POST",
            "/api/v1/data-jobs/queue",
            200,
            duration_ms,
            job_id=job_id,
            shop_id=request.shop_id,
        )

        logger.info(
            "Data job queued successfully",
            job_id=job_id,
            shop_id=request.shop_id,
            event_id=event_id,
            duration_ms=duration_ms,
        )

        return DataJobResponse(
            success=True,
            job_id=job_id,
            message="Data job queued successfully",
            shop_id=request.shop_id,
            status="queued",
        )

    except Exception as e:
        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        log_error(
            e,
            {
                "operation": "queue_data_job",
                "job_id": job_id,
                "shop_id": request.shop_id,
                "duration_ms": duration_ms,
            },
        )

        log_request_end(
            "POST",
            "/api/v1/data-jobs/queue",
            500,
            duration_ms,
            job_id=job_id,
            shop_id=request.shop_id,
            error=str(e),
        )

        raise HTTPException(
            status_code=500, detail=f"Failed to queue data job: {str(e)}"
        )


@router.post("/process", response_model=DataJobResponse)
async def process_data_job_direct(request: DataJobRequestModel):
    """Process a data job directly (synchronous processing)"""

    start_time = asyncio.get_event_loop().time()
    job_id = f"direct_job_{int(asyncio.get_event_loop().time())}_{uuid.uuid4().hex[:8]}"

    log_request_start(
        "POST", "/api/v1/data-jobs/process", job_id=job_id, shop_id=request.shop_id
    )

    try:
        logger.info(
            "Received direct data job processing request",
            job_id=job_id,
            shop_id=request.shop_id,
            shop_domain=request.shop_domain,
            job_type=request.job_type,
        )

        # Initialize data processor if needed
        if not data_processor.data_collection_service.db:
            await data_processor.initialize()

        # Create job record in database
        from app.core.database import get_database

        db = await get_database()

        analysis_job = await db.analysisjob.create(
            data={
                "jobId": job_id,
                "shopId": request.shop_id,
                "status": "processing",
                "progress": 0,
            }
        )

        logger.info(
            "Job record created in database", job_id=job_id, db_id=analysis_job.id
        )

        # Process the job directly
        job_request = DataJobRequest(
            job_id=job_id,
            shop_id=request.shop_id,
            shop_domain=request.shop_domain,
            access_token=request.access_token,
            job_type=request.job_type,
            days_back=request.days_back,
        )

        result = await data_processor.process_data_job(job_request)

        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        if result.success:
            log_request_end(
                "POST",
                "/api/v1/data-jobs/process",
                200,
                duration_ms,
                job_id=job_id,
                shop_id=request.shop_id,
            )

            return DataJobResponse(
                success=True,
                job_id=job_id,
                message=f"Data job completed successfully. Processed {result.orders_count} orders, {result.products_count} products, {result.customers_count} customers.",
                shop_id=request.shop_id,
                status="completed",
            )
        else:
            log_request_end(
                "POST",
                "/api/v1/data-jobs/process",
                500,
                duration_ms,
                job_id=job_id,
                shop_id=request.shop_id,
                error=result.error,
            )

            raise HTTPException(
                status_code=500, detail=f"Data job failed: {result.error}"
            )

    except Exception as e:
        duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

        log_error(
            e,
            {
                "operation": "process_data_job_direct",
                "job_id": job_id,
                "shop_id": request.shop_id,
                "duration_ms": duration_ms,
            },
        )

        log_request_end(
            "POST",
            "/api/v1/data-jobs/process",
            500,
            duration_ms,
            job_id=job_id,
            shop_id=request.shop_id,
            error=str(e),
        )

        raise HTTPException(
            status_code=500, detail=f"Failed to process data job: {str(e)}"
        )


@router.post("/streams/ml-training", response_model=StreamEventResponse)
async def publish_ml_training_event(
    job_id: str, shop_id: str, shop_domain: str, data_collection_completed: bool = True
):
    """Manually publish an ML training event"""

    try:
        # Initialize streams manager if needed
        if not streams_manager.redis:
            await streams_manager.initialize()

        event_id = await streams_manager.publish_ml_training_event(
            job_id=job_id,
            shop_id=shop_id,
            shop_domain=shop_domain,
            data_collection_completed=data_collection_completed,
        )

        return StreamEventResponse(
            success=True,
            event_id=event_id,
            stream_name=settings.ML_TRAINING_STREAM,
            message="ML training event published successfully",
        )

    except Exception as e:
        log_error(
            e,
            {
                "operation": "publish_ml_training_event",
                "job_id": job_id,
                "shop_id": shop_id,
            },
        )

        raise HTTPException(
            status_code=500, detail=f"Failed to publish ML training event: {str(e)}"
        )


@router.post("/streams/user-notification", response_model=StreamEventResponse)
async def publish_user_notification(
    shop_id: str, notification_type: str, message: str, data: dict = None
):
    """Manually publish a user notification event"""

    try:
        # Initialize streams manager if needed
        if not streams_manager.redis:
            await streams_manager.initialize()

        event_id = await streams_manager.publish_user_notification_event(
            shop_id=shop_id,
            notification_type=notification_type,
            message=message,
            data=data or {},
        )

        return StreamEventResponse(
            success=True,
            event_id=event_id,
            stream_name=settings.USER_NOTIFICATIONS_STREAM,
            message="User notification event published successfully",
        )

    except Exception as e:
        log_error(
            e,
            {
                "operation": "publish_user_notification",
                "shop_id": shop_id,
                "notification_type": notification_type,
            },
        )

        raise HTTPException(
            status_code=500, detail=f"Failed to publish user notification: {str(e)}"
        )


@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """Get the status of a data job"""

    try:
        from app.core.database import get_database

        db = await get_database()

        job = await db.analysisjob.find_unique(
            where={"jobId": job_id}, include={"shop": True}
        )

        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

        return {
            "job_id": job.jobId,
            "shop_id": job.shopId,
            "shop_domain": job.shop.shopDomain if job.shop else None,
            "status": job.status,
            "progress": job.progress,
            "error": job.error,
            "results": job.results,
            "created_at": job.createdAt,
            "updated_at": job.updatedAt,
        }

    except HTTPException:
        raise
    except Exception as e:
        log_error(e, {"operation": "get_job_status", "job_id": job_id})

        raise HTTPException(
            status_code=500, detail=f"Failed to get job status: {str(e)}"
        )


@router.post("/start-consumer")
async def start_consumer(background_tasks: BackgroundTasks):
    """Start the Redis Streams consumer in the background"""

    try:
        # Initialize data processor if needed
        if not data_processor.data_collection_service.db:
            await data_processor.initialize()

        # Start the consumer in the background
        background_tasks.add_task(data_processor.consume_data_jobs)

        return {
            "success": True,
            "message": "Data job consumer started successfully",
            "stream_name": settings.DATA_JOB_STREAM,
            "consumer_group": settings.DATA_PROCESSOR_GROUP,
        }

    except Exception as e:
        log_error(e, {"operation": "start_consumer"})

        raise HTTPException(
            status_code=500, detail=f"Failed to start consumer: {str(e)}"
        )


@router.post("/transform/{shop_id}")
async def trigger_transformations(shop_id: str):
    """Manually trigger feature transformations for a shop"""
    try:
        stats = await run_transformations_for_shop(shop_id, backfill_if_needed=True)
        return {"success": True, "shop_id": shop_id, "stats": stats}
    except Exception as e:
        log_error(e, {"operation": "trigger_transformations", "shop_id": shop_id})
        raise HTTPException(
            status_code=500, detail=f"Failed to run transformations: {str(e)}"
        )
