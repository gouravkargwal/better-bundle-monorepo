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

        model = CanonicalCustomer(
            shopId=shop_id,
            entityId=entity_id,
            originalGid=payload.get("id"),
            customerCreatedAt=_parse_iso(payload.get("createdAt")),
            customerUpdatedAt=_parse_iso(payload.get("updatedAt")) or datetime.utcnow(),
            email=payload.get("email"),
            phone=payload.get("phone"),
            firstName=payload.get("firstName"),
            lastName=payload.get("lastName"),
            state=payload.get("state"),
            verifiedEmail=payload.get("verifiedEmail"),
            defaultAddress=payload.get("defaultAddress"),
            addresses=[],
            tags=payload.get("tags") or [],
            currency=None,
            isActive=True,
            extras={},
        )

        return model.dict()
