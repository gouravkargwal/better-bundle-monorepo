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
            refund_amount = float(payload.get("refund_amount") or 0.0)
            refund_note = payload.get("refund_note", "")
            refund_restock = bool(payload.get("refund_restock") or False)

            if not shop_id or not order_id or not refund_id:
                self.logger.error(
                    "Invalid refund_created payload",
                    payload=payload,
                )
                return

            db = await get_database()

            # Check if refund already exists
            existing_refund = await db.refunddata.find_first(
                where={"shopId": shop_id, "refundId": refund_id}
            )
            if existing_refund:
                self.logger.info(
                    "Refund already normalized",
                    shop_id=shop_id,
                    refund_id=refund_id,
                )
                return

            # Load raw refund data from RawOrder
            raw_order = await db.raworder.find_first(
                where={"shopId": shop_id, "shopifyId": order_id}
            )
            if not raw_order or not getattr(raw_order, "payload", None):
                self.logger.warning(
                    "RawOrder not found for refund normalization",
                    shop_id=shop_id,
                    order_id=order_id,
                )
                return

            # Extract refund from payload
            refund_obj = None
            try:
                payload_data = (
                    raw_order.payload if isinstance(raw_order.payload, dict) else {}
                )
                refunds = payload_data.get("refunds") or []
                for r in refunds:
                    if str(r.get("id")) == str(refund_id):
                        refund_obj = r
                        break
                # fallback to last refund if id not matched
                if refund_obj is None and refunds:
                    refund_obj = refunds[-1]
            except Exception as e:
                self.logger.error(
                    "Failed to extract refund from raw payload", error=str(e)
                )
                return

            if not refund_obj:
                self.logger.warning(
                    "Refund object not found in raw payload",
                    shop_id=shop_id,
                    refund_id=refund_id,
                )
                return

            # Create RefundData
            refunded_at = datetime.utcnow()
            if refund_obj.get("created_at"):
                try:
                    refunded_at = datetime.fromisoformat(
                        refund_obj["created_at"].replace("Z", "+00:00")
                    )
                except Exception:
                    pass

            refund_data = await db.refunddata.create(
                data={
                    "shopId": shop_id,
                    "orderId": order_id,
                    "refundId": refund_id,
                    "refundedAt": refunded_at,
                    "note": refund_obj.get("note") or refund_note,
                    "restock": refund_obj.get("restock") or refund_restock,
                    "totalRefundAmount": Decimal(str(refund_amount)),
                    "currencyCode": refund_obj.get("currency") or "USD",
                }
            )

            # Create RefundLineItemData from refund_line_items
            refund_line_items = refund_obj.get("refund_line_items") or []
            for rli in refund_line_items:
                line_item = rli.get("line_item") or {}
                quantity = int(rli.get("quantity") or line_item.get("quantity") or 0)
                if quantity <= 0:
                    continue

                unit_price = float(line_item.get("price") or 0.0)
                refund_amount_item = unit_price * quantity

                await db.refundlineitemdata.create(
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
                        "properties": {},  # Will be populated by attribution consumer
                    }
                )

            self.logger.info(
                "Refund normalized successfully",
                shop_id=shop_id,
                order_id=order_id,
                refund_id=refund_id,
                line_items=len(refund_line_items),
            )

        except Exception as e:
            self.logger.error("Failed to normalize refund", error=str(e))
            raise
