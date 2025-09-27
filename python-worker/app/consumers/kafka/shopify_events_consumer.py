"""
Kafka-based Shopify events consumer - Migrated from Redis-based consumer
"""

import logging
from typing import Dict, Any
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.kafka.consumer import KafkaConsumer
from app.core.kafka.producer import KafkaProducer
from app.core.config.kafka_settings import kafka_settings
from app.core.messaging.event_subscriber import EventSubscriber
from app.core.messaging.interfaces import EventHandler
from app.core.logging import get_logger
from app.core.database.session import get_session_context
from app.core.database.models.raw_data import (
    RawProduct,
    RawOrder,
    RawCustomer,
    RawCollection,
)
from app.core.database.models.shop import Shop
from app.core.database.models.user_interaction import UserInteraction
from app.core.database.models.watermarks import PipelineWatermark

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
            shop_domain = event.get("shop_domain")  # New: get shop domain from event
            shop_id = event.get("shop_id")  # Fallback for backward compatibility
            shopify_id = event.get("shopify_id")
            timestamp = event.get("timestamp")
            raw_payload = event.get("raw_payload") or event.get("payload")

            # Resolve shop_id from shop_domain if needed
            if shop_domain and not shop_id:
                shop_id = await self._resolve_shop_id(shop_domain)
                if not shop_id:
                    self.logger.error(
                        f"❌ Could not resolve shop_id for domain: {shop_domain}"
                    )
                    return False

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
                        await self._persist_raw_entity(
                            event_type, shop_id, shopify_id, raw_payload
                        )
                except Exception as raw_err:
                    self.logger.warning(f"RAW persistence failed: {raw_err}")

                # Note: Webhook events are system events, not user interactions
                # User interactions should only be created for actual user behaviors
                # (like page views, clicks, purchases) not for system webhook events
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

            await self._handle_refund_persistence(
                shop_id, order_id, refund_id, raw_payload
            )

            # Note: Refund webhook events are system events, not user interactions
            # User interactions should only be created for actual user behaviors

            # 3. Publish refund normalization event
            now_dt = datetime.now(timezone.utc)
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

    async def _resolve_shop_id(self, shop_domain: str) -> str:
        """Resolve shop_id from shop_domain using SQLAlchemy"""
        async with get_session_context() as session:
            result = await session.execute(
                select(Shop.id).where(Shop.shop_domain == shop_domain)
            )
            shop = result.scalar_one_or_none()
            return str(shop) if shop else None

    async def _persist_raw_entity(
        self,
        event_type: str,
        shop_id: str,
        shopify_id: str,
        raw_payload: Dict[str, Any],
    ) -> None:
        """Persist raw entity using SQLAlchemy"""
        async with get_session_context() as session:
            # Extract updated timestamp if available in payload
            def _extract_dt(payload):
                for key in ["updated_at", "updatedAt", "processed_at", "processedAt"]:
                    if isinstance(payload, dict) and key in payload:
                        return payload.get(key)
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

            # Get the appropriate model class
            model_class = {
                "product_updated": RawProduct,
                "product_created": RawProduct,
                "product_deleted": RawProduct,
                "order_paid": RawOrder,
                "customer_created": RawCustomer,
                "customer_updated": RawCustomer,
                "collection_created": RawCollection,
                "collection_updated": RawCollection,
                "collection_deleted": RawCollection,
            }.get(event_type)

            if not model_class:
                self.logger.error(
                    f"Unknown event type for raw persistence: {event_type}"
                )
                return

            # Check if record exists
            existing = await session.execute(
                select(model_class).where(
                    model_class.shop_id == shop_id, model_class.shopify_id == shopify_id
                )
            )
            existing_record = existing.scalar_one_or_none()

            if existing_record:
                # Update existing record
                existing_record.payload = raw_payload
                existing_record.shopify_updated_at = shopify_updated
                existing_record.format = "rest"
                existing_record.source = "webhook"
                existing_record.received_at = datetime.now(timezone.utc)
            else:
                # Create new record
                new_record = model_class(
                    shop_id=shop_id,
                    shopify_id=shopify_id,
                    payload=raw_payload,
                    shopify_updated_at=shopify_updated,
                    format="rest",
                    source="webhook",
                    received_at=datetime.now(timezone.utc),
                )
                session.add(new_record)

            await session.commit()
            self.logger.info(
                "🗄️ RAW upsert complete",
                extra={
                    "shop_id": shop_id,
                    "shopify_id": shopify_id,
                    "event_type": event_type,
                },
            )

    async def _persist_user_interaction(
        self, shop_id: str, event_type: str, timestamp: str, event: Dict[str, Any]
    ) -> None:
        """Persist user interaction using SQLAlchemy"""
        async with get_session_context() as session:
            # Create user interaction
            user_interaction = UserInteraction(
                session_id=f"shopify_{timestamp}",
                extension_type="shopify_webhook",
                interaction_type=event_type,
                customer_id=None,
                shop_id=shop_id,
                metadata=event,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            session.add(user_interaction)

            # Update pipeline watermark
            now_dt = datetime.now(timezone.utc).replace(tzinfo=None)

            # Check if watermark exists
            existing_watermark = await session.execute(
                select(PipelineWatermark).where(
                    PipelineWatermark.shop_id == shop_id,
                    PipelineWatermark.data_type == "user_interactions",
                )
            )
            watermark = existing_watermark.scalar_one_or_none()

            if watermark:
                watermark.last_collected_at = now_dt
                watermark.last_window_end = now_dt
            else:
                new_watermark = PipelineWatermark(
                    shop_id=shop_id,
                    data_type="user_interactions",
                    last_collected_at=now_dt,
                    last_window_end=now_dt,
                )
                session.add(new_watermark)

            await session.commit()
            self.logger.info(
                "📝 Stored webhook as user_interaction and updated watermark",
                extra={"shop_id": shop_id, "event_type": event_type},
            )

    async def _handle_refund_persistence(
        self, shop_id: str, order_id: str, refund_id: str, raw_payload: Dict[str, Any]
    ) -> None:
        """Handle refund persistence using SQLAlchemy"""
        async with get_session_context() as session:
            now_dt = datetime.now(timezone.utc)

            # Check if order exists
            existing_order = await session.execute(
                select(RawOrder).where(
                    RawOrder.shop_id == shop_id, RawOrder.shopify_id == order_id
                )
            )
            existing_record = existing_order.scalar_one_or_none()

            if existing_record:
                # Update existing order with refund information
                existing_payload = (
                    existing_record.payload
                    if isinstance(existing_record.payload, dict)
                    else {}
                )
                updated_payload = {
                    **existing_payload,
                    "refunds": [
                        *(existing_payload.get("refunds", [])),
                        raw_payload,
                    ],
                }

                existing_record.payload = updated_payload
                existing_record.shopify_updated_at = now_dt
                existing_record.source = "webhook"
                existing_record.format = "rest"
                existing_record.received_at = now_dt

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

                new_record = RawOrder(
                    shop_id=shop_id,
                    shopify_id=order_id,
                    payload=minimal_order_payload,
                    shopify_created_at=now_dt,
                    shopify_updated_at=now_dt,
                    source="webhook",
                    format="rest",
                    received_at=now_dt,
                )
                session.add(new_record)
                self.logger.info(
                    f"✅ Created minimal order record for {order_id} with refund {refund_id}"
                )

            await session.commit()
