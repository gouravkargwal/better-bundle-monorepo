from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.domains.shopify.normalization.base_adapter import BaseAdapter
from app.domains.shopify.normalization.canonical_models import (
    CanonicalProduct,
    CanonicalVariant,
)


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

        # Variants via edges - now using snake_case field names from paginated data
        variants: List[CanonicalVariant] = []
        for edge in (payload.get("variants", {}) or {}).get("edges", []) or []:
            node = edge.get("node", {})
            variants.append(
                CanonicalVariant(
                    variant_id=_extract_numeric_gid(node.get("id")),
                    title=node.get("title"),
                    price=_to_float(node.get("price")),
                    compare_at_price=_to_float(
                        node.get("compare_at_price")
                    ),  # Updated to snake_case
                    sku=node.get("sku"),
                    barcode=node.get("barcode"),
                    inventory=(
                        int(
                            node.get("inventory_quantity") or 0
                        )  # Updated to snake_case
                        if node.get("inventory_quantity") is not None
                        else None
                    ),
                )
            )

        # Derive key product fields - now using snake_case field names
        total_inventory = payload.get("total_inventory")  # Updated to snake_case
        if total_inventory is None and variants:
            total_inventory = sum([vi.inventory or 0 for vi in variants])

        price = variants[0].price if variants else None
        compare_at = variants[0].compare_at_price if variants else None

        # Note: Derived metrics (variant_count, image_count, tag_count, price_range, collections)
        # are computed in feature engineering, not during normalization

        # Images/media/options via edges → arrays of nodes with extracted IDs and snake_case fields
        def _edges_to_nodes_with_extracted_ids(
            container: Optional[Dict[str, Any]],
        ) -> List[Dict[str, Any]]:
            if not isinstance(container, dict):
                return []
            nodes = []
            for edge in container.get("edges", []) or []:
                node = edge.get("node", {})
                # Extract numeric ID from GraphQL ID
                if "id" in node:
                    node["id"] = _extract_numeric_gid(node["id"])
                # Convert altText to alt_text for images
                if "altText" in node:
                    node["alt_text"] = node.pop("altText")
                nodes.append(node)
            return nodes

        images = _edges_to_nodes_with_extracted_ids(payload.get("images"))
        media = _edges_to_nodes_with_extracted_ids(payload.get("media"))

        # Process metafields - now using snake_case field names from paginated data
        metafields = _edges_to_nodes_with_extracted_ids(payload.get("metafields"))

        # Extract IDs from options array
        options = []
        for option in payload.get("options") or []:
            option_copy = option.copy()
            if "id" in option_copy:
                option_copy["id"] = _extract_numeric_gid(option_copy["id"])
            options.append(option_copy)

        seo = payload.get("seo") or {}
        seo_title = seo.get("title")
        seo_description = seo.get("description")

        # Canonical internal timestamps (required) - now using snake_case field names
        created_at = _parse_iso(payload.get("created_at"))  # Updated to snake_case
        updated_at = (
            _parse_iso(payload.get("updated_at")) or created_at
        )  # Updated to snake_case

        model = CanonicalProduct(
            shop_id=shop_id,
            product_id=entity_id,
            created_at=created_at,
            updated_at=updated_at,
            title=payload.get("title") or "Untitled Product",
            handle=payload.get("handle") or "untitled-product",
            description=payload.get("description"),
            vendor=payload.get("vendor"),
            product_type=payload.get("product_type"),  # Updated to snake_case
            status=payload.get("status"),
            tags=tags,
            price=price,
            compare_at_price=compare_at,
            total_inventory=total_inventory,
            is_active=True if payload.get("status") == "ACTIVE" else False,
            variants=variants,
            images=images,
            media=media,
            options=options,
            metafields=metafields,  # Added metafields processing
            seo_title=seo_title,
            seo_description=seo_description,
            template_suffix=payload.get("template_suffix"),  # Updated to snake_case
            # Derived metrics are computed in feature engineering, not normalization
            extras={},
        )

        return model.model_dump()
