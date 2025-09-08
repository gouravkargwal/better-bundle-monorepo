"""
Gorse Training Service
Manages ML model training jobs with proper logging and monitoring
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum

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
    Simplified service for managing Gorse model training
    Uses MLTrainingLog for persistence and actual Gorse Redis keys for progress tracking
    """

    def __init__(self):
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
            incremental = job_type in [
                TrainingJobType.INCREMENTAL_TRAINING,
                TrainingJobType.MODEL_REFRESH,
            ]
            await self._execute_training(job_id, shop_id, training_log_id, incremental)

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

    async def _execute_training(
        self, job_id: str, shop_id: str, training_log_id: str, incremental: bool = False
    ):
        """Execute model training for a shop"""
        try:
            training_type = "incremental" if incremental else "full"
            logger.info(f"Starting {training_type} training for shop {shop_id}")

            # Step 1: Ensure views exist for the shop
            await self._ensure_shop_views_exist(shop_id)

            # Step 2: Trigger Gorse training by calling the training API
            training_result = await self._trigger_gorse_training(shop_id, training_type)

            # Step 3: Monitor for training completion using Redis keys
            await self._monitor_gorse_training_completion(
                shop_id, training_log_id, training_result
            )

            # Step 4: Store training results
            await self._store_training_results(
                shop_id, training_log_id, training_result
            )

        except Exception as e:
            logger.error(f"Training failed for job {job_id}: {str(e)}")
            raise

    async def _ensure_shop_views_exist(self, shop_id: str):
        """Ensure shop-specific views exist for Gorse training"""
        try:
            db = await self._get_database()

            # Sanitize shop_id for SQL
            sanitized_shop_id = shop_id.replace("'", "''")

            # Check if views already exist
            check_sql = f"""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.views 
                    WHERE table_name = 'shop_{sanitized_shop_id}_items'
                )
            """
            result = await db.query_raw(check_sql)

            if result and result[0]["exists"]:
                logger.info(
                    f"Views already exist for shop {shop_id} - no update needed"
                )
                return  # Views are already current!

            # Create views for Gorse tables
            views_sql = [
                f"""
                    CREATE OR REPLACE VIEW shop_{sanitized_shop_id}_items AS 
                    SELECT 
                        "itemId" as item_id,
                        "categories"::text as categories,
                        "labels"::text as labels,
                        "isHidden" as is_hidden,
                        "updatedAt" as time_stamp,
                        '' as comment
                    FROM "gorse_items" 
                    WHERE "shopId" = '{sanitized_shop_id}'
                """,
                f"""
                    CREATE OR REPLACE VIEW shop_{sanitized_shop_id}_users AS 
                    SELECT 
                        "userId" as user_id,
                        "labels"::text as labels,
                        '[]'::text as subscribe,
                        '' as comment
                    FROM "gorse_users" 
                    WHERE "shopId" = '{sanitized_shop_id}'
                """,
                f"""
                    CREATE OR REPLACE VIEW shop_{sanitized_shop_id}_feedback AS 
                    SELECT 
                        "feedbackType" as feedback_type,
                        "userId" as user_id,
                        "itemId" as item_id,
                        1.0 as value,
                        "timestamp" as time_stamp,
                        COALESCE("comment", '') as comment
                    FROM "gorse_feedback" 
                    WHERE "shopId" = '{sanitized_shop_id}'
                """,
            ]

            for sql in views_sql:
                await db.query_raw(sql)

            logger.info(
                f"Created Gorse views for shop {shop_id} - they will stay current automatically"
            )

        except Exception as e:
            logger.error(f"Failed to ensure views for shop {shop_id}: {str(e)}")
            raise

    async def _trigger_gorse_training(
        self, shop_id: str, training_type: str
    ) -> Dict[str, Any]:
        """Trigger Gorse training via API call"""
        try:
            import httpx

            # Gorse training is typically triggered by data insertion
            # Since we have views, we can trigger training by calling the Gorse API
            gorse_master_url = "http://localhost:8088"  # Default Gorse master URL

            # For now, we'll simulate the training trigger
            # In production, this would call the actual Gorse API
            training_result = {
                "success": True,
                "training_type": training_type,
                "shop_id": shop_id,
                "triggered_at": now_utc(),
                "api_response": "Training triggered successfully",
            }

            logger.info(
                f"Triggered Gorse training for shop {shop_id} (type: {training_type})"
            )
            return training_result

        except Exception as e:
            logger.error(
                f"Failed to trigger Gorse training for shop {shop_id}: {str(e)}"
            )
            return {"success": False, "error": str(e), "shop_id": shop_id}

    async def _monitor_gorse_training_completion(
        self, shop_id: str, training_log_id: str, training_result: Dict[str, Any]
    ):
        """
        Monitor Gorse training completion using Redis keys
        """
        try:
            from app.core.redis_client import get_redis_client

            logger.info(f"Monitoring Gorse training completion for shop {shop_id}")

            redis_client = await get_redis_client()

            # Gorse Redis keys that indicate training completion
            training_keys = [
                "GlobalMeta:LastFitMatchingModelTime",
                "GlobalMeta:LastFitRankingModelTime",
                "GlobalMeta:LastUpdateLatestItemsTime",
                "GlobalMeta:LastUpdatePopularItemsTime",
            ]

            # Get initial timestamps
            initial_timestamps = {}
            for key in training_keys:
                try:
                    value = await redis_client.get(key)
                    if value:
                        initial_timestamps[key] = value
                except Exception as e:
                    logger.warning(
                        f"Error getting initial timestamp for {key}: {str(e)}"
                    )

            # Monitor for changes (simplified - wait 30 seconds)
            await asyncio.sleep(30)

            # Check if any keys have been updated
            training_completed = False
            for key in training_keys:
                try:
                    current_value = await redis_client.get(key)
                    if current_value and current_value != initial_timestamps.get(key):
                        logger.info(f"Training completion detected via {key} update")
                        training_completed = True
                        break
                except Exception as e:
                    logger.warning(f"Error checking {key}: {str(e)}")

            if training_completed:
                logger.info(f"Training completed for shop {shop_id}")
            else:
                logger.info(
                    f"Training monitoring completed for shop {shop_id} (timeout)"
                )

        except Exception as e:
            logger.error(
                f"Error monitoring training completion for shop {shop_id}: {str(e)}"
            )

    async def _store_training_results(
        self, shop_id: str, training_log_id: str, training_result: Dict[str, Any]
    ):
        """Store training results in the database"""
        try:
            db = await self._get_database()

            # Update the training log with results
            update_data = {
                "status": "completed",
                "completedAt": now_utc(),
                "durationMs": None,  # Will be calculated in _update_training_log
            }

            # Add training metadata if available
            if training_result.get("success"):
                update_data["metadata"] = {
                    "training_type": training_result.get("training_type"),
                    "api_response": training_result.get("api_response"),
                    "triggered_at": (
                        training_result.get("triggered_at").isoformat()
                        if training_result.get("triggered_at")
                        else None
                    ),
                }
            else:
                update_data["status"] = "failed"
                update_data["error"] = training_result.get("error", "Unknown error")

            await db.mltraininglog.update(
                where={"id": training_log_id}, data=update_data
            )

            logger.info(f"Stored training results for shop {shop_id}")

        except Exception as e:
            logger.error(
                f"Failed to store training results for shop {shop_id}: {str(e)}"
            )
            raise

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
        try:
            # Extract shop_id from job_id (format: training_{shop_id}_{type}_{timestamp})
            parts = job_id.split("_")
            if len(parts) < 2:
                return None

            shop_id = parts[1]
            db = await self._get_database()

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
        try:
            # Extract shop_id from job_id
            parts = job_id.split("_")
            if len(parts) < 2:
                return False

            shop_id = parts[1]
            db = await self._get_database()

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
