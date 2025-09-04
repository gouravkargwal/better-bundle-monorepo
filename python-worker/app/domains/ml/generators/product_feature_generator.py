"""
Product feature generator for ML feature engineering
"""

from typing import Dict, Any, List, Optional
import statistics

from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.domains.shopify.models import (
    ShopifyProduct,
    ShopifyShop,
    ShopifyOrder,
    ShopifyCollection,
)

from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class ProductFeatureGenerator(BaseFeatureGenerator):
    """Feature generator for Shopify products"""

    async def generate_features(
        self, product: ShopifyProduct, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate features for a product

        Args:
            product: The product to generate features for
            context: Additional context data (shop, orders, collections, etc.)

        Returns:
            Dictionary of generated features
        """
        try:
            logger.debug(f"Computing features for product: {product.id}")

            features = {}
            shop = context.get("shop")
            orders = context.get("orders", [])
            collections = context.get("collections", [])

            # Basic product features
            features.update(self._compute_basic_product_features(product))

            # Variant features
            features.update(self._compute_variant_features(product))

            # Image features
            features.update(self._compute_image_features(product))

            # Tag and category features
            features.update(self._compute_tag_features(product))

            # Collection features
            if collections:
                features.update(self._compute_collection_features(product, collections))

            # Historical performance features (if orders available)
            if orders:
                features.update(self._compute_performance_features(product, orders))

            # Shop context features
            if shop:
                features.update(self._compute_shop_context_features(product, shop))

            # Time-based features
            features.update(self._compute_time_features(product))

            # Quality features
            features.update(self._compute_quality_features(product))

            # Validate and clean features
            features = self.validate_features(features)

            logger.debug(f"Computed {len(features)} features for product: {product.id}")
            return features

        except Exception as e:
            logger.error(
                f"Failed to compute product features for {product.id}: {str(e)}"
            )
            return {}

    def _compute_basic_product_features(
        self, product: ShopifyProduct
    ) -> Dict[str, Any]:
        """Compute basic product features"""
        return {
            "product_id": product.id,
            "title_length": len(product.title or ""),
            "description_length": len(product.body_html or ""),
            "vendor_encoded": self._encode_categorical_feature(product.vendor),
            "product_type_encoded": self._encode_categorical_feature(
                product.product_type
            ),
            "status_encoded": 1 if product.status == "active" else 0,
            "is_published": 1 if product.is_published else 0,
            "variant_count": product.variant_count,
            "has_multiple_variants": 1 if product.has_multiple_variants else 0,
            "tag_count": product.tag_count,
            "collection_count": product.collection_count,
            "has_images": 1 if product.has_images else 0,
            "image_count": product.image_count,
        }

    def _compute_variant_features(self, product: ShopifyProduct) -> Dict[str, Any]:
        """Compute variant-related features"""
        if not product.variants:
            return {
                "variant_count": 0,
                "price_range": 0,
                "price_std": 0,
                "avg_price": 0,
                "min_price": 0,
                "max_price": 0,
                "weight_range": 0,
                "avg_weight": 0,
                "inventory_total": 0,
                "avg_inventory": 0,
            }

        prices = [v.price for v in product.variants if v.price is not None]
        weights = [v.weight for v in product.variants if v.weight is not None]
        inventory = [
            v.inventory_quantity
            for v in product.variants
            if v.inventory_quantity is not None
        ]

        return {
            "variant_count": len(product.variants),
            "price_range": max(prices) - min(prices) if prices else 0,
            "price_std": statistics.stdev(prices) if len(prices) > 1 else 0,
            "avg_price": statistics.mean(prices) if prices else 0,
            "min_price": min(prices) if prices else 0,
            "max_price": max(prices) if prices else 0,
            "weight_range": max(weights) - min(weights) if weights else 0,
            "avg_weight": statistics.mean(weights) if weights else 0,
            "inventory_total": sum(inventory) if inventory else 0,
            "avg_inventory": statistics.mean(inventory) if inventory else 0,
        }

    def _compute_image_features(self, product: ShopifyProduct) -> Dict[str, Any]:
        """Compute image-related features"""
        if not product.images:
            return {
                "image_count": 0,
                "has_images": 0,
                "image_alt_text_coverage": 0,
            }

        alt_text_count = sum(1 for img in product.images if img.alt_text)

        return {
            "image_count": len(product.images),
            "has_images": 1,
            "image_alt_text_coverage": alt_text_count / len(product.images),
        }

    def _compute_tag_features(self, product: ShopifyProduct) -> Dict[str, Any]:
        """Compute tag and category features"""
        tags = product.tags or []

        return {
            "tag_count": len(tags),
            "tag_diversity": len(set(tags)),
            "has_tags": 1 if tags else 0,
            "tag_encoded": self._encode_categorical_feature("|".join(tags)),
        }

    def _compute_collection_features(
        self, product: ShopifyProduct, collections: List[ShopifyCollection]
    ) -> Dict[str, Any]:
        """Compute collection-related features"""
        product_collections = [
            c for c in collections if product.id in [p.id for p in c.products]
        ]

        if not product_collections:
            return {
                "collection_count": 0,
                "avg_collection_size": 0,
                "is_in_featured_collection": 0,
            }

        return {
            "collection_count": len(product_collections),
            "avg_collection_size": statistics.mean(
                [c.products_count for c in product_collections]
            ),
            "is_in_featured_collection": (
                1 if any(c.is_featured for c in product_collections) else 0
            ),
        }

    def _compute_performance_features(
        self, product: ShopifyProduct, orders: List[ShopifyOrder]
    ) -> Dict[str, Any]:
        """Compute historical performance features"""
        product_orders = []
        total_quantity = 0
        total_revenue = 0

        for order in orders:
            for line_item in order.line_items:
                if line_item.product_id == product.id:
                    product_orders.append(order)
                    total_quantity += line_item.quantity
                    total_revenue += line_item.price * line_item.quantity

        return {
            "total_orders": len(product_orders),
            "total_quantity_sold": total_quantity,
            "total_revenue": total_revenue,
            "avg_order_value": (
                total_revenue / len(product_orders) if product_orders else 0
            ),
            "conversion_rate": len(product_orders) / len(orders) if orders else 0,
        }

    def _compute_shop_context_features(
        self, product: ShopifyProduct, shop: ShopifyShop
    ) -> Dict[str, Any]:
        """Compute shop context features"""
        return {
            "shop_plan_encoded": self._encode_categorical_feature(shop.plan_name or ""),
            "shop_currency_encoded": self._encode_categorical_feature(
                shop.currency or ""
            ),
            "shop_country_encoded": self._encode_categorical_feature(
                shop.country or ""
            ),
        }

    def _compute_time_features(self, product: ShopifyProduct) -> Dict[str, Any]:
        """Compute time-based features"""
        return self._compute_time_based_features(product.created_at, product.updated_at)

    def _compute_quality_features(self, product: ShopifyProduct) -> Dict[str, Any]:
        """Compute product quality features"""
        quality_score = 0

        # Title quality
        if product.title and len(product.title) > 10:
            quality_score += 1

        # Description quality
        if product.body_html and len(product.body_html) > 50:
            quality_score += 1

        # Image quality
        if product.has_images:
            quality_score += 1

        # Tag quality
        if product.tags and len(product.tags) > 2:
            quality_score += 1

        # Variant quality
        if product.variant_count > 0:
            quality_score += 1

        return {
            "quality_score": quality_score,
            "quality_tier": (
                "high"
                if quality_score >= 4
                else "medium" if quality_score >= 2 else "low"
            ),
        }
