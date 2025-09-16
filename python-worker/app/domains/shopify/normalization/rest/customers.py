from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from ..base_adapter import BaseAdapter
from ..canonical_models import CanonicalCustomer


def _parse_iso(dt: Any) -> datetime | None:
    if not dt:
        return None
    try:
        if isinstance(dt, str) and dt.endswith("Z"):
            dt = dt.replace("Z", "+00:00")
        return datetime.fromisoformat(dt)
    except Exception:
        return None


class RestCustomerAdapter(BaseAdapter):
    def to_canonical(self, payload: Dict[str, Any], shop_id: str) -> Dict[str, Any]:
        customer_id = str(payload.get("id")) if payload.get("id") is not None else ""

        # Detect delete payload (minimal fields)
        is_delete = customer_id and set(payload.keys()).issubset(
            {"id", "tax_exemptions", "admin_graphql_api_id"}
        )

        # tags can be CSV on REST in some cases; default empty here
        tags: List[str] = []

        model = CanonicalCustomer(
            shopId=shop_id,
            entityId=customer_id,
            originalGid=payload.get("admin_graphql_api_id"),
            customerCreatedAt=_parse_iso(payload.get("created_at")),
            customerUpdatedAt=_parse_iso(payload.get("updated_at"))
            or datetime.utcnow(),
            email=payload.get("email"),
            phone=payload.get("phone"),
            firstName=payload.get("first_name"),
            lastName=payload.get("last_name"),
            state=payload.get("state"),
            verifiedEmail=payload.get("verified_email"),
            defaultAddress=payload.get("default_address"),
            addresses=payload.get("addresses") or [],
            tags=tags,
            currency=payload.get("currency"),
            isActive=not is_delete,
            extras={},
        )

        return model.dict()
