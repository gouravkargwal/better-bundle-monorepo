"""
Shop feature generator for ML feature engineering
"""

from typing import Dict, Any, List, Optional
import statistics

from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.domains.shopify.models import (
    ShopifyShop,
    ShopifyProduct,
    ShopifyOrder,
    ShopifyCustomer,
    ShopifyCollection,
    ShopifyCustomerEvent,
)

from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class ShopFeatureGenerator(BaseFeatureGenerator):
    """Feature generator for Shopify shops"""

    async def generate_features(
        self, shop: ShopifyShop, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate features for a shop

        Args:
            shop: The shop to generate features for
            context: Additional context data (products, orders, customers, etc.)

        Returns:
            Dictionary of generated features
        """
        try:
            logger.debug(f"Computing features for shop: {shop.id}")

            features = {}
            products = context.get("products", [])
            orders = context.get("orders", [])
            customers = context.get("customers", [])
            collections = context.get("collections", [])
            events = context.get("events", [])

            # Basic shop features
            features.update(self._compute_basic_shop_features(shop))

            # Product features
            if products:
                features.update(self._compute_shop_product_features(shop, products))

            # Order features
            if orders:
                features.update(self._compute_shop_order_features(shop, orders))

            # Customer features
            if customers:
                features.update(self._compute_shop_customer_features(shop, customers))

            # Collection features
            if collections:
                features.update(
                    self._compute_shop_collection_features(shop, collections)
                )

            # Event features
            if events:
                features.update(self._compute_shop_event_features(shop, events))

            # Validate and clean features
            features = self.validate_features(features)

            logger.debug(f"Computed {len(features)} features for shop: {shop.id}")
            return features

        except Exception as e:
            logger.error(f"Failed to compute shop features for {shop.id}: {str(e)}")
            return {}

    def _compute_basic_shop_features(self, shop: ShopifyShop) -> Dict[str, Any]:
        """Compute basic shop features"""
        return {
            "shop_id": shop.id,
            "shop_name_length": len(shop.name or ""),
            "domain_encoded": self._encode_categorical_feature(shop.domain or ""),
            "plan_encoded": self._encode_categorical_feature(shop.plan_name or ""),
            "currency_encoded": self._encode_categorical_feature(shop.currency or ""),
            "country_encoded": self._encode_categorical_feature(shop.country or ""),
            "timezone_encoded": self._encode_categorical_feature(
                shop.iana_timezone or ""
            ),
            "is_shopify_plus": 1 if shop.plan_name == "shopify_plus" else 0,
        }

    def _compute_shop_product_features(
        self, shop: ShopifyShop, products: List[ShopifyProduct]
    ) -> Dict[str, Any]:
        """Compute product-related shop features"""
        if not products:
            return {
                "total_products": 0,
                "avg_product_price": 0,
                "product_categories": 0,
                "product_vendors": 0,
            }

        prices = []
        categories = []
        vendors = []

        for product in products:
            if product.variants:
                prices.append(product.variants[0].price)
            if product.product_type:
                categories.append(product.product_type)
            if product.vendor:
                vendors.append(product.vendor)

        return {
            "total_products": len(products),
            "avg_product_price": statistics.mean(prices) if prices else 0,
            "product_categories": len(set(categories)),
            "product_vendors": len(set(vendors)),
        }

    def _compute_shop_order_features(
        self, shop: ShopifyShop, orders: List[ShopifyOrder]
    ) -> Dict[str, Any]:
        """Compute order-related shop features"""
        if not orders:
            return {
                "total_orders": 0,
                "total_revenue": 0,
                "avg_order_value": 0,
                "order_frequency": 0,
            }

        total_revenue = sum(order.total_price for order in orders)
        order_dates = [order.created_at for order in orders]
        order_dates.sort()

        # Calculate time between orders
        time_between_orders = []
        for i in range(1, len(order_dates)):
            days_diff = (order_dates[i] - order_dates[i - 1]).days
            time_between_orders.append(days_diff)

        return {
            "total_orders": len(orders),
            "total_revenue": total_revenue,
            "avg_order_value": total_revenue / len(orders),
            "order_frequency": (
                statistics.mean(time_between_orders) if time_between_orders else 0
            ),
        }

    def _compute_shop_customer_features(
        self, shop: ShopifyShop, customers: List[ShopifyCustomer]
    ) -> Dict[str, Any]:
        """Compute customer-related shop features"""
        if not customers:
            return {
                "total_customers": 0,
                "avg_customer_orders": 0,
                "avg_customer_spent": 0,
                "customer_retention": 0,
            }

        orders_counts = [c.orders_count for c in customers]
        spent_amounts = [c.total_spent for c in customers]

        return {
            "total_customers": len(customers),
            "avg_customer_orders": (
                statistics.mean(orders_counts) if orders_counts else 0
            ),
            "avg_customer_spent": (
                statistics.mean(spent_amounts) if spent_amounts else 0
            ),
            "customer_retention": (
                len([c for c in customers if c.orders_count > 1]) / len(customers)
                if customers
                else 0
            ),
        }

    def _compute_shop_collection_features(
        self, shop: ShopifyShop, collections: List[ShopifyCollection]
    ) -> Dict[str, Any]:
        """Compute collection-related shop features"""
        if not collections:
            return {
                "total_collections": 0,
                "avg_collection_size": 0,
                "automated_collections": 0,
            }

        collection_sizes = [c.products_count for c in collections]
        automated_count = len([c for c in collections if c.is_automated])

        return {
            "total_collections": len(collections),
            "avg_collection_size": (
                statistics.mean(collection_sizes) if collection_sizes else 0
            ),
            "automated_collections": automated_count,
        }

    def _compute_shop_event_features(
        self, shop: ShopifyShop, events: List[ShopifyCustomerEvent]
    ) -> Dict[str, Any]:
        """Compute event-related shop features"""
        if not events:
            return {
                "total_events": 0,
                "unique_event_types": 0,
                "event_frequency": 0,
            }

        event_types = [event.event_type for event in events]
        event_dates = [event.created_at for event in events]
        event_dates.sort()

        # Calculate time between events
        time_between_events = []
        for i in range(1, len(event_dates)):
            days_diff = (event_dates[i] - event_dates[i - 1]).days
            time_between_events.append(days_diff)

        return {
            "total_events": len(events),
            "unique_event_types": len(set(event_types)),
            "event_frequency": (
                statistics.mean(time_between_events) if time_between_events else 0
            ),
        }
