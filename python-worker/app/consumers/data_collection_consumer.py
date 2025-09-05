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

    async def _process_single_message(self, message: Dict[str, Any]):
        """Process a single data collection job message"""
        try:
            # Extract message data - Redis streams return data directly
            message_data = message  # No need to get "data" field

            # Handle both camelCase (from Shopify app) and snake_case (from manual events) field names
            job_id = message_data.get("job_id") or message_data.get("jobId")
            shop_id = message_data.get("shop_id") or message_data.get("shopId")
            shop_domain = message_data.get("shop_domain") or message_data.get(
                "shopDomain"
            )
            access_token = message_data.get("access_token") or message_data.get(
                "accessToken"
            )
            job_type = message_data.get("job_type") or message_data.get(
                "type", "data_collection"
            )

            if not all([job_id, shop_id, shop_domain]):
                raise ValueError(
                    "Missing required job fields: job_id/shop_id/shop_domain (or jobId/shopId/shopDomain)"
                )

            self.logger.info(
                f"Processing data collection job",
                job_id=job_id,
                shop_id=shop_id,
                shop_domain=shop_domain,
                job_type=job_type,
            )

            # Track active job
            self.active_jobs[job_id] = {
                "started_at": datetime.utcnow(),
                "shop_id": shop_id,
                "shop_domain": shop_domain,
                "status": "processing",
            }

            # Process based on job type
            if job_type == "data_collection":
                await self._process_data_collection_job(
                    job_id, shop_id, shop_domain, access_token
                )
            elif job_type == "products_only":
                await self._process_products_collection_job(
                    job_id, shop_id, shop_domain, access_token
                )
            elif job_type == "orders_only":
                await self._process_orders_collection_job(
                    job_id, shop_id, shop_domain, access_token
                )
            elif job_type == "customers_only":
                await self._process_customers_collection_job(
                    job_id, shop_id, shop_domain, access_token
                )
            else:
                self.logger.warning(f"Unknown job type: {job_type}")
                await self._mark_job_failed(job_id, f"Unknown job type: {job_type}")

            # Mark job as completed
            await self._mark_job_completed(job_id)

        except Exception as e:
            self.logger.error(
                f"Failed to process data collection job",
                job_id=message.get("job_id"),  # Redis streams return data directly
                error=str(e),
            )
            raise

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

            self.logger.info(
                f"Data collection completed",
                job_id=job_id,
                shop_id=shop_id,
                total_items=result.get("total_items", 0),
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

    async def _process_products_collection_job(
        self, job_id: str, shop_id: str, shop_domain: str, access_token: str
    ):
        """Process products-only collection job"""
        try:
            self.logger.info(f"Starting products collection", job_id=job_id)

            products = await self.shopify_service.collect_products(shop_domain)

            self.logger.info(
                f"Products collection completed",
                job_id=job_id,
                shop_id=shop_id,
                products_count=len(products),
            )

            # Update job tracking
            if job_id in self.active_jobs:
                self.active_jobs[job_id]["status"] = "completed"
                self.active_jobs[job_id]["result"] = {"products": len(products)}
                self.active_jobs[job_id]["completed_at"] = datetime.utcnow()

        except Exception as e:
            self.logger.error(
                f"Products collection job failed",
                job_id=job_id,
                shop_id=shop_id,
                error=str(e),
            )
            await self._mark_job_failed(job_id, str(e))
            raise

    async def _process_orders_collection_job(
        self, job_id: str, shop_id: str, shop_domain: str, access_token: str
    ):
        """Process orders-only collection job"""
        try:
            self.logger.info(f"Starting orders collection", job_id=job_id)

            # Note: This method doesn't exist yet in the service
            # You'd need to implement it or use a different approach
            self.logger.warning(
                f"Orders-only collection not implemented yet", job_id=job_id
            )

            # For now, mark as completed with warning
            if job_id in self.active_jobs:
                self.active_jobs[job_id]["status"] = "completed"
                self.active_jobs[job_id]["result"] = {"message": "Not implemented yet"}
                self.active_jobs[job_id]["completed_at"] = datetime.utcnow()

        except Exception as e:
            self.logger.error(
                f"Orders collection job failed",
                job_id=job_id,
                shop_id=shop_id,
                error=str(e),
            )
            await self._mark_job_failed(job_id, str(e))
            raise

    async def _process_customers_collection_job(
        self, job_id: str, shop_id: str, shop_domain: str, access_token: str
    ):
        """Process customers-only collection job"""
        try:
            self.logger.info(f"Starting customers collection", job_id=job_id)

            # Note: This method doesn't exist yet in the service
            # You'd need to implement it or use a different approach
            self.logger.warning(
                f"Customers-only collection not implemented yet", job_id=job_id
            )

            # For now, mark as completed with warning
            if job_id in self.active_jobs:
                self.active_jobs[job_id]["status"] = "completed"
                self.active_jobs[job_id]["result"] = {"message": "Not implemented yet"}
                self.active_jobs[job_id]["completed_at"] = datetime.utcnow()

        except Exception as e:
            self.logger.error(
                f"Customers collection job failed",
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
