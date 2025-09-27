from __future__ import annotations

import re
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


def _strip_html(html_content: str) -> str:
    """Strip HTML tags from content to get plain text"""
    if not html_content:
        return ""
    # Remove HTML tags
    clean = re.compile("<.*?>")
    text = re.sub(clean, "", html_content)
    # Decode HTML entities
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    # Clean up whitespace
    text = " ".join(text.split())
    return text


class RestCollectionAdapter(BaseAdapter):
    def to_canonical(
        self, payload: Dict[str, Any], shop_id: str, existing_products: list = None
    ) -> Dict[str, Any]:
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
            shop_id=shop_id,
            collection_id=collection_id,
            title=payload.get("title") or "",
            handle=payload.get("handle") or "",
            description=_strip_html(payload.get("body_html") or ""),
            template_suffix=payload.get("template_suffix"),
            seo_title=None,  # Not available in webhook
            seo_description=None,  # Not available in webhook
            image_url=(
                payload.get("image", {}).get("src") if payload.get("image") else None
            ),
            image_alt=(
                payload.get("image", {}).get("alt") if payload.get("image") else None
            ),
            product_count=0,  # Will be computed from products
            is_automated=False,  # Will be determined from rule_set
            metafields=[],  # Not available in webhook
            products=existing_products
            or [],  # Use existing products if provided, otherwise empty
            created_at=created_at,
            updated_at=updated_at,
            is_active=not is_delete,
            extras={},  # No extra fields - only store what exists in main table
        )

        return model.dict()
