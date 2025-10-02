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

        created_at = (
            _parse_iso(payload.get("created_at")) or datetime.utcnow()
        )  # Updated to snake_case
        updated_at = (
            _parse_iso(payload.get("updated_at")) or created_at
        )  # Updated to snake_case

        model = CanonicalCustomer(
            shop_id=shop_id,
            customer_id=entity_id,
            first_name=payload.get("first_name"),  # Updated to snake_case
            last_name=payload.get("last_name"),  # Updated to snake_case
            total_spent=float(
                (payload.get("total_spent") or {}).get("amount") or 0.0
            ),  # Extract amount from totalSpent object
            order_count=int(payload.get("orders_count") or 0),  # Updated to snake_case
            last_order_date=_parse_iso(
                (payload.get("last_order") or {}).get("created_at")
            ),  # Extract date from lastOrder object
            last_order_id=_extract_numeric_gid(
                (payload.get("last_order") or {}).get("id")
            ),  # Extract ID from lastOrder object
            verified_email=bool(
                payload.get("verified_email") or False
            ),  # Updated to snake_case
            tax_exempt=bool(
                payload.get("tax_exempt") or False
            ),  # Updated to snake_case
            customer_locale=payload.get(
                "customer_locale", "en"
            ),  # Updated to snake_case
            tags=payload.get("tags") or [],
            state=(payload.get("default_address") or {}).get(
                "province"
            ),  # Updated to snake_case
            default_address=self._convert_address_ids(
                payload.get("default_address")
            ),  # Updated to snake_case
            # Add required internal timestamps
            created_at=created_at,
            updated_at=updated_at,
            is_active=True,
            extras={},
        )

        return model.dict()

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
