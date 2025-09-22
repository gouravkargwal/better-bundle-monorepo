"""
Kafka-based data collection consumer for processing Shopify data collection jobs
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.core.messaging.event_subscriber import EventSubscriber
from app.core.messaging.interfaces import EventHandler
from app.domains.shopify.services import ShopifyDataCollectionService
from app.core.logging import get_logger

logger = get_logger(__name__)


class DataCollectionKafkaConsumer:
    """Kafka consumer for data collection jobs"""

    def __init__(self, shopify_service=None):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self.event_subscriber = EventSubscriber(kafka_settings.model_dump())
        self.shopify_service = shopify_service
        self._initialized = False

        # Job tracking
        self.active_jobs: Dict[str, Dict[str, Any]] = {}
        self.job_timeout = 1800  # 30 minutes

    async def initialize(self):
        """Initialize consumer"""
        try:
            logger.info("🔄 Initializing data collection consumer...")

            # Validate shopify service is provided
            if not self.shopify_service:
                raise ValueError(
                    "Shopify service is required for data collection consumer"
                )
            logger.info("✅ Shopify service validation passed")

            # Initialize Kafka consumer
            logger.info(
                "🔄 Initializing Kafka consumer for data-collection-jobs topic..."
            )
            await self.consumer.initialize(
                topics=["data-collection-jobs"], group_id="data-collection-processors"
            )
            logger.info("✅ Kafka consumer initialized")

            # Initialize event subscriber
            logger.info("🔄 Initializing event subscriber...")
            await self.event_subscriber.initialize(
                topics=["data-collection-jobs"], group_id="data-collection-processors"
            )
            logger.info("✅ Event subscriber initialized")

            # Add event handlers
            logger.info("🔄 Adding event handlers...")
            self.event_subscriber.add_handler(DataCollectionJobHandler(self))
            logger.info("✅ Event handlers added")

            self._initialized = True
            logger.info("✅ Data collection Kafka consumer fully initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize data collection consumer: {e}")
            raise

    async def start_consuming(self):
        """Start consuming messages"""
        if not self._initialized:
            logger.info("🔄 Consumer not initialized, initializing first...")
            await self.initialize()

        try:
            logger.info("🚀 Starting data collection consumer...")
            logger.info("📡 Listening for messages on topic: data-collection-jobs")
            logger.info("👥 Consumer group: data-collection-processors")
            await self.event_subscriber.consume_and_handle(
                topics=["data-collection-jobs"], group_id="data-collection-processors"
            )
        except Exception as e:
            logger.error(f"❌ Error in data collection consumer: {e}")
            raise

    async def close(self):
        """Close consumer"""
        if self.consumer:
            await self.consumer.close()
        if self.event_subscriber:
            await self.event_subscriber.close()
        logger.info("Data collection consumer closed")

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific job"""
        return self.active_jobs.get(job_id)

    async def get_all_jobs_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all active jobs"""
        return self.active_jobs.copy()

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
            logger.info(f"Cleaned up {len(jobs_to_remove)} old jobs")

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the data collection consumer"""
        await self.cleanup_old_jobs()

        return {
            "status": "running" if self._initialized else "stopped",
            "active_jobs": len(self.active_jobs),
            "last_health_check": datetime.utcnow().isoformat(),
        }


