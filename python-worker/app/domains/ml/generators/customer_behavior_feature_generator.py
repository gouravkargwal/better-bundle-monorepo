"""
Customer Behavior Feature Generator for ML feature engineering
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
import json
import math
import statistics
from collections import Counter
from app.core.logging import get_logger
from app.domains.ml.adapters.adapter_factory import InteractionEventAdapterFactory
from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class CustomerBehaviorFeatureGenerator(BaseFeatureGenerator):
    """Feature generator for customer behavioral patterns to match CustomerBehaviorFeatures schema"""

    def __init__(self):
        super().__init__()
        self.adapter_factory = InteractionEventAdapterFactory()

    async def generate_features(
        self, customer: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate behavioral features for a customer using unified analytics data

        Args:
            customer: Customer data (from CustomerData table)
            context: Additional context data:
                - shop: Shop data
                - user_interactions: List of UserInteraction for this customer
                - user_sessions: List of UserSession for this customer
                - purchase_attributions: List of PurchaseAttribution for this customer

        Returns:
            Dictionary of generated features matching CustomerBehaviorFeatures schema
        """
        try:
            customer_id = customer.get("customer_id", "")
            logger.debug(
                f"Computing enhanced customer behavior features for customer: {customer_id}"
            )

            features = {}
            shop = context.get("shop", {})

            # Get unified analytics data
            user_interactions = context.get("user_interactions", [])
            user_sessions = context.get("user_sessions", [])
            purchase_attributions = context.get("purchase_attributions", [])

            # If no interaction data, return empty features
            if not user_interactions:
                return self._get_empty_behavior_features(customer, shop)

            # Basic customer features
            features.update(self._compute_basic_features(customer, shop))

            # Enhanced features from unified analytics data
            if user_interactions:
                # Session metrics from user interactions
                features.update(
                    self._compute_interaction_session_metrics(
                        user_interactions, user_sessions
                    )
                )

                # Event counts from user interactions
                features.update(
                    self._compute_interaction_event_counts(user_interactions)
                )

                # Temporal patterns from user interactions
                features.update(
                    self._compute_interaction_temporal_patterns(user_interactions)
                )

                # Behavior patterns (unique items, search terms, etc.)
                features.update(
                    self._compute_interaction_behavior_patterns(user_interactions)
                )

                # Extension-specific features
                features.update(
                    self._compute_extension_features(user_interactions, customer_id)
                )

                # NEW: Device and location features from behavioral events
                features.update(
                    self._compute_device_location_features(user_interactions)
                )

            # Cross-session features
            if user_sessions:
                features.update(
                    self._compute_cross_session_features(user_sessions, customer_id)
                )

            # Attribution features
            if purchase_attributions:
                features.update(
                    self._compute_attribution_features(
                        purchase_attributions, customer_id
                    )
                )

            # Conversion metrics (rates between interaction types)
            features.update(self._compute_conversion_metrics(features))

            # Computed scores (engagement, recency, diversity, behavioral)
            features.update(
                self._compute_computed_scores_from_interactions(
                    features, user_interactions
                )
            )

            # Validate and clean features
            features = self.validate_features(features)

            # Add lastComputedAt timestamp
            from app.shared.helpers import now_utc

            features["last_computed_at"] = now_utc()

            logger.debug(
                f"Computed {len(features)} behavior features for customer: {customer_id}"
            )
            return features

        except Exception as e:
            logger.error(
                f"Failed to compute behavior features for customer: {customer.get('customer_id', 'unknown')}: {str(e)}"
            )
            return {}

    # ===================== NEW METHODS FOR USER INTERACTIONS =====================

    def _compute_interaction_session_metrics(
        self, interactions: List[Dict[str, Any]], sessions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute session metrics from user interactions and sessions"""
        if not sessions:
            # Fallback: estimate sessions from interactions
            session_ids = set(
                i.get("session_id") for i in interactions if i.get("session_id")
            )
            session_count = len(session_ids)

            total_interactions = len(interactions)
            avg_events_per_session = (
                total_interactions / session_count if session_count > 0 else None
            )

            return {
                "session_count": session_count,
                "avgSessionDuration": None,  # Can't calculate without session data
                "avgEventsPerSession": avg_events_per_session,
            }

        # Use actual session data
        session_count = len(sessions)
        total_duration = 0
        total_interactions = len(interactions)

        for session in sessions:
            created_at = self._parse_datetime(session.get("createdAt"))
            last_active = self._parse_datetime(session.get("lastActive"))

            if created_at and last_active:
                duration = int((last_active - created_at).total_seconds())
                total_duration += duration

        avg_duration = total_duration // session_count if session_count > 0 else None
        avg_events_per_session = (
            total_interactions / session_count if session_count > 0 else None
        )

        return {
            "session_count": session_count,
            "avg_session_duration": avg_duration,
            "avg_events_per_session": avg_events_per_session,
        }

    def _compute_interaction_event_counts(
        self, interactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute counts for different interaction types"""
        total_event_count = len(interactions)

        # Initialize counters
        counts = {
            "product_view": 0,
            "collection_view": 0,
            "cart_add": 0,
            "cart_view": 0,
            "cart_remove": 0,
            "search": 0,
            "checkout_start": 0,
            "purchase": 0,
            "recommendation_view": 0,
            "recommendation_click": 0,
        }

        # Extension-specific counters
        extension_counts = {
            "venus": 0,
            "phoenix": 0,
            "apollo": 0,
            "atlas": 0,
        }

        for interaction in interactions:
            interaction_type = interaction.get("interactionType", "").lower()
            extension_type = interaction.get("extensionType", "").lower()

            # Count by extension
            if extension_type in extension_counts:
                extension_counts[extension_type] += 1

            # Use adapter factory for event classification
            if self.adapter_factory.is_view_event(interaction):
                if interaction_type in ["product_viewed", "view"]:
                    counts["product_view"] += 1
                elif interaction_type in ["collection_viewed", "collection_view"]:
                    counts["collection_view"] += 1
                elif interaction_type in ["recommendation_viewed"]:
                    counts["recommendation_view"] += 1

            elif self.adapter_factory.is_cart_event(interaction):
                if interaction_type in ["product_added_to_cart", "add_to_cart"]:
                    counts["cart_add"] += 1
                elif interaction_type in ["cart_viewed"]:
                    counts["cart_view"] += 1
                elif interaction_type in [
                    "product_removed_from_cart",
                    "remove_from_cart",
                ]:
                    counts["cart_remove"] += 1

            elif self.adapter_factory.is_search_event(interaction):
                counts["search"] += 1

            elif self.adapter_factory.is_purchase_event(interaction):
                counts["purchase"] += 1

            elif interaction_type in ["checkout_started", "checkout_begin"]:
                counts["checkout_start"] += 1

            elif interaction_type in ["recommendation_clicked"]:
                counts["recommendation_click"] += 1

        return {
            "total_event_count": total_event_count,
            "product_view_count": counts["product_view"],
            "collection_view_count": counts["collection_view"],
            "cart_add_count": counts["cart_add"],
            "cart_view_count": counts["cart_view"],
            "cart_remove_count": counts["cart_remove"],
            "search_count": counts["search"],
            "checkout_start_count": counts["checkout_start"],
            "purchase_count": counts["purchase"],
            # NEW: Extension-specific counts
            "venus_interaction_count": extension_counts["venus"],
            "phoenix_interaction_count": extension_counts["phoenix"],
            "apollo_interaction_count": extension_counts["apollo"],
            "atlas_interaction_count": extension_counts["atlas"],
            # NEW: Recommendation-specific counts
            "recommendation_click_rate": counts.get("recommendation_click", 0)
            / max(counts.get("recommendation_view", 1), 1),
            "upsell_interaction_count": counts.get("upsell_interaction", 0),
        }

    def _compute_interaction_temporal_patterns(
        self, interactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute temporal patterns from user interactions"""
        if not interactions:
            return {
                "days_since_first_event": 0,
                "days_since_last_event": 0,
                "most_active_hour": None,
                "most_active_day": None,
            }

        # Sort interactions by timestamp
        valid_interactions = []
        for interaction in interactions:
            created_at = self._parse_datetime(interaction.get("created_at"))
            if created_at:
                valid_interactions.append((interaction, created_at))

        if not valid_interactions:
            return {
                "days_since_first_event": 0,
                "days_since_last_event": 0,
                "most_active_hour": None,
                "most_active_day": None,
            }

        valid_interactions.sort(key=lambda x: x[1])

        first_event_time = valid_interactions[0][1]
        last_event_time = valid_interactions[-1][1]
        current_time = datetime.now(timezone.utc)

        days_since_first = (current_time - first_event_time).days
        days_since_last = (current_time - last_event_time).days

        # Calculate most active hour and day
        hours = [timestamp.hour for _, timestamp in valid_interactions]
        days = [timestamp.weekday() for _, timestamp in valid_interactions]

        most_active_hour = max(set(hours), key=hours.count) if hours else None
        most_active_day = max(set(days), key=days.count) if days else None

        return {
            "days_since_first_event": days_since_first,
            "days_since_last_event": days_since_last,
            "most_active_hour": most_active_hour,
            "most_active_day": most_active_day,
        }

    def _compute_interaction_behavior_patterns(
        self, interactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute behavior patterns from user interactions"""
        unique_products = set()
        unique_collections = set()
        search_terms = []
        categories = []
        device_types = []
        referrers = []

        for interaction in interactions:
            metadata = interaction.get("metadata", {})

            # Extract product and collection IDs
            if metadata.get("product_id"):
                unique_products.add(metadata["product_id"])
            if metadata.get("collection_id"):
                unique_collections.add(metadata["collection_id"])

            # Extract search terms
            if metadata.get("search_query"):
                search_terms.append(metadata["search_query"])

            # Extract categories
            if metadata.get("product_category"):
                categories.append(metadata["product_category"])
            elif metadata.get("category"):
                categories.append(metadata["category"])

            # Extract device types
            if metadata.get("device_type"):
                device_types.append(metadata["device_type"])

            # Extract referrers
            if metadata.get("referrer") and metadata["referrer"] != "":
                referrers.append(metadata["referrer"])

        # Get top categories (up to 3)
        category_counts = Counter(categories)
        top_categories = [cat for cat, _ in category_counts.most_common(3)]

        # Get primary device type
        device_counts = Counter(device_types)
        primary_device = device_counts.most_common(1)[0][0] if device_types else None

        # Get primary referrer
        referrer_counts = Counter(referrers)
        primary_referrer = referrer_counts.most_common(1)[0][0] if referrers else None

        return {
            "unique_products_viewed": len(unique_products),
            "unique_collections_viewed": len(unique_collections),
            "search_terms": search_terms[:10],  # Keep last 10 search terms
            "top_categories": top_categories,
            "device_type": primary_device,
            "primary_referrer": primary_referrer,
        }

    def _compute_computed_scores_from_interactions(
        self, features: Dict[str, Any], interactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute engagement, recency, diversity, and behavioral scores from interactions"""

        # Engagement score (based on interaction variety and frequency)
        total_interactions = features.get("total_event_count", 0)
        session_count = features.get("session_count", 1)
        unique_products = features.get("unique_products_viewed", 0)

        # Normalize engagement (0-1 scale)
        engagement_raw = (
            min(total_interactions / 50, 1.0) * 0.4  # Interaction frequency
            + min(unique_products / 20, 1.0) * 0.3  # Product diversity
            + min(session_count / 10, 1.0) * 0.3  # Session frequency
        )
        engagement_score = max(0.0, min(1.0, engagement_raw))

        # Recency score (based on days since last interaction)
        days_since_last = features.get("days_since_last_event", float("inf"))
        if days_since_last == float("inf"):
            recency_score = 0.0
        else:
            # Exponential decay: 1.0 for today, 0.5 for 7 days ago, 0.1 for 30 days ago
            recency_score = max(0.0, min(1.0, math.exp(-days_since_last / 10)))

        # Diversity score (based on variety of interaction types)
        interaction_types = set()
        for interaction in interactions:
            interaction_types.add(interaction.get("interactionType", ""))

        diversity_raw = len(interaction_types) / 8.0  # Assume max 8 different types
        diversity_score = max(0.0, min(1.0, diversity_raw))

        # Behavioral score (weighted combination of all scores)
        behavioral_score = (
            engagement_score * 0.4 + recency_score * 0.3 + diversity_score * 0.3
        )

        return {
            "engagement_score": round(engagement_score, 3),
            "recency_score": round(recency_score, 3),
            "diversity_score": round(diversity_score, 3),
            "behavioral_score": round(behavioral_score, 3),
        }

    def _get_empty_behavior_features(
        self, customer: Dict[str, Any], shop: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Return empty behavior features when no events exist"""
        return {
            "shop_id": shop.get("id", ""),
            "customer_id": customer.get("customer_id", ""),
            "session_count": 0,
            "avg_session_duration": None,
            "avg_events_per_session": None,
            "total_event_count": 0,
            "product_view_count": 0,
            "collection_view_count": 0,
            "cart_add_count": 0,
            "search_count": 0,
            "checkout_start_count": 0,
            "purchase_count": 0,
            "days_since_first_event": 0,
            "days_since_last_event": 0,
            "most_active_hour": None,
            "most_active_day": None,
            "unique_products_viewed": 0,
            "unique_collections_viewed": 0,
            "search_terms": [],
            "top_categories": [],
            "device_type": None,
            "primary_referrer": None,
            "browse_to_cart_rate": None,
            "cart_to_purchase_rate": None,
            "search_to_purchase_rate": None,
            "engagement_score": 0.0,
            "recency_score": 0.0,
            "diversity_score": 0.0,
            "behavioral_score": 0.0,
            # NEW: Extension-specific interaction counts
            "venus_interaction_count": 0,
            "phoenix_interaction_count": 0,
            "apollo_interaction_count": 0,
            "atlas_interaction_count": 0,
            # NEW: Recommendation-specific counts
            "recommendation_click_rate": 0.0,
            "upsell_interaction_count": 0,
        }

    def _compute_basic_features(
        self, customer: Dict[str, Any], shop: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute basic identification features"""
        return {
            "shop_id": shop.get("id", ""),
            "customer_id": customer.get("customer_id", ""),
        }

    def _compute_session_metrics(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute session-level metrics by grouping events into sessions"""
        if not events:
            return {
                "session_count": 0,
                "avg_session_duration": None,
                "avg_events_per_session": None,
            }

        # Group events into sessions (30-minute timeout)
        sessions = self._group_events_into_sessions(events)

        session_count = len(sessions)
        total_duration = 0
        total_events = len(events)

        for session in sessions:
            if len(session) > 1:
                # Calculate session duration in seconds
                start_time = self._parse_datetime(session[0].get("timestamp"))
                end_time = self._parse_datetime(session[-1].get("timestamp"))

                if start_time and end_time:
                    duration = int((end_time - start_time).total_seconds())
                    total_duration += duration

        avg_duration = (
            int(total_duration / session_count) if session_count > 0 else None
        )
        avg_events_per_session = (
            total_events / session_count if session_count > 0 else None
        )

        return {
            "session_count": session_count,
            "avg_session_duration": avg_duration,
            "avg_events_per_session": avg_events_per_session,
        }

    def _compute_event_counts(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute counts for different event types"""
        total_event_count = len(events)
        product_view_count = 0
        collection_view_count = 0
        cart_add_count = 0
        cart_view_count = 0
        cart_remove_count = 0
        search_count = 0
        checkout_start_count = 0
        purchase_count = 0

        for event in events:
            event_type = event.get("event_type", "").lower()

            if event_type in ["product_viewed", "product_view"]:
                product_view_count += 1
            elif event_type in ["collection_viewed", "collection_view"]:
                collection_view_count += 1
            elif event_type in ["product_added_to_cart", "cart_add", "add_to_cart"]:
                cart_add_count += 1
            elif event_type in ["cart_viewed"]:
                cart_view_count += 1
            elif event_type in ["product_removed_from_cart"]:
                cart_remove_count += 1
            elif event_type in ["search_submitted", "search", "search_query"]:
                search_count += 1
            elif event_type in ["checkout_started", "checkout_begin", "begin_checkout"]:
                checkout_start_count += 1
            elif event_type in ["purchase", "checkout_completed", "order_completed"]:
                purchase_count += 1

        return {
            "total_event_count": total_event_count,
            "product_view_count": product_view_count,
            "collection_view_count": collection_view_count,
            "cart_add_count": cart_add_count,
            "cart_view_count": cart_view_count,
            "cart_remove_count": cart_remove_count,
            "search_count": search_count,
            "checkout_start_count": checkout_start_count,
            "purchase_count": purchase_count,
        }

    def _compute_temporal_patterns(
        self, events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute temporal behavioral patterns"""
        if not events:
            return {
                "days_since_first_event": 0,
                "days_since_last_event": 0,
                "most_active_hour": None,
                "most_active_day": None,
            }

        # Sort events by time
        sorted_events = sorted(events, key=lambda e: e.get("timestamp", ""))

        first_event_time = self._parse_datetime(sorted_events[0].get("timestamp"))
        last_event_time = self._parse_datetime(sorted_events[-1].get("timestamp"))
        current_time = datetime.now(timezone.utc)

        # Calculate days since first and last events
        days_since_first = 0
        days_since_last = 0

        if first_event_time:
            days_since_first = (current_time - first_event_time).days
        if last_event_time:
            days_since_last = (current_time - last_event_time).days

        # Find most active hour and day
        hours = []
        days = []

        for event in events:
            event_time = self._parse_datetime(event.get("timestamp"))
            if event_time:
                hours.append(event_time.hour)
                days.append(event_time.weekday())  # 0=Monday, 6=Sunday

        most_active_hour = Counter(hours).most_common(1)[0][0] if hours else None
        most_active_day = Counter(days).most_common(1)[0][0] if days else None

        return {
            "days_since_first_event": days_since_first,
            "days_since_last_event": days_since_last,
            "most_active_hour": most_active_hour,
            "most_active_day": most_active_day,
        }

    def _compute_behavior_patterns(
        self, events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute behavioral pattern features"""
        unique_products = set()
        unique_collections = set()
        search_terms = []
        categories = []
        device_types = []
        referrers = []

        for event in events:
            event_data = event.get("event_data", {})
            # Event data is already parsed from database (no JSON parsing needed)

            # Extract product IDs
            product_id = event_data.get("productId") or event_data.get("product_id")
            if product_id:
                unique_products.add(product_id)

            # Extract collection IDs
            collection_id = event_data.get("collectionId") or event_data.get(
                "collection_id"
            )
            if collection_id:
                unique_collections.add(collection_id)

            # Extract search terms
            if event.get("event_type") in ["search_submitted", "search"]:
                search_term = event_data.get("query") or event_data.get("search_term")
                if search_term:
                    search_terms.append(search_term.lower())

            # Extract product categories
            category = event_data.get("category") or event_data.get("product_type")
            if category:
                categories.append(category)

            # Extract device type (from first occurrence)
            if not device_types:
                device_type = self._extract_device_type(event_data)
                if device_type:
                    device_types.append(device_type)

            # Extract referrer (from first occurrence)
            if not referrers:
                referrer = self._extract_referrer_domain(event_data)
                if referrer:
                    referrers.append(referrer)

        # Get top 3 categories
        top_categories = (
            [cat for cat, _ in Counter(categories).most_common(3)]
            if categories
            else None
        )

        # Get unique search terms (limit to prevent huge JSON)
        unique_search_terms = list(set(search_terms))[:20] if search_terms else []

        # Ensure deviceType is always a string or None
        device_type_value = None
        if device_types:
            device_type = device_types[0]
            if device_type is not None:
                device_type_value = str(device_type)

        # Ensure primaryReferrer is always a string or None
        referrer_value = None
        if referrers:
            referrer = referrers[0]
            if referrer is not None:
                referrer_value = str(referrer)

        return {
            "unique_products_viewed": len(unique_products),
            "unique_collections_viewed": len(unique_collections),
            "search_terms": unique_search_terms if unique_search_terms else [],
            "top_categories": top_categories if top_categories else [],
            "device_type": device_type_value,
            "primary_referrer": referrer_value,
        }

    def _compute_conversion_metrics(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Compute conversion rate metrics"""
        product_views = features.get("product_view_count", 0)
        cart_adds = features.get("cart_add_count", 0)
        purchases = features.get("purchase_count", 0)
        searches = features.get("search_count", 0)

        # Browse to cart rate
        browse_to_cart_rate = (cart_adds / product_views) if product_views > 0 else None

        # Cart to purchase rate
        cart_to_purchase_rate = (purchases / cart_adds) if cart_adds > 0 else None

        # Search to purchase rate
        search_to_purchase_rate = (purchases / searches) if searches > 0 else None

        return {
            "browse_to_cart_rate": browse_to_cart_rate,
            "cart_to_purchase_rate": cart_to_purchase_rate,
            "search_to_purchase_rate": search_to_purchase_rate,
        }

    def _compute_computed_scores(
        self,
        features: Dict[str, Any],
        events: List[Dict[str, Any]],
        user_interactions: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Compute normalized behavioral scores (0-1)"""

        # Engagement Score (based on activity volume and diversity)
        total_events = features.get("total_event_count", 0)
        session_count = features.get("session_count", 0)
        unique_products = features.get("unique_products_viewed", 0)

        # Normalize components (using log scale for large numbers)
        import math

        event_score = min(math.log10(total_events + 1) / 3, 1.0)  # Cap at 1000 events
        session_score = min(session_count / 20.0, 1.0)  # Cap at 20 sessions
        diversity_events = min(unique_products / 50.0, 1.0)  # Cap at 50 unique products

        engagement_score = (event_score + session_score + diversity_events) / 3.0

        # Recency Score (higher for more recent activity)
        days_since_last = features.get("days_since_last_event", 365)
        recency_score = max(
            0, (30 - min(days_since_last, 30)) / 30.0
        )  # Linear decay over 30 days

        # Diversity Score (based on variety of activities)
        diversity_components = []
        if features.get("product_view_count", 0) > 0:
            diversity_components.append(1)
        if features.get("collection_view_count", 0) > 0:
            diversity_components.append(1)
        if features.get("cart_add_count", 0) > 0:
            diversity_components.append(1)
        if features.get("search_count", 0) > 0:
            diversity_components.append(1)
        if features.get("purchase_count", 0) > 0:
            diversity_components.append(1)

        diversity_score = (
            sum(diversity_components) / 5.0
        )  # Max 5 different activity types

        # Behavioral Score (composite of all factors)
        conversion_quality = 0
        if features.get("browse_to_cart_rate"):
            conversion_quality += min(
                features.get("browse_to_cart_rate", 0) / 0.1, 1.0
            )  # Good rate is 10%
        if features.get("cart_to_purchase_rate"):
            conversion_quality += min(
                features.get("cart_to_purchase_rate", 0) / 0.3, 1.0
            )  # Good rate is 30%
        conversion_quality = conversion_quality / 2.0  # Average of both rates

        behavioral_score = (
            engagement_score * 0.4
            + recency_score * 0.2
            + diversity_score * 0.2
            + conversion_quality * 0.2
        )

        return {
            "engagement_score": engagement_score,
            "recency_score": recency_score,
            "diversity_score": diversity_score,
            "behavioral_score": behavioral_score,
        }

    def _group_events_into_sessions(
        self, events: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Group events into sessions using 30-minute timeout"""
        if not events:
            return []

        # Sort events by time
        sorted_events = sorted(events, key=lambda e: e.get("timestamp", ""))

        sessions = []
        current_session = [sorted_events[0]]

        for i in range(1, len(sorted_events)):
            current_event = sorted_events[i]
            previous_event = sorted_events[i - 1]

            current_time = self._parse_datetime(current_event.get("timestamp"))
            previous_time = self._parse_datetime(previous_event.get("timestamp"))

            if current_time and previous_time:
                time_gap_minutes = (current_time - previous_time).total_seconds() / 60

                if time_gap_minutes > 30:  # 30 minutes session timeout
                    sessions.append(current_session)
                    current_session = [current_event]
                else:
                    current_session.append(current_event)
            else:
                current_session.append(current_event)

        sessions.append(current_session)
        return sessions

    def _parse_datetime(self, datetime_str: str) -> Optional[datetime]:
        """Parse datetime string to datetime object"""
        if not datetime_str:
            return None

        try:
            if isinstance(datetime_str, str):
                return datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
            elif isinstance(datetime_str, datetime):
                return datetime_str
            else:
                return None
        except:
            return None

    def _extract_device_type(self, event_data: Dict[str, Any]) -> Optional[str]:
        """Extract device type from event data"""
        # Try different possible locations for device info
        if "device" in event_data:
            device_type = event_data["device"].get("type")
            # Handle case where device type is 0 or invalid
            if device_type and device_type != 0:
                return str(device_type)

        if "context" in event_data:
            context = event_data["context"]
            if "navigator" in context:
                user_agent = context["navigator"].get("userAgent", "")
                return self._classify_device_from_user_agent(user_agent)
            elif "userAgent" in context:
                user_agent = context.get("userAgent", "")
                return self._classify_device_from_user_agent(user_agent)

        return None

    def _extract_referrer_domain(self, event_data: Dict[str, Any]) -> Optional[str]:
        """Extract referrer domain from event data"""
        referrer = None

        if "context" in event_data and "document" in event_data["context"]:
            referrer = event_data["context"]["document"].get("referrer")
        elif "referrer" in event_data:
            referrer = event_data.get("referrer")

        if referrer and referrer != 0:
            try:
                if "://" in str(referrer):
                    domain = str(referrer).split("://")[1].split("/")[0]
                    if domain.startswith("www."):
                        domain = domain[4:]
                    return domain
            except:
                pass

        return None

    def _classify_device_from_user_agent(self, user_agent: str) -> str:
        """Classify device type from user agent"""
        if not user_agent:
            return "desktop"

        user_agent_lower = user_agent.lower()

        if any(
            mobile in user_agent_lower for mobile in ["mobile", "android", "iphone"]
        ):
            return "mobile"
        elif any(tablet in user_agent_lower for tablet in ["ipad", "tablet"]):
            return "tablet"
        else:
            return "desktop"

    # NEW: Enhanced feature computation methods for unified analytics data

    def _compute_cross_session_features(
        self, user_sessions: List[Dict[str, Any]], customer_id: str
    ) -> Dict[str, Any]:
        """Compute cross-session features from unified analytics"""
        try:
            if not user_sessions:
                return {
                    "total_unified_sessions": 0,
                    "cross_session_span_days": 0,
                    "sessionFrequencyScore": 0.0,
                    "deviceDiversity": 0,
                    "avg_session_duration": None,
                }

            # Filter sessions for this customer
            customer_sessions = [
                s for s in user_sessions if s.get("customer_id") == customer_id
            ]

            if not customer_sessions:
                return {
                    "total_unified_sessions": 0,
                    "cross_session_span_days": 0,
                    "sessionFrequencyScore": 0.0,
                    "deviceDiversity": 0,
                    "avg_session_duration": None,
                }

            # Basic session metrics
            total_sessions = len(customer_sessions)

            # Calculate session span
            session_dates = []
            session_durations = []
            user_agents = set()

            for session in customer_sessions:
                created_at = session.get("createdAt")
                if created_at:
                    try:
                        if isinstance(created_at, str):
                            session_date = datetime.fromisoformat(
                                created_at.replace("Z", "+00:00")
                            )
                        else:
                            session_date = created_at
                        session_dates.append(session_date)
                    except:
                        pass

                # Calculate session duration
                start_time = session.get("createdAt")
                last_active = session.get("lastActive")
                if start_time and last_active:
                    try:
                        if isinstance(start_time, str):
                            start_dt = datetime.fromisoformat(
                                start_time.replace("Z", "+00:00")
                            )
                        else:
                            start_dt = start_time
                        if isinstance(last_active, str):
                            end_dt = datetime.fromisoformat(
                                last_active.replace("Z", "+00:00")
                            )
                        else:
                            end_dt = last_active
                        duration = (end_dt - start_dt).total_seconds()
                        session_durations.append(duration)
                    except:
                        pass

                # Track user agents for device diversity
                user_agent = session.get("userAgent")
                if user_agent:
                    user_agents.add(user_agent)

            # Calculate cross-session span
            cross_session_span_days = 0
            if len(session_dates) > 1:
                min_date = min(session_dates)
                max_date = max(session_dates)
                cross_session_span_days = (max_date - min_date).days

            # Calculate session frequency score (sessions per day)
            session_frequency_score = 0.0
            if cross_session_span_days > 0:
                session_frequency_score = total_sessions / cross_session_span_days

            # Calculate average session duration
            avg_session_duration = None
            if session_durations:
                avg_session_duration = sum(session_durations) / len(session_durations)

            return {
                "total_unified_sessions": total_sessions,
                "cross_session_span_days": cross_session_span_days,
                "session_frequency_score": round(session_frequency_score, 4),
                "device_diversity": len(user_agents),
                "avg_session_duration": (
                    round(avg_session_duration, 2) if avg_session_duration else None
                ),
            }

        except Exception as e:
            logger.error(f"Error computing cross-session features: {str(e)}")
            return {
                "total_unified_sessions": 0,
                "cross_session_span_days": 0,
                "session_frequency_score": 0.0,
                "device_diversity": 0,
                "avg_session_duration": None,
            }

    def _compute_extension_features(
        self, user_interactions: List[Dict[str, Any]], customer_id: str
    ) -> Dict[str, Any]:
        """Compute extension-specific features from unified analytics"""
        try:
            if not user_interactions:
                return {
                    "phoenix_interaction_count": 0,
                    "apollo_interaction_count": 0,
                    "venus_interaction_count": 0,
                    "atlas_interaction_count": 0,
                    "extension_engagement_score": 0.0,
                    "recommendation_click_rate": 0.0,
                    "upsell_interaction_count": 0,
                }

            # Filter interactions for this customer
            customer_interactions = [
                i for i in user_interactions if i.get("customer_id") == customer_id
            ]

            if not customer_interactions:
                return {
                    "phoenix_interaction_count": 0,
                    "apollo_interaction_count": 0,
                    "venus_interaction_count": 0,
                    "atlas_interaction_count": 0,
                    "extension_engagement_score": 0.0,
                    "recommendation_click_rate": 0.0,
                    "upsell_interaction_count": 0,
                }

            # Count interactions by extension type
            extension_counts = {}
            recommendation_clicks = 0
            total_interactions = len(customer_interactions)
            upsell_interactions = 0

            for interaction in customer_interactions:
                extension_type = interaction.get("extensionType", "").lower()
                interaction_type = interaction.get("interactionType", "").lower()

                # Count by extension
                extension_counts[extension_type] = (
                    extension_counts.get(extension_type, 0) + 1
                )

                # Count recommendation clicks
                if "recommendation" in interaction_type and "click" in interaction_type:
                    recommendation_clicks += 1

                # Count upsell interactions
                if "upsell" in interaction_type or "post_purchase" in interaction_type:
                    upsell_interactions += 1

            # Calculate extension engagement score (diversity of extensions used)
            extension_engagement_score = (
                len(extension_counts) / 4.0
            )  # 4 total extensions

            # Calculate recommendation click rate
            recommendation_click_rate = 0.0
            if total_interactions > 0:
                recommendation_click_rate = recommendation_clicks / total_interactions

            return {
                "phoenix_interaction_count": extension_counts.get("phoenix", 0),
                "apollo_interaction_count": extension_counts.get("apollo", 0),
                "venus_interaction_count": extension_counts.get("venus", 0),
                "atlas_interaction_count": extension_counts.get("atlas", 0),
                "extension_engagement_score": round(extension_engagement_score, 4),
                "recommendation_click_rate": round(recommendation_click_rate, 4),
                "upsell_interaction_count": upsell_interactions,
            }

        except Exception as e:
            logger.error(f"Error computing extension features: {str(e)}")
            return {
                "phoenix_interaction_count": 0,
                "apollo_interaction_count": 0,
                "venus_interaction_count": 0,
                "atlas_interaction_count": 0,
                "extension_engagement_score": 0.0,
                "recommendation_click_rate": 0.0,
                "upsell_interaction_count": 0,
            }

    def _compute_enhanced_session_metrics(
        self, user_sessions: List[Dict[str, Any]], customer_id: str
    ) -> Dict[str, Any]:
        """Compute enhanced session metrics from unified analytics"""
        try:
            if not user_sessions:
                return {
                    "total_interactions_in_sessions": 0,
                    "avg_interactions_per_session": 0.0,
                    "session_engagement_score": 0.0,
                }

            # Filter sessions for this customer
            customer_sessions = [
                s for s in user_sessions if s.get("customer_id") == customer_id
            ]

            if not customer_sessions:
                return {
                    "total_interactions_in_sessions": 0,
                    "avg_interactions_per_session": 0.0,
                    "session_engagement_score": 0.0,
                }

            # Calculate session interaction metrics
            total_interactions = sum(
                s.get("totalInteractions", 0) for s in customer_sessions
            )
            avg_interactions_per_session = (
                total_interactions / len(customer_sessions) if customer_sessions else 0
            )

            # Calculate session engagement score (based on interaction density)
            session_engagement_score = min(
                avg_interactions_per_session / 10.0, 1.0
            )  # Normalize to 0-1

            return {
                "total_interactions_in_sessions": total_interactions,
                "avg_interactions_per_session": round(avg_interactions_per_session, 2),
                "session_engagement_score": round(session_engagement_score, 4),
            }

        except Exception as e:
            logger.error(f"Error computing enhanced session metrics: {str(e)}")
            return {
                "total_interactions_in_sessions": 0,
                "avg_interactions_per_session": 0.0,
                "session_engagement_score": 0.0,
            }

    def _compute_attribution_features(
        self, purchase_attributions: List[Dict[str, Any]], customer_id: str
    ) -> Dict[str, Any]:
        """Compute attribution features from unified analytics"""
        try:
            if not purchase_attributions:
                return {
                    "multi_touch_attribution_score": 0.0,
                    "attribution_revenue": 0.0,
                    "conversion_path_length": 0,
                    # Note: extensionContributionWeights field removed - not in database schema
                }

            # Filter attributions for this customer
            customer_attributions = [
                a for a in purchase_attributions if a.get("customer_id") == customer_id
            ]

            if not customer_attributions:
                return {
                    "multi_touch_attribution_score": 0.0,
                    "attribution_revenue": 0.0,
                    "conversion_path_length": 0,
                    # Note: extensionContributionWeights field removed - not in database schema
                }

            # Calculate attribution metrics
            total_revenue = sum(
                float(a.get("totalRevenue", 0)) for a in customer_attributions
            )
            total_interactions = sum(
                a.get("totalInteractions", 0) for a in customer_attributions
            )

            # Calculate multi-touch attribution score (based on interaction diversity)
            multi_touch_score = 0.0
            if total_interactions > 0:
                # Higher score for more diverse interaction patterns
                unique_extensions = set()
                for attribution in customer_attributions:
                    contributing_extensions = attribution.get(
                        "contributingExtensions", []
                    )
                    if isinstance(contributing_extensions, list):
                        # Ensure we only add strings, not dictionaries
                        for ext in contributing_extensions:
                            if isinstance(ext, str):
                                unique_extensions.add(ext)
                            elif isinstance(ext, dict):
                                # Extract extension type from dictionary
                                ext_type = ext.get("extensionType", "")
                                if ext_type:
                                    unique_extensions.add(ext_type)
                multi_touch_score = min(
                    len(unique_extensions) / 4.0, 1.0
                )  # Normalize to 0-1

            # Calculate average conversion path length
            conversion_path_length = 0
            if customer_attributions:
                conversion_path_length = int(
                    total_interactions / len(customer_attributions)
                )

            # Calculate extension contribution weights
            extension_weights = {}
            for attribution in customer_attributions:
                attribution_weights = attribution.get("attributionWeights", [])
                if isinstance(attribution_weights, list):
                    for weight_data in attribution_weights:
                        if isinstance(weight_data, dict):
                            ext_type = weight_data.get("extensionType", "")
                            weight = weight_data.get("weight", 0.0)
                            if ext_type:
                                extension_weights[ext_type] = (
                                    extension_weights.get(ext_type, 0.0) + weight
                                )

            # Normalize weights
            total_weight = sum(extension_weights.values())
            if total_weight > 0:
                extension_weights = {
                    k: v / total_weight for k, v in extension_weights.items()
                }

            return {
                "multi_touch_attribution_score": round(multi_touch_score, 4),
                "attribution_revenue": round(total_revenue, 2),
                "conversion_path_length": conversion_path_length,
                # Note: extensionContributionWeights field removed - not in database schema
            }

        except Exception as e:
            logger.error(f"Error computing attribution features: {str(e)}")
            return {
                "multi_touch_attribution_score": 0.0,
                "attribution_revenue": 0.0,
                "conversion_path_length": 0,
                # Note: extensionContributionWeights field removed - not in database schema
            }

    def _compute_device_location_features(
        self, user_interactions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute device and location features from behavioral events"""
        try:
            # Extract device and location data from interactions
            device_types = []
            browser_types = []
            os_types = []
            screen_resolutions = []
            countries = []
            regions = []
            cities = []
            timezones = []
            languages = []
            referrers = []

            for interaction in user_interactions:
                metadata = interaction.get("metadata", {})

                # Device information
                device_type = metadata.get("deviceType", "")
                if device_type:
                    device_types.append(device_type)

                browser_type = metadata.get("browserType", "")
                if browser_type:
                    browser_types.append(browser_type)

                os_type = metadata.get("osType", "")
                if os_type:
                    os_types.append(os_type)

                screen_resolution = metadata.get("screenResolution", "")
                if screen_resolution:
                    screen_resolutions.append(screen_resolution)

                # Location information
                country = metadata.get("country", "")
                if country:
                    countries.append(country)

                region = metadata.get("region", "")
                if region:
                    regions.append(region)

                city = metadata.get("city", "")
                if city:
                    cities.append(city)

                timezone = metadata.get("timezone", "")
                if timezone:
                    timezones.append(timezone)

                language = metadata.get("language", "")
                if language:
                    languages.append(language)

                referrer = metadata.get("referrer", "")
                if referrer:
                    referrers.append(referrer)

            # Calculate diversity metrics
            device_diversity = len(set(device_types)) if device_types else 0
            location_diversity = len(set(countries)) if countries else 0
            referrer_diversity = len(set(referrers)) if referrers else 0

            # Most common values
            most_common_device = (
                Counter(device_types).most_common(1)[0][0] if device_types else ""
            )
            most_common_country = (
                Counter(countries).most_common(1)[0][0] if countries else ""
            )
            most_common_timezone = (
                Counter(timezones).most_common(1)[0][0] if timezones else ""
            )
            most_common_language = (
                Counter(languages).most_common(1)[0][0] if languages else ""
            )

            # Device consistency score (0-100)
            device_consistency = 0
            if device_types:
                device_counts = Counter(device_types)
                total_devices = len(device_types)
                most_common_count = device_counts.most_common(1)[0][1]
                device_consistency = int((most_common_count / total_devices) * 100)

            # Geographic consistency score (0-100)
            geo_consistency = 0
            if countries:
                country_counts = Counter(countries)
                total_countries = len(countries)
                most_common_count = country_counts.most_common(1)[0][1]
                geo_consistency = int((most_common_count / total_countries) * 100)

            # Referrer analysis
            referrer_types = []
            for referrer in referrers:
                if "google" in referrer.lower():
                    referrer_types.append("search")
                elif "facebook" in referrer.lower() or "instagram" in referrer.lower():
                    referrer_types.append("social")
                elif "email" in referrer.lower():
                    referrer_types.append("email")
                elif referrer == "" or referrer == "direct":
                    referrer_types.append("direct")
                else:
                    referrer_types.append("other")

            most_common_referrer_type = (
                Counter(referrer_types).most_common(1)[0][0]
                if referrer_types
                else "direct"
            )

            return {
                "device_diversity": device_diversity,
                "device_consistency": device_consistency,
                "device_type": most_common_device,
                "country": most_common_country,
                "timezone": most_common_timezone,
                "language": most_common_language,
                "referrer_type": most_common_referrer_type,
            }
        except Exception as e:
            logger.error(f"Error computing device location features: {str(e)}")
            return {
                "device_diversity": 0,
                "device_consistency": 0,
                "device_type": "",
                "country": "",
                "timezone": "",
                "language": "",
                "referrer_type": "direct",
            }
