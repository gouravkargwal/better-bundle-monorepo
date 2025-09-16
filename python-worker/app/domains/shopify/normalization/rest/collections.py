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

        model = CanonicalCollection(
            shopId=shop_id,
            entityId=collection_id,
            originalGid=payload.get("admin_graphql_api_id"),
            title=payload.get("title"),
            handle=payload.get("handle"),
            description=payload.get("body_html"),
            templateSuffix=payload.get("template_suffix"),
            publishedAt=_parse_iso(payload.get("published_at")),
            collectionUpdatedAt=_parse_iso(payload.get("updated_at")),
            status=payload.get("published_scope"),
            isActive=not is_delete,
            extras={},
        )

        return model.dict()
