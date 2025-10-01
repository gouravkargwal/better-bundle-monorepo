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
from app.repository.ShopRepository import ShopRepository
from app.core.services.dlq_service import DLQService

logger = get_logger(__name__)


class NormalizationKafkaConsumer:
    """Kafka consumer for normalization jobs"""

    def __init__(self):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self._initialized = False
        self.normalization_service = NormalizationService()
        self.shop_repo = ShopRepository()
        self.dlq_service = DLQService()

    async def initialize(self):
        """Initialize consumer"""
        try:
            # Initialize Kafka consumer
            await self.consumer.initialize(
                topics=["normalization-jobs"], group_id="normalization-processors"
            )

            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize normalization consumer: {e}")
            raise

    async def start_consuming(self):
        """Start consuming messages"""
        if not self._initialized:
            await self.initialize()

        try:
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

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the normalization consumer"""
        return {
            "status": "running" if self._initialized else "stopped",
            "last_health_check": datetime.utcnow().isoformat(),
        }

    async def _handle_message(self, message: Dict[str, Any]):
        """Handle individual normalization messages"""
        try:

            payload = message.get("value") or message
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    pass
            event_type = payload.get("event_type")
            shop_id = payload.get("shop_id")
            if not shop_id:
                logger.error("❌ Invalid normalization event: missing shop_id")
                return

            if not await self.shop_repo.is_shop_active(shop_id):
                logger.warning(
                    "Shop is not active for normalization",
                    shop_id=shop_id,
                )
                await self.dlq_service.send_to_dlq(
                    original_message=payload,
                    reason="shop_suspended",
                    original_topic="normalization-jobs",
                    error_details=f"Shop suspended at {datetime.utcnow().isoformat()}",
                )
                await self.consumer.commit(message)
                return

            if event_type == "normalize_data":
                await self._handle_unified_normalization(payload)

        except Exception as e:
            logger.error(f"Normalization failed: {e}")
            raise

    async def _handle_unified_normalization(self, payload: Dict[str, Any]):
        """Unified normalization handler - no complex mode switching"""
        try:
            shop_id = payload.get("shop_id")
            data_type = payload.get("data_type")
            format_type = payload.get("format", "graphql")
            shopify_id = payload.get("shopify_id")
            source = payload.get("source", "unknown")

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
                # Trigger feature computation for the processed data type
                await self.normalization_service.feature_service.trigger_feature_computation(
                    shop_id, data_type
                )
            else:
                logger.error(f"❌ Normalization failed for {data_type}")
        except Exception as e:
            logger.error(f"Normalization failed: {e}")
            raise
