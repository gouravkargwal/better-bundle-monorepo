"""
Session Feature Generator for ML feature engineering
"""

from typing import Dict, Any, List, Optional
import statistics
from datetime import timedelta

from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.domains.shopify.models import (
    ShopifyCustomer,
    BehavioralEvent,
)

from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class SessionFeatureGenerator(BaseFeatureGenerator):
    """Feature generator for user sessions"""

    async def generate_features(
        self, customer: ShopifyCustomer, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate session-based features for a customer

        Args:
            customer: The customer
            context: Additional context data (events, etc.)

        Returns:
            Dictionary of generated session features
        """
        try:
            logger.debug(f"Computing session features for customer: {customer.id}")

            features = {}
            events = context.get("events", [])

            # Get customer's events
            customer_events = [e for e in events if e.customer_id == customer.id]

            if not customer_events:
                return self._get_empty_session_features()

            # Group events into sessions
            sessions = self._group_events_by_session(customer_events)

            # Session-level features
            features.update(self._compute_session_level_features(sessions))

            # Journey pattern features
            features.update(self._compute_journey_pattern_features(sessions))

            # Engagement features
            features.update(self._compute_engagement_features(sessions))

            # Conversion features
            features.update(self._compute_conversion_features(sessions))

            # Temporal session features
            features.update(self._compute_temporal_session_features(sessions))

            # Device and context features
            features.update(self._compute_context_features(sessions))

            # Validate and clean features
            features = self.validate_features(features)

            logger.debug(
                f"Computed {len(features)} session features for customer: {customer.id}"
            )
            return features

        except Exception as e:
            logger.error(
                f"Failed to compute session features for customer: {customer.id}: {str(e)}"
            )
            return {}

    def _get_empty_session_features(self) -> Dict[str, Any]:
        """Return empty session features when no events exist"""
        return {
            "total_sessions": 0,
            "avg_session_duration": 0.0,
            "avg_session_depth": 0.0,
            "bounce_rate": 0.0,
            "session_frequency": 0.0,
            "journey_type_encoded": 0,
            "conversion_rate": 0.0,
            "cart_abandonment_rate": 0.0,
            "search_usage_rate": 0.0,
            "collection_browsing_rate": 0.0,
            "product_view_rate": 0.0,
            "engagement_score": 0.0,
            "session_consistency": 0.0,
            "peak_session_hour": 0,
            "weekend_session_ratio": 0.0,
            "mobile_session_ratio": 0.0,
            "direct_traffic_ratio": 0.0,
        }

    def _group_events_by_session(
        self, events: List[BehavioralEvent]
    ) -> List[List[BehavioralEvent]]:
        """Group events by session using time proximity and clientId"""
        if not events:
            return []

        # Sort events by time
        sorted_events = sorted(events, key=lambda e: e.occurred_at)

        sessions = []
        current_session = [sorted_events[0]]

        for i in range(1, len(sorted_events)):
            current_event = sorted_events[i]
            previous_event = sorted_events[i - 1]

            # If more than 30 minutes gap, start new session
            time_gap = (
                current_event.occurred_at - previous_event.occurred_at
            ).total_seconds() / 60

            if time_gap > 30:  # 30 minutes session timeout
                sessions.append(current_session)
                current_session = [current_event]
            else:
                current_session.append(current_event)

        sessions.append(current_session)
        return sessions

    def _compute_session_level_features(
        self, sessions: List[List[BehavioralEvent]]
    ) -> Dict[str, Any]:
        """Compute basic session-level features"""
        if not sessions:
            return {}

        session_durations = []
        session_depths = []
        bounce_sessions = 0

        for session in sessions:
            # Session depth (number of events)
            depth = len(session)
            session_depths.append(depth)

            # Session duration
            if depth > 1:
                duration = (
                    session[-1].occurred_at - session[0].occurred_at
                ).total_seconds() / 60  # minutes
                session_durations.append(duration)
            else:
                bounce_sessions += 1
                session_durations.append(0)

        # Calculate session frequency (sessions per week)
        if len(sessions) > 1:
            time_span = (sessions[-1][-1].occurred_at - sessions[0][0].occurred_at).days
            session_frequency = len(sessions) / max(time_span / 7, 1)  # per week
        else:
            session_frequency = 0.0

        return {
            "total_sessions": len(sessions),
            "avg_session_duration": (
                statistics.mean(session_durations) if session_durations else 0.0
            ),
            "avg_session_depth": (
                statistics.mean(session_depths) if session_depths else 0.0
            ),
            "bounce_rate": bounce_sessions / len(sessions) if sessions else 0.0,
            "session_frequency": session_frequency,
        }

    def _compute_journey_pattern_features(
        self, sessions: List[List[BehavioralEvent]]
    ) -> Dict[str, Any]:
        """Compute journey pattern features"""
        if not sessions:
            return {
                "journey_type_encoded": 0,
                "search_usage_rate": 0.0,
                "collection_browsing_rate": 0.0,
                "product_view_rate": 0.0,
                "direct_purchase_rate": 0.0,
            }

        # Analyze journey patterns across all sessions
        total_events = sum(len(session) for session in sessions)
        search_events = 0
        collection_events = 0
        product_view_events = 0
        direct_purchases = 0

        journey_types = []

        for session in sessions:
            session_event_types = [event.event_type for event in session]

            # Count event types in this session
            search_count = session_event_types.count("search_submitted")
            collection_count = session_event_types.count("collection_viewed")
            product_view_count = session_event_types.count("product_viewed")
            checkout_count = session_event_types.count("checkout_started")

            search_events += search_count
            collection_events += collection_count
            product_view_events += product_view_count

            # Direct purchase (checkout without much browsing)
            if checkout_count > 0 and len(session) < 5:
                direct_purchases += 1

            # Classify journey type for this session
            journey_type = self._classify_session_journey_type(session_event_types)
            journey_types.append(journey_type)

        # Calculate rates
        search_usage_rate = search_events / max(total_events, 1)
        collection_browsing_rate = collection_events / max(total_events, 1)
        product_view_rate = product_view_events / max(total_events, 1)
        direct_purchase_rate = direct_purchases / len(sessions)

        # Most common journey type
        most_common_journey = (
            max(set(journey_types), key=journey_types.count) if journey_types else 0
        )

        return {
            "journey_type_encoded": most_common_journey,
            "search_usage_rate": search_usage_rate,
            "collection_browsing_rate": collection_browsing_rate,
            "product_view_rate": product_view_rate,
            "direct_purchase_rate": direct_purchase_rate,
        }

    def _compute_engagement_features(
        self, sessions: List[List[BehavioralEvent]]
    ) -> Dict[str, Any]:
        """Compute engagement features"""
        if not sessions:
            return {
                "engagement_score": 0.0,
                "session_consistency": 0.0,
                "deep_session_ratio": 0.0,
                "return_session_ratio": 0.0,
            }

        # Calculate engagement metrics
        deep_sessions = 0  # Sessions with >5 events
        long_sessions = 0  # Sessions >10 minutes
        return_sessions = 0  # Multiple sessions (already calculated in session count)

        session_depths = []
        session_durations = []

        for session in sessions:
            depth = len(session)
            session_depths.append(depth)

            if depth > 1:
                duration = (
                    session[-1].occurred_at - session[0].occurred_at
                ).total_seconds() / 60
                session_durations.append(duration)
            else:
                session_durations.append(0)

            if depth > 5:
                deep_sessions += 1

            if depth > 1 and session_durations[-1] > 10:
                long_sessions += 1

        # Engagement score (combination of depth, duration, and frequency)
        avg_depth = statistics.mean(session_depths) if session_depths else 0
        avg_duration = statistics.mean(session_durations) if session_durations else 0
        session_count = len(sessions)

        engagement_score = min(
            (avg_depth / 10.0 + avg_duration / 30.0 + session_count / 20.0) / 3.0, 1.0
        )

        # Session consistency (how similar are session patterns)
        if len(session_depths) > 1:
            depth_consistency = 1 - (
                statistics.stdev(session_depths)
                / max(statistics.mean(session_depths), 1)
            )
        else:
            depth_consistency = 0.0

        return {
            "engagement_score": engagement_score,
            "session_consistency": depth_consistency,
            "deep_session_ratio": deep_sessions / len(sessions),
            "return_session_ratio": 1 if len(sessions) > 1 else 0,
        }

    def _compute_conversion_features(
        self, sessions: List[List[BehavioralEvent]]
    ) -> Dict[str, Any]:
        """Compute conversion-related features"""
        if not sessions:
            return {
                "conversion_rate": 0.0,
                "cart_abandonment_rate": 0.0,
                "checkout_abandonment_rate": 0.0,
                "funnel_completion_rate": 0.0,
            }

        total_sessions = len(sessions)
        sessions_with_cart = 0
        sessions_with_checkout = 0
        sessions_with_purchase = 0
        sessions_with_product_view = 0

        for session in sessions:
            event_types = [event.event_type for event in session]

            if "product_viewed" in event_types:
                sessions_with_product_view += 1
            if "product_added_to_cart" in event_types:
                sessions_with_cart += 1
            if "checkout_started" in event_types:
                sessions_with_checkout += 1
            if "checkout_completed" in event_types:
                sessions_with_purchase += 1

        # Calculate conversion rates
        conversion_rate = sessions_with_purchase / max(total_sessions, 1)
        cart_abandonment_rate = (sessions_with_cart - sessions_with_checkout) / max(
            sessions_with_cart, 1
        )
        checkout_abandonment_rate = (
            sessions_with_checkout - sessions_with_purchase
        ) / max(sessions_with_checkout, 1)

        # Funnel completion rate (view -> cart -> checkout -> purchase)
        if sessions_with_product_view > 0:
            funnel_completion_rate = sessions_with_purchase / sessions_with_product_view
        else:
            funnel_completion_rate = 0.0

        return {
            "conversion_rate": conversion_rate,
            "cart_abandonment_rate": cart_abandonment_rate,
            "checkout_abandonment_rate": checkout_abandonment_rate,
            "funnel_completion_rate": funnel_completion_rate,
        }

    def _compute_temporal_session_features(
        self, sessions: List[List[BehavioralEvent]]
    ) -> Dict[str, Any]:
        """Compute temporal session features"""
        if not sessions:
            return {
                "peak_session_hour": 0,
                "weekend_session_ratio": 0.0,
                "session_time_consistency": 0.0,
                "seasonal_session_pattern": 0.0,
            }

        session_hours = []
        weekend_sessions = 0
        session_months = []

        for session in sessions:
            session_start = session[0].occurred_at
            session_hours.append(session_start.hour)
            session_months.append(session_start.month)

            # Weekend sessions (Saturday=5, Sunday=6)
            if session_start.weekday() >= 5:
                weekend_sessions += 1

        # Peak session hour
        peak_hour = (
            max(set(session_hours), key=session_hours.count) if session_hours else 12
        )

        # Weekend session ratio
        weekend_ratio = weekend_sessions / len(sessions)

        # Session time consistency (how consistent are session times)
        if len(session_hours) > 1:
            hour_consistency = 1 - (
                statistics.stdev(session_hours) / max(statistics.mean(session_hours), 1)
            )
        else:
            hour_consistency = 0.0

        # Seasonal session pattern
        seasonal_pattern = self._calculate_seasonal_session_pattern(session_months)

        return {
            "peak_session_hour": peak_hour,
            "weekend_session_ratio": weekend_ratio,
            "session_time_consistency": hour_consistency,
            "seasonal_session_pattern": seasonal_pattern,
        }

    def _compute_context_features(
        self, sessions: List[List[BehavioralEvent]]
    ) -> Dict[str, Any]:
        """Compute device and context features"""
        if not sessions:
            return {
                "mobile_session_ratio": 0.0,
                "desktop_session_ratio": 0.0,
                "direct_traffic_ratio": 0.0,
                "search_traffic_ratio": 0.0,
                "social_traffic_ratio": 0.0,
            }

        mobile_sessions = 0
        desktop_sessions = 0
        direct_sessions = 0
        search_sessions = 0
        social_sessions = 0

        for session in sessions:
            # Analyze first event for context
            first_event = session[0]

            if first_event.event_data:
                # Device type
                user_agent = (
                    first_event.event_data.get("context", {})
                    .get("navigator", {})
                    .get("userAgent", "")
                )
                if self._is_mobile_device(user_agent):
                    mobile_sessions += 1
                else:
                    desktop_sessions += 1

                # Traffic source
                referrer = (
                    first_event.event_data.get("context", {})
                    .get("document", {})
                    .get("referrer", "")
                )
                traffic_source = self._classify_traffic_source(referrer)

                if traffic_source == "direct":
                    direct_sessions += 1
                elif traffic_source == "search":
                    search_sessions += 1
                elif traffic_source == "social":
                    social_sessions += 1

        total_sessions = len(sessions)

        return {
            "mobile_session_ratio": mobile_sessions / total_sessions,
            "desktop_session_ratio": desktop_sessions / total_sessions,
            "direct_traffic_ratio": direct_sessions / total_sessions,
            "search_traffic_ratio": search_sessions / total_sessions,
            "social_traffic_ratio": social_sessions / total_sessions,
        }

    def _classify_session_journey_type(self, event_types: List[str]) -> int:
        """Classify journey type for a session (0=browser, 1=searcher, 2=direct_buyer)"""
        search_count = event_types.count("search_submitted")
        product_views = event_types.count("product_viewed")
        cart_adds = event_types.count("product_added_to_cart")
        checkouts = event_types.count("checkout_started")

        if checkouts > 0 and len(event_types) < 5:
            return 2  # Direct buyer
        elif search_count > product_views * 0.3:
            return 1  # Searcher
        else:
            return 0  # Browser

    def _calculate_seasonal_session_pattern(self, session_months: List[int]) -> float:
        """Calculate seasonal session pattern strength"""
        if not session_months:
            return 0.0

        # Count sessions by season
        seasonal_counts = {"spring": 0, "summer": 0, "fall": 0, "winter": 0}

        for month in session_months:
            if month in [3, 4, 5]:
                seasonal_counts["spring"] += 1
            elif month in [6, 7, 8]:
                seasonal_counts["summer"] += 1
            elif month in [9, 10, 11]:
                seasonal_counts["fall"] += 1
            else:
                seasonal_counts["winter"] += 1

        # Calculate pattern strength (how concentrated in one season)
        total_sessions = sum(seasonal_counts.values())
        if total_sessions == 0:
            return 0.0

        max_season_count = max(seasonal_counts.values())
        pattern_strength = max_season_count / total_sessions

        return pattern_strength

    def _is_mobile_device(self, user_agent: str) -> bool:
        """Check if user agent indicates mobile device"""
        user_agent_lower = user_agent.lower()
        mobile_indicators = ["mobile", "android", "iphone", "ipad", "tablet"]
        return any(indicator in user_agent_lower for indicator in mobile_indicators)

    def _classify_traffic_source(self, referrer: str) -> str:
        """Classify traffic source from referrer"""
        if not referrer:
            return "direct"
        elif any(
            search in referrer.lower()
            for search in ["google", "bing", "yahoo", "search"]
        ):
            return "search"
        elif any(
            social in referrer.lower()
            for social in ["facebook", "twitter", "instagram", "pinterest"]
        ):
            return "social"
        else:
            return "other"
