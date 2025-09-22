"""
Kafka-based normalization consumer for processing entity normalization jobs
"""

import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.core.messaging.event_subscriber import EventSubscriber
from app.core.messaging.interfaces import EventHandler
from app.core.database.simple_db_client import get_database
from app.core.logging import get_logger
from app.domains.shopify.services.normalisation_service import (
    EntityNormalizationService,
    OrderNormalizationService,
    FeatureComputationService,
    EntityDeletionService,
)

logger = get_logger(__name__)


class NormalizationKafkaConsumer:
    """Kafka consumer for normalization jobs"""

    def __init__(self):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self.event_subscriber = EventSubscriber(kafka_settings.model_dump())
        self._initialized = False

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
        return event_type == "normalize_data"  # Only unified event type

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

            if event_type == "normalize_data":
                self.logger.info("📥 Processing normalize_data event")
                await self._handle_unified_normalization(payload)
            else:
                # Ignore non-normalization messages
                self.logger.info(f"⏭️ Ignoring non-normalization message: {event_type}")
                return True

            return True

        except Exception as e:
            self.logger.error(f"Normalization failed: {e}")
            return False

    async def _handle_unified_normalization(self, payload: Dict[str, Any]):
        """Simple, unified normalization handler - always requires time range"""
        self.logger.info(f"🔄 Starting unified normalization: {payload}")

        shop_id = payload.get("shop_id")
        data_type = payload.get("data_type")
        format_type = payload.get("format", "graphql")
        start_time = payload.get("start_time")
        end_time = payload.get("end_time")

        if not shop_id or not data_type:
            self.logger.error(
                "❌ Invalid normalization event: missing shop_id or data_type"
            )
            return

        # Always require time range for both real-time and batch
        if not start_time and not end_time:
            self.logger.error(
                "❌ Invalid normalization event: start_time or end_time is required"
            )
            return

        # Process data with time range filtering
        await self._process_normalization_simple(
            shop_id, data_type, format_type, start_time, end_time
        )

    async def _process_normalization_simple(
        self,
        shop_id: str,
        data_type: str,
        format_type: str,
        start_time: str,
        end_time: str,
    ):
        """Simple, industry-standard normalization processing"""
        self.logger.info(f"🔄 Processing {data_type} for shop {shop_id}")

        # Handle "all" data types
        if data_type == "all":
            data_types = ["products", "orders", "customers", "collections"]
            self.logger.info(f"🔄 Processing all data types: {data_types}")

            for dt in data_types:
                await self._process_single_data_type(
                    shop_id, dt, format_type, start_time, end_time
                )
                # Trigger feature computation after each data type (independent processing)
                await self.consumer.feature_service.trigger_feature_computation(
                    shop_id, dt
                )
                self.logger.info(f"✅ Feature computation triggered for {dt}")
        else:
            # Process single data type
            await self._process_single_data_type(
                shop_id, data_type, format_type, start_time, end_time
            )
            # Trigger feature computation after this data type
            await self.consumer.feature_service.trigger_feature_computation(
                shop_id, data_type
            )
            self.logger.info(f"✅ Feature computation triggered for {data_type}")

    async def _process_single_data_type(
        self,
        shop_id: str,
        data_type: str,
        format_type: str,
        start_time: str,
        end_time: str,
    ):
        """Process a single data type - simple and efficient"""
        db = await get_database()
        raw_table = {
            "orders": db.raworder,
            "products": db.rawproduct,
            "customers": db.rawcustomer,
            "collections": db.rawcollection,
        }.get(data_type)

        if not raw_table:
            self.logger.error(f"❌ Unknown data type: {data_type}")
            return

        # Simple query - get data for this shop and data type
        where_conditions = {"shopId": shop_id}

        # Always add time filters (required for all events)
        time_filter = {}
        if start_time:
            time_filter["gte"] = start_time
        if end_time:
            time_filter["lte"] = end_time
        where_conditions["extractedAt"] = time_filter
        self.logger.info(f"🔍 Time filter on extractedAt: {start_time} to {end_time}")

        self.logger.info(f"🔍 Querying {data_type} with conditions: {where_conditions}")

        # Process data in batches
        page_size = 100
        offset = 0
        total_processed = 0

        while True:
            raw_records = await raw_table.find_many(
                where=where_conditions,
                skip=offset,
                take=page_size,
                order={"extractedAt": "desc"},  # Most recent first
            )

            if not raw_records:
                break

            self.logger.info(
                f"📄 Processing {len(raw_records)} {data_type} records (offset: {offset})"
            )

            # Process records in parallel
            tasks = []
            for raw_record in raw_records:
                if format_type == "graphql":
                    raw_record.format = "graphql"

                if data_type == "orders":
                    task = self.consumer.order_service.normalize_order(
                        raw_record, shop_id, is_webhook=False
                    )
                else:
                    task = self.consumer.entity_service.normalize_entity(
                        raw_record, shop_id, data_type
                    )
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)
            successful = len(
                [r for r in results if r is not None and not isinstance(r, Exception)]
            )
            total_processed += successful

            self.logger.info(
                f"✅ Processed {successful}/{len(raw_records)} records successfully"
            )

            # Check if we need to continue pagination
            if len(raw_records) < page_size:
                break

            offset += page_size

        self.logger.info(
            f"🎉 Normalization complete: {total_processed} {data_type} records processed"
        )
