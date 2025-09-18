from __future__ import annotations

from typing import Any, Dict
from datetime import datetime
from decimal import Decimal

from app.consumers.base_consumer import BaseConsumer
from app.core.logging import get_logger
from app.core.database.simple_db_client import get_database
from app.shared.constants.redis import (
    REFUND_ATTRIBUTION_STREAM,
    REFUND_ATTRIBUTION_GROUP,
)


class RefundAttributionConsumer(BaseConsumer):
    """Consumes refund_created events and creates RefundAttributionAdjustment records.

    Strategy:
    - Read normalized RefundData and RefundLineItemData.
    - Map refund line items to original LineItemData by variantId/productId.
    - Use line item properties to determine extension attribution.
    - Create RefundAttributionAdjustment with per-extension refund amounts.
    """

    def __init__(self) -> None:
        super().__init__(
            stream_name=REFUND_ATTRIBUTION_STREAM,
            consumer_group=REFUND_ATTRIBUTION_GROUP,
            consumer_name="refund-attribution-consumer",
            batch_size=50,
            poll_timeout=1000,
            max_retries=3,
            retry_delay=0.5,
        )
        self.logger = get_logger(__name__)

    async def _process_single_message(self, message: Dict[str, Any]):
        try:
            payload = message.get("data") or message
            if isinstance(payload, str):
                import json as _json

                try:
                    payload = _json.loads(payload)
                except Exception:
                    pass

            if payload.get("event_type") != "refund_created":
                return

            shop_id = payload.get("shop_id")
            order_id = payload.get("shopify_id")
            refund_id = payload.get("refund_id")

            if not shop_id or not order_id or not refund_id:
                self.logger.error(
                    "Invalid refund_created payload",
                    payload=payload,
                )
                return

            db = await get_database()

            # Check if adjustment already exists
            existing_adjustment = await db.refundattributionadjustment.find_first(
                where={"shopId": shop_id, "refundId": refund_id}
            )
            if existing_adjustment:
                self.logger.info(
                    "Refund attribution adjustment already exists",
                    shop_id=shop_id,
                    refund_id=refund_id,
                )
                return

            # Load normalized refund data
            refund_data = await db.refunddata.find_first(
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
            refund_line_items = await db.refundlineitemdata.find_many(
                where={"refundId": refund_data.id}
            )

            # Load original order line items for mapping
            order = await db.orderdata.find_first(
                where={"shopId": shop_id, "orderId": order_id}
            )
            if not order:
                self.logger.warning(
                    "OrderData not found for refund attribution",
                    shop_id=shop_id,
                    order_id=order_id,
                )
                return

            original_line_items = await db.lineitemdata.find_many(
                where={"orderId": order.id}
            )

            # Index original line items by variantId/productId
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

            # Compute per-extension refund amounts
            per_extension_refund: Dict[str, float] = {}
            items_breakdown = []

            for rli in refund_line_items:
                # Find matching original line item
                matched = by_variant.get(rli.variantId) or by_product.get(rli.productId)
                if not matched:
                    continue

                # Get extension from original line item properties
                props = getattr(matched, "properties", None) or {}
                extension = (
                    props.get("_bb_rec_extension")
                    or props.get("bb_rec_extension")
                    or props.get("extension")
                    or "unknown"
                )

                # Add to per-extension total
                refund_amount = float(rli.refundAmount or 0.0)
                per_extension_refund[extension] = (
                    per_extension_refund.get(extension, 0.0) + refund_amount
                )

                items_breakdown.append(
                    {
                        "variant_id": rli.variantId,
                        "product_id": rli.productId,
                        "quantity": rli.quantity,
                        "unit_price": float(rli.unitPrice or 0.0),
                        "refund_amount": refund_amount,
                        "extension": extension,
                    }
                )

            # Create RefundAttributionAdjustment
            await db.refundattributionadjustment.create(
                data={
                    "shopId": shop_id,
                    "orderId": order_id,
                    "refundId": refund_id,
                    "perExtensionRefund": per_extension_refund,
                    "totalRefundAmount": Decimal(str(refund_data.totalRefundAmount)),
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
                "Refund attribution adjustment created",
                shop_id=shop_id,
                order_id=order_id,
                refund_id=refund_id,
                per_extension_refund=per_extension_refund,
            )

        except Exception as e:
            self.logger.error("Failed to process refund attribution", error=str(e))
            raise
