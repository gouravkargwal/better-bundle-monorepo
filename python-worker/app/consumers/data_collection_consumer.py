"""
Data collection consumer for processing Shopify data collection jobs
"""

import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime

from app.consumers.base_consumer import BaseConsumer
from app.shared.constants.redis import DATA_JOB_STREAM, DATA_PROCESSOR_GROUP
from app.domains.shopify.services import ShopifyDataCollectionService
from app.core.logging import get_logger


class DataCollectionConsumer(BaseConsumer):
    """Consumer for processing Shopify data collection jobs"""

    def __init__(self, shopify_service: ShopifyDataCollectionService):
        super().__init__(
            stream_name=DATA_JOB_STREAM,
            consumer_group=DATA_PROCESSOR_GROUP,
            consumer_name="data-collection-consumer",
            batch_size=5,  # Process fewer jobs at once for data collection
            poll_timeout=2000,  # 2 second timeout
            max_retries=3,
            retry_delay=2.0,
            circuit_breaker_failures=3,  # More sensitive for data collection
            circuit_breaker_timeout=120,  # 2 minute recovery
        )

        self.shopify_service = shopify_service
        self.logger = get_logger(__name__)

        # Job tracking
        self.active_jobs: Dict[str, Dict[str, Any]] = {}
        self.job_timeout = 1800  # 30 minutes

    async def _process_data_collection_job(
        self, job_id: str, shop_id: str, shop_domain: str, access_token: str
    ):
        """Process comprehensive data collection job"""
        try:
            self.logger.info(f"Starting comprehensive data collection", job_id=job_id)

            # Debug: Check if shopify service is available
            if not self.shopify_service:
                self.logger.error("Shopify service is not available")
                raise ValueError("Shopify service is not available")

            self.logger.info(f"Shopify service is available, starting data collection")

            # Set access token for the service
            # Note: In a real implementation, you'd need to handle access token management
            # For now, we'll assume the service can handle it

            # Collect all data
            self.logger.info(
                f"Calling shopify_service.collect_all_data for {shop_domain} with access token"
            )
            result = await self.shopify_service.collect_all_data(
                shop_domain=shop_domain,
                access_token=access_token,  # Pass the access token
                shop_id=shop_id,  # Pass the shop_id directly
                include_products=True,
                include_orders=True,
                include_customers=True,
                include_collections=True,
            )

            # Update job tracking
            if job_id in self.active_jobs:
                self.active_jobs[job_id]["status"] = "completed"
                self.active_jobs[job_id]["result"] = result
                self.active_jobs[job_id]["completed_at"] = datetime.utcnow()

        except Exception as e:
            self.logger.error(
                f"Data collection job failed",
                job_id=job_id,
                shop_id=shop_id,
                error=str(e),
            )
            await self._mark_job_failed(job_id, str(e))
            raise

    async def _mark_job_completed(self, job_id: str):
        """Mark job as completed"""
        if job_id in self.active_jobs:
            self.active_jobs[job_id]["status"] = "completed"
            self.active_jobs[job_id]["completed_at"] = datetime.utcnow()

        self.logger.info(f"Job completed successfully", job_id=job_id)

    async def _mark_job_failed(self, job_id: str, error_message: str):
        """Mark job as failed"""
        if job_id in self.active_jobs:
            self.active_jobs[job_id]["status"] = "failed"
            self.active_jobs[job_id]["error"] = error_message
            self.active_jobs[job_id]["failed_at"] = datetime.utcnow()

        self.logger.error(f"Job failed", job_id=job_id, error=error_message)

    async def cleanup_old_jobs(self):
        """Clean up old completed/failed jobs"""
        now = datetime.utcnow()
        jobs_to_remove = []

        for job_id, job_data in self.active_jobs.items():
            if job_data["status"] in ["completed", "failed"]:
                # Check if job is old enough to remove
                if "completed_at" in job_data:
                    age = (now - job_data["completed_at"]).total_seconds()
                elif "failed_at" in job_data:
                    age = (now - job_data["failed_at"]).total_seconds()
                else:
                    continue

                if age > self.job_timeout:
                    jobs_to_remove.append(job_id)

        # Remove old jobs
        for job_id in jobs_to_remove:
            del self.active_jobs[job_id]

        if jobs_to_remove:
            self.logger.info(f"Cleaned up {len(jobs_to_remove)} old jobs")

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific job"""
        return self.active_jobs.get(job_id)

    def get_all_jobs_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all active jobs"""
        return self.active_jobs.copy()

    async def _health_check(self):
        """Extended health check for data collection consumer"""
        await super()._health_check()

        # Clean up old jobs periodically
        await self.cleanup_old_jobs()
