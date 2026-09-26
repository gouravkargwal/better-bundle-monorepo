"""
Kafka consumer for Shopify usage record charging.

Listens on shopify-usage-events and charges paid commissions to Shopify.
"""

import json
import logging
from typing import Dict, Any

from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.domains.billing.services.commission_service_v2 import CommissionServiceV2
from app.core.exceptions import CapError, TransientError, PermanentError

logger = logging.getLogger(__name__)


class ShopifyUsageKafkaConsumer:
    """Consumes shopify-usage-events and charges paid commissions to Shopify."""

    def __init__(self):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self._initialized = False
        self.commission_service = CommissionServiceV2()

    async def initialize(self):
        try:
            await self.consumer.initialize(
                topics=["shopify-usage-events"],
                group_id="shopify-usage-processors",
            )
            self._initialized = True
            logger.info("Shopify usage Kafka consumer initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Shopify usage consumer: {e}")
            raise

    async def start_consuming(self):
        if not self._initialized:
            await self.initialize()

        try:
            logger.info("Starting Shopify usage consumer...")
            async for message in self.consumer.consume():
                try:
                    await self._handle_message(message)
                    await self.consumer.commit(message)
                except Exception as e:
                    logger.error(f"Error processing Shopify usage message: {e}")
                    raise
        except Exception as e:
            logger.error(f"Error in Shopify usage consumer: {e}")
            raise

    async def close(self):
        if self.consumer:
            await self.consumer.close()
        logger.info("Shopify usage consumer closed")

    async def _handle_message(self, message: Dict[str, Any]):
        payload = message.get("value") or message
        if isinstance(payload, str):
            payload = json.loads(payload)

        event_type = payload.get("event_type")
        commission_id = payload.get("commission_id")

        if event_type != "record_usage" or not commission_id:
            logger.warning(
                "Unexpected Shopify usage event",
                event_type=event_type,
                commission_id=commission_id,
            )
            return

        try:
            await self.commission_service.charge_commission_to_shopify(commission_id)
        except TransientError:
            raise
        except (CapError, PermanentError):
            logger.error(
                "Terminal Shopify charge failure for commission %s",
                commission_id,
                exc_info=True,
            )
        except Exception as e:
            logger.error(
                "Unexpected error charging commission %s: %s",
                commission_id,
                e,
                exc_info=True,
            )
