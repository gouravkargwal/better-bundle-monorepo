from __future__ import annotations

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

        # variants
        variants: List[CanonicalVariant] = []
        for v in payload.get("variants", []) or []:
            variants.append(
                CanonicalVariant(
                    variantId=str(v.get("id")) if v.get("id") is not None else None,
                    title=v.get("title"),
                    price=_to_float(v.get("price")),
                    compare_at_price=_to_float(v.get("compare_at_price")),
                    sku=v.get("sku"),
                    barcode=v.get("barcode"),
                    inventory=(
                        int(v.get("inventory_quantity") or 0)
                        if v.get("inventory_quantity") is not None
                        else None
                    ),
                )
            )

        # total inventory from variants sum if available
        total_inventory = (
            sum([vi.inventory or 0 for vi in variants]) if variants else None
        )

        # primary price fields
        price = None
        compare_at = None
        if variants:
            price = variants[0].price
            compare_at = variants[0].compare_at_price

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
            product_id=product_id,  # Fixed: use productId instead of entityId
            created_at=created_at,  # Required field
            updated_at=updated_at,  # Required field
            title=payload.get("title") or "",  # Required field
            handle=payload.get("handle") or "",  # Required field
            description=payload.get("body_html"),
            vendor=payload.get("vendor"),
            product_type=payload.get("product_type"),
            status=payload.get("status"),
            tags=tags,
            price=price or 0.0,  # Required field with default
            compare_at_price=compare_at,
            total_inventory=total_inventory,
            imageUrl=image_url,  # Extract primary image URL
            imageAlt=image_alt,  # Extract primary image alt text
            isActive=True if payload.get("status") != "archived" else False,
            variants=variants,
            images=images,  # Keep full images array
            media=payload.get("media") or [],
            options=payload.get("options") or [],
            templateSuffix=payload.get("template_suffix"),
            extras={},
        )

        return model.dict()
