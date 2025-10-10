"""
Optimized Customer-Product Interaction Feature Generator for State-of-the-Art Gorse Integration
Focuses on interaction signals that actually improve recommendation quality
"""

import datetime
from typing import Dict, Any, List, Optional
from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.domains.ml.adapters.adapter_factory import InteractionEventAdapterFactory
from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class InteractionFeatureGenerator(BaseFeatureGenerator):
    """State-of-the-art interaction feature generator optimized for Gorse collaborative filtering"""

    def __init__(self):
        super().__init__()
        self.adapter_factory = InteractionEventAdapterFactory()

    async def generate_features(
        self,
        shop_id: str,
        customer_id: str,
        product_id: str,
        context: Dict[str, Any],
        product_id_mapping: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Generate optimized interaction features for Gorse

        Args:
            shop_id: The shop ID
            customer_id: The customer ID
            product_id: The product ID
            context: Additional context data (orders, behavioral_events)
            product_id_mapping: Mapping between different product ID formats

        Returns:
            Dictionary with minimal, high-signal interaction features for Gorse
        """
        try:
            logger.debug(
                f"Computing optimized interaction features for: {customer_id} x {product_id}"
            )

            # Get data from context
            user_interactions = context.get("user_interactions", [])
            orders = context.get("orders", [])

            # Filter interactions for this customer-product pair
            filtered_interactions = self._filter_customer_product_interactions(
                user_interactions, customer_id, product_id, product_id_mapping
            )

            # Get purchase data
            product_purchases = self._get_product_purchases(
                orders, customer_id, product_id, product_id_mapping
            )

            # Core Gorse-optimized interaction features
            features = {
                "shop_id": shop_id,
                "customer_id": customer_id,
                "product_id": product_id,
                # === CORE INTERACTION SIGNALS ===
                # These are the most predictive for collaborative filtering
                "interaction_strength_score": self._compute_interaction_strength_score(
                    filtered_interactions, product_purchases
                ),
                "customer_product_affinity": self._compute_customer_product_affinity(
                    filtered_interactions, product_purchases
                ),
                "engagement_progression_score": self._compute_engagement_progression_score(
                    filtered_interactions
                ),
                # === CONVERSION SIGNALS ===
                # High-level patterns Gorse can use for recommendation confidence
                "conversion_likelihood": self._compute_conversion_likelihood(
                    filtered_interactions, product_purchases
                ),
                "purchase_intent_score": self._compute_purchase_intent_score(
                    filtered_interactions
                ),
                # === TEMPORAL SIGNALS ===
                # Recent interaction patterns are most predictive
                "interaction_recency_score": self._compute_interaction_recency_score(
                    filtered_interactions, product_purchases
                ),
                "relationship_maturity": self._compute_relationship_maturity(
                    filtered_interactions, product_purchases
                ),
                # === BEHAVIORAL QUALITY ===
                # Critical for understanding interaction quality vs spam
                "interaction_frequency_score": self._compute_interaction_frequency_score(
                    filtered_interactions
                ),
                "customer_product_loyalty": self._compute_customer_product_loyalty(
                    product_purchases, filtered_interactions
                ),
                # === COMMERCIAL VALUE ===
                # Important for business-focused recommendations
                "total_interaction_value": self._compute_total_interaction_value(
                    product_purchases
                ),
                "last_computed_at": now_utc(),
            }

            return features

        except Exception as e:
            logger.error(f"Failed to compute optimized interaction features: {str(e)}")
            return self._get_minimal_default_features(shop_id, customer_id, product_id)

    def _filter_customer_product_interactions(
        self,
        user_interactions: List[Dict[str, Any]],
        customer_id: str,
        product_id: str,
        product_id_mapping: Optional[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        """Filter interactions for specific customer-product pair"""
        filtered_interactions = []

        for interaction in user_interactions:
            # Check customer match
            if interaction.get("customer_id") != customer_id:
                continue

            # Check product match
            event_product_id = self.adapter_factory.extract_product_id(interaction)
            mapped_product_id = self._map_product_id(
                event_product_id, product_id_mapping
            )

            if mapped_product_id == product_id:
                filtered_interactions.append(interaction)

        return filtered_interactions

    def _compute_interaction_strength_score(
        self, interactions: List[Dict[str, Any]], purchases: List[Dict[str, Any]]
    ) -> float:
        """Compute weighted interaction strength (0-1) - core collaborative filtering signal"""
        if not interactions and not purchases:
            return 0.0

        # Weight different interaction types
        strength_points = 0.0

        for interaction in interactions:
            interaction_type = interaction.get("interactionType", "")

            if interaction_type == "product_viewed":
                strength_points += 1.0
            elif interaction_type == "product_added_to_cart":
                strength_points += 3.0
            elif interaction_type == "checkout_started":
                strength_points += 5.0

        # Purchases get highest weight
        strength_points += len(purchases) * 10.0

        # Normalize strength score (50+ points = max score)
        strength_score = min(strength_points / 50.0, 1.0)
        return round(strength_score, 3)

    def _compute_customer_product_affinity(
        self, interactions: List[Dict[str, Any]], purchases: List[Dict[str, Any]]
    ) -> float:
        """Compute customer-product affinity combining multiple signals"""
        if not interactions and not purchases:
            return 0.0

        # Base affinity from purchase behavior
        purchase_affinity = 0.0
        if purchases:
            # Multiple purchases indicate strong affinity
            purchase_count = len(purchases)
            purchase_affinity = min(
                purchase_count / 3.0, 1.0
            )  # 3+ purchases = max affinity

        # Interaction diversity affinity
        interaction_types = set(
            interaction.get("interactionType", "") for interaction in interactions
        )
        diversity_affinity = min(
            len(interaction_types) / 4.0, 1.0
        )  # 4+ types = max diversity

        # Frequency affinity
        frequency_affinity = min(
            len(interactions) / 10.0, 1.0
        )  # 10+ interactions = high frequency

        # Weighted combination
        if purchases:
            # Purchase behavior is most important
            affinity = (
                (purchase_affinity * 0.6)
                + (diversity_affinity * 0.2)
                + (frequency_affinity * 0.2)
            )
        else:
            # No purchases, rely on interaction patterns
            affinity = (diversity_affinity * 0.6) + (frequency_affinity * 0.4)

        return round(affinity, 3)

    def _compute_engagement_progression_score(
        self, interactions: List[Dict[str, Any]]
    ) -> float:
        """Compute progression through engagement funnel - key quality signal"""
        if not interactions:
            return 0.0

        # Sort interactions by timestamp
        sorted_interactions = sorted(interactions, key=lambda x: x.get("timestamp", ""))

        # Track progression through funnel stages
        stages_reached = set()
        progression_score = 0.0

        for interaction in sorted_interactions:
            interaction_type = interaction.get("interactionType", "")

            if interaction_type == "product_viewed":
                stages_reached.add("view")
                progression_score = max(progression_score, 0.2)
            elif interaction_type == "product_added_to_cart":
                stages_reached.add("cart")
                progression_score = max(progression_score, 0.6)
            elif interaction_type == "checkout_started":
                stages_reached.add("checkout")
                progression_score = max(progression_score, 0.8)
            elif interaction_type == "checkout_completed":
                stages_reached.add("purchase")
                progression_score = 1.0

        return round(progression_score, 3)

    def _compute_conversion_likelihood(
        self, interactions: List[Dict[str, Any]], purchases: List[Dict[str, Any]]
    ) -> float:
        """Compute likelihood of conversion based on interaction patterns"""
        if not interactions and not purchases:
            return 0.0

        # If already purchased, high likelihood
        if purchases:
            return 1.0

        # Analyze interaction patterns for conversion signals
        high_intent_interactions = 0
        total_interactions = len(interactions)

        for interaction in interactions:
            interaction_type = interaction.get("interactionType", "")

            if interaction_type in ["product_added_to_cart", "checkout_started"]:
                high_intent_interactions += 1

        if total_interactions == 0:
            return 0.0

        # High-intent interaction ratio
        intent_ratio = high_intent_interactions / total_interactions

        # Multiple views also indicate interest
        view_count = sum(
            1 for i in interactions if i.get("interactionType") == "product_viewed"
        )
        view_signal = min(view_count / 5.0, 0.5)  # 5+ views contributes 0.5 max

        conversion_likelihood = (intent_ratio * 0.7) + (view_signal * 0.3)
        return round(min(conversion_likelihood, 1.0), 3)

    def _compute_purchase_intent_score(
        self, interactions: List[Dict[str, Any]]
    ) -> float:
        """Compute purchase intent based on recent interactions"""
        if not interactions:
            return 0.0

        # Focus on recent interactions (last 30 days)
        thirty_days_ago = now_utc() - datetime.timedelta(days=30)
        recent_interactions = []

        for interaction in interactions:
            interaction_time = self._parse_date(interaction.get("timestamp"))
            if interaction_time and interaction_time >= thirty_days_ago:
                recent_interactions.append(interaction)

        if not recent_interactions:
            return 0.0

        # Calculate intent score based on interaction types
        intent_score = 0.0
        for interaction in recent_interactions:
            interaction_type = interaction.get("interactionType", "")

            if interaction_type == "product_viewed":
                intent_score += 0.1
            elif interaction_type == "product_added_to_cart":
                intent_score += 0.4
            elif interaction_type == "checkout_started":
                intent_score += 0.7

        # Normalize intent score
        normalized_intent = min(intent_score, 1.0)
        return round(normalized_intent, 3)

    def _compute_interaction_recency_score(
        self, interactions: List[Dict[str, Any]], purchases: List[Dict[str, Any]]
    ) -> float:
        """Compute recency score for customer-product relationship"""
        all_events = []

        # Add interaction timestamps
        for interaction in interactions:
            timestamp = self._parse_date(interaction.get("timestamp"))
            if timestamp:
                all_events.append(timestamp)

        # Add purchase timestamps
        for purchase in purchases:
            timestamp = self._parse_date(purchase.get("order_date"))
            if timestamp:
                all_events.append(timestamp)

        if not all_events:
            return 0.0

        # Find most recent activity
        most_recent = max(all_events)
        days_since_activity = (now_utc() - most_recent).days

        # Exponential decay: 1.0 for today, 0.5 for 30 days ago, 0.1 for 90 days ago
        recency_score = max(0.0, 1.0 - (days_since_activity / 90.0))
        return round(recency_score, 3)

    def _compute_relationship_maturity(
        self, interactions: List[Dict[str, Any]], purchases: List[Dict[str, Any]]
    ) -> str:
        """Determine relationship maturity stage - critical for recommendation strategy"""
        total_interactions = len(interactions)
        total_purchases = len(purchases)

        # Calculate interaction span
        all_timestamps = []

        for interaction in interactions:
            timestamp = self._parse_date(interaction.get("timestamp"))
            if timestamp:
                all_timestamps.append(timestamp)

        for purchase in purchases:
            timestamp = self._parse_date(purchase.get("order_date"))
            if timestamp:
                all_timestamps.append(timestamp)

        if not all_timestamps:
            return "no_relationship"

        # Calculate relationship span in days
        if len(all_timestamps) > 1:
            span_days = (max(all_timestamps) - min(all_timestamps)).days
        else:
            span_days = 0

        # Classify relationship maturity
        if total_purchases >= 3 and span_days >= 90:
            return "loyal_customer"
        elif total_purchases >= 1 and span_days >= 30:
            return "returning_customer"
        elif total_interactions >= 5 and span_days >= 7:
            return "engaged_browser"
        elif total_interactions >= 1:
            return "new_interest"
        else:
            return "no_relationship"

    def _compute_interaction_frequency_score(
        self, interactions: List[Dict[str, Any]]
    ) -> float:
        """Compute interaction frequency score to detect genuine engagement vs spam"""
        if not interactions:
            return 0.0

        # Calculate interaction frequency over time
        timestamps = []
        for interaction in interactions:
            timestamp = self._parse_date(interaction.get("timestamp"))
            if timestamp:
                timestamps.append(timestamp)

        if len(timestamps) <= 1:
            return 0.5 if len(timestamps) == 1 else 0.0

        # Calculate average time between interactions
        timestamps.sort()
        time_gaps = []
        for i in range(1, len(timestamps)):
            gap_hours = (timestamps[i] - timestamps[i - 1]).total_seconds() / 3600
            time_gaps.append(gap_hours)

        avg_gap_hours = sum(time_gaps) / len(time_gaps)

        # Optimal frequency: interactions spaced 1-48 hours apart (not too frequent, not too sparse)
        if 1 <= avg_gap_hours <= 48:
            frequency_score = 1.0
        elif avg_gap_hours < 1:
            # Too frequent - might be spam or bot behavior
            frequency_score = max(0.3, avg_gap_hours / 1.0)
        else:
            # Too sparse - lower engagement
            frequency_score = max(0.2, 48.0 / avg_gap_hours)

        return round(min(frequency_score, 1.0), 3)

    def _compute_customer_product_loyalty(
        self, purchases: List[Dict[str, Any]], interactions: List[Dict[str, Any]]
    ) -> float:
        """Compute loyalty score based on repeat purchases and consistent engagement"""
        if not purchases:
            return 0.0

        purchase_count = len(purchases)

        # Multiple purchases indicate loyalty
        purchase_loyalty = min(purchase_count / 3.0, 1.0)  # 3+ purchases = max loyalty

        # Calculate purchase consistency (regular intervals)
        if purchase_count >= 2:
            purchase_dates = []
            for purchase in purchases:
                date = self._parse_date(purchase.get("order_date"))
                if date:
                    purchase_dates.append(date)

            if len(purchase_dates) >= 2:
                purchase_dates.sort()
                gaps = []
                for i in range(1, len(purchase_dates)):
                    gap_days = (purchase_dates[i] - purchase_dates[i - 1]).days
                    gaps.append(gap_days)

                # Consistent gaps indicate loyalty (30-365 day intervals are good)
                avg_gap = sum(gaps) / len(gaps) if gaps else 0
                if 30 <= avg_gap <= 365:
                    consistency_bonus = 0.2
                else:
                    consistency_bonus = 0.0

                purchase_loyalty += consistency_bonus

        return round(min(purchase_loyalty, 1.0), 3)

    def _compute_total_interaction_value(
        self, purchases: List[Dict[str, Any]]
    ) -> float:
        """Compute total monetary value of customer-product relationship"""
        if not purchases:
            return 0.0

        total_value = 0.0
        for purchase in purchases:
            price = float(purchase.get("price", 0.0))
            quantity = int(purchase.get("quantity", 1))
            total_value += price * quantity

        return round(total_value, 2)

    # Helper methods
    def _map_product_id(
        self,
        event_product_id: Optional[str],
        product_id_mapping: Optional[Dict[str, str]],
    ) -> Optional[str]:
        """Map event product ID to standard product ID"""
        if not event_product_id:
            return None

        if product_id_mapping:
            return product_id_mapping.get(event_product_id, event_product_id)

        return event_product_id

    def _get_product_purchases(
        self,
        orders: List[Dict[str, Any]],
        customer_id: str,
        product_id: str,
        product_id_mapping: Optional[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        """Get all purchases of a product by a customer"""
        purchases = []

        for order in orders:
            if order.get("customer_id") != customer_id:
                continue

            line_items = order.get("line_items", [])
            for item in line_items:
                item_product_id = self._extract_product_id_from_line_item(item)
                mapped_product_id = self._map_product_id(
                    item_product_id, product_id_mapping
                )

                if mapped_product_id == product_id:
                    purchases.append(
                        {
                            "order_id": order.get("order_id"),
                            "order_date": order.get("order_date"),
                            "quantity": item.get("quantity", 1),
                            "price": item.get("price", 0.0),
                        }
                    )
                    break  # Only count once per order

        return purchases

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
        self, shop_id: str, customer_id: str, product_id: str
    ) -> Dict[str, Any]:
        """Return minimal default features when computation fails"""
        return {
            "shop_id": shop_id,
            "customer_id": customer_id,
            "product_id": product_id,
            "interaction_strength_score": 0.0,
            "customer_product_affinity": 0.0,
            "engagement_progression_score": 0.0,
            "conversion_likelihood": 0.0,
            "purchase_intent_score": 0.0,
            "interaction_recency_score": 0.0,
            "relationship_maturity": "no_relationship",
            "interaction_frequency_score": 0.0,
            "customer_product_loyalty": 0.0,
            "total_interaction_value": 0.0,
            "last_computed_at": now_utc(),
        }
