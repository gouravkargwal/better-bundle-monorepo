"""
Kafka-based normalization consumer for processing entity normalization jobs
"""

import json
from typing import Dict, Any
from datetime import datetime
from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.core.logging import get_logger
from app.domains.shopify.services.normalisation_service import (
    NormalizationService,
)

logger = get_logger(__name__)


class NormalizationKafkaConsumer:
    """Kafka consumer for normalization jobs"""

    def __init__(self):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self._initialized = False
        self.normalization_service = NormalizationService()

    async def initialize(self):
        """Initialize consumer"""
        try:
            # Initialize Kafka consumer
            await self.consumer.initialize(
                topics=["normalization-jobs"], group_id="normalization-processors"
            )

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
            async for message in self.consumer.consume():
                try:
                    await self._handle_message(message)
                    await self.consumer.commit(message)
                except Exception as e:
                    logger.error(f"Error processing normalization message: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error in normalization consumer: {e}")
            raise

    async def close(self):
        """Close consumer"""
        if self.consumer:
            await self.consumer.close()
        logger.info("Normalization consumer closed")

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the normalization consumer"""
        return {
            "status": "running" if self._initialized else "stopped",
            "last_health_check": datetime.utcnow().isoformat(),
        }

    async def _handle_message(self, message: Dict[str, Any]):
        """Handle individual normalization messages"""
        try:
            logger.info(f"🔄 Processing normalization message: {message}")

            payload = message.get("value") or message
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    pass
            event_type = payload.get("event_type")

            logger.info(f"📋 Extracted event_type: {event_type}")

            if event_type == "normalize_data":
                logger.info("📥 Processing normalize_data event")
                await self._handle_unified_normalization(payload)
            else:
                # Ignore non-normalization messages
                logger.info(f"⏭️ Ignoring non-normalization message: {event_type}")

        except Exception as e:
            logger.error(f"Normalization failed: {e}")
            raise

    async def _handle_unified_normalization(self, payload: Dict[str, Any]):
        """Unified normalization handler - no complex mode switching"""
        logger.info(f"🔄 Starting unified normalization: {payload}")

        shop_id = payload.get("shop_id")
        data_type = payload.get("data_type")
        format_type = payload.get("format", "graphql")
        shopify_id = payload.get("shopify_id")
        source = payload.get("source", "unknown")

        if not shop_id or not data_type:
            logger.error("❌ Invalid normalization event: missing shop_id or data_type")
            return

        logger.info(
            f"📋 Normalization event details: shop_id={shop_id}, data_type={data_type}, "
            f"format={format_type}, source={source}"
        )

        # Create simplified normalization parameters
        normalization_params = {
            "shopify_id": shopify_id,
            "format": format_type,
            "source": source,
        }

        # Use unified normalization method
        success = await self.normalization_service.normalize_data(
            shop_id, data_type, normalization_params
        )

        if success:
            logger.info(f"✅ Normalization completed for {data_type}")

            # Trigger feature computation for the processed data type
            await self.normalization_service.feature_service.trigger_feature_computation(
                shop_id, data_type
            )
            logger.info(f"✅ Feature computation triggered for {data_type}")
        else:
            logger.error(f"❌ Normalization failed for {data_type}")
