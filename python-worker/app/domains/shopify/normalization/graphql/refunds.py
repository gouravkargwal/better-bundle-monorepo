"""
GraphQL Refund Adapter

Converts GraphQL refund payloads to canonical refund models.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from decimal import Decimal

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


def _extract_numeric_gid(gid: Optional[str]) -> Optional[str]:
    """Extract numeric ID from Shopify GraphQL GID."""
    if not gid:
        return None
    try:
        # Extract ID from gid://shopify/Refund/912073654411
        return gid.split("/")[-1]
    except (IndexError, AttributeError):
        return None


class GraphQLRefundAdapter(BaseAdapter):
    """Adapter for converting GraphQL refund payloads to canonical refund models."""

    def to_canonical(self, payload: Dict[str, Any], shop_id: str) -> CanonicalRefund:
        """Convert GraphQL refund payload to CanonicalRefund."""

        # Extract refund ID
        refund_id = str(payload.get("id", ""))
        order_id = str(payload.get("order_id", ""))

        # Parse timestamps
        created_at = _parse_iso(payload.get("created_at"))
        processed_at = _parse_iso(payload.get("processed_at"))

        # Calculate total refund amount from transactions
        total_refund_amount = 0.0
        currency_code = "USD"

        transactions = payload.get("transactions", [])
        if transactions:
            for transaction in transactions:
                if transaction.get("kind") == "refund":
                    amount = float(transaction.get("amount", 0))
                    total_refund_amount += amount
                    currency_code = transaction.get("currency", "USD")

        # Process refund line items
        refund_line_items = []
        raw_line_items = payload.get("refund_line_items", [])

        for rli in raw_line_items:
            line_item = rli.get("line_item", {})

            refund_line_item = CanonicalRefundLineItem(
                refundId=refund_id,
                orderId=order_id,
                productId=str(line_item.get("product_id", "")),
                variantId=str(line_item.get("variant_id", "")),
                quantity=int(rli.get("quantity", 0)),
                unitPrice=float(rli.get("subtotal", 0)),
                refundAmount=float(rli.get("subtotal", 0)),
                properties=line_item.get("properties", []),
            )
            refund_line_items.append(refund_line_item)

        # Create canonical refund model
        model = CanonicalRefund(
            shopId=shop_id,
            orderId=order_id,
            refundId=refund_id,
            originalGid=payload.get("admin_graphql_api_id"),
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
        """Convert GraphQL refund payload to dictionary format."""
        model = self.to_canonical(payload, shop_id)
        return model.dict()
