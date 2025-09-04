"""
Order feature generator for ML feature engineering
"""

from typing import Dict, Any, List, Optional
import statistics

from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.domains.shopify.models import (
    ShopifyOrder,
    ShopifyShop,
    ShopifyProduct,
)

from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class OrderFeatureGenerator(BaseFeatureGenerator):
    """Feature generator for Shopify orders"""

    async def generate_features(
        self, order: ShopifyOrder, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate features for an order

        Args:
            order: The order to generate features for
            context: Additional context data (shop, products, etc.)

        Returns:
            Dictionary of generated features
        """
        try:
            logger.debug(f"Computing features for order: {order.id}")

            features = {}
            shop = context.get("shop")
            products = context.get("products", [])

            # Basic order features
            features.update(self._compute_basic_order_features(order))

            # Line item features
            features.update(self._compute_line_item_features(order))

            # Customer features
            features.update(self._compute_order_customer_features(order))

            # Product features
            if products:
                features.update(self._compute_order_product_features(order, products))

            # Time features
            features.update(self._compute_order_time_features(order))

            # Financial features
            features.update(self._compute_financial_features(order))

            # Validate and clean features
            features = self.validate_features(features)

            logger.debug(f"Computed {len(features)} features for order: {order.id}")
            return features

        except Exception as e:
            logger.error(f"Failed to compute order features for {order.id}: {str(e)}")
            return {}

    def _compute_basic_order_features(self, order: ShopifyOrder) -> Dict[str, Any]:
        """Compute basic order features"""
        return {
            "order_id": order.id,
            "order_number": order.order_number,
            "total_price": order.total_price,
            "subtotal_price": order.subtotal_price,
            "total_tax": order.total_tax,
            "currency_encoded": self._encode_categorical_feature(order.currency or ""),
            "financial_status_encoded": self._encode_categorical_feature(
                order.financial_status or ""
            ),
            "fulfillment_status_encoded": self._encode_categorical_feature(
                order.fulfillment_status or ""
            ),
            "line_items_count": len(order.line_items),
            "has_discount": 1 if order.total_discounts > 0 else 0,
            "total_discounts": order.total_discounts,
        }

    def _compute_line_item_features(self, order: ShopifyOrder) -> Dict[str, Any]:
        """Compute line item features"""
        if not order.line_items:
            return {
                "line_items_count": 0,
                "total_quantity": 0,
                "avg_item_price": 0,
                "price_std": 0,
                "unique_products": 0,
            }

        quantities = [item.quantity for item in order.line_items]
        prices = [item.price for item in order.line_items]
        product_ids = [item.product_id for item in order.line_items if item.product_id]

        return {
            "line_items_count": len(order.line_items),
            "total_quantity": sum(quantities),
            "avg_item_price": statistics.mean(prices) if prices else 0,
            "price_std": statistics.stdev(prices) if len(prices) > 1 else 0,
            "unique_products": len(set(product_ids)),
        }

    def _compute_order_customer_features(self, order: ShopifyOrder) -> Dict[str, Any]:
        """Compute customer-related order features"""
        return {
            "customer_id": self._encode_categorical_feature(order.customer_id or ""),
            "has_customer": 1 if order.customer_id else 0,
        }

    def _compute_order_product_features(
        self, order: ShopifyOrder, products: List[ShopifyProduct]
    ) -> Dict[str, Any]:
        """Compute product-related order features"""
        product_ids = [item.product_id for item in order.line_items if item.product_id]
        order_products = [p for p in products if p.id in product_ids]

        if not order_products:
            return {
                "avg_product_price": 0,
                "product_categories": 0,
                "product_vendors": 0,
            }

        prices = [p.variants[0].price for p in order_products if p.variants]
        categories = [p.product_type for p in order_products if p.product_type]
        vendors = [p.vendor for p in order_products if p.vendor]

        return {
            "avg_product_price": statistics.mean(prices) if prices else 0,
            "product_categories": len(set(categories)),
            "product_vendors": len(set(vendors)),
        }

    def _compute_order_time_features(self, order: ShopifyOrder) -> Dict[str, Any]:
        """Compute time-based order features"""
        return self._compute_time_based_features(order.created_at, order.updated_at)

    def _compute_financial_features(self, order: ShopifyOrder) -> Dict[str, Any]:
        """Compute financial features"""
        return {
            "total_price": order.total_price,
            "subtotal_price": order.subtotal_price,
            "total_tax": order.total_tax,
            "total_discounts": order.total_discounts,
            "discount_rate": (
                order.total_discounts / order.subtotal_price
                if order.subtotal_price > 0
                else 0
            ),
            "tax_rate": (
                order.total_tax / order.subtotal_price
                if order.subtotal_price > 0
                else 0
            ),
        }
