"""
Collection feature generator for ML feature engineering
"""

from typing import Dict, Any, List, Optional
import statistics

from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.domains.shopify.models import (
    ShopifyCollection,
    ShopifyShop,
    ShopifyProduct,
    ShopifyOrder,
)

from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class CollectionFeatureGenerator(BaseFeatureGenerator):
    """Feature generator for Shopify collections"""

    async def generate_features(
        self, collection: ShopifyCollection, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate features for a collection

        Args:
            collection: The collection to generate features for
            context: Additional context data (shop, products, orders, etc.)

        Returns:
            Dictionary of generated features
        """
        try:
            logger.debug(f"Computing features for collection: {collection.id}")

            features = {}
            shop = context.get("shop")
            products = context.get("products", [])
            orders = context.get("orders", [])

            # Basic collection features
            features.update(self._compute_basic_collection_features(collection))

            # Product features
            if products:
                features.update(
                    self._compute_collection_product_features(collection, products)
                )

            # SEO features
            features.update(self._compute_seo_features(collection))

            # Time features
            features.update(self._compute_collection_time_features(collection))

            # Performance features
            if orders:
                features.update(
                    self._compute_collection_performance_features(collection, orders)
                )

            # Validate and clean features
            features = self.validate_features(features)

            logger.debug(
                f"Computed {len(features)} features for collection: {collection.id}"
            )
            return features

        except Exception as e:
            logger.error(
                f"Failed to compute collection features for {collection.id}: {str(e)}"
            )
            return {}

    def _compute_basic_collection_features(
        self, collection: ShopifyCollection
    ) -> Dict[str, Any]:
        """Compute basic collection features"""
        return {
            "collection_id": collection.id,
            "title_length": len(collection.title or ""),
            "description_length": len(collection.body_html or ""),
            "handle_encoded": self._encode_categorical_feature(collection.handle or ""),
            "sort_order_encoded": self._encode_categorical_feature(
                collection.sort_order or ""
            ),
            "is_published": 1 if collection.published else 0,
            "products_count": collection.products_count,
            "is_automated": 1 if collection.is_automated else 0,
        }

    def _compute_collection_product_features(
        self, collection: ShopifyCollection, products: List[ShopifyProduct]
    ) -> Dict[str, Any]:
        """Compute product-related collection features"""
        collection_products = [p for p in products if p.id in collection.product_ids]

        if not collection_products:
            return {
                "avg_product_price": 0,
                "product_categories": 0,
                "product_vendors": 0,
                "avg_product_rating": 0,
            }

        prices = []
        categories = []
        vendors = []

        for product in collection_products:
            if product.variants:
                prices.append(product.variants[0].price)
            if product.product_type:
                categories.append(product.product_type)
            if product.vendor:
                vendors.append(product.vendor)

        return {
            "avg_product_price": statistics.mean(prices) if prices else 0,
            "product_categories": len(set(categories)),
            "product_vendors": len(set(vendors)),
            "avg_product_rating": 0,  # Placeholder - would need rating data
        }

    def _compute_seo_features(self, collection: ShopifyCollection) -> Dict[str, Any]:
        """Compute SEO-related features"""
        seo_score = 0

        # Title quality
        if collection.title and len(collection.title) > 10:
            seo_score += 1

        # Description quality
        if collection.body_html and len(collection.body_html) > 50:
            seo_score += 1

        # Handle quality
        if collection.handle and len(collection.handle) > 3:
            seo_score += 1

        return {
            "seo_score": seo_score,
            "seo_tier": (
                "high" if seo_score >= 3 else "medium" if seo_score >= 1 else "low"
            ),
        }

    def _compute_collection_time_features(
        self, collection: ShopifyCollection
    ) -> Dict[str, Any]:
        """Compute time-based collection features"""
        return self._compute_time_based_features(
            collection.created_at, collection.updated_at
        )

    def _compute_collection_performance_features(
        self, collection: ShopifyCollection, orders: List[ShopifyOrder]
    ) -> Dict[str, Any]:
        """Compute collection performance features"""
        collection_orders = []
        total_revenue = 0

        for order in orders:
            for line_item in order.line_items:
                if line_item.product_id in collection.product_ids:
                    collection_orders.append(order)
                    total_revenue += line_item.price * line_item.quantity
                    break

        return {
            "total_orders": len(collection_orders),
            "total_revenue": total_revenue,
            "avg_order_value": (
                total_revenue / len(collection_orders) if collection_orders else 0
            ),
            "conversion_rate": (len(collection_orders) / len(orders) if orders else 0),
        }
