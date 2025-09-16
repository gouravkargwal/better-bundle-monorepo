from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..base_adapter import BaseAdapter
from ..canonical_models import CanonicalProduct, CanonicalVariant


def _parse_iso(dt: Optional[str]) -> Optional[datetime]:
    if not dt:
        return None
    try:
        if isinstance(dt, str) and dt.endswith("Z"):
            dt = dt.replace("Z", "+00:00")
        return datetime.fromisoformat(dt)  # type: ignore[arg-type]
    except Exception:
        return None


def _to_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
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


class GraphQLProductAdapter(BaseAdapter):
    def to_canonical(self, payload: Dict[str, Any], shop_id: str) -> Dict[str, Any]:
        entity_id = _extract_numeric_gid(payload.get("id")) or ""

        # Tags can be array in GQL
        raw_tags = payload.get("tags") or []
        tags: List[str] = list(raw_tags) if isinstance(raw_tags, list) else []

        # Variants via edges
        variants: List[CanonicalVariant] = []
        for edge in (payload.get("variants", {}) or {}).get("edges", []) or []:
            node = edge.get("node", {})
            variants.append(
                CanonicalVariant(
                    variantId=_extract_numeric_gid(node.get("id")),
                    title=node.get("title"),
                    price=_to_float(node.get("price")),
                    compareAtPrice=_to_float(node.get("compareAtPrice")),
                    sku=node.get("sku"),
                    barcode=node.get("barcode"),
                    inventory=(
                        int(node.get("inventoryQuantity") or 0)
                        if node.get("inventoryQuantity") is not None
                        else None
                    ),
                )
            )

        # Derive key product fields
        total_inventory = payload.get("totalInventory")
        if total_inventory is None and variants:
            total_inventory = sum([vi.inventory or 0 for vi in variants])

        price = variants[0].price if variants else None
        compare_at = variants[0].compareAtPrice if variants else None

        # Images/media/options via edges → arrays of nodes
        def _edges_to_nodes(
            container: Optional[Dict[str, Any]],
        ) -> List[Dict[str, Any]]:
            if not isinstance(container, dict):
                return []
            return [edge.get("node", {}) for edge in container.get("edges", []) or []]

        images = _edges_to_nodes(payload.get("images"))
        media = _edges_to_nodes(payload.get("media"))
        options = payload.get("options") or []

        seo = payload.get("seo") or {}
        seo_title = seo.get("title")
        seo_description = seo.get("description")

        model = CanonicalProduct(
            shopId=shop_id,
            entityId=entity_id,
            originalGid=payload.get("id"),
            productCreatedAt=_parse_iso(payload.get("createdAt")),
            productUpdatedAt=_parse_iso(payload.get("updatedAt")) or datetime.utcnow(),
            title=payload.get("title"),
            handle=payload.get("handle"),
            description=payload.get("description"),
            vendor=payload.get("vendor"),
            productType=payload.get("productType"),
            status=payload.get("status"),
            tags=tags,
            price=price,
            compareAtPrice=compare_at,
            totalInventory=total_inventory,
            isActive=True if payload.get("status") == "ACTIVE" else False,
            variants=variants,
            images=images,
            media=media,
            options=options,
            seoTitle=seo_title,
            seoDescription=seo_description,
            templateSuffix=payload.get("templateSuffix"),
            extras={},
        )

        return model.dict()
