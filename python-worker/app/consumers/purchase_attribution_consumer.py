from __future__ import annotations

from typing import Any, Dict
from datetime import datetime

from app.consumers.base_consumer import BaseConsumer
from app.core.logging import get_logger
from app.core.redis_client import streams_manager
from app.core.database.simple_db_client import get_database
from app.shared.constants.redis import (
    PURCHASE_ATTRIBUTION_STREAM,
    PURCHASE_ATTRIBUTION_GROUP,
)
from app.domains.billing.services.billing_service import BillingService
from app.domains.billing.models import PurchaseEvent


class PurchaseAttributionConsumer(BaseConsumer):
    """Consumes purchase_ready_for_attribution events and persists PurchaseAttribution."""

    def __init__(self) -> None:
        super().__init__(
            stream_name=PURCHASE_ATTRIBUTION_STREAM,
            consumer_group=PURCHASE_ATTRIBUTION_GROUP,
            consumer_name="purchase-attribution-consumer",
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

            if payload.get("event_type") != "purchase_ready_for_attribution":
                return

            shop_id = payload.get("shop_id")
            order_id = payload.get("order_id")
            if not shop_id or not order_id:
                self.logger.error(
                    "Invalid purchase_ready_for_attribution payload", payload=payload
                )
                return

            db = await get_database()

            # Load normalized order and line items
            order = await db.orderdata.find_first(
                where={"shopId": shop_id, "orderId": str(order_id)}
            )
            if not order:
                self.logger.warning(
                    "OrderData not found for attribution",
                    shop_id=shop_id,
                    order_id=order_id,
                )
                return

            line_items = await db.lineitemdata.find_many(where={"orderId": order.id})

            # Construct PurchaseEvent
            products = []
            for li in line_items or []:
                products.append(
                    {
                        "product_id": li.productId,
                        "variant_id": li.variantId,
                        "quantity": li.quantity,
                        "price": li.price,
                        "properties": getattr(li, "properties", None) or {},
                    }
                )

            total_amount = float(getattr(order, "totalAmount", 0.0) or 0.0)
            currency = getattr(order, "currencyCode", None) or "USD"
            customer_id = getattr(order, "customerId", None)

            # Try to find a recent session for this customer (optional)
            session = None
            if customer_id:
                session = await db.usersession.find_first(
                    where={"shopId": shop_id, "customerId": customer_id},
                    order={"createdAt": "desc"},
                )

            purchase_event = PurchaseEvent(
                order_id=order_id,
                customer_id=customer_id,
                shop_id=shop_id,
                session_id=getattr(session, "id", None),
                total_amount=total_amount,
                currency=currency,
                products=products,
                created_at=getattr(order, "orderDate", None) or datetime.utcnow(),
                metadata={
                    "source": "normalization",
                    "line_item_count": len(products),
                },
            )

            # Process attribution
            billing = BillingService(await get_database())
            await billing.process_purchase_attribution(purchase_event)

            self.logger.info(
                "Purchase attribution stored",
                shop_id=shop_id,
                order_id=order_id,
                line_items=len(products),
            )

        except Exception as e:
            self.logger.error("Failed to process purchase attribution", error=str(e))
            raise
