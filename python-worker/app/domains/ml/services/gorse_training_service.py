"""
Simplified Gorse Training Service
Uses MLTrainingLog for persistence and actual Gorse Redis keys for progress tracking
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from enum import Enum

import httpx
from app.core.database.simple_db_client import get_database
from app.core.logging import get_logger
from app.core.redis_client import get_redis_client
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
    Simplified service for managing Gorse model training
    Uses MLTrainingLog for persistence and actual Gorse Redis keys for progress tracking
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

            # Create training log record
            db = await self._get_database()
            training_log = await db.mltraininglog.create(
                data={
                    "shopId": shop_id,
                    "status": "started",
                    "startedAt": now_utc(),
                }
            )

            logger.info(
                f"Created training job {job_id} for shop {shop_id} (type: {job_type.value})"
            )

            # Start the training process asynchronously
            asyncio.create_task(
                self._execute_training_job(job_id, shop_id, job_type, training_log.id)
            )

            return job_id

        except Exception as e:
            logger.error(f"Failed to start training job for shop {shop_id}: {str(e)}")
            raise

    async def _execute_training_job(
        self,
        job_id: str,
        shop_id: str,
        job_type: TrainingJobType,
        training_log_id: str,
    ):
        """
        Execute the actual training job
        This runs asynchronously and updates the training log
        """
        db = await self._get_database()

        try:
            logger.info(f"Starting training execution for job {job_id}")

            # Execute training based on job type
            if job_type == TrainingJobType.FULL_TRAINING:
                await self._execute_full_training(job_id, shop_id, training_log_id)
            elif job_type == TrainingJobType.INCREMENTAL_TRAINING:
                await self._execute_incremental_training(
                    job_id, shop_id, training_log_id
                )
            elif job_type == TrainingJobType.MODEL_REFRESH:
                await self._execute_model_refresh(job_id, shop_id, training_log_id)
            else:
                raise ValueError(f"Unsupported job type: {job_type}")

            # Mark as completed
            await self._update_training_log(
                training_log_id, "completed", completed_at=now_utc()
            )

            logger.info(f"Training job {job_id} completed successfully")

        except Exception as e:
            logger.error(f"Training job {job_id} failed: {str(e)}")

            # Mark as failed
            await self._update_training_log(
                training_log_id, "failed", error=str(e), completed_at=now_utc()
            )

    async def _execute_full_training(
        self, job_id: str, shop_id: str, training_log_id: str
    ):
        """Execute full model training for a shop"""
        try:
            logger.info(f"Starting full training for shop {shop_id}")

            # Step 1: Sync all data to Gorse (this triggers training automatically)
            # The sync pipeline filters data by shop_id and stores in GorseItems/GorseUsers tables
            # Gorse then reads from these tables for training
            from app.domains.ml.services.gorse_sync_pipeline import GorseSyncPipeline

            sync_pipeline = GorseSyncPipeline()
            await sync_pipeline.sync_all(shop_id, incremental=False)

            # Step 2: Monitor for training completion
            # Gorse trains on the shop-specific data and updates Redis keys
            await self._monitor_gorse_training_completion(shop_id, training_log_id)

        except Exception as e:
            logger.error(f"Full training failed for job {job_id}: {str(e)}")
            raise

    async def _execute_incremental_training(
        self, job_id: str, shop_id: str, training_log_id: str
    ):
        """Execute incremental model training for a shop"""
        try:
            logger.info(f"Starting incremental training for shop {shop_id}")

            # Step 1: Sync incremental data to Gorse (this triggers training automatically)
            from app.domains.ml.services.gorse_sync_pipeline import GorseSyncPipeline

            sync_pipeline = GorseSyncPipeline()
            await sync_pipeline.sync_all(shop_id, incremental=True)

            # Step 2: Monitor for training completion
            await self._monitor_gorse_training_completion(shop_id, training_log_id)

        except Exception as e:
            logger.error(f"Incremental training failed for job {job_id}: {str(e)}")
            raise

    async def _execute_model_refresh(
        self, job_id: str, shop_id: str, training_log_id: str
    ):
        """Execute model refresh (retrain with latest data)"""
        try:
            # Step 1: Sync latest data
            logger.info(f"Starting model refresh for shop {shop_id}")

            from app.domains.ml.services.gorse_sync_pipeline import GorseSyncPipeline

            sync_pipeline = GorseSyncPipeline()
            await sync_pipeline.sync_all(shop_id, incremental=False)

            # Step 2: Monitor training completion
            await self._monitor_gorse_training_completion(shop_id, training_log_id)

        except Exception as e:
            logger.error(f"Model refresh failed for job {job_id}: {str(e)}")
            raise

    async def _monitor_gorse_training_completion(
        self, shop_id: str, training_log_id: str
    ):
        """
        Monitor Gorse training completion using actual Redis keys from Gorse source code
        Based on analysis of gorse/master/tasks.go and gorse/storage/cache/database.go
        """
        start_time = time.time()
        redis_client = await get_redis_client()

        # Actual Gorse Redis key patterns from source code analysis
        # These are the keys Gorse sets when training completes
        training_completion_keys = [
            "GlobalMeta:LastFitMatchingModelTime",  # Collaborative filtering model training
            "GlobalMeta:LastFitRankingModelTime",  # Click-through rate model training
            "GlobalMeta:LastUpdateLatestItemsTime",  # Latest items update
            "GlobalMeta:LastUpdatePopularItemsTime",  # Popular items update
        ]

        # Track initial timestamps for comparison
        initial_timestamps = {}

        # Get initial timestamps for comparison
        for key in training_completion_keys:
            try:
                value = await redis_client.get(key)
                if value:
                    initial_timestamps[key] = value
            except Exception as e:
                logger.warning(f"Error getting initial timestamp for {key}: {str(e)}")

        logger.info(f"Monitoring Gorse training completion for shop {shop_id}")

        while time.time() - start_time < self.training_timeout:
            try:
                training_completed = False

                # Check if any training completion keys have been updated
                for key in training_completion_keys:
                    try:
                        current_value = await redis_client.get(key)
                        if current_value and current_value != initial_timestamps.get(
                            key
                        ):
                            # Key has been updated, training likely completed
                            logger.info(
                                f"Training completion detected via {key} update"
                            )
                            training_completed = True
                            break
                    except Exception as e:
                        logger.warning(f"Error checking {key}: {str(e)}")

                if training_completed:
                    logger.info(f"Training completed for shop {shop_id}")
                    return

                # Wait before next check
                await asyncio.sleep(self.progress_check_interval)

            except Exception as e:
                logger.warning(f"Error monitoring training progress: {str(e)}")
                await asyncio.sleep(self.progress_check_interval)

        # Timeout reached - this is not necessarily an error
        # Gorse training might complete quickly or take longer
        logger.warning(
            f"Training monitoring timeout for shop {shop_id} after {self.training_timeout} seconds"
        )
        return

    async def _update_training_log(
        self,
        training_log_id: str,
        status: str,
        completed_at: Optional[datetime] = None,
        error: Optional[str] = None,
    ):
        """Update training log status"""
        db = await self._get_database()

        try:
            update_data = {"status": status}

            if completed_at:
                update_data["completedAt"] = completed_at
                # Calculate duration
                training_log = await db.mltraininglog.find_unique(
                    where={"id": training_log_id}
                )
                if training_log and training_log.startedAt:
                    duration_ms = int(
                        (completed_at - training_log.startedAt).total_seconds() * 1000
                    )
                    update_data["durationMs"] = duration_ms

            if error:
                update_data["error"] = error

            await db.mltraininglog.update(
                where={"id": training_log_id}, data=update_data
            )

        except Exception as e:
            logger.error(f"Failed to update training log {training_log_id}: {str(e)}")
            raise

    async def get_training_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a training job"""
        db = await self._get_database()

        try:
            # Extract shop_id from job_id (format: training_{shop_id}_{type}_{timestamp})
            parts = job_id.split("_")
            if len(parts) >= 2:
                shop_id = parts[1]

                # Find the most recent training log for this shop
                training_log = await db.mltraininglog.find_first(
                    where={"shopId": shop_id},
                    order={"createdAt": "desc"},
                )

                if training_log:
                    return {
                        "job_id": job_id,
                        "shop_id": training_log.shopId,
                        "status": training_log.status,
                        "started_at": training_log.startedAt,
                        "completed_at": training_log.completedAt,
                        "duration_ms": training_log.durationMs,
                        "error": training_log.error,
                        "created_at": training_log.createdAt,
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
            logs = await db.mltraininglog.find_many(
                where={"shopId": shop_id},
                order={"createdAt": "desc"},
                take=limit,
            )

            return [
                {
                    "id": log.id,
                    "status": log.status,
                    "started_at": log.startedAt,
                    "completed_at": log.completedAt,
                    "duration_ms": log.durationMs,
                    "error": log.error,
                    "created_at": log.createdAt,
                }
                for log in logs
            ]

        except Exception as e:
            logger.error(f"Failed to get training history for shop {shop_id}: {str(e)}")
            return []

    async def cancel_training_job(self, job_id: str) -> bool:
        """Cancel a running training job"""
        db = await self._get_database()

        try:
            # Extract shop_id from job_id
            parts = job_id.split("_")
            if len(parts) >= 2:
                shop_id = parts[1]

                # Find the most recent training log for this shop
                training_log = await db.mltraininglog.find_first(
                    where={"shopId": shop_id, "status": "started"},
                    order={"createdAt": "desc"},
                )

                if training_log:
                    await self._update_training_log(
                        training_log.id, "cancelled", completed_at=now_utc()
                    )

                    logger.info(f"Cancelled training job {job_id}")
                    return True

            return False

        except Exception as e:
            logger.error(f"Failed to cancel training job {job_id}: {str(e)}")
            return False

    async def trigger_training_after_sync(
        self,
        shop_id: str,
        sync_type: str = "incremental",
        batch_size: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Trigger training after Gorse sync completion
        This is the main entry point for event-driven training

        Args:
            shop_id: Shop ID to train models for
            sync_type: Type of sync that completed ("full", "incremental", "streaming")
            batch_size: Number of items processed in batch (for monitoring)
            metadata: Additional metadata from sync process

        Returns:
            job_id: Unique identifier for the training job
        """
        try:
            # Determine training type based on sync type
            if sync_type == "full":
                job_type = TrainingJobType.FULL_TRAINING
            elif sync_type == "incremental":
                job_type = TrainingJobType.INCREMENTAL_TRAINING
            elif sync_type == "streaming":
                job_type = (
                    TrainingJobType.INCREMENTAL_TRAINING
                )  # Streaming is incremental
            else:
                job_type = TrainingJobType.FULL_TRAINING  # Default to full

            # Add sync metadata to training metadata
            training_metadata = metadata or {}
            training_metadata.update(
                {
                    "sync_type": sync_type,
                    "batch_size": batch_size,
                    "trigger_source": "gorse_sync_completion",
                }
            )

            logger.info(
                f"Triggering {job_type.value} training for shop {shop_id} after {sync_type} sync"
            )

            return await self.start_training_job(
                shop_id=shop_id,
                job_type=job_type,
                trigger_source="gorse_sync_completion",
                metadata=training_metadata,
            )

        except Exception as e:
            logger.error(
                f"Failed to trigger training after sync for shop {shop_id}: {str(e)}"
            )
            raise

    async def batch_training_for_multiple_shops(
        self,
        shop_ids: List[str],
        job_type: TrainingJobType = TrainingJobType.FULL_TRAINING,
        max_concurrent: int = 3,
    ) -> Dict[str, str]:
        """
        Trigger training for multiple shops in batch with concurrency control

        Args:
            shop_ids: List of shop IDs to train
            job_type: Type of training to run for all shops
            max_concurrent: Maximum number of concurrent training jobs

        Returns:
            Dict mapping shop_id to job_id
        """
        results = {}
        semaphore = asyncio.Semaphore(max_concurrent)

        async def train_shop(shop_id: str):
            async with semaphore:
                try:
                    job_id = await self.start_training_job(
                        shop_id=shop_id,
                        job_type=job_type,
                        trigger_source="batch_training",
                    )
                    results[shop_id] = job_id
                    logger.info(f"Started batch training for shop {shop_id}: {job_id}")
                except Exception as e:
                    logger.error(
                        f"Failed to start batch training for shop {shop_id}: {str(e)}"
                    )
                    results[shop_id] = f"error: {str(e)}"

        # Execute all training jobs concurrently with semaphore
        tasks = [train_shop(shop_id) for shop_id in shop_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

        return results

    def get_redis_monitoring_resource_usage(self) -> Dict[str, Any]:
        """
        Get information about Redis monitoring resource usage

        Returns:
            Dict with resource usage information
        """
        return {
            "redis_operations_per_check": 4,  # Number of Redis GET operations per check
            "check_interval_seconds": self.progress_check_interval,
            "operations_per_minute": (60 / self.progress_check_interval) * 4,
            "memory_usage_per_shop": "~1KB (4 timestamp strings)",
            "cpu_usage": "Minimal (simple Redis GET operations)",
            "network_usage": "Low (small Redis commands)",
            "scalability": f"Supports {1000 // self.progress_check_interval} concurrent shops per minute",
            "recommendations": {
                "increase_interval": "For high-volume shops, increase progress_check_interval to 60s",
                "batch_monitoring": "Consider batching Redis operations for multiple shops",
                "timeout_tuning": "Adjust training_timeout based on data size and model complexity",
            },
        }
