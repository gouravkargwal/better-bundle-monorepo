from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from ..base_adapter import BaseAdapter
from ..canonical_models import CanonicalLineItem, CanonicalOrder


def _to_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _money_from_price_set(node: Any) -> float:
    # Extract amount from REST price_set shape: { shop_money: { amount: ".." } }
    try:
        if not isinstance(node, dict):
            return 0.0
        shop_money = node.get("shop_money") or node.get("shopMoney") or {}
        return _to_float(shop_money.get("amount"))
    except Exception:
        return 0.0


class RestOrderAdapter(BaseAdapter):
    def to_canonical(self, payload: Dict[str, Any], shop_id: str) -> Dict[str, Any]:
        order_id = str(payload.get("id")) if payload.get("id") is not None else ""

        # line items
        items = []
        for li in payload.get("line_items", []) or []:
            items.append(
                CanonicalLineItem(
                    productId=(
                        str(li.get("product_id"))
                        if li.get("product_id") is not None
                        else None
                    ),
                    variantId=(
                        str(li.get("variant_id"))
                        if li.get("variant_id") is not None
                        else None
                    ),
                    title=li.get("title"),
                    quantity=int(li.get("quantity") or 0),
                    price=_to_float(li.get("price")),
                )
            )

        # Prefer *_set amounts when available, fallback to simple string fields
        total_amount = _money_from_price_set(
            payload.get("total_price_set")
        ) or _to_float(payload.get("total_price"))
        subtotal_amount = _money_from_price_set(
            payload.get("subtotal_price_set")
        ) or _to_float(payload.get("subtotal_price"))
        total_tax_amount = _money_from_price_set(
            payload.get("total_tax_set")
        ) or _to_float(payload.get("total_tax"))
        total_shipping_amount = _money_from_price_set(
            payload.get("total_shipping_price_set")
        )
        total_refunded_amount = _money_from_price_set(
            payload.get("total_refunded_set")
        ) or _to_float(payload.get("total_refunded"))
        total_outstanding_amount = _to_float(payload.get("total_outstanding"))

        model = CanonicalOrder(
            shopId=shop_id,
            entityId=order_id,
            originalGid=None,
            shopifyUpdatedAt=(
                datetime.fromisoformat(payload.get("updated_at"))
                if payload.get("updated_at")
                else datetime.utcnow()
            ),
            currencyCode=payload.get("currency"),
            presentmentCurrencyCode=payload.get("presentment_currency")
            or payload.get("presentment_currency_code"),
            totalAmount=total_amount,
            subtotalAmount=subtotal_amount,
            totalTaxAmount=total_tax_amount,
            totalShippingAmount=total_shipping_amount,
            totalRefundedAmount=total_refunded_amount,
            totalOutstandingAmount=total_outstanding_amount,
            orderDate=(
                datetime.fromisoformat(payload.get("created_at"))
                if payload.get("created_at")
                else None
            ),
            processedAt=(
                datetime.fromisoformat(payload.get("processed_at"))
                if payload.get("processed_at")
                else None
            ),
            cancelledAt=(
                datetime.fromisoformat(payload.get("cancelled_at"))
                if payload.get("cancelled_at")
                else None
            ),
            confirmed=payload.get("confirmed"),
            test=payload.get("test"),
            orderName=payload.get("name"),
            note=payload.get("note"),
            email=payload.get("email"),
            phone=payload.get("phone"),
            financialStatus=payload.get("financial_status"),
            fulfillmentStatus=payload.get("fulfillment_status"),
            customerId=(
                str(payload.get("customer", {}).get("id"))
                if payload.get("customer")
                else None
            ),
            tags=[
                t.strip() for t in (payload.get("tags") or "").split(",") if t.strip()
            ],
            noteAttributes=payload.get("note_attributes")
            or [],  # Extract note_attributes for attribution
            lineItems=items,
            billingAddress=payload.get("billing_address"),
            shippingAddress=payload.get("shipping_address"),
            discountApplications=payload.get("discount_applications") or [],
            metafields=payload.get("metafields") or [],
            transactions=payload.get("transactions") or [],
            extras={},
        )

        return model.dict()
