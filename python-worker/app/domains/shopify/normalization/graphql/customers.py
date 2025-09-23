from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..base_adapter import BaseAdapter
from ..canonical_models import CanonicalCustomer


def _parse_iso(dt: Optional[str]) -> Optional[datetime]:
    if not dt:
        return None
    try:
        if isinstance(dt, str) and dt.endswith("Z"):
            dt = dt.replace("Z", "+00:00")
        return datetime.fromisoformat(dt)  # type: ignore[arg-type]
    except Exception:
        return None


def _extract_numeric_gid(gid: Optional[str]) -> Optional[str]:
    if not gid or not isinstance(gid, str):
        return None
    try:
        if gid.startswith("gid://shopify/"):
            return gid.split("/")[-1]
        return gid
    except Exception:
        return None


class GraphQLCustomerAdapter(BaseAdapter):
    def to_canonical(self, payload: Dict[str, Any], shop_id: str) -> Dict[str, Any]:
        entity_id = _extract_numeric_gid(payload.get("id")) or ""

        created_at = _parse_iso(payload.get("createdAt")) or datetime.utcnow()
        updated_at = _parse_iso(payload.get("updatedAt")) or created_at

        model = CanonicalCustomer(
            shop_id=shop_id,
            customer_id=entity_id,
            email=payload.get("email"),
            first_name=payload.get("firstName"),
            last_name=payload.get("lastName"),
            total_spent=float(payload.get("totalSpent") or 0.0),
            order_count=int(payload.get("ordersCount") or 0),
            last_order_date=_parse_iso(payload.get("lastOrderDate")),
            tags=payload.get("tags") or [],
            customer_created_at=created_at,
            customer_updated_at=updated_at,
            last_order_id=_extract_numeric_gid(payload.get("lastOrderId")),
            location=payload.get("defaultAddress"),
            metafields=payload.get("metafields") or [],
            state=(payload.get("defaultAddress") or {}).get("province"),
            verified_email=bool(payload.get("verifiedEmail") or False),
            tax_exempt=bool(payload.get("taxExempt") or False),
            default_address=payload.get("defaultAddress"),
            addresses=payload.get("addresses") or [],
            currency_code=payload.get("currencyCode"),
            customer_locale=payload.get("locale"),
            # Add required internal timestamps
            created_at=created_at,
            updated_at=updated_at,
            is_active=True,
            extras={},
        )

        return model.dict()
