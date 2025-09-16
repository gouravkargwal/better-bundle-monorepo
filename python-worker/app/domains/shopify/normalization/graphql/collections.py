from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from ..base_adapter import BaseAdapter
from ..canonical_models import CanonicalCollection


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


class GraphQLCollectionAdapter(BaseAdapter):
    def to_canonical(self, payload: Dict[str, Any], shop_id: str) -> Dict[str, Any]:
        entity_id = _extract_numeric_gid(payload.get("id")) or ""

        model = CanonicalCollection(
            shopId=shop_id,
            entityId=entity_id,
            originalGid=payload.get("id"),
            title=payload.get("title"),
            handle=payload.get("handle"),
            description=payload.get("description") or payload.get("descriptionHtml"),
            templateSuffix=payload.get("templateSuffix"),
            publishedAt=None,  # not present in provided payload
            collectionUpdatedAt=_parse_iso(payload.get("updatedAt")),
            status=None,
            isActive=True,
            extras={},
        )

        return model.dict()
