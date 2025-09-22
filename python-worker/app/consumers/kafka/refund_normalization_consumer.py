"""
Kafka-based refund normalization consumer for processing refund_created events
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta
from decimal import Decimal

from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.core.messaging.event_subscriber import EventSubscriber
from app.core.messaging.interfaces import EventHandler
from app.core.messaging.event_publisher import EventPublisher
from app.core.database.simple_db_client import get_database
from app.core.logging import get_logger
from prisma import Json


logger = get_logger(__name__)


class RefundNormalizationKafkaConsumer:
    """Kafka consumer for refund normalization jobs (listens to shopify-events)."""

    def __init__(self):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self.event_subscriber = EventSubscriber(kafka_settings.model_dump())
        self.publisher = EventPublisher(kafka_settings.model_dump())
        self._initialized = False

    async def initialize(self):
        """Initialize consumer and handlers."""
        try:
            # Initialize Kafka consumer and event subscriber on refund-specific topic
            topics = ["refund-normalization-jobs"]
            group_id = "refund-normalization-processors"

            await self.consumer.initialize(topics=topics, group_id=group_id)
            await self.event_subscriber.initialize(topics=topics, group_id=group_id)

            # Add handler
            self.event_subscriber.add_handler(
                RefundNormalizationJobHandler(self.publisher)
            )

            self._initialized = True
            logger.info("Refund normalization Kafka consumer initialized")

        except Exception as e:
            logger.error(f"Failed to initialize refund normalization consumer: {e}")
            raise

    async def start_consuming(self):
        """Start consuming messages."""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info("Starting refund normalization consumer...")
            await self.event_subscriber.consume_and_handle(
                topics=["refund-normalization-jobs"],
                group_id="refund-normalization-processors",
            )
        except Exception as e:
            logger.error(f"Error in refund normalization consumer: {e}")
            raise

    async def close(self):
        """Close consumer and dependencies."""
        if self.consumer:
            await self.consumer.close()
        if self.event_subscriber:
            await self.event_subscriber.close()
        if self.publisher:
            await self.publisher.close()
        logger.info("Refund normalization consumer closed")

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the refund normalization consumer."""
        return {
            "status": "running" if self._initialized else "stopped",
            "last_health_check": datetime.utcnow().isoformat(),
        }


