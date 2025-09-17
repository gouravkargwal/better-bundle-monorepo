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
            shopId=shop_id,
            customerId=entity_id,
            originalGid=payload.get("id"),
            email=payload.get("email"),
            firstName=payload.get("firstName"),
            lastName=payload.get("lastName"),
            totalSpent=float(payload.get("totalSpent") or 0.0),
            orderCount=int(payload.get("ordersCount") or 0),
            lastOrderDate=_parse_iso(payload.get("lastOrderDate")),
            tags=payload.get("tags") or [],
            customerCreatedAt=created_at,
            customerUpdatedAt=updated_at,
            lastOrderId=_extract_numeric_gid(payload.get("lastOrderId")),
            location=payload.get("defaultAddress"),
            metafields=payload.get("metafields") or [],
            state=(payload.get("defaultAddress") or {}).get("province"),
            verifiedEmail=bool(payload.get("verifiedEmail") or False),
            taxExempt=bool(payload.get("taxExempt") or False),
            defaultAddress=payload.get("defaultAddress"),
            addresses=payload.get("addresses") or [],
            currencyCode=payload.get("currencyCode") or "USD",
            customerLocale=payload.get("locale") or "en",
            # Add required internal timestamps
            createdAt=created_at,
            updatedAt=updated_at,
            isActive=True,
            extras={},
        )

        return model.dict()
