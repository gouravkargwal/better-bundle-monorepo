"""
Kafka-based refund attribution consumer for processing refund attribution events
"""

import logging
from typing import Any, Dict, List
from datetime import datetime
from decimal import Decimal
from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.core.messaging.event_subscriber import EventSubscriber
from app.core.messaging.interfaces import EventHandler
from app.core.database.simple_db_client import get_database
from app.core.logging import get_logger

logger = get_logger(__name__)


class RefundAttributionKafkaConsumer:
    """Kafka consumer for refund attribution jobs"""

    def __init__(self):
        self.consumer = KafkaConsumer(kafka_settings.dict())
        self.event_subscriber = EventSubscriber(kafka_settings.dict())
        self._initialized = False

    async def initialize(self):
        """Initialize consumer"""
        try:
            # Initialize Kafka consumer
            await self.consumer.initialize(
                topics=["refund-attribution-jobs"],
                group_id="refund-attribution-processors",
            )

            # Initialize event subscriber
            await self.event_subscriber.initialize(
                topics=["refund-attribution-jobs"],
                group_id="refund-attribution-processors",
            )

            # Add event handlers
            self.event_subscriber.add_handler(RefundAttributionJobHandler())

            self._initialized = True
            logger.info("Refund attribution Kafka consumer initialized")

        except Exception as e:
            logger.error(f"Failed to initialize refund attribution consumer: {e}")
            raise

    async def start_consuming(self):
        """Start consuming messages"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info("Starting refund attribution consumer...")
            await self.event_subscriber.consume_and_handle(
                topics=["refund-attribution-jobs"],
                group_id="refund-attribution-processors",
            )
        except Exception as e:
            logger.error(f"Error in refund attribution consumer: {e}")
            raise

    async def close(self):
        """Close consumer"""
        if self.consumer:
            await self.consumer.close()
        if self.event_subscriber:
            await self.event_subscriber.close()
        logger.info("Refund attribution consumer closed")

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the refund attribution consumer"""
        return {
            "status": "running" if self._initialized else "stopped",
            "last_health_check": datetime.utcnow().isoformat(),
        }


