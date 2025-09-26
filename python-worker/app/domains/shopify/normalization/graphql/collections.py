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

    def _normalize_products(self, products):
        """Normalize products data from GraphQL to store in database"""
        if not products or not isinstance(products, dict):
            return []

        products_edges = products.get("edges", [])
        if not isinstance(products_edges, list):
            return []

        # Extract and normalize product data
        normalized_products = []
        for edge in products_edges:
            if not isinstance(edge, dict):
                continue

            node = edge.get("node", {})
            if not isinstance(node, dict):
                continue

            # Extract numeric ID from GraphQL ID
            product_id = self._extract_numeric_gid(node.get("id"))
            if not product_id:
                continue

            # Normalize product data - now using snake_case field names from paginated data
            normalized_product = {
                "id": product_id,
                "title": node.get("title", ""),
                "handle": node.get("handle", ""),
                "product_type": node.get("product_type", ""),  # Updated to snake_case
                "vendor": node.get("vendor", ""),
                "tags": node.get("tags", []),
                "price_range": node.get("price_range", {}),  # Updated to snake_case
            }

            normalized_products.append(normalized_product)

        return normalized_products

    def _extract_numeric_gid(self, gid):
        """Extract numeric ID from GraphQL ID"""
        if not gid or not isinstance(gid, str):
            return None
        try:
            if gid.startswith("gid://shopify/"):
                return gid.split("/")[-1]
            return gid
        except Exception:
            return None

    def to_canonical(self, payload: Dict[str, Any], shop_id: str) -> Dict[str, Any]:
        collectionId = _extract_numeric_gid(payload.get("id")) or ""
        created_at = (
            _parse_iso(payload.get("created_at"))  # Updated to snake_case
            or _parse_iso(payload.get("updated_at"))  # Updated to snake_case
            or datetime.utcnow()
        )
        updated_at = (
            _parse_iso(payload.get("updated_at")) or created_at
        )  # Updated to snake_case

        model = CanonicalCollection(
            shop_id=shop_id,
            collection_id=collectionId,
            title=payload.get("title") or "Untitled Collection",
            handle=payload.get("handle") or "untitled-collection",
            description=payload.get("description")
            or payload.get("description_html")  # Updated to snake_case
            or "",
            template_suffix=payload.get("template_suffix")
            or "",  # Updated to snake_case
            seo_title=(payload.get("seo", {}) or {}).get("title"),
            seo_description=(payload.get("seo", {}) or {}).get("description"),
            image_url=(
                (payload.get("image") or {}).get("url")
                if isinstance(payload.get("image"), dict)
                else None
            ),
            image_alt=(
                (payload.get("image") or {}).get("alt_text")  # Updated to snake_case
                if isinstance(payload.get("image"), dict)
                else None
            ),
            product_count=(
                len(payload.get("products", {}).get("edges", []))
                if isinstance(payload.get("products"), dict)
                else 0
            ),
            is_automated=bool(payload.get("ruleSet") is not None),
            metafields=self._normalize_metafields(payload.get("metafields")),
            products=self._normalize_products(
                payload.get("products")
            ),  # Store products data
            created_at=created_at,
            updated_at=updated_at,
            is_active=True,
            extras={},
        )

        return model.dict()
