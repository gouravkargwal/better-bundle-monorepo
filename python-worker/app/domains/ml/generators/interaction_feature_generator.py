"""
Customer-Product Interaction Feature Generator for ML feature engineering
"""

import datetime
from typing import Dict, Any, List, Optional
import statistics
from datetime import timedelta

from app.core.logging import get_logger
from app.shared.helpers import now_utc

from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class InteractionFeatureGenerator(BaseFeatureGenerator):
    """Feature generator for customer-product interactions"""

    async def generate_features(
        self,
        customer: Dict[str, Any],
        product: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate interaction features between a customer and product

        Args:
            customer: The customer
            product: The product
            context: Additional context data (orders, events, etc.)

        Returns:
            Dictionary of generated interaction features
        """
        try:
            logger.debug(
                f"Computing interaction features for customer: {customer.get('id', 'unknown')}, product: {product.get('id', 'unknown')}"
            )

            features = {}
            orders = context.get("orders", [])
            events = context.get("events", [])

            # Customer-product affinity features
            features.update(
                self._compute_affinity_features(customer, product, events, orders)
            )

            # Purchase history features
            features.update(
                self._compute_purchase_history_features(customer, product, orders)
            )

            # Behavioral interaction features
            features.update(
                self._compute_behavioral_interaction_features(customer, product, events)
            )

            # Temporal interaction features
            features.update(
                self._compute_temporal_interaction_features(
                    customer, product, events, orders
                )
            )

            # Intent and engagement features
            features.update(self._compute_intent_features(customer, product, events))

            # Validate and clean features
            features = self.validate_features(features)

            logger.debug(
                f"Computed {len(features)} interaction features for customer: {customer.get('id', 'unknown')}, product: {product.get('id', 'unknown')}"
            )
            return features

        except Exception as e:
            logger.error(
                f"Failed to compute interaction features for customer: {customer.get('id', 'unknown')}, product: {product.get('id', 'unknown')}: {str(e)}"
            )
            return {}

    def _compute_affinity_features(
        self,
        customer: Dict[str, Any],
        product: Dict[str, Any],
        events: List[Dict[str, Any]],
        orders: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compute customer-product affinity features"""
        # Get customer's interaction with this specific product
        product_events = [
            e
            for e in events
            if e.get("customerId") == customer.get("id")
            and e.get("productId") == product.get("id")
        ]
        product_orders = []
        for order in orders:
            if order.get("customerId") == customer.get("id"):
                for line_item in order.get("lineItems", []):
                    if line_item.get("productId") == product.get("id"):
                        product_orders.append(order)
                        break

        # Calculate affinity scores
        view_count = sum(1 for e in product_events if e.get("isProductViewed", False))
        cart_count = sum(
            1 for e in product_events if e.get("isProductAddedToCart", False)
        )
        purchase_count = len(product_orders)

        # Total interactions
        total_interactions = len(product_events)

        # Affinity score (0-1)
        if total_interactions == 0:
            affinity_score = 0.0
        else:
            # Weight different interactions
            weighted_score = view_count * 0.1 + cart_count * 0.3 + purchase_count * 0.6
            affinity_score = min(weighted_score / max(total_interactions, 1), 1.0)

        # Category affinity
        category_affinity = self._calculate_category_affinity(
            customer, product, events, orders
        )

        # Price affinity
        price_affinity = self._calculate_price_affinity(
            customer, product, events, orders
        )

        # Brand affinity
        brand_affinity = self._calculate_brand_affinity(
            customer, product, events, orders
        )

        return {
            "customer_product_affinity_score": affinity_score,
            "view_count": view_count,
            "cart_count": cart_count,
            "purchase_count": purchase_count,
            "total_interactions": total_interactions,
            "category_affinity": category_affinity,
            "price_affinity": price_affinity,
            "brand_affinity": brand_affinity,
        }

    def _compute_purchase_history_features(
        self,
        customer: Dict[str, Any],
        product: Dict[str, Any],
        orders: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compute purchase history features for this customer-product pair"""
        # Get customer's orders containing this product
        product_orders = []
        total_quantity = 0
        total_spent = 0.0

        for order in orders:
            if order.get("customerId") == customer.get("id"):
                for line_item in order.get("lineItems", []):
                    if line_item.get("productId") == product.get("id"):
                        product_orders.append(order)
                        total_quantity += line_item.get("quantity", 0)
                        total_spent += line_item.get("price", 0.0) * line_item.get(
                            "quantity", 0
                        )

        if not product_orders:
            return {
                "has_purchased": 0,
                "purchase_frequency": 0.0,
                "total_quantity_purchased": 0,
                "total_spent_on_product": 0.0,
                "average_quantity_per_purchase": 0.0,
                "days_since_last_purchase": 0,
                "purchase_recency_score": 0.0,
                "repeat_purchase_probability": 0.0,
            }

        # Calculate purchase patterns
        order_dates = [order.get("orderDate") for order in product_orders]
        order_dates.sort()

        # Purchase frequency (purchases per month)
        if len(order_dates) > 1:
            time_span = (order_dates[-1] - order_dates[0]).days
            purchase_frequency = len(product_orders) / max(
                time_span / 30, 1
            )  # per month
        else:
            purchase_frequency = 0.0

        # Average quantity per purchase
        avg_quantity = total_quantity / len(product_orders)

        # Days since last purchase
        last_order_date = order_dates[-1]
        if isinstance(last_order_date, str):
            last_order_date = datetime.fromisoformat(
                last_order_date.replace("Z", "+00:00")
            )
        days_since_last = (now_utc() - last_order_date).days

        # Purchase recency score (higher = more recent)
        recency_score = max(0, 1 - (days_since_last / 365))  # Decay over a year

        # Repeat purchase probability (based on frequency and recency)
        repeat_probability = min(purchase_frequency * recency_score, 1.0)

        return {
            "has_purchased": 1,
            "purchase_frequency": purchase_frequency,
            "total_quantity_purchased": total_quantity,
            "total_spent_on_product": total_spent,
            "average_quantity_per_purchase": avg_quantity,
            "days_since_last_purchase": days_since_last,
            "purchase_recency_score": recency_score,
            "repeat_purchase_probability": repeat_probability,
        }

    def _compute_behavioral_interaction_features(
        self,
        customer: Dict[str, Any],
        product: Dict[str, Any],
        events: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compute behavioral interaction features"""
        # Get customer's events for this product
        product_events = [
            e
            for e in events
            if e.get("customerId") == customer.get("id")
            and e.get("productId") == product.get("id")
        ]

        if not product_events:
            return {
                "interaction_depth": 0.0,
                "engagement_intensity": 0.0,
                "browsing_time_seconds": 0.0,
                "session_participation": 0.0,
                "search_to_view_conversion": 0.0,
                "view_to_cart_conversion": 0.0,
                "cart_to_purchase_conversion": 0.0,
                "abandonment_points": [],
                "recovery_actions": 0,
            }

        # Calculate interaction depth (how many different types of interactions)
        interaction_types = set(e.event_type for e in product_events)
        interaction_depth = (
            len(interaction_types) / 7.0
        )  # Normalize by max possible interactions

        # Engagement intensity (events per session)
        sessions = self._group_events_by_session(product_events)
        if sessions:
            avg_events_per_session = sum(len(session) for session in sessions) / len(
                sessions
            )
            engagement_intensity = min(avg_events_per_session / 10.0, 1.0)  # Normalize
        else:
            engagement_intensity = 0.0

        # Estimated browsing time (assume 30 seconds per view)
        view_events = [e for e in product_events if e.get("isProductViewed", False)]
        browsing_time = len(view_events) * 30.0

        # Session participation (how many sessions included this product)
        total_customer_sessions = len(
            self._group_events_by_session(
                [e for e in events if e.get("customerId") == customer.get("id")]
            )
        )
        session_participation = len(sessions) / max(total_customer_sessions, 1)

        # Conversion rates
        search_events = sum(
            1 for e in product_events if e.get("isSearchSubmitted", False)
        )
        view_events_count = sum(
            1 for e in product_events if e.get("isProductViewed", False)
        )
        cart_events = sum(
            1 for e in product_events if e.get("isProductAddedToCart", False)
        )
        purchase_events = sum(
            1 for e in product_events if e.get("isCheckoutCompleted", False)
        )

        search_to_view = (
            view_events_count / max(search_events, 1) if search_events > 0 else 0.0
        )
        view_to_cart = (
            cart_events / max(view_events_count, 1) if view_events_count > 0 else 0.0
        )
        cart_to_purchase = (
            purchase_events / max(cart_events, 1) if cart_events > 0 else 0.0
        )

        # Abandonment analysis
        abandonment_points = self._analyze_abandonment_points(product_events)
        recovery_actions = self._count_recovery_actions(product_events)

        return {
            "interaction_depth": interaction_depth,
            "engagement_intensity": engagement_intensity,
            "browsing_time_seconds": browsing_time,
            "session_participation": session_participation,
            "search_to_view_conversion": search_to_view,
            "view_to_cart_conversion": view_to_cart,
            "cart_to_purchase_conversion": cart_to_purchase,
            "abandonment_points": abandonment_points,
            "recovery_actions": recovery_actions,
        }

    def _compute_temporal_interaction_features(
        self,
        customer: Dict[str, Any],
        product: Dict[str, Any],
        events: List[Dict[str, Any]],
        orders: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compute temporal interaction features"""
        # Get customer's events and orders for this product
        product_events = [
            e
            for e in events
            if e.get("customerId") == customer.get("id")
            and e.get("productId") == product.get("id")
        ]
        product_orders = []
        for order in orders:
            if order.get("customerId") == customer.get("id"):
                for line_item in order.get("lineItems", []):
                    if line_item.get("productId") == product.get("id"):
                        product_orders.append(order)
                        break

        if not product_events and not product_orders:
            return {
                "first_interaction_days_ago": 0,
                "last_interaction_days_ago": 0,
                "interaction_span_days": 0,
                "interaction_frequency": 0.0,
                "seasonal_preference": 0.0,
                "time_of_day_preference": 0,
                "day_of_week_preference": 0,
                "interaction_consistency": 0.0,
            }

        # Combine events and orders for temporal analysis
        all_interactions = []
        for event in product_events:
            all_interactions.append(("event", event.occurred_at))
        for order in product_orders:
            all_interactions.append(("order", order.get("orderDate")))

        all_interactions.sort(key=lambda x: x[1])

        if not all_interactions:
            return {}

        first_interaction = all_interactions[0][1]
        last_interaction = all_interactions[-1][1]

        # Parse dates if they are strings
        if isinstance(first_interaction, str):
            first_interaction = datetime.fromisoformat(
                first_interaction.replace("Z", "+00:00")
            )
        if isinstance(last_interaction, str):
            last_interaction = datetime.fromisoformat(
                last_interaction.replace("Z", "+00:00")
            )

        first_interaction_days = (now_utc() - first_interaction).days
        last_interaction_days = (now_utc() - last_interaction).days
        interaction_span = (last_interaction - first_interaction).days

        # Interaction frequency (interactions per month)
        if interaction_span > 0:
            interaction_frequency = len(all_interactions) / (interaction_span / 30.0)
        else:
            interaction_frequency = 0.0

        # Temporal preferences
        hours = [interaction[1].hour for interaction in all_interactions]
        days_of_week = [interaction[1].weekday() for interaction in all_interactions]
        months = [interaction[1].month for interaction in all_interactions]

        time_of_day_pref = max(set(hours), key=hours.count) if hours else 12
        day_of_week_pref = (
            max(set(days_of_week), key=days_of_week.count) if days_of_week else 0
        )

        # Seasonal preference
        seasonal_pref = self._calculate_seasonal_preference(months)

        # Interaction consistency (how regular are the interactions)
        if len(all_interactions) > 1:
            time_gaps = []
            for i in range(1, len(all_interactions)):
                gap = (all_interactions[i][1] - all_interactions[i - 1][1]).days
                time_gaps.append(gap)

            if time_gaps:
                mean_gap = statistics.mean(time_gaps)
                std_gap = statistics.stdev(time_gaps) if len(time_gaps) > 1 else 0
                consistency = 1 - (std_gap / max(mean_gap, 1)) if mean_gap > 0 else 0
            else:
                consistency = 0.0
        else:
            consistency = 0.0

        return {
            "first_interaction_days_ago": first_interaction_days,
            "last_interaction_days_ago": last_interaction_days,
            "interaction_span_days": interaction_span,
            "interaction_frequency": interaction_frequency,
            "seasonal_preference": seasonal_pref,
            "time_of_day_preference": time_of_day_pref,
            "day_of_week_preference": day_of_week_pref,
            "interaction_consistency": consistency,
        }

    def _compute_intent_features(
        self,
        customer: Dict[str, Any],
        product: Dict[str, Any],
        events: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Compute intent and engagement features"""
        # Get customer's events for this product
        product_events = [
            e
            for e in events
            if e.get("customerId") == customer.get("id")
            and e.get("productId") == product.get("id")
        ]

        if not product_events:
            return {
                "purchase_intent_score": 0.0,
                "urgency_score": 0.0,
                "research_depth": 0.0,
                "price_sensitivity": 0.0,
                "social_proof_sensitivity": 0.0,
                "impulse_buy_tendency": 0.0,
                "loyalty_score": 0.0,
            }

        # Purchase intent score (based on progression through funnel)
        view_count = sum(1 for e in product_events if e.get("isProductViewed", False))
        cart_count = sum(
            1 for e in product_events if e.get("isProductAddedToCart", False)
        )
        checkout_count = sum(
            1 for e in product_events if e.get("isCheckoutStarted", False)
        )

        if view_count > 0:
            intent_score = (cart_count * 0.4 + checkout_count * 0.6) / view_count
        else:
            intent_score = 0.0

        # Urgency score (based on recent activity and checkout behavior)
        recent_events = []
        for e in product_events:
            occurred_at = e.get("occurredAt")
            if isinstance(occurred_at, str):
                occurred_at = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
            if occurred_at and (now_utc() - occurred_at).days <= 7:
                recent_events.append(e)
        recent_checkouts = sum(
            1 for e in recent_events if e.get("isCheckoutStarted", False)
        )
        urgency_score = min(recent_checkouts / max(len(recent_events), 1), 1.0)

        # Research depth (how much they research before buying)
        search_count = sum(
            1 for e in product_events if e.get("isSearchSubmitted", False)
        )
        research_depth = search_count / max(view_count, 1)

        # Price sensitivity (based on price comparison behavior)
        price_sensitivity = self._calculate_price_sensitivity_for_product(
            customer, product, events
        )

        # Social proof sensitivity (based on review viewing, etc.)
        social_proof_sensitivity = self._calculate_social_proof_sensitivity(
            product_events
        )

        # Impulse buy tendency (quick purchases without much research)
        impulse_tendency = self._calculate_impulse_tendency(product_events)

        # Loyalty score (consistency in interactions)
        loyalty_score = self._calculate_loyalty_score(customer, product, events)

        return {
            "purchase_intent_score": intent_score,
            "urgency_score": urgency_score,
            "research_depth": research_depth,
            "price_sensitivity": price_sensitivity,
            "social_proof_sensitivity": social_proof_sensitivity,
            "impulse_buy_tendency": impulse_tendency,
            "loyalty_score": loyalty_score,
        }

    def _calculate_category_affinity(
        self,
        customer: Dict[str, Any],
        product: Dict[str, Any],
        events: List[Dict[str, Any]],
        orders: List[Dict[str, Any]],
    ) -> float:
        """Calculate customer's affinity for this product's category"""
        product_category = product.get("productType", "") or ""
        if not product_category:
            return 0.0

        # Count customer's interactions with this category
        category_interactions = 0
        total_interactions = 0

        for event in events:
            if event.get("customerId") == customer.get("id", ""):
                total_interactions += 1
                if event.get("eventData"):
                    event_product = (
                        event.get("eventData", {})
                        .get("productVariant", {})
                        .get("product", {})
                    )
                    if event_product.get("type") == product_category:
                        category_interactions += 1

        return category_interactions / max(total_interactions, 1)

    def _calculate_price_affinity(
        self,
        customer: Dict[str, Any],
        product: Dict[str, Any],
        events: List[Dict[str, Any]],
        orders: List[Dict[str, Any]],
    ) -> float:
        """Calculate customer's affinity for this product's price point"""
        if not product.get("variants", []):
            return 0.0

        product_price = product.get("variants", [{}])[0].get("price", 0.0)
        if product_price == 0:
            return 0.0

        # Get customer's purchase history prices
        customer_prices = []
        for order in orders:
            if order.get("customerId") == customer.get("id"):
                for line_item in order.get("lineItems", []):
                    customer_prices.append(line_item.get("price", 0.0))

        if not customer_prices:
            return 0.0

        # Calculate how close this price is to customer's typical price range
        avg_customer_price = statistics.mean(customer_prices)
        price_variance = (
            statistics.stdev(customer_prices)
            if len(customer_prices) > 1
            else avg_customer_price * 0.2
        )

        # Calculate affinity (higher = closer to customer's price preference)
        price_diff = abs(product_price - avg_customer_price)
        affinity = max(0, 1 - (price_diff / max(price_variance, 1)))

        return affinity

    def _calculate_brand_affinity(
        self,
        customer: Dict[str, Any],
        product: Dict[str, Any],
        events: List[Dict[str, Any]],
        orders: List[Dict[str, Any]],
    ) -> float:
        """Calculate customer's affinity for this product's brand/vendor"""
        product_vendor = product.get("vendor", "") or ""
        if not product_vendor:
            return 0.0

        # Count customer's interactions with this vendor
        vendor_interactions = 0
        total_interactions = 0

        for event in events:
            if event.get("customerId") == customer.get("id", ""):
                total_interactions += 1
                if event.get("eventData"):
                    event_product = (
                        event.get("eventData", {})
                        .get("productVariant", {})
                        .get("product", {})
                    )
                    if event_product.get("vendor") == product_vendor:
                        vendor_interactions += 1

        return vendor_interactions / max(total_interactions, 1)

    def _group_events_by_session(
        self, events: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Group events by session using time proximity"""
        if not events:
            return []

        sorted_events = sorted(events, key=lambda e: e.get("occurredAt", ""))
        sessions = []
        current_session = [sorted_events[0]]

        for i in range(1, len(sorted_events)):
            current_event = sorted_events[i]
            previous_event = sorted_events[i - 1]

            # If more than 30 minutes gap, start new session
            time_gap = (
                current_event.occurred_at - previous_event.occurred_at
            ).total_seconds() / 60

            if time_gap > 30:
                sessions.append(current_session)
                current_session = [current_event]
            else:
                current_session.append(current_event)

        sessions.append(current_session)
        return sessions

    def _analyze_abandonment_points(
        self, product_events: List[Dict[str, Any]]
    ) -> List[str]:
        """Analyze where customer abandons the product journey"""
        abandonment_points = []

        # Check for common abandonment patterns
        has_viewed = any(e.get("isProductViewed", False) for e in product_events)
        has_carted = any(e.get("isProductAddedToCart", False) for e in product_events)
        has_checkout = any(e.get("isCheckoutStarted", False) for e in product_events)
        has_purchased = any(e.get("isCheckoutCompleted", False) for e in product_events)

        if has_viewed and not has_carted:
            abandonment_points.append("after_view")
        if has_carted and not has_checkout:
            abandonment_points.append("after_cart")
        if has_checkout and not has_purchased:
            abandonment_points.append("after_checkout")

        return abandonment_points

    def _count_recovery_actions(self, product_events: List[Dict[str, Any]]) -> int:
        """Count recovery actions (return visits after abandonment)"""
        # This is a simplified version - in practice, you'd track more sophisticated recovery patterns
        sessions = self._group_events_by_session(product_events)
        return max(0, len(sessions) - 1)  # Multiple sessions indicate return visits

    def _calculate_seasonal_preference(self, months: List[int]) -> float:
        """Calculate seasonal preference based on interaction months"""
        if not months:
            return 0.0

        # Count interactions by season
        seasonal_counts = {"spring": 0, "summer": 0, "fall": 0, "winter": 0}

        for month in months:
            if month in [3, 4, 5]:
                seasonal_counts["spring"] += 1
            elif month in [6, 7, 8]:
                seasonal_counts["summer"] += 1
            elif month in [9, 10, 11]:
                seasonal_counts["fall"] += 1
            else:
                seasonal_counts["winter"] += 1

        # Calculate preference strength (how concentrated in one season)
        total_interactions = sum(seasonal_counts.values())
        if total_interactions == 0:
            return 0.0

        max_season_count = max(seasonal_counts.values())
        preference_strength = max_season_count / total_interactions

        return preference_strength

    def _calculate_price_sensitivity_for_product(
        self,
        customer: Dict[str, Any],
        product: Dict[str, Any],
        events: List[Dict[str, Any]],
    ) -> float:
        """Calculate price sensitivity for this specific product"""
        # Get all product prices this customer has viewed
        prices_viewed = []
        for event in events:
            if event.get("customerId") == customer.get("id", "") and event.get(
                "productId"
            ) == product.get("id", ""):
                price = event.get("productPrice")
                if price is not None:
                    prices_viewed.append(price)

        if len(prices_viewed) < 2:
            return 0.0

        # Price sensitivity = coefficient of variation
        mean_price = statistics.mean(prices_viewed)
        if mean_price == 0:
            return 0.0

        std_price = statistics.stdev(prices_viewed)
        return std_price / mean_price

    def _calculate_social_proof_sensitivity(
        self, product_events: List[Dict[str, Any]]
    ) -> float:
        """Calculate social proof sensitivity (placeholder)"""
        # In practice, you'd track review viewing, social sharing, etc.
        # For now, return a placeholder based on interaction depth
        return min(len(product_events) / 10.0, 1.0)

    def _calculate_impulse_tendency(
        self, product_events: List[Dict[str, Any]]
    ) -> float:
        """Calculate impulse buy tendency"""
        if not product_events:
            return 0.0

        # Quick purchases without much research
        view_count = sum(1 for e in product_events if e.get("isProductViewed", False))
        cart_count = sum(
            1 for e in product_events if e.get("isProductAddedToCart", False)
        )
        search_count = sum(
            1 for e in product_events if e.get("isSearchSubmitted", False)
        )

        if view_count == 0:
            return 0.0

        # High cart rate with low research = impulse tendency
        cart_rate = cart_count / view_count
        research_rate = search_count / view_count

        impulse_tendency = cart_rate * (1 - research_rate)
        return impulse_tendency

    def _calculate_loyalty_score(
        self,
        customer: Dict[str, Any],
        product: Dict[str, Any],
        events: List[Dict[str, Any]],
    ) -> float:
        """Calculate loyalty score for this customer-product relationship"""
        if not events:
            return 0.0

        # Count interactions over time
        product_events = [
            e
            for e in events
            if e.get("customerId") == customer.get("id")
            and e.get("productId") == product.get("id")
        ]

        if not product_events:
            return 0.0

        # Loyalty based on consistency and frequency
        sessions = self._group_events_by_session(product_events)
        session_count = len(sessions)

        # Time span of interactions
        if len(product_events) > 1:
            time_span = (
                product_events[-1].occurred_at - product_events[0].occurred_at
            ).days
            if time_span > 0:
                loyalty_score = session_count / (time_span / 30.0)  # Sessions per month
            else:
                loyalty_score = session_count
        else:
            loyalty_score = 0.0

        return min(loyalty_score / 10.0, 1.0)  # Normalize to 0-1
