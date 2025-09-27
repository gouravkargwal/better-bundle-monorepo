from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List

from ..base_adapter import BaseAdapter
from ..canonical_models import CanonicalProduct, CanonicalVariant


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


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


class RestProductAdapter(BaseAdapter):
    def to_canonical(self, payload: Dict[str, Any], shop_id: str) -> Dict[str, Any]:
        product_id = str(payload.get("id")) if payload.get("id") is not None else ""

        # tags can be CSV
        raw_tags = payload.get("tags") or []
        tags: List[str]
        if isinstance(raw_tags, str):
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        else:
            tags = list(raw_tags)

        # variants - store complete variant data as JSON
        variants = []
        for v in payload.get("variants", []) or []:
            variant_data = {
                "variant_id": str(v.get("id")) if v.get("id") is not None else None,
                "title": v.get("title"),
                "price": _to_float(v.get("price")),
                "compare_at_price": _to_float(v.get("compare_at_price")),
                "sku": v.get("sku"),
                "barcode": v.get("barcode"),
                "inventory_quantity": (
                    int(v.get("inventory_quantity") or 0)
                    if v.get("inventory_quantity") is not None
                    else None
                ),
                "taxable": v.get("taxable"),
                "inventory_policy": v.get("inventory_policy"),
                "position": v.get("position"),
                "created_at": (
                    _parse_iso(v.get("created_at")).isoformat()
                    if _parse_iso(v.get("created_at"))
                    else None
                ),
                "updated_at": (
                    _parse_iso(v.get("updated_at")).isoformat()
                    if _parse_iso(v.get("updated_at"))
                    else None
                ),
                "option1": v.get("option1"),
                "option2": v.get("option2"),
                "option3": v.get("option3"),
                "image_id": v.get("image_id"),
                "inventory_item_id": v.get("inventory_item_id"),
                "old_inventory_quantity": v.get("old_inventory_quantity"),
                "admin_graphql_api_id": v.get("admin_graphql_api_id"),
            }
            variants.append(variant_data)

        # total inventory from variants sum if available
        total_inventory = (
            sum([vi.get("inventory_quantity") or 0 for vi in variants])
            if variants
            else None
        )

        # primary price fields
        price = None
        compare_at = None
        if variants:
            price = variants[0].get("price")
            compare_at = variants[0].get("compare_at_price")

        # Parse timestamps
        created_at = _parse_iso(payload.get("created_at")) or datetime.utcnow()
        updated_at = _parse_iso(payload.get("updated_at")) or datetime.utcnow()

        # Extract primary image URL and alt text
        images = payload.get("images") or []
        primary_image = images[0] if images else {}
        image_url = primary_image.get("src") if primary_image else None
        image_alt = primary_image.get("alt") if primary_image else None

        model = CanonicalProduct(
            shop_id=shop_id,
            product_id=product_id,
            created_at=created_at,
            updated_at=updated_at,
            title=payload.get("title") or "",
            handle=payload.get("handle") or "",
            description=_strip_html(payload.get("body_html") or ""),
            product_type=payload.get("product_type"),
            vendor=payload.get("vendor"),
            tags=tags,
            status=payload.get("status"),
            total_inventory=total_inventory,
            price=price or 0.0,
            compare_at_price=compare_at,
            price_range={},  # Will be computed in feature engineering
            collections=[],  # Will be populated from collection relationships
            seo_title=None,  # Not available in webhook
            seo_description=None,  # Not available in webhook
            template_suffix=payload.get("template_suffix"),
            variants=variants,
            images=images,
            media=payload.get("media") or [],
            options=payload.get("options") or [],
            metafields=[],  # Not available in webhook
            extras={},  # No extra fields - only store what exists in main table
        )

        return model.dict()
