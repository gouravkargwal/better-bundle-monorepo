from __future__ import annotations

from typing import Any, Dict
from datetime import datetime
from decimal import Decimal

from app.consumers.base_consumer import BaseConsumer
from app.core.logging import get_logger
from app.core.database.simple_db_client import get_database
from app.shared.constants.redis import (
    REFUND_NORMALIZATION_STREAM,
    REFUND_NORMALIZATION_GROUP,
)
from prisma import Json


class RefundNormalizationConsumer(BaseConsumer):
    """Consumes refund_created events and normalizes refund data into RefundData and RefundLineItemData."""

    def __init__(self) -> None:
        super().__init__(
            stream_name=REFUND_NORMALIZATION_STREAM,
            consumer_group=REFUND_NORMALIZATION_GROUP,
            consumer_name="refund-normalization-consumer",
            batch_size=50,
            poll_timeout=1000,
            max_retries=3,
            retry_delay=0.5,
        )
        self.logger = get_logger(__name__)

    async def _process_single_message(self, message: Dict[str, Any]):
        try:
            self.logger.info(f"🔄 Processing refund normalization message: {message}")

            # Handle both string keys and numbered keys from Redis Stream
            # String keys: {'event_type': 'refund_created', 'shop_id': '...', ...}
            # Numbered keys: {'0': 'event_type', '1': 'refund_created', '2': 'shop_id', ...}
            if "event_type" in message:
                # String keys format
                event_type = message.get("event_type")
                shop_id = message.get("shop_id")
                order_id = message.get("shopify_id")
                raw_record_id = message.get("raw_record_id")
            else:
                # Numbered keys format - convert to string keys
                event_type = message.get("1")  # '1' contains the event_type value
                shop_id = message.get("3")  # '3' contains the shop_id value
                order_id = message.get("5")  # '5' contains the shopify_id value
                raw_record_id = message.get("7")  # '7' contains the raw_record_id value

            self.logger.info(
                f"📋 Extracted data: event_type={event_type}, shop_id={shop_id}, order_id={order_id}, raw_record_id={raw_record_id}"
            )

            if event_type != "refund_created":
                self.logger.warning(f"⚠️ Skipping non-refund event: {event_type}")
                return

            if not shop_id or not order_id or not raw_record_id:
                self.logger.error(
                    "❌ Invalid refund_created payload - missing required fields",
                    message=message,
                )
                return

            db = await get_database()
            self.logger.info(
                f"🔍 Fetching RawOrder data using raw_record_id: {raw_record_id}"
            )

            # Load raw refund data from RawOrder using the raw_record_id
            raw_order = await db.raworder.find_unique(where={"id": raw_record_id})
            if not raw_order or not getattr(raw_order, "payload", None):
                self.logger.warning(
                    "RawOrder not found for refund normalization",
                    shop_id=shop_id,
                    order_id=order_id,
                )
                return

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
                # This is normal - the order webhook will update this record with complete data
                # For now, we can still process the refund with minimal data

            # Extract refund from payload
            refund_obj = None
            refund_id = None
            try:
                refunds = payload_data.get("refunds") or []
                if refunds:
                    # Get the most recent refund (last one in the array)
                    refund_obj = refunds[-1]
                    refund_id = str(refund_obj.get("id", ""))
                    self.logger.info(f"📋 Processing refund ID: {refund_id}")
                else:
                    self.logger.warning("No refunds found in payload")
                    return
            except Exception as e:
                self.logger.error(
                    "Failed to extract refund from raw payload", error=str(e)
                )
                return

            if not refund_obj:
                self.logger.warning(
                    "Refund object not found in raw payload",
                    shop_id=shop_id,
                    order_id=order_id,
                )
                return

            # PRE-CHECK: Only process refunds from orders with extension interactions
            if not await self._has_extension_interactions_for_order(
                db, shop_id, order_id
            ):
                self.logger.info(
                    f"⏭️ Skipping refund normalization for order {order_id} - no extension interactions found",
                    shop_id=shop_id,
                    order_id=order_id,
                )
                return

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
                            "properties": Json(
                                {}
                            ),  # Will be populated by attribution consumer
                        }
                    )

            self.logger.info(
                "Refund normalized successfully",
                shop_id=shop_id,
                order_id=order_id,
                refund_id=refund_id,
                line_items=len(refund_line_items),
            )

            # Trigger refund attribution after successful normalization
            from app.core.stream_manager import stream_manager, StreamType

            await stream_manager.publish_to_domain(
                StreamType.REFUND_ATTRIBUTION, message
            )
            self.logger.info("📤 Triggered refund attribution after normalization")

        except Exception as e:
            self.logger.error("Failed to normalize refund", error=str(e))
            raise

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

            # Check for interactions in the last 30 days
            from datetime import timedelta

            cutoff_time = datetime.utcnow() - timedelta(days=30)

            # Check for any interactions from attribution-eligible extensions
            # (Phoenix, Venus, Apollo - excluding Atlas web pixel tracking)
            interactions = await db.userinteraction.find_many(
                where={
                    "shopId": shop_id,
                    "customerId": customer_id,
                    "createdAt": {"gte": cutoff_time},
                    "extensionType": {
                        "in": [
                            "phoenix",
                            "venus",
                            "apollo",
                        ]  # Attribution-eligible extensions
                    },
                },
                take=1,  # We only need to know if any exist
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
