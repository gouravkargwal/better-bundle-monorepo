"""
REST Refund Adapter

Converts REST refund payloads to canonical refund models.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.domains.shopify.normalization.base_adapter import BaseAdapter
from app.domains.shopify.normalization.canonical_models import (
    CanonicalRefund,
    CanonicalRefundLineItem,
)
from app.shared.helpers import now_utc


def _parse_iso(date_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string to datetime object."""
    if not date_str:
        return None
    try:
        # Handle both with and without timezone info
        if date_str.endswith("Z"):
            date_str = date_str[:-1] + "+00:00"
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


class RestRefundAdapter(BaseAdapter):
    """Adapter for converting REST refund payloads to canonical refund models."""

    def to_canonical(self, payload: Dict[str, Any], shop_id: str) -> CanonicalRefund:
        """Convert REST refund payload to CanonicalRefund."""

        # Extract refund ID
        refund_id = str(payload.get("id", ""))
        order_id = str(payload.get("order_id", ""))

        # Parse timestamps
        created_at = _parse_iso(payload.get("created_at"))
        processed_at = _parse_iso(payload.get("processed_at"))

        # Calculate total refund amount
        total_refund_amount = float(payload.get("total_refund_amount", 0))
        currency_code = payload.get("currency", "USD")

        # Process refund line items
        refund_line_items = []
        raw_line_items = payload.get("refund_line_items", [])

        for rli in raw_line_items:
            refund_line_item = CanonicalRefundLineItem(
                refundId=refund_id,
                orderId=order_id,
                productId=str(rli.get("product_id", "")),
                variantId=str(rli.get("variant_id", "")),
                quantity=int(rli.get("quantity", 0)),
                unitPrice=float(rli.get("unit_price", 0)),
                refundAmount=float(rli.get("refund_amount", 0)),
                properties=rli.get("properties", {}),
            )
            refund_line_items.append(refund_line_item)

        # Create canonical refund model
        model = CanonicalRefund(
            shopId=shop_id,
            orderId=order_id,
            refundId=refund_id,
            originalGid=None,  # REST doesn't have GraphQL IDs
            refundedAt=created_at or processed_at or now_utc(),
            note=payload.get("note", ""),
            restock=payload.get("restock", False),
            totalRefundAmount=total_refund_amount,
            currencyCode=currency_code,
            refundLineItems=refund_line_items,
            createdAt=now_utc(),
            updatedAt=now_utc(),
            extras=payload,
        )

        return model

    def to_dict(self, payload: Dict[str, Any], shop_id: str) -> Dict[str, Any]:
        """Convert REST refund payload to dictionary format."""
        model = self.to_canonical(payload, shop_id)
        return model.dict()
