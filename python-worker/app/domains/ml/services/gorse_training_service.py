"""
Gorse Training Service
Manages data pushing to Gorse API which automatically triggers training
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum

from app.core.database.simple_db_client import get_database
from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.shared.gorse_api_client import GorseApiClient

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
    Service for pushing data to Gorse API which automatically triggers training
    Reads from bridge tables (gorse_users, gorse_items, gorse_feedback) and pushes to Gorse
    """

    def __init__(
        self,
        gorse_base_url: str = "http://localhost:8088",
        gorse_api_key: Optional[str] = None,
    ):
        """
        Initialize Gorse training service

        Args:
            gorse_base_url: Gorse master server URL
            gorse_api_key: Optional API key for Gorse authentication
        """
        self._db_client = None
        self.gorse_client = GorseApiClient(
            base_url=gorse_base_url, api_key=gorse_api_key
        )
        self.batch_size = 100  # Batch size for API calls

    async def _get_database(self):
        """Get database connection with caching"""
        if self._db_client is None:
            self._db_client = await get_database()
        return self._db_client

    async def push_data_to_gorse(
        self,
        shop_id: str,
        job_type: TrainingJobType = TrainingJobType.FULL_TRAINING,
        trigger_source: str = "api",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Push all data for a shop to Gorse API, which automatically triggers training

        Args:
            shop_id: Shop ID to push data for
            job_type: Type of data push job
            trigger_source: Source that triggered the data push
            metadata: Additional metadata for the job

        Returns:
            job_id: Unique identifier for the data push job
        """
        try:
            job_id = f"data_push_{shop_id}_{job_type.value}_{int(time.time())}"

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
                f"Created data push job {job_id} for shop {shop_id} (type: {job_type.value})"
            )

            # Start the data push process asynchronously
            asyncio.create_task(
                self._execute_data_push_job(job_id, shop_id, job_type, training_log.id)
            )

            return job_id

        except Exception as e:
            logger.error(f"Failed to start data push job for shop {shop_id}: {str(e)}")
            raise

    async def _execute_data_push_job(
        self,
        job_id: str,
        shop_id: str,
        job_type: TrainingJobType,
        training_log_id: str,
    ):
        """
        Execute the data push job to Gorse API
        """
        try:
            logger.info(f"Starting data push job {job_id} for shop {shop_id}")

            # Update training log status
            db = await self._get_database()
            await db.mltraininglog.update(
                where={"id": training_log_id},
                data={"status": "running"},
            )

            # Step 1: Check Gorse API health
            health_check = await self.gorse_client.health_check()
            if not health_check["success"]:
                raise Exception(
                    f"Gorse API is not healthy: {health_check.get('error', 'Unknown error')}"
                )

            # Step 2: Get last push timestamps for incremental logic
            last_push_info = await self._get_last_push_timestamps(shop_id)

            # Step 3: Push all data types incrementally using unified method
            data_types = ["users", "items", "feedback"]
            results = {}

            for data_type in data_types:
                result = await self._push_data_incremental(
                    data_type, shop_id, training_log_id, last_push_info
                )
                results[data_type] = result
                logger.info(f"Pushed {result['pushed']} {data_type} for shop {shop_id}")

            # Step 4: Update training log with success
            total_pushed = sum(result["pushed"] for result in results.values())

            await db.mltraininglog.update(
                where={"id": training_log_id},
                data={
                    "status": "completed",
                    "completedAt": now_utc(),
                    "usersPushed": results["users"]["pushed"],
                    "itemsPushed": results["items"]["pushed"],
                    "feedbackPushed": results["feedback"]["pushed"],
                    "totalPushed": total_pushed,
                    "jobType": job_type.value,
                    "pushStrategy": "incremental",
                },
            )

            logger.info(
                f"Data push job {job_id} completed successfully. Total records pushed: {total_pushed}"
            )

        except Exception as e:
            logger.error(f"Data push job {job_id} failed: {str(e)}")
            try:
                db = await self._get_database()
                await db.mltraininglog.update(
                    where={"id": training_log_id},
                    data={
                        "status": "failed",
                        "completedAt": now_utc(),
                        "error": str(e),
                    },
                )
            except Exception as log_error:
                logger.error(f"Failed to update training log: {str(log_error)}")

    async def _get_last_push_timestamps(self, shop_id: str) -> Optional[Dict[str, Any]]:
        """Get the last push timestamps for a shop from training logs"""
        try:
            db = await self._get_database()

            # Get the most recent training log (regardless of status)
            last_log = await db.mltraininglog.find_first(
                where={"shopId": shop_id}, order={"startedAt": "desc"}
            )

            if last_log:
                return {
                    "usersLastPushAt": last_log.usersLastPushAt,
                    "itemsLastPushAt": last_log.itemsLastPushAt,
                    "feedbackLastPushAt": last_log.feedbackLastPushAt,
                }

            return None

        except Exception as e:
            logger.error(
                f"Failed to get last push timestamps for shop {shop_id}: {str(e)}"
            )
            return None

    async def _push_data_incremental(
        self,
        data_type: str,
        shop_id: str,
        training_log_id: str,
        last_push_info: Optional[Dict],
    ) -> Dict[str, Any]:
        """Unified incremental data push method - DRY implementation"""

        # Configuration for each data type
        configs = {
            "users": {
                "table": "gorseusers",
                "timestamp_field": "updatedAt",
                "last_push_key": "usersLastPushAt",
                "converter": self._convert_user_to_gorse_format,
                "api_method": "users",
            },
            "items": {
                "table": "gorseitems",
                "timestamp_field": "updatedAt",
                "last_push_key": "itemsLastPushAt",
                "converter": self._convert_item_to_gorse_format,
                "api_method": "items",
            },
            "feedback": {
                "table": "gorsefeedback",
                "timestamp_field": "timestamp",
                "last_push_key": "feedbackLastPushAt",
                "converter": self._convert_feedback_to_gorse_format,
                "api_method": "feedback",
            },
        }

        if data_type not in configs:
            return {
                "pushed": 0,
                "success": False,
                "error": f"Unknown data type: {data_type}",
            }

        config = configs[data_type]

        try:
            db = await self._get_database()
            total_pushed = 0
            offset = 0

            # Determine the cutoff timestamp
            if last_push_info and last_push_info.get(config["last_push_key"]):
                cutoff_timestamp = last_push_info[config["last_push_key"]]
                logger.info(
                    f"Incremental {data_type} push for shop {shop_id} since {cutoff_timestamp}"
                )
            else:
                # First time - push all data
                cutoff_timestamp = datetime.min
                logger.info(
                    f"First {data_type} push for shop {shop_id} - pushing all {data_type}"
                )

            while True:
                # Get data updated since last push
                where_clause = {
                    "shopId": shop_id,
                    config["timestamp_field"]: {"gt": cutoff_timestamp},
                }

                data_records = await getattr(db, config["table"]).find_many(
                    where=where_clause,
                    skip=offset,
                    take=self.batch_size,
                    order={config["timestamp_field"]: "asc"},
                )

                if not data_records:
                    break

                # Log raw database data before conversion
                logger.info(f"=== RAW {data_type.upper()} DATA FROM DATABASE ===")
                logger.info(
                    f"Fetched {len(data_records)} {data_type} records from database"
                )
                for i, record in enumerate(data_records[:3]):  # Show first 3 records
                    logger.info(f"Raw {data_type.title()} {i+1}: {record}")
                if len(data_records) > 3:
                    logger.info(
                        f"... and {len(data_records) - 3} more {data_type} records from database"
                    )
                logger.info(f"=== END RAW {data_type.upper()} DATA ===")

                # Convert and push with retry logic
                gorse_data = [config["converter"](record) for record in data_records]
                result = await self._push_batch_with_retry(
                    gorse_data, config["api_method"]
                )

                if result["success"]:
                    total_pushed += result["count"]
                    # Update timestamp to the latest record in this batch
                    latest_timestamp = max(
                        getattr(record, config["timestamp_field"])
                        for record in data_records
                    )
                    await self._update_training_log_metadata(
                        training_log_id, {config["last_push_key"]: latest_timestamp}
                    )
                else:
                    logger.error(
                        f"Failed to push {data_type} batch: {result.get('error')}"
                    )
                    # Continue with next batch instead of breaking

                offset += self.batch_size

            logger.info(f"Pushed {total_pushed} {data_type} for shop {shop_id}")
            return {"pushed": total_pushed, "success": True}

        except Exception as e:
            logger.error(
                f"Failed to push {data_type} data for shop {shop_id}: {str(e)}"
            )
            return {"pushed": 0, "success": False, "error": str(e)}

    async def _push_batch_with_retry(
        self, batch_data: List[Dict], data_type: str, max_retries: int = 3
    ) -> Dict[str, Any]:
        """Simple retry logic for API calls - only on network/transient errors"""

        for attempt in range(max_retries):
            try:
                if data_type == "users":
                    result = await self.gorse_client.insert_users_batch(batch_data)
                elif data_type == "items":
                    result = await self.gorse_client.insert_items_batch(batch_data)
                elif data_type == "feedback":
                    result = await self.gorse_client.insert_feedback_batch(batch_data)
                else:
                    return {
                        "success": False,
                        "error": f"Unknown data type: {data_type}",
                        "count": 0,
                    }

                # If API call succeeded, we're done
                if result["success"]:
                    return result

                # Only retry on network/transient errors
                if (
                    self._is_retryable_error(result["error"])
                    and attempt < max_retries - 1
                ):
                    wait_time = 2**attempt
                    logger.warning(
                        f"Retryable error on attempt {attempt + 1}: {result['error']}. Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue

                # Don't retry on API errors (400, 401, etc.) - return immediately
                return result

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = 2**attempt
                    logger.warning(
                        f"Exception on attempt {attempt + 1}: {str(e)}. Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    return {"success": False, "error": str(e), "count": 0}

        return {"success": False, "error": "Max retries exceeded", "count": 0}

    def _is_retryable_error(self, error: str) -> bool:
        """Only retry on network/transient errors"""
        retryable_errors = [
            "timeout",
            "connection",
            "503",
            "502",
            "504",  # Network/server issues
        ]

        error_lower = error.lower()
        return any(retryable in error_lower for retryable in retryable_errors)

    async def _update_training_log_metadata(
        self, training_log_id: str, metadata_updates: Dict[str, Any]
    ):
        """Update training log with new timestamp information"""
        try:
            db = await self._get_database()

            # Prepare update data for flat fields
            update_data = {}
            for key, value in metadata_updates.items():
                if key == "usersLastPushAt":
                    update_data["usersLastPushAt"] = value
                elif key == "itemsLastPushAt":
                    update_data["itemsLastPushAt"] = value
                elif key == "feedbackLastPushAt":
                    update_data["feedbackLastPushAt"] = value

            # Update the log with flat fields
            if update_data:
                await db.mltraininglog.update(
                    where={"id": training_log_id},
                    data=update_data,
                )

        except Exception as e:
            logger.error(f"Failed to update training log metadata: {str(e)}")

    def _convert_user_to_gorse_format(self, user) -> Dict[str, Any]:
        """Convert database user to Gorse API format"""
        return {
            "userId": user.userId,
            "labels": user.labels if isinstance(user.labels, dict) else {},
            # GorseUsers doesn't have subscribe or comment fields, so we omit them
        }

    def _convert_item_to_gorse_format(self, item) -> Dict[str, Any]:
        """Convert database item to Gorse API format"""
        return {
            "itemId": item.itemId,
            "categories": item.categories if isinstance(item.categories, list) else [],
            "labels": item.labels if isinstance(item.labels, dict) else {},
            "isHidden": item.isHidden,
            # GorseItems doesn't have comment or timestamp fields, so we omit them
        }

    def _convert_feedback_to_gorse_format(self, feedback) -> Dict[str, Any]:
        """Convert database feedback to Gorse API format"""
        return {
            "userId": feedback.userId,
            "itemId": feedback.itemId,
            "feedbackType": feedback.feedbackType,
            "timestamp": (
                feedback.timestamp.isoformat()
                if feedback.timestamp
                else now_utc().isoformat()
            ),
            "comment": feedback.comment or "",
        }

    async def trigger_training_after_sync(self, shop_id: str) -> str:
        """
        Convenience method to trigger data push after sync operations
        This is the main method that should be called after data sync
        """
        return await self.push_data_to_gorse(
            shop_id=shop_id,
            job_type=TrainingJobType.INCREMENTAL_TRAINING,
            trigger_source="sync_completion",
        )

    async def get_data_push_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a data push job"""
        try:
            # Extract shop_id from job_id (format: data_push_{shop_id}_{type}_{timestamp})
            parts = job_id.split("_")
            if len(parts) < 3:
                return None

            shop_id = parts[2]  # data_push_{shop_id}_{type}_{timestamp}
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
                    "metadata": {
                        "usersPushed": training_log.usersPushed,
                        "itemsPushed": training_log.itemsPushed,
                        "feedbackPushed": training_log.feedbackPushed,
                        "totalPushed": training_log.totalPushed,
                        "jobType": training_log.jobType,
                        "pushStrategy": training_log.pushStrategy,
                        "triggerSource": training_log.triggerSource,
                        "usersLastPushAt": (
                            training_log.usersLastPushAt.isoformat()
                            if training_log.usersLastPushAt
                            else None
                        ),
                        "itemsLastPushAt": (
                            training_log.itemsLastPushAt.isoformat()
                            if training_log.itemsLastPushAt
                            else None
                        ),
                        "feedbackLastPushAt": (
                            training_log.feedbackLastPushAt.isoformat()
                            if training_log.feedbackLastPushAt
                            else None
                        ),
                    },
                }
            return None

        except Exception as e:
            logger.error(f"Failed to get data push job status for {job_id}: {str(e)}")
            return None

    async def get_shop_data_push_history(
        self, shop_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get data push history for a shop"""
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
                    "metadata": {
                        "usersPushed": training_log.usersPushed,
                        "itemsPushed": training_log.itemsPushed,
                        "feedbackPushed": training_log.feedbackPushed,
                        "totalPushed": training_log.totalPushed,
                        "jobType": training_log.jobType,
                        "pushStrategy": training_log.pushStrategy,
                        "triggerSource": training_log.triggerSource,
                        "usersLastPushAt": (
                            training_log.usersLastPushAt.isoformat()
                            if training_log.usersLastPushAt
                            else None
                        ),
                        "itemsLastPushAt": (
                            training_log.itemsLastPushAt.isoformat()
                            if training_log.itemsLastPushAt
                            else None
                        ),
                        "feedbackLastPushAt": (
                            training_log.feedbackLastPushAt.isoformat()
                            if training_log.feedbackLastPushAt
                            else None
                        ),
                    },
                }
                for log in logs
            ]

        except Exception as e:
            logger.error(
                f"Failed to get data push history for shop {shop_id}: {str(e)}"
            )
            return []

    async def batch_data_push_for_multiple_shops(
        self,
        shop_ids: List[str],
        max_concurrent: int = 3,
    ) -> Dict[str, str]:
        """
        Push data for multiple shops in batch with concurrency control
        Always uses incremental push strategy

        Args:
            shop_ids: List of shop IDs to push data for
            max_concurrent: Maximum number of concurrent data push jobs

        Returns:
            Dict mapping shop_id to job_id
        """
        results = {}
        semaphore = asyncio.Semaphore(max_concurrent)

        async def push_shop_data(shop_id: str):
            async with semaphore:
                try:
                    job_id = await self.push_data_to_gorse(
                        shop_id=shop_id,
                        job_type=TrainingJobType.INCREMENTAL_TRAINING,
                        trigger_source="batch_data_push",
                    )
                    results[shop_id] = job_id
                    logger.info(f"Started batch data push for shop {shop_id}: {job_id}")
                except Exception as e:
                    logger.error(
                        f"Failed to start batch data push for shop {shop_id}: {str(e)}"
                    )
                    results[shop_id] = f"error: {str(e)}"

        # Execute all data push jobs concurrently with semaphore
        tasks = [push_shop_data(shop_id) for shop_id in shop_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

        return results

    async def start_training_job(
        self,
        shop_id: str,
        job_type: TrainingJobType,
        trigger_source: str = "api",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Start a training job by pushing data to Gorse

        This method handles the complete training flow:
        1. Push data to Gorse (users, items, feedback)
        2. Gorse automatically triggers training based on the data

        Args:
            shop_id: Shop ID to train models for
            job_type: Type of training job
            trigger_source: Source that triggered the training
            metadata: Additional metadata for the training job

        Returns:
            Job ID for tracking the training job
        """
        try:
            logger.info(
                f"Starting training job for shop {shop_id} (type: {job_type.value})"
            )

            # Generate job ID for tracking
            job_id = (
                f"training_{shop_id}_{job_type.value}_{int(datetime.now().timestamp())}"
            )

            # Push data to Gorse - this automatically triggers training
            if job_type == TrainingJobType.FULL_TRAINING:
                # Full training - push all data
                await self.push_data_to_gorse(
                    shop_id=shop_id,
                    job_type=job_type,
                    trigger_source=trigger_source,
                    metadata=metadata or {},
                )
            elif job_type == TrainingJobType.INCREMENTAL_TRAINING:
                # Incremental training - push recent data
                await self.push_data_to_gorse(
                    shop_id=shop_id,
                    job_type=job_type,
                    trigger_source=trigger_source,
                    metadata=metadata or {},
                )
            elif job_type == TrainingJobType.MODEL_REFRESH:
                # Model refresh - push all data to refresh models
                await self.push_data_to_gorse(
                    shop_id=shop_id,
                    job_type=job_type,
                    trigger_source=trigger_source,
                    metadata=metadata or {},
                )
            else:
                # Custom training - use default behavior
                await self.push_data_to_gorse(
                    shop_id=shop_id,
                    job_type=job_type,
                    trigger_source=trigger_source,
                    metadata=metadata or {},
                )

            logger.info(
                f"Training job {job_id} completed successfully for shop {shop_id}"
            )
            return job_id

        except Exception as e:
            logger.error(f"Training job failed for shop {shop_id}: {str(e)}")
            raise
