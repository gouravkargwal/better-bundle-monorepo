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
from app.core.database.simple_db_client import get_database

# Using string values directly for database insertion
from datetime import datetime, timezone

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

            # Initialize event subscriber with existing consumer to avoid duplicate consumers
            await self.event_subscriber.initialize(
                topics=["shopify-events"],
                group_id="shopify-events-processors",
                existing_consumer=self.consumer,  # Reuse existing consumer
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
            "refund_created",
            "normalize_entity",  # Skip our own forwarded messages
        ]

    async def handle(self, event: Dict[str, Any]) -> bool:
        """Handle Shopify events and forward to normalization jobs"""
        try:
            event_type = event.get("event_type")
            shop_id = event.get("shop_id")
            shopify_id = event.get("shopify_id")
            timestamp = event.get("timestamp")
            raw_payload = event.get("raw_payload") or event.get("payload")

            self.logger.info(
                f"📥 Received Shopify event: {event_type} for shop {shop_id}, entity {shopify_id}"
            )

            # Skip normalize_entity events (these are our own forwarded messages)
            if event_type == "normalize_entity":
                self.logger.debug(
                    "⏭️ Skipping normalize_entity - our own forwarded message"
                )
                return True

            # Handle refund_created events specially
            if event_type == "refund_created":
                return await self._handle_refund_event(event)

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
                # 0) Persist RAW entity if payload is present (idempotent upsert)
                try:
                    if raw_payload and shopify_id and shop_id:
                        db = await get_database()
                        data_type = self._get_entity_type(event_type)
                        table = {
                            "products": db.rawproduct,
                            "orders": db.raworder,
                            "customers": db.rawcustomer,
                            "collections": db.rawcollection,
                        }.get(data_type)
                        if table:
                            # Extract updated timestamp if available in payload
                            def _extract_dt(p):
                                for key in [
                                    "updated_at",
                                    "updatedAt",
                                    "processed_at",
                                    "processedAt",
                                ]:
                                    if isinstance(p, dict) and key in p:
                                        return p.get(key)
                                return None

                            updated_str = _extract_dt(raw_payload)
                            shopify_updated = None
                            if updated_str:
                                try:
                                    shopify_updated = datetime.fromisoformat(
                                        str(updated_str).replace("Z", "+00:00")
                                    )
                                except Exception:
                                    shopify_updated = None
                            # Upsert by (shopId, shopifyId)
                            await table.upsert(
                                where={
                                    "shop_id_shopify_id": {
                                        "shop_id": str(shop_id),
                                        "shopify_id": str(shopify_id),
                                    }
                                },
                                data={
                                    "update": {
                                        "payload": raw_payload,
                                        "shopifyUpdatedAt": shopify_updated,
                                        "format": "rest",
                                        "source": "webhook",
                                    },
                                    "create": {
                                        "shop_id": str(shop_id),
                                        "payload": raw_payload,
                                        "shopify_id": str(shopify_id),
                                        "shopifyUpdatedAt": shopify_updated,
                                        "format": "rest",
                                        "source": "webhook",
                                    },
                                },
                            )
                            self.logger.info(
                                "🗄️ RAW upsert complete",
                                extra={
                                    "shop_id": shop_id,
                                    "shopify_id": shopify_id,
                                    "data_type": data_type,
                                },
                            )
                except Exception as raw_err:
                    self.logger.warning(f"RAW persistence failed: {raw_err}")

                # 1) Persist as real-time user interaction (non-historical)
                try:
                    db = await get_database()
                    await db.userinteraction.create(
                        data={
                            "sessionId": f"shopify_{timestamp}",
                            "extensionType": "shopify_webhook",
                            "interactionType": event_type,
                            "customerId": None,
                            "shop_id": str(shop_id),
                            "metadata": event,
                        }
                    )
                    # Update PipelineWatermark for user_interactions
                    now_dt = datetime.now(timezone.utc)
                    await db.pipelinewatermark.upsert(
                        where={
                            "shop_id_data_type": {
                                "shop_id": str(shop_id),
                                "data_type": "user_interactions",
                            }
                        },
                        data={
                            "update": {
                                "lastCollectedAt": now_dt,
                                "lastWindowEnd": now_dt,
                            },
                            "create": {
                                "shop_id": str(shop_id),
                                "data_type": "user_interactions",
                                "lastCollectedAt": now_dt,
                                "lastWindowEnd": now_dt,
                            },
                        },
                    )
                    self.logger.info(
                        "📝 Stored webhook as user_interaction and updated watermark",
                        extra={"shop_id": shop_id, "event_type": event_type},
                    )
                except Exception as persist_err:
                    self.logger.error(
                        f"Failed to persist user_interaction: {persist_err}",
                    )
                # 2) Create a normalize_entity job for the resource itself (REST single-entity)
                normalize_job = {
                    "event_type": "normalize_data",
                    "data_type": self._get_entity_type(event_type),
                    "format": "rest",  # Webhooks are REST format
                    "shop_id": str(shop_id),
                    "shopify_id": shopify_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "original_event_type": event_type,
                }

                # Publish to normalization-jobs topic using Kafka producer
                try:
                    await self.producer.send(
                        topic="normalization-jobs",
                        message=normalize_job,
                        key=f"{shop_id}_{shopify_id}_{event_type}",
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

    async def _handle_refund_event(self, event: Dict[str, Any]) -> bool:
        """Handle refund_created events - store in RawOrder and trigger refund normalization"""
        try:
            shop_id = event.get("shop_id")
            order_id = event.get("shopify_id")  # This is the order ID for refunds
            refund_id = event.get("refund_id")
            raw_payload = event.get("raw_payload")
            timestamp = event.get("timestamp")

            self.logger.info(
                f"💰 Processing refund event: refund_id={refund_id}, order_id={order_id}, shop_id={shop_id}"
            )

            if not all([shop_id, order_id, refund_id, raw_payload]):
                self.logger.error("❌ Missing required fields for refund event")
                return False

            db = await get_database()
            now_dt = datetime.now(timezone.utc)

            # 1. Store/update refund data in RawOrder table
            try:
                # Check if order exists
                existing_order = await db.raworder.find_first(
                    where={"shop_id": shop_id, "shopify_id": order_id},
                    select={"id": True, "payload": True},
                )

                if existing_order:
                    # Update existing order with refund information
                    existing_payload = (
                        existing_order.payload
                        if isinstance(existing_order.payload, dict)
                        else {}
                    )
                    updated_payload = {
                        **existing_payload,
                        "refunds": [
                            *(existing_payload.get("refunds", [])),
                            raw_payload,
                        ],
                    }

                    await db.raworder.update(
                        where={"id": existing_order.id},
                        data={
                            "payload": updated_payload,
                            "shopifyUpdatedAt": now_dt,
                            "source": "webhook",
                            "format": "rest",
                            "receivedAt": now_dt,
                        },
                    )
                    self.logger.info(
                        f"✅ Updated existing order {order_id} with refund {refund_id}"
                    )
                else:
                    # Create minimal order record with refund data
                    self.logger.info(
                        f"⚠️ Order {order_id} not found, creating minimal record with refund data"
                    )

                    minimal_order_payload = {
                        "refunds": [raw_payload],
                        "id": order_id,
                        "created_at": raw_payload.get("created_at", now_dt.isoformat()),
                        "line_items": [],  # Empty array to prevent consumer errors
                        "total_price": "0.00",
                        "currency": "USD",
                    }

                    await db.raworder.create(
                        data={
                            "shop_id": shop_id,
                            "payload": minimal_order_payload,
                            "shopify_id": order_id,
                            "shopifyCreatedAt": now_dt,
                            "shopifyUpdatedAt": now_dt,
                            "source": "webhook",
                            "format": "rest",
                            "receivedAt": now_dt,
                        }
                    )
                    self.logger.info(
                        f"✅ Created minimal order record for {order_id} with refund {refund_id}"
                    )

            except Exception as raw_err:
                self.logger.error(f"❌ Failed to store refund in RawOrder: {raw_err}")
                return False

            # 2. Record user interaction
            try:
                await db.userinteraction.create(
                    data={
                        "sessionId": f"refund_{timestamp}",
                        "extensionType": "shopify_webhook",
                        "interactionType": "refund_created",
                        "customerId": None,
                        "shop_id": str(shop_id),
                        "metadata": event,
                        "createdAt": now_dt,
                    }
                )

                # Update PipelineWatermark for user_interactions
                await db.pipelinewatermark.upsert(
                    where={
                        "shop_id_data_type": {
                            "shop_id": str(shop_id),
                            "data_type": "user_interactions",
                        }
                    },
                    data={
                        "update": {
                            "lastCollectedAt": now_dt,
                            "lastWindowEnd": now_dt,
                        },
                        "create": {
                            "shop_id": str(shop_id),
                            "data_type": "user_interactions",
                            "lastCollectedAt": now_dt,
                            "lastWindowEnd": now_dt,
                        },
                    },
                )
                self.logger.info(
                    "✅ Recorded refund as user interaction and updated watermark"
                )

            except Exception as persist_err:
                self.logger.error(
                    f"❌ Failed to persist user interaction: {persist_err}"
                )

            # 3. Publish refund normalization event
            refund_normalize_job = {
                "event_type": "refund_created",
                "shop_id": str(shop_id),
                "shopify_id": order_id,
                "refund_id": refund_id,
                "timestamp": now_dt.isoformat(),
            }

            try:
                await self.producer.send(
                    topic="refund-normalization-jobs",
                    message=refund_normalize_job,
                    key=f"{shop_id}_{order_id}_{refund_id}",
                )
                self.logger.info(
                    f"✅ Published refund normalization job for order {order_id}, refund {refund_id}"
                )

            except Exception as e:
                self.logger.error(f"❌ Failed to publish refund normalization job: {e}")
                return False

            return True

        except Exception as e:
            self.logger.error(f"❌ Error processing refund event: {e}")
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