class RefundAttributionJobHandler(EventHandler):
    """Handler for refund attribution jobs"""

    def __init__(self):
        self.logger = get_logger(__name__)

    def can_handle(self, event_type: str) -> bool:
        return event_type in [
            "refund_created",
            "refund_attribution_batch",
            "refund_attribution",
        ]

    async def handle(self, event: Dict[str, Any]) -> bool:
        try:
            self.logger.info(f"🔄 Processing refund attribution message: {event}")

            event_type = event.get("event_type")

            # Route to appropriate handler
            if event_type == "refund_created":
                await self._handle_individual_refund_attribution(event)
            elif event_type == "refund_attribution_batch":
                await self._handle_batch_refund_attribution(event)
            else:
                self.logger.warning(f"⚠️ Unknown event type: {event_type}")
                return True

            return True

        except Exception as e:
            self.logger.error(f"Failed to process refund attribution message: {e}")
            return False

    async def _handle_individual_refund_attribution(self, message: Dict[str, Any]):
        """Handle individual refund attribution (real-time events)."""
        try:
            # Extract and validate required fields
            shop_id = message.get("shop_id")
            refund_id = message.get("refund_id")
            order_id = message.get("shopify_id") or message.get("order_id")

            # Robust refund_id extraction with fallback
            if not refund_id:
                refund_id = message.get("raw_record_id")
                if not refund_id:
                    self.logger.warning(
                        "⚠️ No refund_id or raw_record_id found in message, skipping refund attribution"
                    )
                    return

            if not shop_id or not refund_id:
                self.logger.error(
                    "❌ Invalid refund_created payload - missing required fields",
                    message=message,
                )
                return

            self.logger.info(
                f"📋 Processing individual refund attribution: shop_id={shop_id}, refund_id={refund_id}, order_id={order_id}"
            )

            # Use shared processing logic
            db = await get_database()
            await self._process_single_refund_attribution(refund_id, shop_id, db)

        except Exception as e:
            self.logger.error(
                "Failed to process individual refund attribution", error=str(e)
            )
            raise

    async def _handle_batch_refund_attribution(self, message: Dict[str, Any]):
        """Handle batch refund attribution (triggered by normalization batches)."""
        shop_id = message.get("shop_id")
        refund_ids = message.get("refund_ids", [])

        if not shop_id or not refund_ids:
            self.logger.error(
                "❌ Invalid refund_attribution_batch payload - missing required fields",
                message=message,
            )
            return

        self.logger.info(
            f"🔄 Processing batch refund attribution: shop_id={shop_id}, refund_count={len(refund_ids)}"
        )

        db = await get_database()
        successful = 0
        failed = 0

        # Process all refunds in a single transaction for consistency
        try:
            async with db.tx() as transaction:
                for refund_id in refund_ids:
                    try:
                        await self._process_single_refund_attribution(
                            refund_id, shop_id, transaction
                        )
                        successful += 1
                    except Exception as e:
                        self.logger.error(
                            f"Failed to process refund attribution for {refund_id}: {e}"
                        )
                        failed += 1
                        continue

            self.logger.info(
                f"✅ Batch refund attribution completed: successful={successful}, failed={failed}"
            )

        except Exception as e:
            self.logger.error(f"Failed to process batch refund attribution: {e}")
            raise

    async def _process_single_refund_attribution(
        self, refund_id: str, shop_id: str, db_client: Any
    ):
        """Process attribution for a single refund (used by both individual and batch)."""
        # Check if adjustment already exists (idempotency)
        existing_adjustment = await db_client.refundattributionadjustment.find_first(
            where={"shopId": shop_id, "refundId": refund_id}
        )
        if existing_adjustment:
            self.logger.info(
                f"✅ Refund attribution adjustment already exists - skipping",
                shop_id=shop_id,
                refund_id=refund_id,
            )
            return

        # Load normalized refund data
        refund_data = await db_client.refunddata.find_first(
            where={"shopId": shop_id, "refundId": refund_id}
        )
        if not refund_data:
            self.logger.warning(
                "RefundData not found for attribution adjustment",
                shop_id=shop_id,
                refund_id=refund_id,
            )
            return

        # Load refund line items
        refund_line_items = await db_client.refundlineitemdata.find_many(
            where={"refundId": refund_data.id}
        )

        # Load original order line items for mapping
        order = await db_client.orderdata.find_first(
            where={"shopId": shop_id, "orderId": refund_data.orderId}
        )
        if not order:
            self.logger.warning(
                "OrderData not found for refund attribution",
                shop_id=shop_id,
                order_id=refund_data.orderId,
            )
            return

        original_line_items = await db_client.lineitemdata.find_many(
            where={"orderId": order.id}
        )

        # Compute attribution using consistent logic
        per_extension_refund, items_breakdown = self._compute_refund_attribution(
            refund_line_items, original_line_items
        )

        # Create refund attribution adjustment
        await db_client.refundattributionadjustment.create(
            data={
                "shopId": shop_id,
                "orderId": refund_data.orderId,
                "refundId": refund_id,
                "perExtensionRefund": per_extension_refund,
                "totalRefundAmount": float(refund_data.totalRefundAmount),
                "computedAt": datetime.utcnow(),
                "metadata": {
                    "items_breakdown": items_breakdown,
                    "computation_method": "item_level_mapping",
                    "refund_note": refund_data.note,
                    "refund_restock": refund_data.restock,
                },
            }
        )

        self.logger.info(
            f"✅ Refund attribution adjustment created successfully",
            shop_id=shop_id,
            order_id=refund_data.orderId,
            refund_id=refund_id,
            per_extension_refund=per_extension_refund,
        )

    def _compute_refund_attribution(
        self, refund_line_items: List[Any], original_line_items: List[Any]
    ) -> tuple[Dict[str, float], List[Dict]]:
        """Compute refund attribution using consistent logic for both individual and batch processing."""
        # Index original line items by variantId/productId for O(1) lookup
        by_variant = {
            getattr(li, "variantId", None): li
            for li in original_line_items
            if getattr(li, "variantId", None)
        }
        by_product = {
            getattr(li, "productId", None): li
            for li in original_line_items
            if getattr(li, "productId", None)
        }

        per_extension_refund: Dict[str, float] = {}
        items_breakdown = []

        for refund_line_item in refund_line_items:
            # Find matching original line item (variantId first, then productId)
            original_item = None
            if refund_line_item.variantId and refund_line_item.variantId in by_variant:
                original_item = by_variant[refund_line_item.variantId]
            elif (
                refund_line_item.productId and refund_line_item.productId in by_product
            ):
                original_item = by_product[refund_line_item.productId]

            if original_item and hasattr(original_item, "properties"):
                # Extract extension attribution from original line item properties
                # Use consistent property extraction logic
                extension = self._extract_extension_from_properties(
                    original_item.properties
                )
                refund_amount = float(refund_line_item.refundAmount or 0.0)

                # Add to per-extension total
                per_extension_refund[extension] = (
                    per_extension_refund.get(extension, 0.0) + refund_amount
                )

            items_breakdown.append(
                {
                    "refund_line_item_id": refund_line_item.id,
                    "variant_id": refund_line_item.variantId,
                    "product_id": refund_line_item.productId,
                    "refund_amount": float(refund_line_item.refundAmount or 0.0),
                    "matched_original": original_item.id if original_item else None,
                    "extension": self._extract_extension_from_properties(
                        original_item.properties if original_item else {}
                    ),
                }
            )

        return per_extension_refund, items_breakdown

    def _extract_extension_from_properties(self, properties: Any) -> str:
        """Extract extension identifier from line item properties using consistent logic."""
        if not isinstance(properties, dict):
            return "unknown"

        # Try multiple property keys in order of preference
        extension_keys = [
            "_bb_rec_extension",
            "bb_rec_extension",
            "extension",
            "_bb_extension",
            "bb_extension",
        ]

        for key in extension_keys:
            if key in properties and properties[key]:
                return str(properties[key])

        return "unknown"
