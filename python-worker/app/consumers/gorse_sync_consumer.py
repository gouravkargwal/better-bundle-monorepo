"""
Gorse Sync Consumer for processing Gorse data synchronization jobs
"""

import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime

from app.consumers.base_consumer import BaseConsumer
from app.shared.constants.redis import GORSE_SYNC_STREAM, GORSE_SYNC_GROUP
from app.domains.ml.services.gorse_sync_pipeline import GorseSyncPipeline
from app.core.logging import get_logger


class GorseSyncConsumer(BaseConsumer):
    """Consumer for processing Gorse data synchronization jobs"""

    def __init__(self):
        super().__init__(
            stream_name=GORSE_SYNC_STREAM,
            consumer_group=GORSE_SYNC_GROUP,
            consumer_name="gorse-sync-consumer",
            batch_size=3,  # Process fewer jobs as sync is intensive
            poll_timeout=2000,  # 2 second timeout
            max_retries=2,
            retry_delay=5.0,
            circuit_breaker_failures=3,
            circuit_breaker_timeout=180,  # 3 minutes recovery
        )

        self.gorse_pipeline = GorseSyncPipeline()
        self.logger = get_logger(__name__)

        # Gorse sync job tracking
        self.active_sync_jobs: Dict[str, Dict[str, Any]] = {}
        self.job_timeout = 1800  # 30 minutes for sync operations

    async def _process_single_message(self, message: Dict[str, Any]):
        """Process a single Gorse sync job message"""
        try:
            # Extract message data
            job_id = message.get("job_id")
            shop_id = message.get("shop_id")
            sync_type = message.get("sync_type", "all")  # all, users, items, feedback
            since_hours = int(message.get("since_hours", 24))
            metadata = message.get("metadata", {})

            if not job_id or not shop_id:
                self.logger.error("Invalid message: missing job_id or shop_id")
                return

            self.logger.info(
                f"Processing Gorse sync job",
                job_id=job_id,
                shop_id=shop_id,
                sync_type=sync_type,
                since_hours=since_hours,
            )

            # Track the job
            self.active_sync_jobs[job_id] = {
                "shop_id": shop_id,
                "sync_type": sync_type,
                "started_at": datetime.utcnow(),
                "status": "processing",
                "metadata": metadata,
            }

            # Determine if this should be a full sync based on since_hours
            incremental = since_hours > 0  # Full sync if since_hours=0
            
            self.logger.info(
                f"Sync configuration | incremental={incremental} | since_hours={since_hours}"
            )
            
            # Execute the appropriate sync operation
            if sync_type == "users":
                await self.gorse_pipeline.sync_users(shop_id, incremental=incremental)
            elif sync_type == "items":
                await self.gorse_pipeline.sync_items(shop_id, incremental=incremental)
            elif sync_type == "feedback":
                await self.gorse_pipeline.sync_feedback(shop_id, since_hours)
            else:  # sync_type == "all" or any other value
                await self.gorse_pipeline.sync_all(shop_id, incremental=incremental)

            # Mark job as completed
            if job_id in self.active_sync_jobs:
                self.active_sync_jobs[job_id]["status"] = "completed"
                self.active_sync_jobs[job_id]["completed_at"] = datetime.utcnow()

            self.logger.info(
                f"Gorse sync job completed",
                job_id=job_id,
                shop_id=shop_id,
                sync_type=sync_type,
            )

        except Exception as e:
            # Update job status
            job_id = message.get("job_id")
            if job_id and job_id in self.active_sync_jobs:
                self.active_sync_jobs[job_id]["status"] = "failed"
                self.active_sync_jobs[job_id]["error"] = str(e)
                self.active_sync_jobs[job_id]["failed_at"] = datetime.utcnow()

            self.logger.error(
                f"Failed to process Gorse sync job: {str(e)}",
                job_id=job_id,
                shop_id=message.get("shop_id"),
                sync_type=message.get("sync_type"),
            )
            raise

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a Gorse sync job"""
        return self.active_sync_jobs.get(job_id)

    async def cleanup_old_jobs(self):
        """Clean up old completed jobs to prevent memory leaks"""
        current_time = datetime.utcnow()
        jobs_to_remove = []

        for job_id, job_data in self.active_sync_jobs.items():
            # Remove jobs older than timeout or completed more than 2 hours ago
            if job_data["status"] in ["completed", "failed"]:
                completed_at = job_data.get("completed_at") or job_data.get("failed_at")
                if (
                    completed_at
                    and (current_time - completed_at).total_seconds() > 7200
                ):  # 2 hours
                    jobs_to_remove.append(job_id)
            elif (
                current_time - job_data["started_at"]
            ).total_seconds() > self.job_timeout:
                # Mark timed out jobs as failed
                job_data["status"] = "timeout"
                job_data["failed_at"] = current_time
                jobs_to_remove.append(job_id)

        for job_id in jobs_to_remove:
            del self.active_sync_jobs[job_id]

        if jobs_to_remove:
            self.logger.info(f"Cleaned up {len(jobs_to_remove)} old Gorse sync jobs")

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the Gorse sync consumer"""
        await self.cleanup_old_jobs()

        active_jobs_by_status = {}
        for job_data in self.active_sync_jobs.values():
            status = job_data["status"]
            active_jobs_by_status[status] = active_jobs_by_status.get(status, 0) + 1

        return {
            "status": self.status.value,
            "active_jobs": len(self.active_sync_jobs),
            "active_jobs_by_status": active_jobs_by_status,
            "circuit_breaker_state": self.circuit_breaker.state,
            "metrics": {
                "messages_processed": self.metrics.messages_processed,
                "messages_failed": self.metrics.messages_failed,
                "processing_time_avg": self.metrics.processing_time_avg,
                "consecutive_failures": self.consecutive_failures,
            },
            "last_health_check": self.last_health_check.isoformat(),
        }

    async def _periodic_cleanup(self):
        """Perform periodic cleanup tasks"""
        await self.cleanup_old_jobs()
