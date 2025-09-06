"""
Main Table Processing Consumer for BetterBundle Python Worker

This consumer handles the processing of raw Shopify data into structured main tables
with data cleaning and field extraction.
"""

import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime

from app.consumers.base_consumer import BaseConsumer
from app.shared.constants.redis import DATA_JOB_STREAM, DATA_PROCESSOR_GROUP
from app.domains.shopify.services.main_table_storage import MainTableStorageService
from app.core.logging import get_logger


class MainTableProcessingConsumer(BaseConsumer):
    """Consumer for processing main table storage jobs"""

    def __init__(self):
        super().__init__(
            stream_name=DATA_JOB_STREAM,
            consumer_group=DATA_PROCESSOR_GROUP,
            consumer_name="main-table-processing-consumer",
            batch_size=3,  # Process fewer jobs as main table processing is resource-intensive
            poll_timeout=2000,  # 2 second timeout
            max_retries=3,
            retry_delay=2.0,
            circuit_breaker_failures=3,  # More sensitive for main table processing
            circuit_breaker_timeout=120,  # 2 minute recovery
        )

        self.logger = get_logger(__name__)
        self.main_table_service = MainTableStorageService()

        # Job tracking
        self.active_jobs: Dict[str, Dict[str, Any]] = {}
        self.job_timeout = 1800  # 30 minutes for main table processing

    async def _process_single_message(self, message: Dict[str, Any]):
        """Process a single main table processing job message"""
        job_id = message.get("job_id")
        shop_id = message.get("shop_id")
        shop_domain = message.get("shop_domain")
        job_type = message.get("job_type")

        # Check if this is a main table processing job
        if job_type != "main_table_processing":
            # Skip non-main-table-processing jobs
            self.logger.debug(
                f"Skipping non-main-table-processing job: {job_type}",
                job_id=job_id,
                shop_id=shop_id,
            )
            return

        # Validate required fields for main table processing jobs
        if not job_id or not shop_id or not shop_domain:
            self.logger.error(
                "Invalid main table processing message: missing required fields",
                job_id=job_id,
                shop_id=shop_id,
                shop_domain=shop_domain,
            )
            raise ValueError("Missing required fields for main table processing job")

        self.logger.info(
            f"Processing main table processing job",
            job_id=job_id,
            shop_id=shop_id,
            shop_domain=shop_domain,
        )

        # Track job BEFORE processing starts
        self.active_jobs[job_id] = {
            "status": "processing",
            "shop_id": shop_id,
            "shop_domain": shop_domain,
            "started_at": datetime.utcnow(),
        }

        try:
            # Process the main table processing job
            await self._process_main_table_job(job_id, shop_id, shop_domain)

            # Mark job as completed ONLY if processing succeeded
            await self._mark_job_completed(job_id)

        except Exception as e:
            # Mark job as failed if processing failed
            await self._mark_job_failed(job_id, str(e))

            self.logger.error(
                f"Failed to process main table processing message",
                job_id=job_id,
                error=str(e),
            )
            # Re-raise the exception so the base consumer can handle retries
            raise

    async def _process_main_table_job(
        self, job_id: str, shop_id: str, shop_domain: str
    ):
        """Process main table storage for a shop"""
        self.logger.info(
            f"Starting main table processing",
            job_id=job_id,
            shop_id=shop_id,
            shop_domain=shop_domain,
        )

        # Run main table storage with incremental processing
        result = await self.main_table_service.store_all_data(
            shop_id=shop_id, incremental=True
        )

        if result.success:
            self.logger.info(
                f"Main table processing completed successfully",
                job_id=job_id,
                shop_id=shop_id,
                shop_domain=shop_domain,
                processed_count=result.processed_count,
                error_count=result.error_count,
                duration_ms=result.duration_ms,
            )

            # Update job tracking with results
            if job_id in self.active_jobs:
                self.active_jobs[job_id]["result"] = {
                    "processed_count": result.processed_count,
                    "error_count": result.error_count,
                    "duration_ms": result.duration_ms,
                    "errors": result.errors,
                }
        else:
            error_msg = f"Main table processing failed: {result.errors}"
            self.logger.error(
                f"Main table processing failed",
                job_id=job_id,
                shop_id=shop_id,
                shop_domain=shop_domain,
                errors=result.errors,
            )
            raise Exception(error_msg)

    async def _mark_job_completed(self, job_id: str):
        """Mark a job as completed"""
        if job_id in self.active_jobs:
            self.active_jobs[job_id]["status"] = "completed"
            self.active_jobs[job_id]["completed_at"] = datetime.utcnow()

    async def _mark_job_failed(self, job_id: str, error: str):
        """Mark a job as failed"""
        if job_id in self.active_jobs:
            self.active_jobs[job_id]["status"] = "failed"
            self.active_jobs[job_id]["failed_at"] = datetime.utcnow()
            self.active_jobs[job_id]["error"] = error

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a main table processing job"""
        return self.active_jobs.get(job_id)

    async def _periodic_cleanup(self):
        """Override base class cleanup to handle job tracking"""
        await self.cleanup_old_jobs()

    async def cleanup_old_jobs(self):
        """Clean up old completed jobs to prevent memory leaks"""
        current_time = datetime.utcnow()
        jobs_to_remove = []

        for job_id, job_data in self.active_jobs.items():
            # Remove jobs older than timeout or completed more than 1 hour ago
            if job_data["status"] in ["completed", "failed", "timeout"]:
                completed_at = job_data.get("completed_at") or job_data.get(
                    "failed_at", current_time
                )
                if (current_time - completed_at).total_seconds() > 3600:  # 1 hour
                    jobs_to_remove.append(job_id)
            elif (
                current_time - job_data["started_at"]
            ).total_seconds() > self.job_timeout:
                # Mark timed out jobs as failed
                job_data["status"] = "timeout"
                job_data["failed_at"] = current_time
                job_data["error"] = "Job timed out"
                jobs_to_remove.append(job_id)

        for job_id in jobs_to_remove:
            del self.active_jobs[job_id]

        if jobs_to_remove:
            self.logger.info(
                f"Cleaned up {len(jobs_to_remove)} old main table processing jobs"
            )

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the main table processing consumer"""
        await self.cleanup_old_jobs()

        return {
            "status": self.status.value,
            "active_jobs": len(self.active_jobs),
            "circuit_breaker_state": self.circuit_breaker.state,
            "metrics": {
                "messages_processed": self.metrics.messages_processed,
                "messages_failed": self.metrics.messages_failed,
                "processing_time_avg": self.metrics.processing_time_avg,
                "consecutive_failures": self.metrics.consecutive_failures,
            },
            "last_health_check": self.last_health_check.isoformat(),
        }
