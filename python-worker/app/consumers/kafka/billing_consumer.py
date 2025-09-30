"""
Kafka-based billing consumer
"""

import logging
from typing import Dict, Any
from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings

logger = logging.getLogger(__name__)


class BillingKafkaConsumer:
    """Kafka consumer for billing events"""

    def __init__(self):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self._initialized = False

    async def initialize(self):
        """Initialize consumer"""
        try:
            # Initialize Kafka consumer
            await self.consumer.initialize(
                topics=["billing-events"], group_id="billing-processors"
            )

            self._initialized = True
            logger.info("Billing Kafka consumer initialized")

        except Exception as e:
            logger.error(f"Failed to initialize billing consumer: {e}")
            raise

    async def start_consuming(self):
        """Start consuming messages"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info("Starting billing consumer...")
            async for message in self.consumer.consume():
                try:
                    await self._handle_message(message)
                    await self.consumer.commit(message)
                except Exception as e:
                    logger.error(f"Error processing billing message: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error in billing consumer: {e}")
            raise

    async def close(self):
        """Close consumer"""
        if self.consumer:
            await self.consumer.close()
        logger.info("Billing consumer closed")

    async def _handle_message(self, message: Dict[str, Any]):
        """Handle individual billing messages"""
        try:
            logger.info(f"🔄 Processing billing message: {message}")

            payload = message.get("value") or message
            if isinstance(payload, str):
                try:
                    import json

                    payload = json.loads(payload)
                except Exception:
                    pass

            event_type = payload.get("event_type")
            shop_id = payload.get("shop_id")
            plan_id = payload.get("plan_id")

            logger.info(f"Processing {event_type} for shop {shop_id} (plan: {plan_id})")

            # Add your billing event processing logic here
            # For example:
            # - Update shop billing status
            # - Suspend shop services
            # - Send billing notifications
            # - Update access control
            # - Trigger plan expiration workflows

        except Exception as e:
            logger.error(f"Error handling billing event: {e}")
            raise
