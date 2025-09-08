"""
Gorse Training Consumer
Handles training job processing from Redis streams
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional

from app.consumers.base_consumer import BaseConsumer
from app.core.logging import get_logger
from app.domains.ml.services.gorse_training_service import (
    GorseTrainingService,
    TrainingJobType,
    TrainingStatus,
)
from app.shared.helpers import now_utc

logger = get_logger(__name__)


class GorseTrainingConsumer(BaseConsumer):
    """
    Consumer for processing Gorse training jobs
    Handles training requests from API or Gorse webhooks
    """

    def __init__(self):
        super().__init__(
            stream_name="betterbundle:gorse-training",
            consumer_group="gorse-training-consumer",
            consumer_name="gorse-training-consumer",
            batch_size=2,  # Process fewer jobs as training is intensive
            poll_timeout=2000,  # 2 second timeout
            max_retries=2,
            retry_delay=5.0,
            circuit_breaker_failures=3,
            circuit_breaker_timeout=180,  # 3 minutes recovery
        )

        self.training_service = GorseTrainingService()
        self.max_concurrent_jobs = 3  # Limit concurrent training jobs
        self.active_jobs = {}  # Track active training jobs

    async def _process_single_message(self, message: Dict[str, Any]):
        """Process a single training job message (required by BaseConsumer)"""
        try:
            # Extract message data
            job_id = message.get("job_id")
            shop_id = message.get("shop_id")
            job_type_str = message.get("job_type", "full_training")
            trigger_source = message.get("trigger_source", "api")
            metadata = message.get("metadata", {})

            if not job_id or not shop_id:
                self.logger.error("Invalid message: missing job_id or shop_id")
                return False

            # Parse job type
            try:
                job_type = TrainingJobType(job_type_str)
            except ValueError:
                self.logger.error(f"Invalid job type: {job_type_str}")
                return False

            # Check if we're already at max concurrent jobs
            if len(self.active_jobs) >= self.max_concurrent_jobs:
                self.logger.warning(
                    f"Max concurrent jobs ({self.max_concurrent_jobs}) reached, skipping job {job_id}"
                )
                return False

            # Add job to active jobs tracking
            self.active_jobs[job_id] = {
                "shop_id": shop_id,
                "job_type": job_type,
                "started_at": now_utc(),
            }

            try:
                # Execute the training job
                await self._execute_training_job(
                    job_id, shop_id, job_type, trigger_source, metadata
                )

                self.logger.info(
                    f"Training job completed successfully | job_id={job_id} | shop_id={shop_id}"
                )
                return True

            except Exception as e:
                self.logger.error(
                    f"Training job failed | job_id={job_id} | shop_id={shop_id} | error={str(e)}"
                )
                return False

            finally:
                # Remove from active jobs
                self.active_jobs.pop(job_id, None)

        except Exception as e:
            self.logger.error(
                f"Failed to process training message: {str(e)} | message_data={message}"
            )
            return False

    async def _execute_training_job(
        self,
        job_id: str,
        shop_id: str,
        job_type: TrainingJobType,
        trigger_source: str,
        metadata: Dict[str, Any],
    ):
        """Execute the actual training job using the training service"""
        try:
            logger.info(
                f"Starting training job {job_id} for shop {shop_id} (type: {job_type.value})"
            )

            # Use the training service to execute the training
            # The training service handles the complete flow: sync → views → training
            await self.training_service.start_training_job(
                shop_id=shop_id,
                job_type=job_type,
                trigger_source=trigger_source,
                metadata=metadata,
            )

            logger.info(f"Training job {job_id} completed successfully")

        except Exception as e:
            logger.error(f"Training execution failed for job {job_id}: {str(e)}")
            raise

    async def get_active_jobs(self) -> Dict[str, Any]:
        """Get information about currently active training jobs"""
        return {
            "active_jobs": len(self.active_jobs),
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "jobs": [
                {
                    "job_id": job_id,
                    "shop_id": job_data["shop_id"],
                    "job_type": job_data["job_type"].value,
                    "started_at": job_data["started_at"],
                    "duration": (now_utc() - job_data["started_at"]).total_seconds(),
                }
                for job_id, job_data in self.active_jobs.items()
            ],
        }

    async def health_check(self) -> Dict[str, Any]:
        """Health check for the training consumer"""
        try:
            # Check Redis connection
            from app.core.redis_client import get_redis_client

            redis_client = await get_redis_client()
            redis_health = await redis_client.ping()

            # Check database connection
            db = await self.training_service._get_database()
            db_health = True  # If we can get the database, it's healthy

            return {
                "status": "healthy",
                "redis_connected": redis_health,
                "database_connected": db_health,
                "active_jobs": len(self.active_jobs),
                "max_concurrent_jobs": self.max_concurrent_jobs,
                "consumer_name": self.consumer_name,
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "consumer_name": self.consumer_name,
            }
