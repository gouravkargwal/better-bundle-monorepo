"""
Kafka-based normalization consumer for processing entity normalization jobs
"""

import json
import time
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.core.messaging.event_subscriber import EventSubscriber
from app.core.messaging.interfaces import EventHandler
from app.domains.shopify.normalization.factory import get_adapter
from app.domains.shopify.normalization.canonical_models import NormalizeJob
from app.core.database.simple_db_client import get_database
from app.core.logging import get_logger

logger = get_logger(__name__)


class NormalizationKafkaConsumer:
    """Kafka consumer for normalization jobs"""

    def __init__(self):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self.event_subscriber = EventSubscriber(kafka_settings.model_dump())
        self._initialized = False

        # Initialize services (imported from the original consumer)
        from app.consumers.normalization_consumer import (
            EntityNormalizationService,
            OrderNormalizationService,
            FeatureComputationService,
            EntityDeletionService,
        )

        self.entity_service = EntityNormalizationService()
        self.order_service = OrderNormalizationService()
        self.feature_service = FeatureComputationService()
        self.deletion_service = EntityDeletionService()

    async def initialize(self):
        """Initialize consumer"""
        try:
            # Initialize Kafka consumer
            await self.consumer.initialize(
                topics=["normalization-jobs"], group_id="normalization-processors"
            )

            # Initialize event subscriber
            await self.event_subscriber.initialize(
                topics=["normalization-jobs"], group_id="normalization-processors"
            )

            # Add event handlers
            self.event_subscriber.add_handler(NormalizationJobHandler(self))

            self._initialized = True
            logger.info("Normalization Kafka consumer initialized")

        except Exception as e:
            logger.error(f"Failed to initialize normalization consumer: {e}")
            raise

    async def start_consuming(self):
        """Start consuming messages"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info("Starting normalization consumer...")
            await self.event_subscriber.consume_and_handle(
                topics=["normalization-jobs"], group_id="normalization-processors"
            )
        except Exception as e:
            logger.error(f"Error in normalization consumer: {e}")
            raise

    async def close(self):
        """Close consumer"""
        if self.consumer:
            await self.consumer.close()
        if self.event_subscriber:
            await self.event_subscriber.close()
        logger.info("Normalization consumer closed")

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the normalization consumer"""
        return {
            "status": "running" if self._initialized else "stopped",
            "last_health_check": datetime.utcnow().isoformat(),
        }


