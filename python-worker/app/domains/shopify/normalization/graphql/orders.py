from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

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
    # Expect shape: { shopMoney: { amount: ".." } }
    try:
        return _to_float(node.get("shopMoney", {}).get("amount"))
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
    def to_canonical(self, payload: Dict[str, Any], shop_id: str) -> Dict[str, Any]:
        # IDs
        entity_id = _extract_numeric_gid(payload.get("id")) or ""
        customer_gid = (
            payload.get("customer", {}).get("id") if payload.get("customer") else None
        )
        customer_id = _extract_numeric_gid(customer_gid)

        # Line items (edges → nodes)
        line_items: List[CanonicalLineItem] = []
        li_edges = (payload.get("lineItems", {}) or {}).get("edges", []) or []
        for edge in li_edges:
            node = edge.get("node", {})
            variant = node.get("variant", {}) or {}
            product = variant.get("product", {}) or {}
            # Map customAttributes (array of {key, value}) into a dict for properties
            custom_attrs = node.get("customAttributes") or []
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
                    price=_to_float(variant.get("price")),
                    properties=props_dict,
                )
            )

        # Totals from *Set nodes
        total_amount = _money_from_set(payload.get("totalPriceSet", {}) or {})
        subtotal_amount = _money_from_set(payload.get("subtotalPriceSet", {}) or {})
        total_tax_amount = _money_from_set(payload.get("totalTaxSet", {}) or {})
        total_shipping_amount = _money_from_set(
            payload.get("totalShippingPriceSet", {}) or {}
        )
        total_refunded_amount = _money_from_set(
            payload.get("totalRefundedSet", {}) or {}
        )
        total_outstanding_amount = _money_from_set(
            payload.get("totalOutstandingSet", {}) or {}
        )

        # Tags can be array in GQL
        tags = payload.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

        # Compute canonical timestamps
        created_at = _parse_iso(payload.get("createdAt")) or datetime.utcnow()
        updated_at = (
            _parse_iso(payload.get("updatedAt"))
            or _parse_iso(payload.get("createdAt"))
            or created_at
        )

        model = CanonicalOrder(
            shop_id=shop_id,
            order_id=entity_id,
            created_at=created_at,
            updated_at=updated_at,
            currency_code=payload.get("currencyCode"),
            presentment_currency_code=payload.get("presentmentCurrencyCode"),
            totalAmount=total_amount,
            subtotal_amount=subtotal_amount,
            total_tax_amount=total_tax_amount,
            total_shipping_amount=total_shipping_amount,
            total_refunded_amount=total_refunded_amount,
            total_outstanding_amount=total_outstanding_amount,
            order_date=_parse_iso(payload.get("createdAt")) or created_at,
            processed_at=_parse_iso(payload.get("processedAt")),
            cancelled_at=_parse_iso(payload.get("cancelledAt")),
            confirmed=payload.get("confirmed", False),
            test=payload.get("test", False),
            order_name=payload.get("name"),
            note=payload.get("note"),
            customer_email=payload.get("email"),
            customer_phone=payload.get("phone"),
            customer_display_name=(payload.get("customer") or {}).get("displayName"),
            financial_status=payload.get("financialStatus") or None,
            fulfillment_status=payload.get("fulfillmentStatus") or None,
            customer_id=customer_id,
            tags=tags,
            note_attributes=payload.get("customAttributes")
            or [],  # GraphQL uses customAttributes for note_attributes
            line_items=line_items,
            billing_address=payload.get("billingAddress"),
            shipping_address=payload.get("shippingAddress"),
            discount_applications=(payload.get("discountApplications", {}) or {}).get(
                "edges", []
            ),
            metafields=(payload.get("metafields", {}) or {}).get("edges", []),
            transactions=payload.get("transactions") or [],
            refunds=self._extract_refunds(payload, shop_id),
            extras={},
        )

        return model.dict()

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
