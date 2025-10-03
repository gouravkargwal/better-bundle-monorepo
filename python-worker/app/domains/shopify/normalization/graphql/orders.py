from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from ..base_adapter import BaseAdapter
from ..canonical_models import CanonicalLineItem, CanonicalOrder


def _parse_iso(dt: Optional[str]) -> Optional[datetime]:
    if not dt:
        return None
    try:
        # Handle Z suffix
        if isinstance(dt, str) and dt.endswith("Z"):
            dt = dt.replace("Z", "+00:00")
        return datetime.fromisoformat(dt)  # type: ignore[arg-type]
    except Exception:
        return None


def _to_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _money_from_set(node: Dict[str, Any]) -> float:
    # Expect shape: { shop_money: { amount: ".." } } - now using snake_case
    try:
        return _to_float(
            node.get("shop_money", {}).get("amount")
        )  # Updated to snake_case
    except Exception:
        return 0.0


def _extract_numeric_gid(gid: Optional[str]) -> Optional[str]:
    if not gid or not isinstance(gid, str):
        return None
    try:
        if gid.startswith("gid://shopify/"):
            return gid.split("/")[-1]
        return gid
    except Exception:
        return None


class GraphQLOrderAdapter(BaseAdapter):
    def __init__(self):
        self.logger = get_logger(__name__)

    def to_canonical(self, payload: Dict[str, Any], shop_id: str) -> Dict[str, Any]:
        # IDs
        entity_id = _extract_numeric_gid(payload.get("id")) or ""
        customer_gid = (
            payload.get("customer", {}).get("id") if payload.get("customer") else None
        )
        customer_id = _extract_numeric_gid(customer_gid)

        # Line items (edges → nodes) - now using snake_case field names from paginated data
        line_items: List[CanonicalLineItem] = []
        li_edges = (payload.get("line_items", {}) or {}).get(
            "edges", []
        ) or []  # Updated to snake_case

        for i, edge in enumerate(li_edges):
            node = edge.get("node", {})
            variant = node.get("variant", {}) or {}
            product = (
                node.get("product", {}) or {}
            )  # Product is directly on the node, not nested in variant

            # Extract price information - handle both direct price and price sets
            original_unit_price = None
            discounted_unit_price = None
            currency_code = None

            # First try direct price field (from your raw data)
            if node.get("original_unit_price"):
                original_unit_price = _to_float(node.get("original_unit_price"))
                # Get currency from order level
                currency_code = payload.get("currency_code")

            # Fallback to price sets if direct price not available
            if original_unit_price is None:
                original_price_set = node.get("original_unit_price_set", {})
                if original_price_set:
                    shop_money = original_price_set.get("shop_money", {})
                    original_unit_price = _to_float(shop_money.get("amount"))
                    currency_code = shop_money.get("currency_code")

            # Extract from discountedUnitPriceSet
            discounted_price_set = node.get("discounted_unit_price_set", {})
            if discounted_price_set:
                shop_money = discounted_price_set.get("shop_money", {})
                discounted_unit_price = _to_float(shop_money.get("amount"))
                if not currency_code:
                    currency_code = shop_money.get("currency_code")

            # Map custom_attributes (array of {key, value}) into a dict for properties
            custom_attrs = node.get("custom_attributes") or []
            props_dict: Dict[str, Any] = {}
            try:
                for attr in custom_attrs:
                    k = attr.get("key") if isinstance(attr, dict) else None
                    v = attr.get("value") if isinstance(attr, dict) else None
                    if k is not None:
                        # Map both old and new property names for backward compatibility
                        if k.startswith("_bb_rec_"):
                            # New hidden properties
                            props_dict[str(k)] = v
                        elif k.startswith("bb_rec_"):
                            # Old visible properties - map to new hidden names
                            new_key = f"_{k}"
                            props_dict[new_key] = v
                        else:
                            props_dict[str(k)] = v
            except Exception:
                props_dict = {}

            line_items.append(
                CanonicalLineItem(
                    product_id=_extract_numeric_gid(product.get("id")),
                    variant_id=_extract_numeric_gid(variant.get("id")),
                    title=node.get("title"),
                    quantity=int(node.get("quantity") or 0),
                    price=original_unit_price
                    or _to_float(node.get("original_unit_price"))
                    or 0.0,
                    original_unit_price=original_unit_price,
                    discounted_unit_price=discounted_unit_price,
                    currency_code=currency_code,
                    variant_data=variant,  # Store complete variant information
                    properties=props_dict,
                )
            )

        # Extract order totals - use direct field names from the raw data
        total_amount = _to_float(payload.get("total_price", 0.0))
        subtotal_amount = _to_float(payload.get("subtotal_price", 0.0))
        total_tax_amount = _to_float(payload.get("total_tax", 0.0))
        total_shipping_amount = _to_float(payload.get("total_shipping", 0.0))
        total_refunded_amount = _to_float(payload.get("total_refunded", 0.0))
        total_outstanding_amount = _to_float(payload.get("total_outstanding", 0.0))

        # Tags can be array in GQL
        tags = payload.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        # Compute canonical timestamps - now using snake_case field names
        created_at = (
            _parse_iso(payload.get("created_at")) or datetime.utcnow()
        )  # Updated to snake_case
        updated_at = (
            _parse_iso(payload.get("updated_at"))  # Updated to snake_case
            or _parse_iso(payload.get("created_at"))  # Updated to snake_case
            or created_at
        )

        model = CanonicalOrder(
            shop_id=shop_id,
            order_id=entity_id,
            created_at=created_at,
            updated_at=updated_at,
            currency_code=payload.get("currency_code"),  # Updated to snake_case
            presentment_currency_code=payload.get(
                "presentment_currency_code"
            ),  # Updated to snake_case
            total_amount=total_amount,
            subtotal_amount=subtotal_amount,
            total_tax_amount=total_tax_amount,
            total_shipping_amount=total_shipping_amount,
            total_refunded_amount=total_refunded_amount,
            total_outstanding_amount=total_outstanding_amount,
            order_date=_parse_iso(payload.get("created_at"))
            or created_at,  # Updated to snake_case
            processed_at=_parse_iso(
                payload.get("processed_at")
            ),  # Updated to snake_case
            cancelled_at=_parse_iso(
                payload.get("cancelled_at")
            ),  # Updated to snake_case
            confirmed=payload.get("confirmed", False),
            test=payload.get("test", False),
            order_name=payload.get("name"),
            note=payload.get("note"),
            customer_display_name=f"{(payload.get('customer') or {}).get('firstName', '')} {(payload.get('customer') or {}).get('lastName', '')}".strip(),
            financial_status=payload.get("financial_status") or None,
            fulfillment_status=payload.get("fulfillment_status") or None,
            customer_id=customer_id,
            tags=tags,
            note_attributes=payload.get("customAttributes")
            or [],  # GraphQL uses customAttributes for note_attributes
            line_items=line_items,
            billing_address=self._convert_address_ids(
                payload.get("billing_address")
            ),  # Updated to snake_case
            shipping_address=self._convert_address_ids(
                payload.get("shipping_address")
            ),  # Updated to snake_case
            discount_applications=(
                payload.get("discount_applications", {}) or {}
            ).get(  # Updated to snake_case
                "edges", []
            ),
            metafields=(payload.get("metafields", {}) or {}).get("edges", []),
            transactions=payload.get("transactions") or [],
            refunds=self._extract_refunds(payload, shop_id),
            extras={},
        )

        result = model.dict()
        return result

    def _convert_address_ids(
        self, address: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Convert GraphQL IDs in address to numeric IDs"""
        if not address:
            return address

        # Create a copy to avoid modifying the original
        converted_address = address.copy()

        # Convert the main address ID
        if "id" in converted_address:
            converted_address["id"] = _extract_numeric_gid(converted_address["id"])

        return converted_address

    def _extract_refunds(
        self, payload: Dict[str, Any], shop_id: str
    ) -> List[Dict[str, Any]]:
        """Extract refunds from GraphQL order payload."""
        refunds = []
        raw_refunds = payload.get("refunds", [])

        for refund in raw_refunds:
            try:
                # Calculate total refund amount from transactions
                total_refund_amount = 0.0
                currency_code = "USD"

                transactions = refund.get("transactions", [])
                if transactions:
                    for transaction in transactions:
                        if transaction.get("kind") == "refund":
                            amount = float(transaction.get("amount", 0))
                            total_refund_amount += amount
                            currency_code = transaction.get("currency", "USD")

                # Process refund line items
                refund_line_items = []
                raw_line_items = refund.get("refund_line_items", [])

                for rli in raw_line_items:
                    line_item = rli.get("line_item", {})

                    refund_line_item = {
                        "refund_id": str(refund.get("id", "")),
                        "order_id": str(payload.get("id", "")),
                        "product_id": str(line_item.get("product_id", "")),
                        "variant_id": str(line_item.get("variant_id", "")),
                        "quantity": int(rli.get("quantity", 0)),
                        "unit_price": float(rli.get("subtotal", 0)),
                        "refund_amount": float(rli.get("subtotal", 0)),
                        "properties": line_item.get("properties", []),
                    }
                    refund_line_items.append(refund_line_item)

                # Create refund data
                refund_data = {
                    "shop_id": shop_id,
                    "order_id": str(payload.get("id", "")),
                    "refund_id": str(refund.get("id", "")),
                    "refunded_at": self._parse_iso(refund.get("created_at")),
                    "note": refund.get("note", ""),
                    "restock": refund.get("restock", False),
                    "total_refund_amount": total_refund_amount,
                    "currency_code": currency_code,
                    "refund_line_items": refund_line_items,
                    "created_at": self._parse_iso(refund.get("created_at")),
                    "updated_at": self._parse_iso(refund.get("processed_at")),
                    "extras": refund,
                }

                refunds.append(refund_data)

            except Exception as e:
                self.logger.warning(f"Failed to extract refund: {e}")
                continue

        return refunds