class NormalizationJobHandler(EventHandler):
    """Handler for normalization jobs"""

    def __init__(self, consumer: NormalizationKafkaConsumer):
        self.consumer = consumer
        self.logger = get_logger(__name__)

    def can_handle(self, event_type: str) -> bool:
        return event_type in [
            "normalize_entity",
            "normalize_batch",
        ]

    async def handle(self, event: Dict[str, Any]) -> bool:
        try:
            self.logger.info(f"🔄 Processing normalization message: {event}")

            payload = event.get("data") or event
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    pass
            event_type = payload.get("event_type")

            self.logger.info(f"📋 Extracted event_type: {event_type}")

            if event_type == "normalize_entity":
                self.logger.info("📥 Processing normalize_entity event")
                await self._handle_normalize_entity(payload)
            elif event_type == "normalize_batch":
                self.logger.info("📥 Processing normalize_batch event")
                await self._handle_normalize_batch(payload)
            else:
                # Ignore non-normalization messages
                self.logger.info(f"⏭️ Ignoring non-normalization message: {event_type}")
                return True

            return True

        except Exception as e:
            self.logger.error(f"Normalization failed: {e}")
            return False

    async def _handle_normalize_entity(self, payload: Dict[str, Any]):
        """Handle single entity normalization (webhooks)."""
        job = NormalizeJob(**payload)
        db = await get_database()

        # Check if this is a deletion event
        original_event_type = payload.get("original_event_type")
        is_deletion_event = original_event_type in [
            "product_deleted",
            "collection_deleted",
            "customer_redacted",
        ]

        if is_deletion_event:
            await self.consumer.deletion_service.handle_entity_deletion(job, db)
            await self.consumer.feature_service.trigger_feature_computation(
                job.shop_id, job.data_type
            )
            return

        # Find raw record
        raw_table = {
            "orders": db.raworder,
            "products": db.rawproduct,
            "customers": db.rawcustomer,
            "collections": db.rawcollection,
        }[job.data_type]

        raw = await raw_table.find_first(
            where={"shopifyId": str(job.shopify_id), "shopId": job.shop_id}
        )

        if not raw:
            self.logger.warning(
                "Raw record not found for non-deletion event",
                shopify_id=job.shopify_id,
                shop_id=job.shop_id,
                event_type=original_event_type,
            )
            return

        try:
            # Use appropriate service based on data type
            if job.data_type == "orders":
                success = await self.consumer.order_service.normalize_order(
                    raw, job.shop_id
                )
            else:
                success = await self.consumer.entity_service.normalize_entity(
                    raw, job.shop_id, job.data_type
                )

            # Always trigger feature computation, even if normalization was skipped
            # This ensures features are updated when new behavioral data is collected
            await self.consumer.feature_service.trigger_feature_computation(
                job.shop_id, job.data_type
            )

        except Exception as e:
            self.logger.error(f"Normalization failed: {e}")
            raise

    async def _handle_normalize_batch(self, payload: Dict[str, Any]):
        """Handle batch normalization with pagination."""
        self.logger.info(f"🔄 Starting batch normalization: {payload}")

        shop_id = payload.get("shop_id")
        data_type = payload.get("data_type")
        fmt = payload.get("format")
        since = payload.get("since")
        page_size = payload.get("page_size", 100)

        self.logger.info(
            f"📋 Batch params: shop_id={shop_id}, data_type={data_type}, format={fmt}, since={since}, page_size={page_size}"
        )

        if not all([shop_id, data_type]):
            self.logger.error(
                "Invalid normalize_batch job: missing required fields", payload=payload
            )
            return

        # Check if we need to process all data types
        if data_type == "all":
            # Process all data types from the payload
            data_types = payload.get(
                "data_types", ["products", "orders", "customers", "collections"]
            )
            self.logger.info(f"🔄 Processing all data types: {data_types}")

            # Process each data type
            for dt in data_types:
                self.logger.info(f"🔄 Processing {dt} data type")
                await self._process_normalize_batch_recursive(
                    shop_id, dt, fmt, since, page_size
                )

            # Trigger feature computation only once after all data types are complete
            self.logger.info(
                f"🚀 All data types complete, triggering feature computation"
            )
            # Trigger feature computation for products (primary data type) which will process all data
            await self.consumer.feature_service.trigger_feature_computation(
                shop_id, "products"
            )
        else:
            # Process single data type
            await self._process_normalize_batch_recursive(
                shop_id, data_type, fmt, since, page_size
            )

            # After all batches are complete, trigger feature computation
            self.logger.info(
                f"🚀 All batches complete for {data_type}, triggering feature computation"
            )
            await self.consumer.feature_service.trigger_feature_computation(
                shop_id, data_type
            )

    async def _process_normalize_batch_recursive(
        self, shop_id: str, data_type: str, fmt: str, since: str, page_size: int
    ):
        """Recursively process all batches for a data type without firing events"""

        db = await get_database()
        raw_table = {
            "orders": db.raworder,
            "products": db.rawproduct,
            "customers": db.rawcustomer,
            "collections": db.rawcollection,
        }[data_type]

        # Build query conditions
        where_conditions = {"shopId": shop_id}
        if isinstance(since, str) and since.lower() in ("none", "null", ""):
            since = None

        if since:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            where_conditions["shopifyUpdatedAt"] = {"gt": since_dt}

        # Fetch page of raw records
        raw_records = await raw_table.find_many(
            where=where_conditions,
            order=[{"shopifyUpdatedAt": "asc"}, {"id": "asc"}],
            take=page_size,
        )

        if not raw_records:
            return

        # Process each record concurrently
        semaphore = asyncio.Semaphore(20)

        async def process_record(raw_record):
            async with semaphore:
                try:
                    if fmt == "graphql":
                        setattr(raw_record, "format", "graphql")

                    # Use appropriate service
                    if data_type == "orders":
                        success = await self.consumer.order_service.normalize_order(
                            raw_record, shop_id, is_webhook=False
                        )
                    else:
                        success = await self.consumer.entity_service.normalize_entity(
                            raw_record, shop_id, data_type
                        )

                    return raw_record.shopifyUpdatedAt if success else None
                except Exception as e:
                    self.logger.error(f"Failed to normalize record: {e}")
                    return None

        tasks = [process_record(raw_record) for raw_record in raw_records]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter successful results
        successful_results = [
            r for r in results if r is not None and not isinstance(r, Exception)
        ]
        last_updated_at = max(successful_results) if successful_results else None

        # Log batch results
        failed_count = len(results) - len(successful_results)
        if failed_count > 0:
            self.logger.warning(
                f"Batch processing completed with failures",
                shop_id=shop_id,
                data_type=data_type,
                total_records=len(raw_records),
                successful=len(successful_results),
                failed=failed_count,
            )

        # Continue pagination if needed - handle directly without events
        if len(raw_records) == page_size:
            self.logger.info(
                f"📄 More records available, continuing pagination for {data_type}"
            )
            # Recursively call the same method for next batch
            await self._process_normalize_batch_recursive(
                shop_id,
                data_type,
                fmt,
                last_updated_at.isoformat() if last_updated_at else None,
                page_size,
            )
        else:
            # Entire normalization process is complete for this data type
            self.logger.info(f"✅ {data_type} normalization process complete")

        # Update watermark
        if last_updated_at is not None:
            await db.normalizationwatermark.upsert(
                where={"shopId_dataType": {"shopId": shop_id, "dataType": data_type}},
                data={
                    "update": {"lastNormalizedAt": last_updated_at},
                    "create": {
                        "shopId": shop_id,
                        "dataType": data_type,
                        "lastNormalizedAt": last_updated_at,
                    },
                },
            )
