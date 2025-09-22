"""
Kafka-based billing consumer
"""

import logging
from typing import Dict, Any
from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.core.messaging.event_subscriber import EventSubscriber
from app.core.messaging.interfaces import EventHandler

logger = logging.getLogger(__name__)


class BillingKafkaConsumer:
    """Kafka consumer for billing events"""

    def __init__(self):
        self.consumer = KafkaConsumer(kafka_settings.dict())
        self.event_subscriber = EventSubscriber(kafka_settings.dict())
        self._initialized = False

    async def initialize(self):
        """Initialize consumer"""
        try:
            # Initialize Kafka consumer
            await self.consumer.initialize(
                topics=["billing-events"], group_id="billing-processors"
            )

            # Initialize event subscriber
            await self.event_subscriber.initialize(
                topics=["billing-events"], group_id="billing-processors"
            )

            # Add event handlers
            self.event_subscriber.add_handler(BillingEventHandler())

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
            await self.event_subscriber.consume_and_handle(
                topics=["billing-events"], group_id="billing-processors"
            )
        except Exception as e:
            logger.error(f"Error in billing consumer: {e}")
            raise

    async def close(self):
        """Close consumer"""
        if self.consumer:
            await self.consumer.close()
        if self.event_subscriber:
            await self.event_subscriber.close()
        logger.info("Billing consumer closed")


class BillingEventHandler(EventHandler):
    """Handler for billing events"""

    def can_handle(self, event_type: str) -> bool:
        return event_type in [
            "plan_expired",
            "trial_ended",
            "subscription_cancelled",
            "payment_failed",
            "charge_created",
            "charge_failed",
            "charge_cancelled",
        ]

    async def handle(self, event: Dict[str, Any]) -> bool:
        try:
            event_type = event.get("event_type")
            shop_id = event.get("shop_id")
            plan_id = event.get("plan_id")

            logger.info(f"Processing {event_type} for shop {shop_id} (plan: {plan_id})")

            # Add your billing event processing logic here
            # For example:
            # - Update shop billing status
            # - Suspend shop services
            # - Send billing notifications
            # - Update access control
            # - Trigger plan expiration workflows

            return True

        except Exception as e:
            logger.error(f"Error handling billing event: {e}")
            return False
