"""
Optimized Product-Pair Feature Generator for State-of-the-Art Gorse Integration
Focuses on product co-occurrence signals that actually improve recommendation quality
"""

import datetime
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict
from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.domains.ml.adapters.adapter_factory import InteractionEventAdapterFactory
from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class ProductPairFeatureGenerator(BaseFeatureGenerator):
    """State-of-the-art product-pair feature generator optimized for Gorse collaborative filtering"""

    def __init__(self):
        super().__init__()
        self.adapter_factory = InteractionEventAdapterFactory()

    async def generate_features(
        self,
        shop_id: str,
        product_id1: str,
        product_id2: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate optimized product-pair features for Gorse

        Args:
            shop_id: The shop ID
            product_id1: The first product ID
            product_id2: The second product ID
            context: Additional context data (orders, behavioral_events)

        Returns:
            Dictionary with minimal, high-signal product-pair features for Gorse
        """
        try:
            logger.debug(
                f"Computing optimized product-pair features for: ({product_id1}, {product_id2})"
            )

            # Get data from context
            orders = context.get("orders", [])
            user_interactions = context.get("user_interactions", [])
            variant_to_product_map = context.get("variant_to_product_map", {})

            # Core Gorse-optimized product-pair features
            features = {
                "shop_id": shop_id,
                "product_id1": product_id1,
                "product_id2": product_id2,
                # === CORE CO-OCCURRENCE SIGNALS ===
                # These are the most predictive for product recommendations
                "co_purchase_strength": self._compute_co_purchase_strength(
                    orders, product_id1, product_id2, variant_to_product_map
                ),
                "co_engagement_score": self._compute_co_engagement_score(
                    user_interactions, product_id1, product_id2
                ),
                "pair_affinity_score": self._compute_pair_affinity_score(
                    orders,
                    user_interactions,
                    product_id1,
                    product_id2,
                    variant_to_product_map,
                ),
                # === COMMERCIAL VIABILITY ===
                # High-level patterns Gorse can use for business value optimization
                "total_pair_revenue": self._compute_total_pair_revenue(
                    orders, product_id1, product_id2, variant_to_product_map
                ),
                "pair_frequency_score": self._compute_pair_frequency_score(
                    orders, product_id1, product_id2, variant_to_product_map
                ),
                # === TEMPORAL SIGNALS ===
                # Recent co-occurrence is most predictive for recommendations
                "days_since_last_co_occurrence": self._compute_days_since_last_co_occurrence(
                    orders,
                    user_interactions,
                    product_id1,
                    product_id2,
                    variant_to_product_map,
                ),
                "pair_recency_score": self._compute_pair_recency_score(
                    orders,
                    user_interactions,
                    product_id1,
                    product_id2,
                    variant_to_product_map,
                ),
                # === RECOMMENDATION CONFIDENCE ===
                # Critical for understanding pair reliability
                "pair_confidence_level": self._compute_pair_confidence_level(
                    orders, product_id1, product_id2, variant_to_product_map
                ),
                "cross_sell_potential": self._compute_cross_sell_potential(
                    orders,
                    user_interactions,
                    product_id1,
                    product_id2,
                    variant_to_product_map,
                ),
                "last_computed_at": now_utc(),
            }

            return features

        except Exception as e:
            logger.error(f"Failed to compute optimized product-pair features: {str(e)}")
            return self._get_minimal_default_features(shop_id, product_id1, product_id2)

    def _compute_co_purchase_strength(
        self,
        orders: List[Dict[str, Any]],
        product_id1: str,
        product_id2: str,
        variant_to_product_map: Dict[str, str],
    ) -> float:
        """Compute normalized co-purchase strength (0-1) - core collaborative filtering signal"""
        co_purchase_count = 0
        product1_purchase_count = 0
        product2_purchase_count = 0

        target_ids = {product_id1, product_id2}

        for order in orders:
            line_items = order.get("line_items", [])
            product_ids_in_order = {
                self._extract_product_id_from_line_item(item, variant_to_product_map)
                for item in line_items
            }
            product_ids_in_order.discard("")  # Remove empty strings

            # Count individual product purchases
            if product_id1 in product_ids_in_order:
                product1_purchase_count += 1
            if product_id2 in product_ids_in_order:
                product2_purchase_count += 1

            # Count co-purchases
            if target_ids.issubset(product_ids_in_order):
                co_purchase_count += 1

        if product1_purchase_count == 0 or product2_purchase_count == 0:
            return 0.0

        # Normalized co-purchase strength (Jaccard similarity approach)
        min_individual_purchases = min(product1_purchase_count, product2_purchase_count)
        strength = co_purchase_count / min_individual_purchases

        return round(min(1.0, strength), 3)

    def _compute_co_engagement_score(
        self,
        user_interactions: List[Dict[str, Any]],
        product_id1: str,
        product_id2: str,
    ) -> float:
        """Compute co-engagement score from user interactions - behavioral affinity signal"""
        sessions = self._group_interactions_by_session(user_interactions)

        co_engagement_sessions = 0
        total_sessions_with_either = 0

        target_ids = {product_id1, product_id2}

        for session_interactions in sessions:
            session_product_ids = {
                self.adapter_factory.extract_product_id(interaction)
                for interaction in session_interactions
            }
            session_product_ids.discard(None)  # Remove None values
            session_product_ids.discard("")  # Remove empty strings

            # Check if session has either product
            if target_ids & session_product_ids:  # Intersection
                total_sessions_with_either += 1

                # Check if session has both products
                if target_ids.issubset(session_product_ids):
                    co_engagement_sessions += 1

        if total_sessions_with_either == 0:
            return 0.0

        engagement_score = co_engagement_sessions / total_sessions_with_either
        return round(engagement_score, 3)

    def _compute_pair_affinity_score(
        self,
        orders: List[Dict[str, Any]],
        user_interactions: List[Dict[str, Any]],
        product_id1: str,
        product_id2: str,
        variant_to_product_map: Dict[str, str],
    ) -> float:
        """Compute overall pair affinity combining purchase and engagement signals"""
        co_purchase_strength = self._compute_co_purchase_strength(
            orders, product_id1, product_id2, variant_to_product_map
        )
        co_engagement_score = self._compute_co_engagement_score(
            user_interactions, product_id1, product_id2
        )

        # Weighted combination: purchases are more indicative than views
        affinity_score = (co_purchase_strength * 0.7) + (co_engagement_score * 0.3)
        return round(affinity_score, 3)

    def _compute_total_pair_revenue(
        self,
        orders: List[Dict[str, Any]],
        product_id1: str,
        product_id2: str,
        variant_to_product_map: Dict[str, str],
    ) -> float:
        """Compute total revenue from orders containing both products"""
        total_revenue = 0.0
        target_ids = {product_id1, product_id2}

        for order in orders:
            line_items = order.get("line_items", [])
            product_ids_in_order = {
                self._extract_product_id_from_line_item(item, variant_to_product_map)
                for item in line_items
            }
            product_ids_in_order.discard("")

            # If order contains both products, add its total value
            if target_ids.issubset(product_ids_in_order):
                order_total = float(order.get("totalAmount", 0.0))
                total_revenue += order_total

        return round(total_revenue, 2)

    def _compute_pair_frequency_score(
        self,
        orders: List[Dict[str, Any]],
        product_id1: str,
        product_id2: str,
        variant_to_product_map: Dict[str, str],
    ) -> float:
        """Compute frequency score normalized by total orders (0-1)"""
        co_purchase_count = 0
        total_orders = len(orders)
        target_ids = {product_id1, product_id2}

        if total_orders == 0:
            return 0.0

        for order in orders:
            line_items = order.get("line_items", [])
            product_ids_in_order = {
                self._extract_product_id_from_line_item(item, variant_to_product_map)
                for item in line_items
            }
            product_ids_in_order.discard("")

            if target_ids.issubset(product_ids_in_order):
                co_purchase_count += 1

        frequency_score = co_purchase_count / total_orders
        return round(min(1.0, frequency_score * 10), 3)  # Scale up small frequencies

    def _compute_days_since_last_co_occurrence(
        self,
        orders: List[Dict[str, Any]],
        user_interactions: List[Dict[str, Any]],
        product_id1: str,
        product_id2: str,
        variant_to_product_map: Dict[str, str],
    ) -> Optional[int]:
        """Compute days since last co-occurrence (purchase or engagement)"""
        last_co_occurrence = None
        target_ids = {product_id1, product_id2}

        # Check orders for co-purchases
        for order in orders:
            line_items = order.get("line_items", [])
            product_ids_in_order = {
                self._extract_product_id_from_line_item(item, variant_to_product_map)
                for item in line_items
            }
            product_ids_in_order.discard("")

            if target_ids.issubset(product_ids_in_order):
                order_date = self._parse_date(order.get("order_date"))
                if order_date:
                    if not last_co_occurrence or order_date > last_co_occurrence:
                        last_co_occurrence = order_date

        # Check interactions for co-engagement
        sessions = self._group_interactions_by_session(user_interactions)
        for session_interactions in sessions:
            session_product_ids = {
                self.adapter_factory.extract_product_id(interaction)
                for interaction in session_interactions
            }
            session_product_ids.discard(None)
            session_product_ids.discard("")

            if target_ids.issubset(session_product_ids):
                # Find latest timestamp in this session
                session_times = [
                    self._parse_date(interaction.get("timestamp"))
                    for interaction in session_interactions
                ]
                session_times = [t for t in session_times if t is not None]

                if session_times:
                    session_latest = max(session_times)
                    if not last_co_occurrence or session_latest > last_co_occurrence:
                        last_co_occurrence = session_latest

        if not last_co_occurrence:
            return None

        return (now_utc() - last_co_occurrence).days

    def _compute_pair_recency_score(
        self,
        orders: List[Dict[str, Any]],
        user_interactions: List[Dict[str, Any]],
        product_id1: str,
        product_id2: str,
        variant_to_product_map: Dict[str, str],
    ) -> float:
        """Compute recency score for product pair (0-1)"""
        days_since_last = self._compute_days_since_last_co_occurrence(
            orders, user_interactions, product_id1, product_id2, variant_to_product_map
        )

        if days_since_last is None:
            return 0.0

        # Exponential decay: 1.0 for today, 0.5 for 14 days ago, 0.1 for 60 days ago
        recency_score = max(0.0, 1.0 - (days_since_last / 60.0))
        return round(recency_score, 3)

    def _compute_pair_confidence_level(
        self,
        orders: List[Dict[str, Any]],
        product_id1: str,
        product_id2: str,
        variant_to_product_map: Dict[str, str],
    ) -> str:
        """Determine confidence level for product pair recommendations"""
        co_purchase_strength = self._compute_co_purchase_strength(
            orders, product_id1, product_id2, variant_to_product_map
        )

        # Count total co-purchases for sample size
        co_purchase_count = 0
        target_ids = {product_id1, product_id2}

        for order in orders:
            line_items = order.get("line_items", [])
            product_ids_in_order = {
                self._extract_product_id_from_line_item(item, variant_to_product_map)
                for item in line_items
            }
            product_ids_in_order.discard("")

            if target_ids.issubset(product_ids_in_order):
                co_purchase_count += 1

        # Classify confidence based on strength and sample size
        if co_purchase_strength >= 0.5 and co_purchase_count >= 10:
            return "high"
        elif co_purchase_strength >= 0.3 and co_purchase_count >= 5:
            return "medium"
        elif co_purchase_strength >= 0.1 and co_purchase_count >= 2:
            return "low"
        else:
            return "very_low"

    def _compute_cross_sell_potential(
        self,
        orders: List[Dict[str, Any]],
        user_interactions: List[Dict[str, Any]],
        product_id1: str,
        product_id2: str,
        variant_to_product_map: Dict[str, str],
    ) -> float:
        """Compute cross-sell potential score (0-1) for business value"""
        pair_affinity = self._compute_pair_affinity_score(
            orders, user_interactions, product_id1, product_id2, variant_to_product_map
        )
        pair_frequency = self._compute_pair_frequency_score(
            orders, product_id1, product_id2, variant_to_product_map
        )
        pair_recency = self._compute_pair_recency_score(
            orders, user_interactions, product_id1, product_id2, variant_to_product_map
        )

        # Weighted combination for cross-sell potential
        cross_sell_score = (
            (pair_affinity * 0.5) + (pair_frequency * 0.3) + (pair_recency * 0.2)
        )
        return round(cross_sell_score, 3)

    # Helper methods
    def _group_interactions_by_session(
        self, user_interactions: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Group user interactions by session with 30-minute timeout"""
        if not user_interactions:
            return []

        # Group by session_id if available, otherwise use time-based grouping
        sessions_dict = defaultdict(list)

        for interaction in user_interactions:
            session_id = interaction.get("session_id")
            if session_id:
                sessions_dict[session_id].append(interaction)

        # If we have session IDs, return those groups
        if sessions_dict:
            return list(sessions_dict.values())

        # Fallback to time-based session grouping
        sorted_interactions = sorted(
            user_interactions, key=lambda x: x.get("timestamp", "")
        )

        if not sorted_interactions:
            return []

        sessions = []
        current_session = [sorted_interactions[0]]

        for i in range(1, len(sorted_interactions)):
            current_interaction = sorted_interactions[i]
            previous_interaction = sorted_interactions[i - 1]

            current_time = self._parse_date(current_interaction.get("timestamp"))
            previous_time = self._parse_date(previous_interaction.get("timestamp"))

            if current_time and previous_time:
                time_gap_minutes = (current_time - previous_time).total_seconds() / 60

                # New session if > 30 minutes gap or different customer
                if time_gap_minutes > 30 or current_interaction.get(
                    "customer_id"
                ) != previous_interaction.get("customer_id"):
                    sessions.append(current_session)
                    current_session = [current_interaction]
                else:
                    current_session.append(current_interaction)
            else:
                current_session.append(current_interaction)

        sessions.append(current_session)
        return sessions

    def _extract_product_id_from_line_item(
        self, line_item: Dict[str, Any], variant_to_product_map: Dict[str, str]
    ) -> str:
        """Extract product ID from order line item"""
        if "product_id" in line_item:
            return str(line_item["product_id"])

        if "variant" in line_item and isinstance(line_item["variant"], dict):
            variant = line_item["variant"]
            if "product" in variant and isinstance(variant["product"], dict):
                return variant["product"].get("id", "")
            elif "id" in variant and variant_to_product_map:
                variant_id = variant["id"]
                return variant_to_product_map.get(variant_id, "")

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
        self, shop_id: str, product_id1: str, product_id2: str
    ) -> Dict[str, Any]:
        """Return minimal default features when computation fails"""
        return {
            "shop_id": shop_id,
            "product_id1": product_id1,
            "product_id2": product_id2,
            "co_purchase_strength": 0.0,
            "co_engagement_score": 0.0,
            "pair_affinity_score": 0.0,
            "total_pair_revenue": 0.0,
            "pair_frequency_score": 0.0,
            "days_since_last_co_occurrence": None,
            "pair_recency_score": 0.0,
            "pair_confidence_level": "very_low",
            "cross_sell_potential": 0.0,
            "last_computed_at": now_utc(),
        }
