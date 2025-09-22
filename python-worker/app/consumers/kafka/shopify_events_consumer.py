"""
Kafka-based Shopify events consumer - Migrated from Redis-based consumer
"""

import logging
from typing import Dict, Any
from datetime import datetime
from app.core.kafka.consumer import KafkaConsumer
from app.core.kafka.producer import KafkaProducer
from app.core.config.kafka_settings import kafka_settings
from app.core.messaging.event_subscriber import EventSubscriber
from app.core.messaging.interfaces import EventHandler
from app.core.logging import get_logger

logger = get_logger(__name__)


class ShopifyEventsKafkaConsumer:
    """Kafka consumer for Shopify events - Migrated from Redis-based consumer"""

    def __init__(self):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self.producer = KafkaProducer(kafka_settings.model_dump())
        self.event_subscriber = EventSubscriber(kafka_settings.model_dump())
        self._initialized = False

    async def initialize(self):
        """Initialize consumer and producer"""
        try:
            # Initialize Kafka consumer
            await self.consumer.initialize(
                topics=["shopify-events"], group_id="shopify-events-processors"
            )

            # Initialize Kafka producer for publishing normalization jobs
            await self.producer.initialize()

            # Initialize event subscriber
            await self.event_subscriber.initialize(
                topics=["shopify-events"], group_id="shopify-events-processors"
            )

            # Add event handlers
            self.event_subscriber.add_handler(ShopifyEventHandler(self.producer))

            self._initialized = True
            logger.info("Shopify events Kafka consumer initialized")

        except Exception as e:
            logger.error(f"Failed to initialize Shopify events consumer: {e}")
            raise

    async def start_consuming(self):
        """Start consuming messages"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info("Starting Shopify events consumer...")
            await self.event_subscriber.consume_and_handle(
                topics=["shopify-events"], group_id="shopify-events-processors"
            )
        except Exception as e:
            logger.error(f"Error in Shopify events consumer: {e}")
            raise

    async def close(self):
        """Close consumer and producer"""
        if self.consumer:
            await self.consumer.close()
        if self.producer:
            await self.producer.close()
        if self.event_subscriber:
            await self.event_subscriber.close()
        logger.info("Shopify events consumer closed")


class ShopifyEventHandler(EventHandler):
    """Handler for all Shopify events - Migrated from Redis-based consumer logic"""

    def __init__(self, producer: KafkaProducer):
        self.producer = producer
        self.logger = get_logger(__name__)

    def can_handle(self, event_type: str) -> bool:
        """Check if this handler can handle the event type"""
        return event_type in [
            "product_updated",
            "product_created",
            "product_deleted",
            "order_paid",
            "customer_created",
            "customer_updated",
            "collection_created",
            "collection_updated",
            "collection_deleted",
            "normalize_entity",  # Skip our own forwarded messages
            "refund_created",  # Skip - handled directly by webhook
        ]

    async def handle(self, event: Dict[str, Any]) -> bool:
        """Handle Shopify events and forward to normalization jobs"""
        try:
            event_type = event.get("event_type")
            shop_id = event.get("shop_id")
            shopify_id = event.get("shopify_id")
            timestamp = event.get("timestamp")

            self.logger.info(
                f"📥 Received Shopify event: {event_type} for shop {shop_id}, entity {shopify_id}"
            )

            # Skip normalize_entity events (these are our own forwarded messages)
            if event_type == "normalize_entity":
                self.logger.debug(
                    "⏭️ Skipping normalize_entity - our own forwarded message"
                )
                return True

            # Skip refund_created events - they are now handled directly by webhook
            if event_type == "refund_created":
                self.logger.info(
                    f"⏭️ Skipping {event_type} - handled directly by webhook"
                )
                return True

            # Only process original Shopify webhook events, not our own forwarded messages
            elif event_type in [
                "product_updated",
                "product_created",
                "product_deleted",
                "order_paid",
                "customer_created",
                "customer_updated",
                "collection_created",
                "collection_updated",
                "collection_deleted",
            ]:
                # Create a normalize_entity job for the event
                normalize_job = {
                    "event_type": "normalize_entity",
                    "data_type": self._get_entity_type(event_type),
                    "format": "rest",  # All webhook events are REST format
                    "shop_id": str(shop_id),  # Ensure string
                    "shopify_id": shopify_id,  # Keep as integer - NormalizeJob now accepts both
                    "timestamp": datetime.utcnow().isoformat(),  # Convert to ISO string
                    "original_event_type": event_type,  # Pass the original Shopify event type
                }

                # Publish to normalization-jobs topic using Kafka producer
                try:
                    await self.producer.send(
                        topic="normalization-jobs",
                        message=normalize_job,
                        key=f"{shop_id}_{shopify_id}_{event_type}",  # Use shop_id for partitioning
                    )

                    self.logger.info(
                        f"✅ Published normalization job for {event_type} -> {normalize_job['data_type']} "
                        f"(shop: {shop_id}, entity: {shopify_id})"
                    )

                except Exception as e:
                    self.logger.error(f"❌ Failed to publish normalization job: {e}")
                    return False

            else:
                self.logger.warning(f"⚠️ Unknown event type: {event_type}")

            return True

        except Exception as e:
            self.logger.error(f"❌ Error processing Shopify event: {e}")
            return False

    def _get_entity_type(self, event_type: str) -> str:
        """Map event type to entity type - Migrated from Redis-based consumer"""
        mapping = {
            "product_updated": "products",
            "product_created": "products",
            "product_deleted": "products",
            "order_paid": "orders",
            "customer_created": "customers",
            "customer_updated": "customers",
            "customer_redacted": "customers",
            "collection_created": "collections",
            "collection_updated": "collections",
            "collection_deleted": "collections",
        }
        return mapping.get(event_type, "unknown")
