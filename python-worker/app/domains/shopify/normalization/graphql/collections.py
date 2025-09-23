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
    def _normalize_metafields(self, metafields):
        """Normalize metafields to ensure proper JSON type for Prisma."""
        if not metafields:
            return []
        if isinstance(metafields, dict):
            # Handle GraphQL connection format
            edges = metafields.get("edges", [])
            return edges if isinstance(edges, list) else []
        if isinstance(metafields, list):
            return metafields
        return []

    def to_canonical(self, payload: Dict[str, Any], shop_id: str) -> Dict[str, Any]:
        collectionId = _extract_numeric_gid(payload.get("id")) or ""
        created_at = (
            _parse_iso(payload.get("createdAt"))
            or _parse_iso(payload.get("updatedAt"))
            or datetime.utcnow()
        )
        updated_at = _parse_iso(payload.get("updatedAt")) or created_at

        model = CanonicalCollection(
            shop_id=shop_id,
            collection_id=collectionId,
            title=payload.get("title") or "Untitled Collection",
            handle=payload.get("handle") or "untitled-collection",
            description=payload.get("description")
            or payload.get("descriptionHtml")
            or "",
            template_suffix=payload.get("templateSuffix") or "",
            seo_title=(payload.get("seo", {}) or {}).get("title"),
            seo_description=(payload.get("seo", {}) or {}).get("description"),
            imageUrl=(
                (payload.get("image") or {}).get("url")
                if isinstance(payload.get("image"), dict)
                else None
            ),
            image_alt=(
                (payload.get("image") or {}).get("altText")
                if isinstance(payload.get("image"), dict)
                else None
            ),
            product_count=(
                len(payload.get("products") or [])
                if isinstance(payload.get("products"), list)
                else 0
            ),
            is_automated=bool(payload.get("ruleSet") is not None),
            metafields=self._normalize_metafields(payload.get("metafields")),
            created_at=created_at,
            updated_at=updated_at,
            is_active=True,
            extras={},
        )

        return model.dict()
