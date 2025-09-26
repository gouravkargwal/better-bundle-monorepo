"""
Kafka-based normalization consumer for processing entity normalization jobs
"""

import json
from typing import Dict, Any
from datetime import datetime
from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.core.messaging.event_subscriber import EventSubscriber
from app.core.messaging.interfaces import EventHandler
from app.core.logging import get_logger
from app.domains.shopify.services.normalisation_service import (
    NormalizationService,
)

logger = get_logger(__name__)


class NormalizationKafkaConsumer:
    """Kafka consumer for normalization jobs"""

    def __init__(self):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self.event_subscriber = EventSubscriber(kafka_settings.model_dump())
        self._initialized = False

        self.normalization_service = NormalizationService()

    async def initialize(self):
        """Initialize consumer"""
        try:
            # Initialize Kafka consumer
            await self.consumer.initialize(
                topics=["normalization-jobs"], group_id="normalization-processors"
            )

            # Initialize event subscriber with existing consumer to avoid duplicate consumers
            await self.event_subscriber.initialize(
                topics=["normalization-jobs"],
                group_id="normalization-processors",
                existing_consumer=self.consumer,  # Reuse existing consumer
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
        """Simple, unified normalization handler"""
        self.logger.info(f"🔄 Starting unified normalization: {payload}")

        shop_id = payload.get("shop_id")
        data_type = payload.get("data_type")
        format_type = payload.get("format", "graphql")
        start_time = payload.get("start_time")
        end_time = payload.get("end_time")
        shopify_id = payload.get("shopify_id")

        if not shop_id or not data_type:
            self.logger.error(
                "❌ Invalid normalization event: missing shop_id or data_type"
            )
            return

        # If REST single-entity event with explicit shopify_id, process only that entity
        if format_type == "rest" and shopify_id:
            success = await self.consumer.normalization_service.process_rest_entity(
                shop_id, data_type, shopify_id
            )
            if success:
                # Feature computation for this type
                await self.consumer.normalization_service.feature_service.trigger_feature_computation(
                    shop_id, data_type
                )
                self.logger.info(
                    f"✅ Feature computation triggered for {data_type} (REST single entity)"
                )
            return

        # Check for processing mode (historical vs incremental)
        mode = payload.get(
            "mode", "incremental"
        )  # Default to incremental for backward compatibility

        if mode == "historical":
            # Process all historical data
            await self.consumer.normalization_service.process_historical_data(
                shop_id, data_type, format_type
            )
        else:
            # Process data with time range filtering (GraphQL or REST without id falls back to window)
            await self.consumer.normalization_service.process_normalization_window(
                shop_id, data_type, format_type, start_time, end_time, mode
            )
