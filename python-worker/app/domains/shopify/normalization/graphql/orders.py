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
                    productId=_extract_numeric_gid(product.get("id")),
                    variantId=_extract_numeric_gid(variant.get("id")),
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
            shopId=shop_id,
            orderId=entity_id,
            originalGid=payload.get("id"),
            # Canonical internal timestamps
            createdAt=created_at,
            updatedAt=updated_at,
            currencyCode=payload.get("currencyCode"),
            presentmentCurrencyCode=payload.get("presentmentCurrencyCode"),
            totalAmount=total_amount,
            subtotalAmount=subtotal_amount,
            totalTaxAmount=total_tax_amount,
            totalShippingAmount=total_shipping_amount,
            totalRefundedAmount=total_refunded_amount,
            totalOutstandingAmount=total_outstanding_amount,
            orderDate=_parse_iso(payload.get("createdAt")),
            processedAt=_parse_iso(payload.get("processedAt")),
            cancelledAt=_parse_iso(payload.get("cancelledAt")),
            confirmed=payload.get("confirmed"),
            test=payload.get("test"),
            orderName=payload.get("name"),
            note=payload.get("note"),
            customerEmail=payload.get("email"),
            customerPhone=payload.get("phone"),
            customerDisplayName=(payload.get("customer") or {}).get("displayName"),
            financialStatus=payload.get("financialStatus") or None,
            fulfillmentStatus=payload.get("fulfillmentStatus") or None,
            customerId=customer_id,
            tags=tags,
            noteAttributes=payload.get("customAttributes")
            or [],  # GraphQL uses customAttributes for note_attributes
            lineItems=line_items,
            billingAddress=payload.get("billingAddress"),
            shippingAddress=payload.get("shippingAddress"),
            discountApplications=(payload.get("discountApplications", {}) or {}).get(
                "edges", []
            ),
            metafields=(payload.get("metafields", {}) or {}).get("edges", []),
            transactions=payload.get("transactions") or [],
            extras={},
        )

        return model.dict()
