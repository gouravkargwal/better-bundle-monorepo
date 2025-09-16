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
                    compareAtPrice=_to_float(v.get("compare_at_price")),
                    sku=v.get("sku"),
                    barcode=v.get("barcode"),
                    inventory=int(v.get("inventory_quantity") or 0)
                    if v.get("inventory_quantity") is not None
                    else None,
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
            compare_at = variants[0].compareAtPrice

        model = CanonicalProduct(
            shopId=shop_id,
            entityId=product_id,
            originalGid=payload.get("admin_graphql_api_id"),
            productCreatedAt=_parse_iso(payload.get("created_at")),
            productUpdatedAt=_parse_iso(payload.get("updated_at")) or datetime.utcnow(),
            title=payload.get("title"),
            handle=payload.get("handle"),
            description=payload.get("body_html"),
            vendor=payload.get("vendor"),
            productType=payload.get("product_type"),
            status=payload.get("status"),
            tags=tags,
            price=price,
            compareAtPrice=compare_at,
            totalInventory=total_inventory,
            isActive=True if payload.get("status") != "archived" else False,
            variants=variants,
            images=payload.get("images") or [],
            media=payload.get("media") or [],
            options=payload.get("options") or [],
            templateSuffix=payload.get("template_suffix"),
            extras={},
        )

        return model.dict()


