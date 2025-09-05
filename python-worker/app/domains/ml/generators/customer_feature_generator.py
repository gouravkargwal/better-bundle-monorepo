"""
Customer feature generator for ML feature engineering
"""

from typing import Dict, Any, List, Optional
import statistics

from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.domains.shopify.models import (
    ShopifyCustomer,
    ShopifyShop,
    ShopifyOrder,
    BehavioralEvent,
)

from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class CustomerFeatureGenerator(BaseFeatureGenerator):
    """Feature generator for Shopify customers"""

    async def generate_features(
        self, customer: ShopifyCustomer, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate features for a customer

        Args:
            customer: The customer to generate features for
            context: Additional context data (shop, orders, events, etc.)

        Returns:
            Dictionary of generated features
        """
        try:
            logger.debug(f"Computing features for customer: {customer.id}")

            features = {}
            shop = context.get("shop")
            orders = context.get("orders", [])
            events = context.get("events", [])

            # Basic customer features
            features.update(self._compute_basic_customer_features(customer))

            # Order history features
            if orders:
                customer_orders = [o for o in orders if o.customer_id == customer.id]
                features.update(
                    self._compute_order_history_features(customer, customer_orders)
                )

            # Behavioral features
            if events:
                customer_events = [e for e in events if e.customer_id == customer.id]
                features.update(
                    self._compute_behavioral_features(customer, customer_events)
                )

            # Address features
            features.update(self._compute_address_features(customer))

            # Time-based features
            features.update(self._compute_customer_time_features(customer))

            # Engagement features
            features.update(self._compute_engagement_features(customer))

            # Validate and clean features
            features = self.validate_features(features)

            logger.debug(
                f"Computed {len(features)} features for customer: {customer.id}"
            )
            return features

        except Exception as e:
            logger.error(
                f"Failed to compute customer features for {customer.id}: {str(e)}"
            )
            return {}

    def _compute_basic_customer_features(
        self, customer: ShopifyCustomer
    ) -> Dict[str, Any]:
        """Compute basic customer features"""
        return {
            "customer_id": customer.id,
            "accepts_marketing": 1 if customer.accepts_marketing else 0,
            "orders_count": customer.orders_count,
            "total_spent": customer.total_spent,
            "state_encoded": self._encode_categorical_feature(customer.state or ""),
            "note_encoded": self._encode_categorical_feature(customer.note or ""),
            "verified_email": 1 if customer.verified_email else 0,
            "multipass_identifier": self._encode_categorical_feature(
                customer.multipass_identifier or ""
            ),
            "tax_exempt": 1 if customer.tax_exempt else 0,
            "phone_encoded": self._encode_categorical_feature(customer.phone or ""),
            "tags_encoded": self._encode_categorical_feature(
                "|".join(customer.tags or [])
            ),
            "last_order_id": self._encode_categorical_feature(
                customer.last_order_id or ""
            ),
            "currency_encoded": self._encode_categorical_feature(
                customer.currency or ""
            ),
        }

    def _compute_order_history_features(
        self, customer: ShopifyCustomer, orders: List[ShopifyOrder]
    ) -> Dict[str, Any]:
        """Compute order history features"""
        if not orders:
            return {
                "total_orders": 0,
                "total_spent": 0,
                "average_order_value": 0,
                "days_since_last_order": 0,
                "order_frequency": 0,
                "order_consistency": 0,
            }

        total_spent = sum(order.total_price for order in orders)
        order_dates = [order.created_at for order in orders]
        order_dates.sort()

        # Calculate time between orders
        time_between_orders = []
        for i in range(1, len(order_dates)):
            days_diff = (order_dates[i] - order_dates[i - 1]).days
            time_between_orders.append(days_diff)

        return {
            "total_orders": len(orders),
            "total_spent": total_spent,
            "average_order_value": total_spent / len(orders),
            "days_since_last_order": (
                (now_utc() - order_dates[-1]).days if order_dates else 0
            ),
            "order_frequency": (
                statistics.mean(time_between_orders) if time_between_orders else 0
            ),
            "order_consistency": (
                1
                - (
                    statistics.stdev(time_between_orders)
                    / statistics.mean(time_between_orders)
                )
                if time_between_orders and statistics.mean(time_between_orders) > 0
                else 0
            ),
        }

    def _compute_behavioral_features(
        self, customer: ShopifyCustomer, events: List[BehavioralEvent]
    ) -> Dict[str, Any]:
        """Compute rich behavioral features from customer events"""
        if not events:
            return {
                "event_count": 0,
                "unique_event_types": 0,
                "last_event_days": 0,
                "event_frequency": 0,
                "engagement_score": 0,
                "page_views": 0,
                "product_views": 0,
                "cart_additions": 0,
                "collection_views": 0,
                "search_queries": 0,
                "checkout_starts": 0,
                "checkout_completions": 0,
                "unique_products_viewed": 0,
                "unique_collections_viewed": 0,
                "total_cart_value": 0.0,
                "average_product_price_viewed": 0.0,
                "search_diversity": 0.0,
                "conversion_rate": 0.0,
                "cart_abandonment_rate": 0.0,
                "browsing_intensity": 0.0,
                "purchase_intent_score": 0.0,
            }

        # Basic event metrics
        event_types = [event.event_type for event in events]
        event_dates = [event.occurred_at for event in events]
        event_dates.sort()

        # Calculate time between events
        time_between_events = []
        for i in range(1, len(event_dates)):
            days_diff = (event_dates[i] - event_dates[i - 1]).days
            time_between_events.append(days_diff)

        # Event type counts
        page_views = sum(1 for event in events if event.is_page_viewed)
        product_views = sum(1 for event in events if event.is_product_viewed)
        cart_additions = sum(1 for event in events if event.is_product_added_to_cart)
        collection_views = sum(1 for event in events if event.is_collection_viewed)
        search_queries = sum(1 for event in events if event.is_search_submitted)
        checkout_starts = sum(1 for event in events if event.is_checkout_started)
        checkout_completions = sum(1 for event in events if event.is_checkout_completed)

        # Unique items viewed
        unique_products = set()
        unique_collections = set()
        search_terms = set()
        cart_values = []
        product_prices = []

        for event in events:
            # Track unique products viewed
            product_id = event.get_product_id()
            if product_id:
                unique_products.add(product_id)

            # Track unique collections viewed
            collection_id = event.get_collection_id()
            if collection_id:
                unique_collections.add(collection_id)

            # Track search terms
            search_query = event.get_search_query()
            if search_query:
                search_terms.add(search_query.lower().strip())

            # Track cart values
            cart_value = event.get_cart_value()
            if cart_value is not None:
                cart_values.append(cart_value)

            # Track product prices viewed
            product_price = event.get_product_price()
            if product_price is not None:
                product_prices.append(product_price)

        # Calculate derived metrics
        total_cart_value = sum(cart_values) if cart_values else 0.0
        average_product_price_viewed = (
            statistics.mean(product_prices) if product_prices else 0.0
        )
        search_diversity = (
            len(search_terms) / max(search_queries, 1) if search_queries > 0 else 0.0
        )

        # Conversion metrics
        conversion_rate = (
            checkout_completions / max(product_views, 1) if product_views > 0 else 0.0
        )
        cart_abandonment_rate = (
            (checkout_starts - checkout_completions) / max(checkout_starts, 1)
            if checkout_starts > 0
            else 0.0
        )

        # Engagement metrics
        browsing_intensity = (product_views + collection_views + page_views) / max(
            len(events), 1
        )
        purchase_intent_score = (
            (cart_additions + checkout_starts) / max(product_views, 1)
            if product_views > 0
            else 0.0
        )

        # Overall engagement score (normalized 0-1)
        engagement_score = min(
            (len(events) + len(unique_products) + len(unique_collections)) / 20.0, 1.0
        )

        return {
            # Basic metrics
            "event_count": len(events),
            "unique_event_types": len(set(event_types)),
            "last_event_days": (now_utc() - event_dates[-1]).days if event_dates else 0,
            "event_frequency": (
                statistics.mean(time_between_events) if time_between_events else 0
            ),
            "engagement_score": engagement_score,
            # Event type counts
            "page_views": page_views,
            "product_views": product_views,
            "cart_additions": cart_additions,
            "collection_views": collection_views,
            "search_queries": search_queries,
            "checkout_starts": checkout_starts,
            "checkout_completions": checkout_completions,
            # Unique items
            "unique_products_viewed": len(unique_products),
            "unique_collections_viewed": len(unique_collections),
            # Financial metrics
            "total_cart_value": total_cart_value,
            "average_product_price_viewed": average_product_price_viewed,
            # Behavioral metrics
            "search_diversity": search_diversity,
            "conversion_rate": conversion_rate,
            "cart_abandonment_rate": cart_abandonment_rate,
            "browsing_intensity": browsing_intensity,
            "purchase_intent_score": purchase_intent_score,
        }

    def _compute_address_features(self, customer: ShopifyCustomer) -> Dict[str, Any]:
        """Compute address-related features"""
        if not customer.default_address:
            return {
                "has_address": 0,
                "country_encoded": 0,
                "province_encoded": 0,
                "city_encoded": 0,
            }

        address = customer.default_address
        return {
            "has_address": 1,
            "country_encoded": self._encode_categorical_feature(address.country or ""),
            "province_encoded": self._encode_categorical_feature(
                address.province or ""
            ),
            "city_encoded": self._encode_categorical_feature(address.city or ""),
        }

    def _compute_customer_time_features(
        self, customer: ShopifyCustomer
    ) -> Dict[str, Any]:
        """Compute time-based features for customer"""
        return self._compute_time_based_features(
            customer.created_at, customer.updated_at
        )

    def _compute_engagement_features(self, customer: ShopifyCustomer) -> Dict[str, Any]:
        """Compute customer engagement features"""
        engagement_score = 0

        # Marketing acceptance
        if customer.accepts_marketing:
            engagement_score += 1

        # Email verification
        if customer.verified_email:
            engagement_score += 1

        # Order history
        if customer.orders_count > 0:
            engagement_score += 1

        # Spending history
        if customer.total_spent > 0:
            engagement_score += 1

        # Address provided
        if customer.default_address:
            engagement_score += 1

        return {
            "engagement_score": engagement_score,
            "engagement_tier": (
                "high"
                if engagement_score >= 4
                else "medium" if engagement_score >= 2 else "low"
            ),
        }
