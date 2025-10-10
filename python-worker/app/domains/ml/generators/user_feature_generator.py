"""
Optimized User/Customer Feature Generator for State-of-the-Art Gorse Integration
Focuses on high-signal features that actually improve recommendation quality
"""

import datetime
from typing import Dict, Any, List, Optional
import statistics
from app.core.logging import get_logger
from app.shared.helpers import now_utc

from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class UserFeatureGenerator(BaseFeatureGenerator):
    """State-of-the-art feature generator for user/customer features optimized for Gorse"""

    async def generate_features(
        self,
        shop_id: str,
        customer_id: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate optimized user features for Gorse collaborative filtering

        Args:
            shop_id: The shop ID
            customer_id: The customer ID
            context: Additional context data (orders, customer_data, behavioral_events)

        Returns:
            Dictionary with minimal, high-signal features for Gorse
        """
        try:
            logger.debug(
                f"Computing optimized user features for customer: {customer_id}"
            )

            # Get data from context
            orders = context.get("orders", [])
            user_interactions = context.get("user_interactions", [])

            # Filter customer's orders
            customer_orders = [
                order for order in orders if order.get("customer_id") == customer_id
            ]

            # Filter customer's interactions
            customer_interactions = [
                interaction
                for interaction in user_interactions
                if interaction.get("customer_id") == customer_id
            ]

            # Core Gorse-optimized features
            features = {
                "shop_id": shop_id,
                "customer_id": customer_id,
                # === CORE ENGAGEMENT SIGNALS ===
                # These are the most predictive for collaborative filtering
                "total_purchases": len(customer_orders),
                "total_interactions": len(customer_interactions),
                "lifetime_value": self._compute_lifetime_value(customer_orders),
                # === BEHAVIORAL PREFERENCES ===
                # High-level patterns Gorse can use for clustering
                "avg_order_value": self._compute_avg_order_value(customer_orders),
                "purchase_frequency_score": self._compute_purchase_frequency(
                    customer_orders
                ),
                "interaction_diversity_score": self._compute_interaction_diversity_score(
                    customer_interactions
                ),
                # === TEMPORAL SIGNALS ===
                # Recent behavior is most predictive
                "days_since_last_purchase": self._compute_days_since_last_purchase(
                    customer_orders
                ),
                "recency_score": self._compute_recency_score(
                    customer_orders, customer_interactions
                ),
                # === CONVERSION QUALITY ===
                # User's propensity to convert
                "conversion_rate": self._compute_conversion_rate(
                    customer_interactions, customer_orders
                ),
                # === CATEGORY AFFINITY ===
                # For cold-start recommendations
                "primary_category": self._compute_primary_category(
                    customer_orders, context.get("products", [])
                ),
                "category_diversity": self._compute_category_diversity(
                    customer_orders, context.get("products", [])
                ),
                # === USER LIFECYCLE STAGE ===
                # Critical for recommendation strategy
                "user_lifecycle_stage": self._compute_lifecycle_stage(
                    customer_orders, customer_interactions
                ),
                # === RISK FACTORS ===
                # Important for recommendation quality
                "churn_risk_score": self._compute_churn_risk(
                    customer_orders, customer_interactions
                ),
                "last_computed_at": now_utc(),
            }

            return features

        except Exception as e:
            logger.error(f"Failed to compute optimized user features: {str(e)}")
            return self._get_minimal_default_features(shop_id, customer_id)

    def _compute_lifetime_value(self, customer_orders: List[Dict[str, Any]]) -> float:
        """Compute total customer lifetime value - core signal for Gorse"""
        if not customer_orders:
            return 0.0

        total_value = sum(
            float(order.get("totalAmount", 0.0)) for order in customer_orders
        )

        # Apply refund adjustment
        for order in customer_orders:
            if order.get("financialStatus") == "refunded":
                refunded_amount = float(
                    order.get("totalRefundedAmount", order.get("totalAmount", 0.0))
                )
                total_value -= refunded_amount

        return round(max(0.0, total_value), 2)

    def _compute_avg_order_value(self, customer_orders: List[Dict[str, Any]]) -> float:
        """Compute average order value - key for price-based clustering"""
        if not customer_orders:
            return 0.0

        total_value = sum(
            float(order.get("totalAmount", 0.0)) for order in customer_orders
        )
        return round(total_value / len(customer_orders), 2)

    def _compute_purchase_frequency(
        self, customer_orders: List[Dict[str, Any]]
    ) -> float:
        """Compute purchase frequency score - critical for active user identification"""
        if len(customer_orders) <= 1:
            return 0.0

        # Sort orders by date
        sorted_orders = sorted(
            customer_orders, key=lambda x: self._parse_date(x.get("order_date"))
        )

        first_order = self._parse_date(sorted_orders[0].get("order_date"))
        last_order = self._parse_date(sorted_orders[-1].get("order_date"))

        if not first_order or not last_order:
            return 0.0

        # Calculate orders per month
        days_span = max(1, (last_order - first_order).days)
        frequency_per_month = (len(customer_orders) - 1) / (days_span / 30.0)

        # Normalize to 0-1 scale (4+ orders per month = max score)
        return round(min(1.0, frequency_per_month / 4.0), 3)

    def _compute_interaction_diversity_score(
        self, customer_interactions: List[Dict[str, Any]]
    ) -> float:
        """Compute interaction diversity - helps Gorse understand user engagement patterns"""
        if not customer_interactions:
            return 0.0

        # Count unique interaction types
        interaction_types = set(
            interaction.get("interactionType", "")
            for interaction in customer_interactions
        )

        # Normalize diversity score (8+ types = max diversity)
        diversity = len(interaction_types) / 8.0
        return round(min(1.0, diversity), 3)

    def _compute_days_since_last_purchase(
        self, customer_orders: List[Dict[str, Any]]
    ) -> Optional[int]:
        """Days since last purchase - critical recency signal"""
        if not customer_orders:
            return None

        latest_order_date = max(
            (self._parse_date(order.get("order_date")) for order in customer_orders),
            default=None,
        )

        if not latest_order_date:
            return None

        return (now_utc() - latest_order_date).days

    def _compute_recency_score(
        self,
        customer_orders: List[Dict[str, Any]],
        customer_interactions: List[Dict[str, Any]],
    ) -> float:
        """Compute combined recency score from orders and interactions"""

        # Get most recent activity (order or interaction)
        most_recent_activity = None

        # Check orders
        if customer_orders:
            latest_order = max(
                (
                    self._parse_date(order.get("order_date"))
                    for order in customer_orders
                ),
                default=None,
            )
            if latest_order:
                most_recent_activity = latest_order

        # Check interactions
        if customer_interactions:
            latest_interaction = max(
                (
                    self._parse_date(interaction.get("created_at"))
                    for interaction in customer_interactions
                ),
                default=None,
            )
            if latest_interaction:
                if (
                    not most_recent_activity
                    or latest_interaction > most_recent_activity
                ):
                    most_recent_activity = latest_interaction

        if not most_recent_activity:
            return 0.0

        # Calculate recency score with exponential decay
        days_since_activity = (now_utc() - most_recent_activity).days

        # Score decays: 1.0 for today, 0.5 for 14 days ago, 0.1 for 60 days ago
        recency_score = max(0.0, 1.0 - (days_since_activity / 60.0))
        return round(recency_score, 3)

    def _compute_conversion_rate(
        self,
        customer_interactions: List[Dict[str, Any]],
        customer_orders: List[Dict[str, Any]],
    ) -> float:
        """Compute user's conversion rate - key quality signal for Gorse"""
        if not customer_interactions:
            return 0.0

        # Count high-intent interactions (views, cart adds)
        high_intent_interactions = sum(
            1
            for interaction in customer_interactions
            if interaction.get("interactionType")
            in ["product_viewed", "product_added_to_cart", "cart_viewed"]
        )

        if high_intent_interactions == 0:
            return 0.0

        # Count purchases (completed orders)
        purchase_count = len(customer_orders)

        conversion_rate = purchase_count / high_intent_interactions
        return round(min(1.0, conversion_rate), 3)

    def _compute_primary_category(
        self, customer_orders: List[Dict[str, Any]], products: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Find user's primary product category - for content-based signals in Gorse"""
        if not customer_orders or not products:
            return None

        category_counts = {}

        for order in customer_orders:
            for item in order.get("line_items", []):
                product_id = self._extract_product_id_from_line_item(item)
                if not product_id:
                    continue

                # Find product info
                product_info = next(
                    (p for p in products if p.get("product_id") == product_id), None
                )

                if product_info:
                    category = product_info.get("productType") or product_info.get(
                        "category"
                    )
                    if category:
                        quantity = int(item.get("quantity", 1))
                        category_counts[category] = (
                            category_counts.get(category, 0) + quantity
                        )

        return (
            max(category_counts, key=category_counts.get) if category_counts else None
        )

    def _compute_category_diversity(
        self, customer_orders: List[Dict[str, Any]], products: List[Dict[str, Any]]
    ) -> int:
        """Count distinct categories user has purchased from"""
        if not customer_orders or not products:
            return 0

        categories = set()

        for order in customer_orders:
            for item in order.get("line_items", []):
                product_id = self._extract_product_id_from_line_item(item)
                if not product_id:
                    continue

                product_info = next(
                    (p for p in products if p.get("product_id") == product_id), None
                )

                if product_info:
                    category = product_info.get("productType") or product_info.get(
                        "category"
                    )
                    if category:
                        categories.add(category)

        return len(categories)

    def _compute_lifecycle_stage(
        self,
        customer_orders: List[Dict[str, Any]],
        customer_interactions: List[Dict[str, Any]],
    ) -> str:
        """Determine user lifecycle stage - critical for recommendation strategy"""

        total_orders = len(customer_orders)
        total_interactions = len(customer_interactions)

        # Get recency
        days_since_last_purchase = self._compute_days_since_last_purchase(
            customer_orders
        )

        # Classify lifecycle stage
        if total_orders == 0:
            if total_interactions > 0:
                return "browser"  # Engaged but never purchased
            else:
                return "new"  # No activity

        elif total_orders == 1:
            if days_since_last_purchase and days_since_last_purchase <= 30:
                return "new_customer"  # Recent first purchase
            else:
                return "one_time"  # Single purchase, long ago

        elif total_orders >= 2:
            if days_since_last_purchase and days_since_last_purchase <= 60:
                return "repeat_active"  # Regular repeat customer
            elif days_since_last_purchase and days_since_last_purchase <= 180:
                return "repeat_dormant"  # Repeat customer going dormant
            else:
                return "repeat_churned"  # Churned repeat customer

        return "unknown"

    def _compute_churn_risk(
        self,
        customer_orders: List[Dict[str, Any]],
        customer_interactions: List[Dict[str, Any]],
    ) -> float:
        """Compute churn risk score - helps Gorse prioritize retention recommendations"""

        if not customer_orders and not customer_interactions:
            return 1.0  # High churn risk for inactive users

        churn_signals = 0
        max_signals = 5

        # Signal 1: Long time since last purchase
        days_since_last_purchase = self._compute_days_since_last_purchase(
            customer_orders
        )
        if days_since_last_purchase and days_since_last_purchase > 90:
            churn_signals += 1

        # Signal 2: Low interaction frequency
        if len(customer_interactions) < 5:
            churn_signals += 1

        # Signal 3: Low purchase frequency
        purchase_frequency = self._compute_purchase_frequency(customer_orders)
        if purchase_frequency < 0.1:  # Less than once per 10 months
            churn_signals += 1

        # Signal 4: High refund rate
        if customer_orders:
            refunded_orders = sum(
                1
                for order in customer_orders
                if order.get("financialStatus") == "refunded"
            )
            refund_rate = refunded_orders / len(customer_orders)
            if refund_rate > 0.2:  # More than 20% refund rate
                churn_signals += 1

        # Signal 5: Single category only (low engagement breadth)
        category_diversity = self._compute_category_diversity(customer_orders, [])
        if category_diversity <= 1 and len(customer_orders) > 1:
            churn_signals += 1

        churn_risk = churn_signals / max_signals
        return round(churn_risk, 3)

    # Helper methods
    def _extract_product_id_from_line_item(self, line_item: Dict[str, Any]) -> str:
        """Extract product ID from order line item"""
        if "product_id" in line_item:
            return str(line_item["product_id"])

        if "variant" in line_item and isinstance(line_item["variant"], dict):
            product = line_item["variant"].get("product", {})
            if isinstance(product, dict):
                return product.get("id", "")

        return ""

    def _parse_date(self, date_value: Any) -> Optional[datetime.datetime]:
        """Parse date from various formats"""
        if not date_value:
            return None

        if isinstance(date_value, datetime.datetime):
            return date_value

        if isinstance(date_value, str):
            try:
                return datetime.datetime.fromisoformat(
                    date_value.replace("Z", "+00:00")
                )
            except:
                return None

        return None

    def _get_minimal_default_features(
        self, shop_id: str, customer_id: str
    ) -> Dict[str, Any]:
        """Return minimal default features when computation fails"""
        return {
            "shop_id": shop_id,
            "customer_id": customer_id,
            "total_purchases": 0,
            "total_interactions": 0,
            "lifetime_value": 0.0,
            "avg_order_value": 0.0,
            "purchase_frequency_score": 0.0,
            "interaction_diversity_score": 0.0,
            "days_since_last_purchase": None,
            "recency_score": 0.0,
            "conversion_rate": 0.0,
            "primary_category": None,
            "category_diversity": 0,
            "user_lifecycle_stage": "new",
            "churn_risk_score": 1.0,
            "last_computed_at": now_utc(),
        }