class DataCollectionJobHandler(EventHandler):
    """Handler for data collection jobs"""

    def __init__(self, consumer: DataCollectionKafkaConsumer):
        self.consumer = consumer
        self.logger = get_logger(__name__)

    def can_handle(self, event_type: str) -> bool:
        return event_type in [
            "data_collection",
            "collect_products",
            "collect_orders",
            "collect_customers",
        ]

    async def handle(self, event: Dict[str, Any]) -> bool:
        try:
            self.logger.info(
                "🔄 DataCollectionJobHandler received event",
                event_keys=list(event.keys()),
            )

            # Extract message data
            job_id = event.get("job_id")
            shop_id = event.get("shop_id")
            shop_domain = event.get("shop_domain")
            access_token = event.get("access_token")
            job_type = event.get("job_type")

            self.logger.info(
                "📋 Extracted event data",
                job_id=job_id,
                shop_id=shop_id,
                shop_domain=shop_domain,
                job_type=job_type,
                has_access_token=bool(access_token),
            )

            # Check if this is a data collection job
            if job_type != "data_collection":
                self.logger.info(f"⏭️ Skipping non-data-collection job: {job_type}")
                return True

            # Validate required fields for data collection jobs
            if not job_id or not shop_id or not shop_domain or not access_token:
                self.logger.error(
                    "❌ Invalid data collection message: missing required fields",
                    job_id=job_id,
                    shop_id=shop_id,
                    shop_domain=shop_domain,
                    has_access_token=bool(access_token),
                )
                return False

            self.logger.info(
                "🚀 Processing data collection job",
                job_id=job_id,
                shop_id=shop_id,
                shop_domain=shop_domain,
            )

            # Track job
            self.consumer.active_jobs[job_id] = {
                "status": "processing",
                "shop_id": shop_id,
                "shop_domain": shop_domain,
                "started_at": datetime.utcnow(),
            }

            # Process the data collection job
            await self._process_data_collection_job(
                job_id, shop_id, shop_domain, access_token
            )

            # Mark job as completed
            await self._mark_job_completed(job_id)

            return True

        except Exception as e:
            self.logger.error(
                f"Failed to process data collection message",
                job_id=event.get("job_id"),
                error=str(e),
            )
            if job_id:
                await self._mark_job_failed(job_id, str(e))
            return False

    async def _process_data_collection_job(
        self, job_id: str, shop_id: str, shop_domain: str, access_token: str
    ):
        """Process comprehensive data collection job"""
        try:
            self.logger.info("🔄 Starting comprehensive data collection", job_id=job_id)

            # Debug: Check if shopify service is available
            if not self.consumer.shopify_service:
                self.logger.error("❌ Shopify service is not available")
                raise ValueError("Shopify service is not available")

            self.logger.info(
                "✅ Shopify service is available, starting data collection"
            )

            # Collect all data
            self.logger.info(
                "📞 Calling shopify_service.collect_all_data",
                shop_domain=shop_domain,
                shop_id=shop_id,
                has_access_token=bool(access_token),
            )

            result = await self.consumer.shopify_service.collect_all_data(
                shop_domain=shop_domain,
                access_token=access_token,  # Pass the access token
                shop_id=shop_id,  # Pass the shop_id directly
                include_products=True,
                include_orders=True,
                include_customers=True,
                include_collections=True,
            )

            self.logger.info(
                "✅ Data collection completed successfully",
                job_id=job_id,
                result_keys=(
                    list(result.keys())
                    if isinstance(result, dict)
                    else "non-dict result"
                ),
            )

            # Update job tracking
            if job_id in self.consumer.active_jobs:
                self.consumer.active_jobs[job_id]["status"] = "completed"
                self.consumer.active_jobs[job_id]["result"] = result
                self.consumer.active_jobs[job_id]["completed_at"] = datetime.utcnow()

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
        if job_id in self.consumer.active_jobs:
            self.consumer.active_jobs[job_id]["status"] = "completed"
            self.consumer.active_jobs[job_id]["completed_at"] = datetime.utcnow()

        self.logger.info(f"Job completed successfully", job_id=job_id)

    async def _mark_job_failed(self, job_id: str, error_message: str):
        """Mark job as failed"""
        if job_id in self.consumer.active_jobs:
            self.consumer.active_jobs[job_id]["status"] = "failed"
            self.consumer.active_jobs[job_id]["error"] = error_message
            self.consumer.active_jobs[job_id]["failed_at"] = datetime.utcnow()

        self.logger.error(f"Job failed", job_id=job_id, error=error_message)
