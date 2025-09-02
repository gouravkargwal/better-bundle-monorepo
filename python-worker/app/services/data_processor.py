"""
Data processing service that orchestrates data collection and ML training events
"""

import asyncio
import uuid
from typing import Dict, Any, Optional
from pydantic import BaseModel

from app.core.config import settings
from app.core.redis_client import streams_manager
from app.services.data_collection import DataCollectionService, DataCollectionConfig

from app.services.gorse_service import gorse_service
from app.core.logging import get_logger, log_error, log_performance, log_stream_event

logger = get_logger(__name__)


class DataJobRequest(BaseModel):
    """Data job request model"""

    job_id: str
    shop_id: str
    shop_domain: str
    access_token: str
    job_type: str = "complete"  # complete or incremental
    days_back: Optional[int] = None


class DataJobResult(BaseModel):
    """Data job result model"""

    job_id: str
    shop_id: str
    shop_db_id: str
    success: bool
    orders_count: int = 0
    products_count: int = 0
    customers_count: int = 0
    duration_ms: float = 0
    error: str = None


class DataProcessor:
    """Main data processor that handles the complete data processing workflow"""

    def __init__(self):
        self.data_collection_service = DataCollectionService()
        self.streams_manager = streams_manager

    async def initialize(self):
        """Initialize the data processor"""
        await self.data_collection_service.initialize()
        await self.streams_manager.initialize()
        logger.info("Data processor initialized successfully")

    async def process_data_job(self, request: DataJobRequest) -> DataJobResult:
        """
        Process a data job: collect data, save to database, and publish ML training event
        """
        start_time = asyncio.get_event_loop().time()

        logger.info(
            "Starting data job processing",
            job_id=request.job_id,
            shop_id=request.shop_id,
            shop_domain=request.shop_domain,
            job_type=request.job_type,
        )

        try:
            # Step 1: Update job status to processing
            await self._update_job_status(request.job_id, "processing", 10)

            # Analysis started - no need to track onboarding status anymore

            # Step 2: Collect and save data
            collection_config = DataCollectionConfig(
                shop_id=request.shop_id,
                shop_domain=request.shop_domain,
                access_token=request.access_token,
                days_back=request.days_back,
                is_incremental=(request.job_type == "incremental"),
            )

            if request.job_type == "incremental":
                collection_result = await self.data_collection_service.collect_and_save_incremental_data(
                    collection_config
                )
            else:
                collection_result = (
                    await self.data_collection_service.collect_and_save_complete_data(
                        collection_config
                    )
                )

            if not collection_result.success:
                # Data collection failed
                await self._update_job_status(
                    request.job_id, "failed", 0, collection_result.error
                )

                return DataJobResult(
                    job_id=request.job_id,
                    shop_id=request.shop_id,
                    shop_db_id=collection_result.shop_db_id,
                    success=False,
                    error=collection_result.error,
                )

            # Step 3: Update job status to data collection completed (60%)
            await self._update_job_status(request.job_id, "processing", 60)

            # Step 4: Run feature transformations here (to be implemented)
            try:
                from app.services.transformations import run_transformations_for_shop

                transform_stats = await run_transformations_for_shop(
                    shop_id=request.shop_id,
                    backfill_if_needed=True,
                )

                # Step 5: Publish features-computed event
                features_event_id = (
                    await self.streams_manager.publish_features_computed_event(
                        job_id=request.job_id,
                        shop_id=request.shop_id,
                        features_ready=True,
                        metadata=transform_stats,
                    )
                )

                logger.info(
                    "Features computed and event published",
                    job_id=request.job_id,
                    shop_id=request.shop_id,
                    features_event_id=features_event_id,
                )

                # Step 5.5: Send data to Gorse for automatic training (if enabled)
                if settings.ENABLE_GORSE_SYNC:
                    try:
                        await gorse_service.initialize()
                        gorse_result = await gorse_service.train_model_for_shop(
                            shop_id=request.shop_id, shop_domain=request.shop_domain
                        )

                        if gorse_result["success"]:
                            logger.info(
                                "Data sent to Gorse successfully",
                                job_id=request.job_id,
                                shop_id=request.shop_id,
                                gorse_result=gorse_result,
                            )
                        else:
                            logger.warning(
                                "Gorse training failed",
                                job_id=request.job_id,
                                shop_id=request.shop_id,
                                error=gorse_result.get("error"),
                            )
                    except Exception as gorse_error:
                        log_error(
                            gorse_error,
                            {
                                "operation": "gorse_training",
                                "job_id": request.job_id,
                                "shop_id": request.shop_id,
                            },
                        )
                        logger.warning(
                            "Failed to send data to Gorse, but continuing with ML training event",
                            job_id=request.job_id,
                            shop_id=request.shop_id,
                            error=str(gorse_error),
                        )

                # Step 6: Publish ML training event (decoupled, still triggered here)
                ml_event_id = await self.streams_manager.publish_ml_training_event(
                    job_id=request.job_id,
                    shop_id=request.shop_id,
                    shop_domain=request.shop_domain,
                    data_collection_completed=True,
                )

                logger.info(
                    "ML training event published successfully",
                    job_id=request.job_id,
                    shop_id=request.shop_id,
                    ml_event_id=ml_event_id,
                )

                # Step 7: Update job status to ML training queued (80%)
                await self._update_job_status(request.job_id, "ml_training_queued", 80)

                # Step 8: Publish user notification
                await self.streams_manager.publish_user_notification_event(
                    shop_id=request.shop_id,
                    notification_type="data_collection_completed",
                    message=f"Data collection and feature computation completed for {request.shop_domain}. ML training has been queued.",
                    data={
                        "job_id": request.job_id,
                        "orders_count": collection_result.orders_count,
                        "products_count": collection_result.products_count,
                        "customers_count": collection_result.customers_count,
                        "transform_stats": transform_stats,
                    },
                )

            except Exception as stream_error:
                log_error(
                    stream_error,
                    {
                        "operation": "publish_ml_training_event",
                        "job_id": request.job_id,
                        "shop_id": request.shop_id,
                    },
                )

                # Even if stream publishing fails, data collection succeeded
                # Just log the error and continue
                logger.warning(
                    "Failed to publish ML training event, but data collection succeeded",
                    job_id=request.job_id,
                    shop_id=request.shop_id,
                    error=str(stream_error),
                )

            total_duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            log_performance(
                "data_job_processing",
                total_duration_ms,
                job_id=request.job_id,
                shop_id=request.shop_id,
                job_type=request.job_type,
            )

            logger.info(
                "Data job processing completed successfully",
                job_id=request.job_id,
                shop_id=request.shop_id,
                shop_domain=request.shop_domain,
                total_duration_ms=total_duration_ms,
                orders_count=collection_result.orders_count,
                products_count=collection_result.products_count,
                customers_count=collection_result.customers_count,
            )

            # Analysis completed successfully - user can proceed to widget setup

            return DataJobResult(
                job_id=request.job_id,
                shop_id=request.shop_id,
                shop_db_id=collection_result.shop_db_id,
                success=True,
                orders_count=collection_result.orders_count,
                products_count=collection_result.products_count,
                customers_count=collection_result.customers_count,
                duration_ms=total_duration_ms,
            )

        except Exception as e:
            total_duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            log_error(
                e,
                {
                    "operation": "data_job_processing",
                    "job_id": request.job_id,
                    "shop_id": request.shop_id,
                    "shop_domain": request.shop_domain,
                    "total_duration_ms": total_duration_ms,
                },
            )

            # Try to update job status to failed - but don't let failures stop us
            try:
                await self._update_job_status(request.job_id, "failed", 0, str(e))
            except Exception as status_error:
                log_error(
                    status_error,
                    {
                        "operation": "update_job_status_failed",
                        "job_id": request.job_id,
                        "original_error": str(e),
                    },
                )

            # Analysis failed - log the error for debugging
            logger.error(
                "Analysis failed",
                shop_id=request.shop_id,
                shop_domain=request.shop_domain,
                job_id=request.job_id,
                error=str(e),
            )

            # Publish failure notification
            try:
                await self.streams_manager.publish_user_notification_event(
                    shop_id=request.shop_id,
                    notification_type="data_collection_failed",
                    message=f"Data collection failed for {request.shop_domain}: {str(e)}",
                    data={"job_id": request.job_id, "error": str(e)},
                )
            except Exception:
                # Ignore notification failures
                pass

            return DataJobResult(
                job_id=request.job_id,
                shop_id=request.shop_id,
                shop_db_id="",
                success=False,
                duration_ms=total_duration_ms,
                error=str(e),
            )

    async def _update_job_status(
        self, job_id: str, status: str, progress: int, error: str = None
    ) -> None:
        """Update job status in database"""
        try:
            from app.core.database import get_database

            db = await get_database()

            from datetime import datetime

            update_data = {
                "status": status,
                "progress": progress,
                "updatedAt": datetime.now(),
            }

            if error:
                update_data["error"] = error

            await db.analysisjob.update(where={"jobId": job_id}, data=update_data)

            logger.info(
                "Job status updated",
                job_id=job_id,
                status=status,
                progress=progress,
                error=error,
            )

        except Exception as e:
            log_error(
                e,
                {
                    "operation": "update_job_status",
                    "job_id": job_id,
                    "status": status,
                    "progress": progress,
                },
            )
            # Don't raise - status update failures shouldn't stop the main process

    async def consume_data_jobs(self):
        """
        Consumer loop for processing data jobs from Redis Streams
        """
        consumer_name = f"{settings.WORKER_ID}-{uuid.uuid4().hex[:8]}"

        logger.info(
            "Starting data job consumer",
            stream_name=settings.DATA_JOB_STREAM,
            consumer_group=settings.DATA_PROCESSOR_GROUP,
            consumer_name=consumer_name,
        )

        while True:
            try:
                # Consume events from the stream
                events = await self.streams_manager.consume_events(
                    stream_name=settings.DATA_JOB_STREAM,
                    consumer_group=settings.DATA_PROCESSOR_GROUP,
                    consumer_name=consumer_name,
                    count=1,
                    block=1000,  # Reduced from 5000ms to 1000ms to prevent aggressive timeouts
                )

                for event in events:
                    try:
                        # Process the data job - handle both camelCase and snake_case field names
                        job_id = event.get("job_id") or event.get("jobId")
                        shop_id = event.get("shop_id") or event.get("shopId")
                        shop_domain = event.get("shop_domain") or event.get(
                            "shopDomain"
                        )
                        access_token = event.get("access_token") or event.get(
                            "accessToken"
                        )
                        job_type = event.get("job_type") or event.get(
                            "jobType", "complete"
                        )
                        # Handle days_back field - only convert to int if it exists and is not None
                        days_back_raw = event.get("days_back") or event.get("daysBack")
                        days_back = (
                            int(days_back_raw) if days_back_raw is not None else None
                        )

                        # Log the field mapping for debugging
                        logger.info(
                            "Field mapping for data job",
                            original_event=event,
                            mapped_fields={
                                "job_id": job_id,
                                "shop_id": shop_id,
                                "shop_domain": shop_domain,
                                "job_type": job_type,
                                "days_back": days_back,
                            },
                        )

                        # Validate required fields
                        if not all([job_id, shop_id, shop_domain, access_token]):
                            missing_fields = []
                            if not job_id:
                                missing_fields.append("job_id")
                            if not shop_id:
                                missing_fields.append("shop_id")
                            if not shop_domain:
                                missing_fields.append("shop_domain")
                            if not access_token:
                                missing_fields.append("access_token")

                            error_msg = (
                                f"Missing required fields: {', '.join(missing_fields)}"
                            )
                            logger.error(error_msg, event=event)
                            raise ValueError(error_msg)

                        request = DataJobRequest(
                            job_id=job_id,
                            shop_id=shop_id,
                            shop_domain=shop_domain,
                            access_token=access_token,
                            job_type=job_type,
                            days_back=days_back,
                        )

                        logger.info(
                            "Processing data job from stream",
                            job_id=request.job_id,
                            shop_id=request.shop_id,
                            message_id=event["_message_id"],
                        )

                        # Process the job
                        result = await self.process_data_job(request)

                        # Acknowledge successful processing
                        await self.streams_manager.acknowledge_event(
                            stream_name=settings.DATA_JOB_STREAM,
                            consumer_group=settings.DATA_PROCESSOR_GROUP,
                            message_id=event["_message_id"],
                        )

                        logger.info(
                            "Data job processed and acknowledged",
                            job_id=request.job_id,
                            shop_id=request.shop_id,
                            success=result.success,
                            message_id=event["_message_id"],
                        )

                    except Exception as e:
                        log_error(
                            e,
                            {
                                "operation": "process_stream_event",
                                "event": event,
                                "message_id": event.get("_message_id"),
                            },
                        )

                        # For now, acknowledge even failed events to avoid infinite retries
                        # In production, you might want to implement a dead letter queue
                        await self.streams_manager.acknowledge_event(
                            stream_name=settings.DATA_JOB_STREAM,
                            consumer_group=settings.DATA_PROCESSOR_GROUP,
                            message_id=event["_message_id"],
                        )

            except Exception as e:
                log_error(e, {"operation": "consume_data_jobs"})
                # Wait before retrying
                await asyncio.sleep(5)


# Global data processor instance
data_processor = DataProcessor()
