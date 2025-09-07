"""
Gorse Training Service
Handles model training, progress tracking, and training job management
"""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional
from enum import Enum

import httpx
from app.core.database.simple_db_client import get_database
from app.core.logging import get_logger
from app.shared.helpers import now_utc

logger = get_logger(__name__)


class TrainingStatus(Enum):
    """Training job status enumeration"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TrainingJobType(Enum):
    """Training job type enumeration"""

    FULL_TRAINING = "full_training"
    INCREMENTAL_TRAINING = "incremental_training"
    MODEL_REFRESH = "model_refresh"
    CUSTOM_TRAINING = "custom_training"


class GorseTrainingService:
    """
    Service for managing Gorse model training jobs
    Handles training initiation, progress tracking, and status monitoring
    """

    def __init__(
        self,
        gorse_master_url: str = "http://localhost:8087",
        gorse_worker_url: str = "http://localhost:8088",
        training_timeout: int = 3600,  # 1 hour timeout
        progress_check_interval: int = 30,  # Check progress every 30 seconds
    ):
        self.gorse_master_url = gorse_master_url.rstrip("/")
        self.gorse_worker_url = gorse_worker_url.rstrip("/")
        self.training_timeout = training_timeout
        self.progress_check_interval = progress_check_interval
        self._db_client = None

    async def _get_database(self):
        """Get database connection with caching"""
        if self._db_client is None:
            self._db_client = await get_database()
        return self._db_client

    async def start_training_job(
        self,
        shop_id: str,
        job_type: TrainingJobType = TrainingJobType.FULL_TRAINING,
        trigger_source: str = "api",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Start a new training job for a shop

        Args:
            shop_id: Shop ID to train models for
            job_type: Type of training job to run
            trigger_source: Source that triggered the training (api, gorse, scheduled, etc.)
            metadata: Additional metadata for the training job

        Returns:
            job_id: Unique identifier for the training job
        """
        try:
            job_id = f"training_{shop_id}_{job_type.value}_{int(time.time())}"

            # Create training job record
            db = await self._get_database()
            training_job = await db.trainingjob.create(
                data={
                    "jobId": job_id,
                    "shopId": shop_id,
                    "jobType": job_type.value,
                    "status": TrainingStatus.PENDING.value,
                    "triggerSource": trigger_source,
                    "metadata": json.dumps(metadata or {}),
                    "startedAt": now_utc(),
                    "progress": 0.0,
                }
            )

            logger.info(
                f"Created training job {job_id} for shop {shop_id} (type: {job_type.value})"
            )

            # Start the training process asynchronously
            asyncio.create_task(self._execute_training_job(job_id, shop_id, job_type))

            return job_id

        except Exception as e:
            logger.error(f"Failed to start training job for shop {shop_id}: {str(e)}")
            raise

    async def _execute_training_job(
        self,
        job_id: str,
        shop_id: str,
        job_type: TrainingJobType,
    ):
        """
        Execute the actual training job
        This runs asynchronously and updates the job status
        """
        db = await self._get_database()

        try:
            # Update status to running
            await db.trainingjob.update(
                where={"jobId": job_id},
                data={
                    "status": TrainingStatus.RUNNING.value,
                    "progress": 0.0,
                },
            )

            logger.info(f"Starting training execution for job {job_id}")

            # Execute training based on job type
            if job_type == TrainingJobType.FULL_TRAINING:
                await self._execute_full_training(job_id, shop_id)
            elif job_type == TrainingJobType.INCREMENTAL_TRAINING:
                await self._execute_incremental_training(job_id, shop_id)
            elif job_type == TrainingJobType.MODEL_REFRESH:
                await self._execute_model_refresh(job_id, shop_id)
            else:
                raise ValueError(f"Unsupported job type: {job_type}")

            # Mark as completed
            await db.trainingjob.update(
                where={"jobId": job_id},
                data={
                    "status": TrainingStatus.COMPLETED.value,
                    "progress": 100.0,
                    "completedAt": now_utc(),
                },
            )

            logger.info(f"Training job {job_id} completed successfully")

        except Exception as e:
            logger.error(f"Training job {job_id} failed: {str(e)}")

            # Mark as failed
            await db.trainingjob.update(
                where={"jobId": job_id},
                data={
                    "status": TrainingStatus.FAILED.value,
                    "errorMessage": str(e),
                    "completedAt": now_utc(),
                },
            )

    async def _execute_full_training(self, job_id: str, shop_id: str):
        """Execute full model training for a shop"""
        db = await self._get_database()

        try:
            # Step 1: Trigger Gorse training
            await self._update_progress(job_id, 10.0, "Starting Gorse training...")

            training_result = await self._trigger_gorse_training(shop_id, "full")

            if not training_result.get("success"):
                raise Exception(
                    f"Gorse training failed: {training_result.get('error')}"
                )

            # Step 2: Monitor training progress
            await self._update_progress(job_id, 30.0, "Training in progress...")

            await self._monitor_training_progress(
                job_id, shop_id, training_result.get("task_id")
            )

            # Step 3: Validate training results
            await self._update_progress(job_id, 80.0, "Validating training results...")

            validation_result = await self._validate_training_results(shop_id)

            if not validation_result.get("success"):
                raise Exception(
                    f"Training validation failed: {validation_result.get('error')}"
                )

            # Step 4: Update model metadata
            await self._update_progress(job_id, 90.0, "Updating model metadata...")

            await self._update_model_metadata(
                shop_id,
                {
                    "last_training": now_utc(),
                    "training_type": "full",
                    "model_version": training_result.get("model_version"),
                    "performance_metrics": validation_result.get("metrics", {}),
                },
            )

            await self._update_progress(
                job_id, 100.0, "Training completed successfully"
            )

        except Exception as e:
            logger.error(f"Full training failed for job {job_id}: {str(e)}")
            raise

    async def _execute_incremental_training(self, job_id: str, shop_id: str):
        """Execute incremental model training for a shop"""
        db = await self._get_database()

        try:
            # Step 1: Trigger incremental training
            await self._update_progress(
                job_id, 20.0, "Starting incremental training..."
            )

            training_result = await self._trigger_gorse_training(shop_id, "incremental")

            if not training_result.get("success"):
                raise Exception(
                    f"Incremental training failed: {training_result.get('error')}"
                )

            # Step 2: Monitor training progress
            await self._update_progress(
                job_id, 50.0, "Incremental training in progress..."
            )

            await self._monitor_training_progress(
                job_id, shop_id, training_result.get("task_id")
            )

            # Step 3: Update model metadata
            await self._update_progress(job_id, 90.0, "Updating model metadata...")

            await self._update_model_metadata(
                shop_id,
                {
                    "last_incremental_training": now_utc(),
                    "training_type": "incremental",
                    "model_version": training_result.get("model_version"),
                },
            )

            await self._update_progress(job_id, 100.0, "Incremental training completed")

        except Exception as e:
            logger.error(f"Incremental training failed for job {job_id}: {str(e)}")
            raise

    async def _execute_model_refresh(self, job_id: str, shop_id: str):
        """Execute model refresh (retrain with latest data)"""
        db = await self._get_database()

        try:
            # Step 1: Sync latest data
            await self._update_progress(job_id, 10.0, "Syncing latest data...")

            from app.domains.ml.services.gorse_sync_pipeline import GorseSyncPipeline

            sync_pipeline = GorseSyncPipeline()
            await sync_pipeline.sync_all(shop_id, incremental=False)

            # Step 2: Trigger full training
            await self._update_progress(
                job_id, 30.0, "Starting model refresh training..."
            )

            training_result = await self._trigger_gorse_training(shop_id, "full")

            if not training_result.get("success"):
                raise Exception(
                    f"Model refresh training failed: {training_result.get('error')}"
                )

            # Step 3: Monitor training progress
            await self._update_progress(job_id, 60.0, "Model refresh in progress...")

            await self._monitor_training_progress(
                job_id, shop_id, training_result.get("task_id")
            )

            # Step 4: Update model metadata
            await self._update_progress(job_id, 90.0, "Updating model metadata...")

            await self._update_model_metadata(
                shop_id,
                {
                    "last_refresh": now_utc(),
                    "training_type": "refresh",
                    "model_version": training_result.get("model_version"),
                },
            )

            await self._update_progress(job_id, 100.0, "Model refresh completed")

        except Exception as e:
            logger.error(f"Model refresh failed for job {job_id}: {str(e)}")
            raise

    async def _trigger_gorse_training(
        self, shop_id: str, training_type: str
    ) -> Dict[str, Any]:
        """Trigger training in Gorse and return the result"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Trigger training via Gorse API
                response = await client.post(
                    f"{self.gorse_master_url}/api/train",
                    json={
                        "shop_id": shop_id,
                        "training_type": training_type,
                    },
                )

                if response.status_code == 200:
                    result = response.json()
                    return {
                        "success": True,
                        "task_id": result.get("task_id"),
                        "model_version": result.get("model_version"),
                        "message": result.get("message"),
                    }
                else:
                    return {
                        "success": False,
                        "error": f"HTTP {response.status_code}: {response.text}",
                    }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def _monitor_training_progress(self, job_id: str, shop_id: str, task_id: str):
        """Monitor training progress and update job status"""
        start_time = time.time()

        while time.time() - start_time < self.training_timeout:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    # Check training status
                    response = await client.get(
                        f"{self.gorse_master_url}/api/train/status/{task_id}"
                    )

                    if response.status_code == 200:
                        status_data = response.json()
                        progress = status_data.get("progress", 0)
                        status = status_data.get("status", "unknown")

                        # Update progress (scale to 30-80% range for monitoring phase)
                        scaled_progress = 30 + (progress * 0.5)
                        await self._update_progress(
                            job_id,
                            scaled_progress,
                            f"Training status: {status} ({progress}%)",
                        )

                        if status == "completed":
                            return
                        elif status == "failed":
                            raise Exception(
                                f"Training failed: {status_data.get('error')}"
                            )

                    # Wait before next check
                    await asyncio.sleep(self.progress_check_interval)

            except Exception as e:
                logger.warning(f"Error monitoring training progress: {str(e)}")
                await asyncio.sleep(self.progress_check_interval)

        # Timeout reached
        raise Exception(f"Training timeout after {self.training_timeout} seconds")

    async def _validate_training_results(self, shop_id: str) -> Dict[str, Any]:
        """Validate training results and return performance metrics"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Get model performance metrics
                response = await client.get(
                    f"{self.gorse_master_url}/api/model/metrics/{shop_id}"
                )

                if response.status_code == 200:
                    metrics = response.json()
                    return {
                        "success": True,
                        "metrics": metrics,
                    }
                else:
                    return {
                        "success": False,
                        "error": f"Failed to get metrics: HTTP {response.status_code}",
                    }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }

    async def _update_model_metadata(self, shop_id: str, metadata: Dict[str, Any]):
        """Update model metadata in the database"""
        db = await self._get_database()

        try:
            # Update or create model metadata record
            await db.modelmetadata.upsert(
                where={"shopId": shop_id},
                data={
                    "create": {
                        "shopId": shop_id,
                        "metadata": json.dumps(metadata),
                        "updatedAt": now_utc(),
                    },
                    "update": {
                        "metadata": json.dumps(metadata),
                        "updatedAt": now_utc(),
                    },
                },
            )

        except Exception as e:
            logger.error(
                f"Failed to update model metadata for shop {shop_id}: {str(e)}"
            )
            raise

    async def _update_progress(self, job_id: str, progress: float, message: str = ""):
        """Update training job progress"""
        db = await self._get_database()

        try:
            await db.trainingjob.update(
                where={"jobId": job_id},
                data={
                    "progress": progress,
                    "statusMessage": message,
                    "updatedAt": now_utc(),
                },
            )

            logger.debug(f"Updated progress for job {job_id}: {progress}% - {message}")

        except Exception as e:
            logger.error(f"Failed to update progress for job {job_id}: {str(e)}")

    async def get_training_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a training job"""
        db = await self._get_database()

        try:
            job = await db.trainingjob.find_unique(where={"jobId": job_id})

            if job:
                return {
                    "job_id": job.jobId,
                    "shop_id": job.shopId,
                    "job_type": job.jobType,
                    "status": job.status,
                    "progress": job.progress,
                    "status_message": job.statusMessage,
                    "trigger_source": job.triggerSource,
                    "metadata": json.loads(job.metadata) if job.metadata else {},
                    "started_at": job.startedAt,
                    "completed_at": job.completedAt,
                    "error_message": job.errorMessage,
                    "created_at": job.createdAt,
                    "updated_at": job.updatedAt,
                }
            return None

        except Exception as e:
            logger.error(f"Failed to get training job status for {job_id}: {str(e)}")
            return None

    async def get_shop_training_history(
        self, shop_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get training history for a shop"""
        db = await self._get_database()

        try:
            jobs = await db.trainingjob.find_many(
                where={"shopId": shop_id},
                order={"createdAt": "desc"},
                take=limit,
            )

            return [
                {
                    "job_id": job.jobId,
                    "job_type": job.jobType,
                    "status": job.status,
                    "progress": job.progress,
                    "trigger_source": job.triggerSource,
                    "started_at": job.startedAt,
                    "completed_at": job.completedAt,
                    "created_at": job.createdAt,
                }
                for job in jobs
            ]

        except Exception as e:
            logger.error(f"Failed to get training history for shop {shop_id}: {str(e)}")
            return []

    async def cancel_training_job(self, job_id: str) -> bool:
        """Cancel a running training job"""
        db = await self._get_database()

        try:
            # Update job status to cancelled
            await db.trainingjob.update(
                where={"jobId": job_id},
                data={
                    "status": TrainingStatus.CANCELLED.value,
                    "completedAt": now_utc(),
                    "statusMessage": "Job cancelled by user",
                },
            )

            logger.info(f"Cancelled training job {job_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel training job {job_id}: {str(e)}")
            return False
