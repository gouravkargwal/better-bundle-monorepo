from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from ..base_adapter import BaseAdapter
from ..canonical_models import CanonicalCollection


def _parse_iso(dt: Any) -> datetime | None:
    if not dt:
        return None
    try:
        if isinstance(dt, str) and dt.endswith("Z"):
            dt = dt.replace("Z", "+00:00")
        return datetime.fromisoformat(dt)
    except Exception:
        return None


class RestCollectionAdapter(BaseAdapter):
    def to_canonical(self, payload: Dict[str, Any], shop_id: str) -> Dict[str, Any]:
        collection_id = str(payload.get("id")) if payload.get("id") is not None else ""

        # Detect delete payload (id + minimal fields)
        is_delete = collection_id and set(payload.keys()).issubset(
            {"id", "published_scope", "admin_graphql_api_id"}
        )

        # Extract timestamps
        created_at = _parse_iso(payload.get("created_at"))
        updated_at = _parse_iso(payload.get("updated_at"))

        # Use current time as fallback if timestamps are missing
        if not created_at:
            created_at = datetime.utcnow()
        if not updated_at:
            updated_at = datetime.utcnow()

        model = CanonicalCollection(
            shopId=shop_id,
            collectionId=collection_id,  # Fixed: use collectionId instead of entityId
            originalGid=payload.get("admin_graphql_api_id"),
            title=payload.get("title") or "",  # Provide default empty string
            handle=payload.get("handle") or "",  # Provide default empty string
            description=payload.get("body_html"),
            templateSuffix=payload.get("template_suffix"),
            publishedAt=_parse_iso(payload.get("published_at")),
            collectionUpdatedAt=updated_at,
            status=payload.get("published_scope"),
            isActive=not is_delete,
            createdAt=created_at,  # Added required field
            updatedAt=updated_at,  # Added required field
            extras={},
        )

        return model.dict()