class RefundNormalizationJobHandler(EventHandler):
    """Handler for refund normalization events coming from shopify-events."""

    def __init__(self, publisher: EventPublisher):
        self.logger = get_logger(__name__)
        self.publisher = publisher

    def can_handle(self, event_type: str) -> bool:
        # We only handle refund_created events from the unified shopify-events topic
        return event_type == "refund_created"

    async def handle(self, event: Dict[str, Any]) -> bool:
        try:
            self.logger.info(f"🔄 Processing refund normalization message: {event}")

            # Extract data from the simplified event structure
            event_type = event.get("event_type")
            shop_id = event.get("shop_id")
            order_id = event.get("shopify_id")
            refund_id = event.get("refund_id")

            self.logger.info(
                f"📋 Extracted data: event_type={event_type}, shop_id={shop_id}, order_id={order_id}, refund_id={refund_id}"
            )

            if event_type != "refund_created":
                self.logger.info(f"⏭️ Ignoring non-refund event: {event_type}")
                return True

            if not shop_id or not order_id or not refund_id:
                self.logger.error(
                    "❌ Invalid refund_created payload - missing required fields",
                    message=event,
                )
                return True

            db = await get_database()
            self.logger.info(
                f"🔍 Fetching RawOrder data for shop_id: {shop_id}, order_id: {order_id}"
            )

            # Load raw refund data from RawOrder using shop_id and order_id
            raw_order = await db.raworder.find_first(
                where={"shopId": shop_id, "shopifyId": order_id}
            )
            if not raw_order or not getattr(raw_order, "payload", None):
                self.logger.warning(
                    "RawOrder not found for refund normalization",
                    shop_id=shop_id,
                    order_id=order_id,
                )
                return True

            # Extract refund from payload
            payload_data = (
                raw_order.payload if isinstance(raw_order.payload, dict) else {}
            )

            # Check if this is a minimal record created by refund webhook (order webhook hasn't arrived yet)
            if "refunds" in payload_data and not payload_data.get("line_items"):
                self.logger.info(
                    "Order data incomplete - refund webhook arrived before order webhook",
                    shop_id=shop_id,
                    order_id=order_id,
                )

            # Extract specific refund from payload by refund_id
            refund_obj: Optional[Dict[str, Any]] = None
            try:
                refunds: List[Dict[str, Any]] = payload_data.get("refunds") or []
                if refunds:
                    # Find the specific refund by refund_id
                    for refund in refunds:
                        if str(refund.get("id", "")) == str(refund_id):
                            refund_obj = refund
                            break

                    if refund_obj:
                        self.logger.info(f"📋 Processing refund ID: {refund_id}")
                    else:
                        self.logger.warning(
                            f"Refund {refund_id} not found in payload refunds"
                        )
                        return True
                else:
                    self.logger.warning("No refunds found in payload")
                    return True
            except Exception as e:
                self.logger.error(
                    "Failed to extract refund from raw payload", error=str(e)
                )
                return True

            if not refund_obj:
                self.logger.warning(
                    "Refund object not found in raw payload",
                    shop_id=shop_id,
                    order_id=order_id,
                )
                return True

            # PRE-CHECK: Only process refunds from orders with extension interactions
            if not await self._has_extension_interactions_for_order(
                db, shop_id, order_id
            ):
                self.logger.info(
                    f"⏭️ Skipping refund normalization for order {order_id} - no extension interactions found",
                    shop_id=shop_id,
                    order_id=order_id,
                )
                return True

            # Process refund within a transaction
            async with db.tx() as transaction:
                # Get currency from original order data
                order_data = await transaction.orderdata.find_first(
                    where={"shopId": shop_id, "orderId": order_id}
                )
                currency_code = "USD"  # Default fallback
                if order_data and order_data.currencyCode:
                    currency_code = order_data.currencyCode
                elif order_data and order_data.presentmentCurrencyCode:
                    currency_code = order_data.presentmentCurrencyCode

                # Create RefundData
                refunded_at = datetime.utcnow()
                if refund_obj.get("created_at"):
                    try:
                        refunded_at = datetime.fromisoformat(
                            refund_obj["created_at"].replace("Z", "+00:00")
                        )
                    except Exception:
                        pass

                # Calculate refund amount from Shopify data
                shopify_refund_amount = 0.0
                if refund_obj.get("transactions"):
                    shopify_refund_amount = sum(
                        float(t.get("amount", 0)) for t in refund_obj["transactions"]
                    )

                # Use Shopify refund amount
                final_refund_amount = shopify_refund_amount

                refund_data = await transaction.refunddata.create(
                    data={
                        "shopId": shop_id,
                        "orderId": order_id,
                        "refundId": refund_id,
                        "refundedAt": refunded_at,
                        "note": refund_obj.get("note") or "",
                        "restock": refund_obj.get("restock", False),
                        "totalRefundAmount": Decimal(str(final_refund_amount)),
                        "currencyCode": currency_code,
                    }
                )

                # Create RefundLineItemData from refund_line_items
                refund_line_items = refund_obj.get("refund_line_items") or []
                for rli in refund_line_items:
                    line_item = rli.get("line_item") or {}
                    quantity = int(
                        rli.get("quantity") or line_item.get("quantity") or 0
                    )
                    if quantity <= 0:
                        continue

                    # Use subtotal from refund_line_item (more accurate than calculating)
                    refund_amount_item = float(rli.get("subtotal") or 0.0)
                    unit_price = refund_amount_item / quantity if quantity > 0 else 0.0

                    await transaction.refundlineitemdata.create(
                        data={
                            "refundId": refund_data.id,
                            "orderId": order_id,
                            "productId": (
                                str(line_item.get("product_id"))
                                if line_item.get("product_id")
                                else None
                            ),
                            "variantId": (
                                str(line_item.get("variant_id"))
                                if line_item.get("variant_id")
                                else None
                            ),
                            "quantity": quantity,
                            "unitPrice": Decimal(str(unit_price)),
                            "refundAmount": Decimal(str(refund_amount_item)),
                            "properties": Json({}),  # Populated by attribution consumer
                        }
                    )

            self.logger.info(
                "Refund normalized successfully",
                shop_id=shop_id,
                order_id=order_id,
                refund_id=refund_id,
                line_items=len(refund_line_items),
            )

            # Trigger refund attribution after successful normalization via Kafka
            await self.publisher.publish_refund_attribution_event(
                {
                    "event_type": "refund_created",
                    "shop_id": shop_id,
                    "refund_id": refund_id,
                    "shopify_id": order_id,
                }
            )
            self.logger.info(
                "📤 Triggered refund attribution after normalization (Kafka)"
            )

            return True

        except Exception as e:
            self.logger.error("Failed to normalize refund", error=str(e))
            return False

    async def _has_extension_interactions_for_order(
        self, db, shop_id: str, order_id: str
    ) -> bool:
        """
        Check if the original order had any extension interactions that could drive attribution.
        Only processes refunds from orders that had extension interactions.
        """
        try:
            # First, get the order data to find customer_id
            order = await db.orderdata.find_first(
                where={"shopId": shop_id, "orderId": order_id}
            )
            if not order:
                self.logger.warning(
                    f"Order not found for refund interaction check",
                    shop_id=shop_id,
                    order_id=order_id,
                )
                return False

            customer_id = getattr(order, "customerId", None)
            if not customer_id:
                self.logger.info(
                    f"No customer_id for order {order_id} - skipping refund processing",
                    shop_id=shop_id,
                    order_id=order_id,
                )
                return False

            cutoff_time = datetime.utcnow() - timedelta(days=30)

            # Check for any interactions from attribution-eligible extensions
            interactions = await db.userinteraction.find_many(
                where={
                    "shopId": shop_id,
                    "customerId": customer_id,
                    "createdAt": {"gte": cutoff_time},
                    "extensionType": {"in": ["phoenix", "venus", "apollo"]},
                },
                take=1,
            )

            has_interactions = len(interactions) > 0

            if has_interactions:
                self.logger.info(
                    f"✅ Found {len(interactions)} extension interactions for order {order_id}",
                    shop_id=shop_id,
                    order_id=order_id,
                    customer_id=customer_id,
                )
            else:
                self.logger.info(
                    f"❌ No extension interactions found for order {order_id}",
                    shop_id=shop_id,
                    order_id=order_id,
                    customer_id=customer_id,
                )

            return has_interactions

        except Exception as e:
            self.logger.error(f"Error checking extension interactions for order: {e}")
            # If we can't check, err on the side of processing to avoid missing refunds
            return True
