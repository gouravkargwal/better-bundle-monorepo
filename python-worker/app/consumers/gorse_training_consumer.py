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
        """Execute the actual training job"""
        try:
            # Update job status to running
            await self._update_job_status(
                job_id, TrainingStatus.RUNNING, "Starting training..."
            )

            # Execute training based on job type
            if job_type == TrainingJobType.FULL_TRAINING:
                await self._execute_full_training(job_id, shop_id)
            elif job_type == TrainingJobType.INCREMENTAL_TRAINING:
                await self._execute_incremental_training(job_id, shop_id)
            elif job_type == TrainingJobType.MODEL_REFRESH:
                await self._execute_model_refresh(job_id, shop_id)
            elif job_type == TrainingJobType.CUSTOM_TRAINING:
                await self._execute_custom_training(job_id, shop_id, metadata)
            else:
                raise ValueError(f"Unsupported job type: {job_type}")

            # Mark as completed
            await self._update_job_status(
                job_id, TrainingStatus.COMPLETED, "Training completed successfully"
            )

        except Exception as e:
            logger.error(f"Training execution failed for job {job_id}: {str(e)}")
            await self._update_job_status(
                job_id, TrainingStatus.FAILED, f"Training failed: {str(e)}"
            )
            raise

    async def _execute_full_training(self, job_id: str, shop_id: str):
        """Execute full model training"""
        try:
            # Step 1: Trigger Gorse training
            await self._update_job_progress(job_id, 10.0, "Starting Gorse training...")

            training_result = await self.training_service._trigger_gorse_training(
                shop_id, "full"
            )

            if not training_result.get("success"):
                raise Exception(
                    f"Gorse training failed: {training_result.get('error')}"
                )

            # Step 2: Monitor training progress
            await self._update_job_progress(job_id, 30.0, "Training in progress...")

            await self.training_service._monitor_training_progress(
                job_id, shop_id, training_result.get("task_id")
            )

            # Step 3: Validate training results
            await self._update_job_progress(
                job_id, 80.0, "Validating training results..."
            )

            validation_result = await self.training_service._validate_training_results(
                shop_id
            )

            if not validation_result.get("success"):
                raise Exception(
                    f"Training validation failed: {validation_result.get('error')}"
                )

            # Step 4: Update model metadata
            await self._update_job_progress(job_id, 90.0, "Updating model metadata...")

            await self.training_service._update_model_metadata(
                shop_id,
                {
                    "last_training": now_utc(),
                    "training_type": "full",
                    "model_version": training_result.get("model_version"),
                    "performance_metrics": validation_result.get("metrics", {}),
                },
            )

            await self._update_job_progress(
                job_id, 100.0, "Training completed successfully"
            )

        except Exception as e:
            logger.error(f"Full training failed for job {job_id}: {str(e)}")
            raise

    async def _execute_incremental_training(self, job_id: str, shop_id: str):
        """Execute incremental model training"""
        try:
            # Step 1: Trigger incremental training
            await self._update_job_progress(
                job_id, 20.0, "Starting incremental training..."
            )

            training_result = await self.training_service._trigger_gorse_training(
                shop_id, "incremental"
            )

            if not training_result.get("success"):
                raise Exception(
                    f"Incremental training failed: {training_result.get('error')}"
                )

            # Step 2: Monitor training progress
            await self._update_job_progress(
                job_id, 50.0, "Incremental training in progress..."
            )

            await self.training_service._monitor_training_progress(
                job_id, shop_id, training_result.get("task_id")
            )

            # Step 3: Update model metadata
            await self._update_job_progress(job_id, 90.0, "Updating model metadata...")

            await self.training_service._update_model_metadata(
                shop_id,
                {
                    "last_incremental_training": now_utc(),
                    "training_type": "incremental",
                    "model_version": training_result.get("model_version"),
                },
            )

            await self._update_job_progress(
                job_id, 100.0, "Incremental training completed"
            )

        except Exception as e:
            logger.error(f"Incremental training failed for job {job_id}: {str(e)}")
            raise

    async def _execute_model_refresh(self, job_id: str, shop_id: str):
        """Execute model refresh (retrain with latest data)"""
        try:
            # Step 1: Sync latest data
            await self._update_job_progress(job_id, 10.0, "Syncing latest data...")

            from app.domains.ml.services.gorse_sync_pipeline import GorseSyncPipeline

            sync_pipeline = GorseSyncPipeline()
            await sync_pipeline.sync_all(shop_id, incremental=False)

            # Step 2: Trigger full training
            await self._update_job_progress(
                job_id, 30.0, "Starting model refresh training..."
            )

            training_result = await self.training_service._trigger_gorse_training(
                shop_id, "full"
            )

            if not training_result.get("success"):
                raise Exception(
                    f"Model refresh training failed: {training_result.get('error')}"
                )

            # Step 3: Monitor training progress
            await self._update_job_progress(
                job_id, 60.0, "Model refresh in progress..."
            )

            await self.training_service._monitor_training_progress(
                job_id, shop_id, training_result.get("task_id")
            )

            # Step 4: Update model metadata
            await self._update_job_progress(job_id, 90.0, "Updating model metadata...")

            await self.training_service._update_model_metadata(
                shop_id,
                {
                    "last_refresh": now_utc(),
                    "training_type": "refresh",
                    "model_version": training_result.get("model_version"),
                },
            )

            await self._update_job_progress(job_id, 100.0, "Model refresh completed")

        except Exception as e:
            logger.error(f"Model refresh failed for job {job_id}: {str(e)}")
            raise

    async def _execute_custom_training(
        self, job_id: str, shop_id: str, metadata: Dict[str, Any]
    ):
        """Execute custom training with specific parameters"""
        try:
            # Extract custom parameters from metadata
            training_params = metadata.get("training_params", {})
            model_type = training_params.get("model_type", "full")

            await self._update_job_progress(
                job_id, 10.0, f"Starting custom training ({model_type})..."
            )

            # Trigger custom training
            training_result = await self.training_service._trigger_gorse_training(
                shop_id, model_type
            )

            if not training_result.get("success"):
                raise Exception(
                    f"Custom training failed: {training_result.get('error')}"
                )

            # Monitor training progress
            await self._update_job_progress(
                job_id, 50.0, "Custom training in progress..."
            )

            await self.training_service._monitor_training_progress(
                job_id, shop_id, training_result.get("task_id")
            )

            # Update model metadata
            await self._update_job_progress(job_id, 90.0, "Updating model metadata...")

            await self.training_service._update_model_metadata(
                shop_id,
                {
                    "last_custom_training": now_utc(),
                    "training_type": "custom",
                    "training_params": training_params,
                    "model_version": training_result.get("model_version"),
                },
            )

            await self._update_job_progress(job_id, 100.0, "Custom training completed")

        except Exception as e:
            logger.error(f"Custom training failed for job {job_id}: {str(e)}")
            raise

    async def _update_job_status(
        self, job_id: str, status: TrainingStatus, message: str = ""
    ):
        """Update training job status"""
        try:
            db = await self.training_service._get_database()

            update_data = {
                "status": status.value,
                "statusMessage": message,
                "updatedAt": now_utc(),
            }

            if status in [
                TrainingStatus.COMPLETED,
                TrainingStatus.FAILED,
                TrainingStatus.CANCELLED,
            ]:
                update_data["completedAt"] = now_utc()

            await db.trainingjob.update(
                where={"jobId": job_id},
                data=update_data,
            )

            logger.debug(f"Updated job status: {job_id} -> {status.value} - {message}")

        except Exception as e:
            logger.error(f"Failed to update job status for {job_id}: {str(e)}")

    async def _update_job_progress(
        self, job_id: str, progress: float, message: str = ""
    ):
        """Update training job progress"""
        try:
            db = await self.training_service._get_database()

            await db.trainingjob.update(
                where={"jobId": job_id},
                data={
                    "progress": progress,
                    "statusMessage": message,
                    "updatedAt": now_utc(),
                },
            )

            logger.debug(f"Updated job progress: {job_id} -> {progress}% - {message}")

        except Exception as e:
            logger.error(f"Failed to update job progress for {job_id}: {str(e)}")

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
