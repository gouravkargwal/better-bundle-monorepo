"""
ML Training Consumer Service
Consumes ML training events from Redis Streams and processes them asynchronously
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, Any

from app.core.config import settings
from app.core.redis_client import streams_manager
from app.core.database import get_database
from app.services.gorse_service import gorse_service
from app.services.gorse_training_monitor import gorse_training_monitor
from app.core.logger import get_logger

logger = get_logger("ml-training-consumer")


class MLTrainingConsumer:
    """Consumer for ML training events"""

    def __init__(self):
        self._shutdown_event = asyncio.Event()
        self._consumer_task = None

    async def initialize(self):
        """Initialize the consumer"""
        await streams_manager.initialize()
        await gorse_service.initialize()
        await gorse_training_monitor.initialize()

    async def shutdown(self):
        """Gracefully shutdown the consumer"""
        self._shutdown_event.set()

        if self._consumer_task and not self._consumer_task.done():
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

        # Shutdown the training monitor
        await gorse_training_monitor.shutdown()

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested"""
        return self._shutdown_event.is_set()

    async def start_consumer(self):
        """Start the consumer in a separate task"""
        if self._consumer_task and not self._consumer_task.done():
            logger.warning("Consumer is already running")
            return

        self._consumer_task = asyncio.create_task(
            self.consume_ml_training_events(), name="ml-training-consumer"
        )

    async def stop_consumer(self):
        """Stop the consumer task"""
        if self._consumer_task and not self._consumer_task.done():
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

    async def consume_ml_training_events(self):
        """Main consumer loop for ML training events"""
        consumer_name = (
            f"ml-training-consumer-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        )
        consecutive_failures = 0
        max_consecutive_failures = 3

        while not self.is_shutdown_requested():
            try:
                # Consume events from ML training stream
                events = await streams_manager.consume_events(
                    stream_name=settings.ML_TRAINING_STREAM,
                    consumer_group=settings.ML_TRAINING_GROUP,
                    consumer_name=consumer_name,
                    count=settings.CONSUMER_BATCH_SIZE,
                    block=10000,  # 10 seconds (increased from 5 seconds)
                )

                if events:
                    consecutive_failures = 0

                    for event in events:
                        if self.is_shutdown_requested():
                            return

                        try:
                            await self._process_ml_training_event(event)

                            # Acknowledge successful processing
                            await streams_manager.acknowledge_event(
                                stream_name=settings.ML_TRAINING_STREAM,
                                consumer_group="ml-training-consumers",
                                message_id=event["_message_id"],
                            )

                        except Exception as e:
                            logger.error(
                                "Error processing ML training event",
                                event_id=event.get("_message_id"),
                                error=str(e),
                            )

                            # Acknowledge failed events to avoid infinite retries
                            await streams_manager.acknowledge_event(
                                stream_name=settings.ML_TRAINING_STREAM,
                                consumer_group="ml-training-consumers",
                                message_id=event["_message_id"],
                            )

                            consecutive_failures += 1

                else:
                    # No events, sleep briefly
                    await asyncio.sleep(2)

                # Check for too many consecutive failures
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(
                        f"Too many consecutive failures ({consecutive_failures}), "
                        "waiting before retrying"
                    )
                    await asyncio.sleep(30)
                    consecutive_failures = 0

            except Exception as e:
                logger.error(f"Error in ML training consumer loop: {e}")
                consecutive_failures += 1
                await asyncio.sleep(5)

    async def _process_ml_training_event(self, event: Dict[str, Any]):
        """Process a single ML training event"""
        try:
            event_type = event.get("event_type")
            job_id = event.get("job_id")
            shop_id = event.get("shop_id")
            shop_domain = event.get("shop_domain")
            training_type = event.get("training_type")

            if (
                event_type == "ML_TRAINING_REQUESTED"
                and training_type == "gorse_recommendations"
            ):
                # Process Gorse training
                await self._process_gorse_training(job_id, shop_id, shop_domain)
            else:
                logger.warning(
                    "Unknown event type or training type",
                    event_type=event_type,
                    training_type=training_type,
                )

        except Exception as e:
            logger.error(f"Error processing ML training event: {e}")
            raise

    async def _process_gorse_training(
        self, job_id: str, shop_id: str, shop_domain: str
    ):
        """Process Gorse training for a shop"""
        try:

            # Create MLTrainingLog record to reflect in-progress status
            try:
                db = await get_database()
                # Create MLTrainingLog record using Prisma's native relation handling
                training_log = await db.mltraininglog.create(
                    data={
                        "shopId": shop_id,
                        "status": "started",
                        "startedAt": datetime.now(timezone.utc),
                    }
                )

            except Exception as e:
                logger.warning(
                    "Failed to create MLTrainingLog record at start",
                    shop_id=shop_id,
                    error=str(e),
                )

            # Start monitoring Gorse training progress (resource-efficient)
            async def training_progress_callback(progress: Dict[str, Any]):
                """Callback for training progress updates"""

            await gorse_training_monitor.start_monitoring_shop(
                shop_id=shop_id, job_id=job_id, callback=training_progress_callback
            )

            # Execute Gorse training
            result = await gorse_service.train_model_for_shop(
                shop_id=shop_id, shop_domain=shop_domain
            )

            if result["success"]:
                if result.get("skipped", False):

                    # Publish completion event for skipped training
                    completion_event = {
                        "event_type": "ML_TRAINING_SKIPPED",
                        "job_id": job_id,
                        "shop_id": shop_id,
                        "shop_domain": shop_domain,
                        "training_type": "gorse_recommendations",
                        "result": result,
                        "completed_at": datetime.now().isoformat(),
                        "skipped_reason": result.get("reason"),
                    }
                else:

                    # Publish completion event for successful training
                    completion_event = {
                        "event_type": "ML_TRAINING_COMPLETED",
                        "job_id": job_id,
                        "shop_id": shop_id,
                        "shop_domain": shop_domain,
                        "training_type": "gorse_recommendations",
                        "result": result,
                        "completed_at": datetime.now().isoformat(),
                    }

                await streams_manager.publish_event(
                    stream_name=settings.ML_TRAINING_COMPLETE_STREAM,
                    event_data=completion_event,
                )

            else:
                logger.error(
                    "Gorse training failed",
                    job_id=job_id,
                    shop_id=shop_id,
                    error=result.get("error"),
                )

                # Publish failure event
                failure_event = {
                    "event_type": "ML_TRAINING_FAILED",
                    "job_id": job_id,
                    "shop_id": shop_id,
                    "shop_domain": shop_domain,
                    "training_type": "gorse_recommendations",
                    "error": result.get("error"),
                    "failed_at": datetime.now().isoformat(),
                    "success": False,  # Add success field
                    "skipped": False,  # Add skipped field
                }

                await streams_manager.publish_event(
                    stream_name=settings.ML_TRAINING_COMPLETE_STREAM,
                    event_data=failure_event,
                )

        except Exception as e:
            logger.error(
                "Exception during Gorse training",
                job_id=job_id,
                shop_id=shop_id,
                error=str(e),
            )

            # Publish failure event
            failure_event = {
                "event_type": "ML_TRAINING_FAILED",
                "job_id": job_id,
                "shop_id": shop_id,
                "shop_domain": shop_domain,
                "training_type": "gorse_recommendations",
                "error": str(e),
                "failed_at": datetime.now().isoformat(),
            }

            await streams_manager.publish_event(
                stream_name=settings.ML_TRAINING_COMPLETE_STREAM,
                event_data=failure_event,
            )

            raise


# Global instance
ml_training_consumer = MLTrainingConsumer()
