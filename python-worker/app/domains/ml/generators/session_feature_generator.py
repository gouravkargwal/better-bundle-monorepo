"""
Optimized Session Feature Generator for State-of-the-Art Gorse Integration
Focuses on session-level signals that actually improve recommendation quality
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from app.core.logging import get_logger
from app.domains.ml.adapters.adapter_factory import InteractionEventAdapterFactory
from app.shared.helpers import now_utc
from app.shared.helpers.datetime_utils import parse_iso_timestamp
from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class SessionFeatureGenerator(BaseFeatureGenerator):
    """State-of-the-art session feature generator optimized for Gorse collaborative filtering"""

    def __init__(self):
        super().__init__()
        self.adapter_factory = InteractionEventAdapterFactory()

    async def generate_features(
        self, session_data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate optimized session features for Gorse

        Args:
            session_data: Dictionary containing session info and events
            context: Additional context data (shop, orders)

        Returns:
            Dictionary with minimal, high-signal session features for Gorse
        """
        try:
            session_id = session_data.get("session_id", "")
            customer_id = session_data.get("customer_id")
            events = session_data.get("events", [])

            logger.debug(
                f"Computing optimized session features for session: {session_id}"
            )

            if not events:
                return self._get_minimal_default_features(session_data, context)

            # Core Gorse-optimized session features
            features = {
                "shop_id": context.get("shop", {}).get("id", ""),
                "session_id": session_id,
                "customer_id": customer_id,
                # === CORE SESSION SIGNALS ===
                # These are the most predictive for session-based recommendations
                "session_duration_minutes": self._compute_session_duration(events),
                "interaction_count": len(events),
                "interaction_intensity": self._compute_interaction_intensity(events),
                # === ENGAGEMENT DEPTH ===
                # High-level patterns Gorse can use for session quality
                "unique_products_viewed": self._compute_unique_products_viewed(events),
                "browse_depth_score": self._compute_browse_depth_score(events),
                # === CONVERSION SIGNALS ===
                # Critical for understanding session intent and success
                "conversion_funnel_stage": self._compute_conversion_funnel_stage(
                    events
                ),
                "purchase_intent_score": self._compute_purchase_intent_score(events),
                # Ensure NOT NULL: default 0.0 when no purchase value is found
                "session_value": (
                    self._compute_session_value(events, context.get("order_data", []))
                    or 0.0
                ),
                # === BEHAVIORAL PATTERN ===
                # Session-level behavior patterns for clustering
                "session_type": self._compute_session_type(events),
                "bounce_session": self._is_bounce_session(events),
                # === TRAFFIC QUALITY ===
                # Important for recommendation relevance
                "traffic_source": self._compute_traffic_source(events),
                "returning_visitor": self._is_returning_visitor(customer_id),
                "last_computed_at": now_utc(),
            }

            return features

        except Exception as e:
            logger.error(f"Failed to compute optimized session features: {str(e)}")
            return self._get_minimal_default_features(session_data, context)

    def _compute_session_duration(self, events: List[Dict[str, Any]]) -> int:
        """Compute session duration in minutes - core engagement signal"""
        if len(events) <= 1:
            return 0

        sorted_events = sorted(events, key=lambda e: e.get("timestamp", ""))

        start_time = self._parse_datetime(sorted_events[0].get("timestamp"))
        end_time = self._parse_datetime(sorted_events[-1].get("timestamp"))

        if not start_time or not end_time:
            return 0

        duration_seconds = (end_time - start_time).total_seconds()
        return max(0, int(duration_seconds / 60))  # Convert to minutes

    def _compute_interaction_intensity(self, events: List[Dict[str, Any]]) -> float:
        """Compute interactions per minute - key engagement quality metric"""
        duration_minutes = self._compute_session_duration(events)

        if duration_minutes == 0:
            return len(events)  # All interactions in < 1 minute

        intensity = len(events) / duration_minutes
        return round(min(intensity, 10.0), 2)  # Cap at 10 interactions/minute

    def _compute_unique_products_viewed(self, events: List[Dict[str, Any]]) -> int:
        """Count unique products viewed - diversity signal for Gorse"""
        unique_products = set()

        for event in events:
            if self.adapter_factory.is_view_event(event):
                product_id = self.adapter_factory.extract_product_id(event)
                if product_id:
                    unique_products.add(product_id)

        return len(unique_products)

    def _compute_browse_depth_score(self, events: List[Dict[str, Any]]) -> float:
        """Compute browse depth score (0-1) - engagement quality"""
        if not events:
            return 0.0

        # Count different types of engagement
        engagement_types = set()

        for event in events:
            event_type = event.get("interactionType", event.get("eventType", ""))

            if event_type in ["product_viewed", "collection_viewed"]:
                engagement_types.add("browse")
            elif event_type in ["search_submitted"]:
                engagement_types.add("search")
            elif event_type in ["product_added_to_cart", "cart_viewed"]:
                engagement_types.add("cart")
            elif event_type in ["checkout_started", "checkout_completed"]:
                engagement_types.add("checkout")

        # Normalize depth score (4 types max)
        depth_score = len(engagement_types) / 4.0
        return round(min(1.0, depth_score), 3)

    def _compute_conversion_funnel_stage(self, events: List[Dict[str, Any]]) -> str:
        """Determine highest funnel stage reached - critical for recommendations"""
        stages = {
            "awareness": False,  # Product/collection views
            "interest": False,  # Multiple views, search
            "consideration": False,  # Cart activity
            "purchase": False,  # Checkout completion
        }

        view_count = 0

        for event in events:
            event_type = event.get("interactionType", event.get("eventType", ""))

            if event_type in ["product_viewed", "collection_viewed"]:
                stages["awareness"] = True
                view_count += 1

            elif event_type in ["search_submitted"]:
                stages["interest"] = True

            elif event_type in ["product_added_to_cart", "cart_viewed"]:
                stages["consideration"] = True

            elif event_type in ["checkout_completed"]:
                stages["purchase"] = True

        # Multiple views also indicate interest
        if view_count >= 3:
            stages["interest"] = True

        # Return highest stage reached
        if stages["purchase"]:
            return "purchase"
        elif stages["consideration"]:
            return "consideration"
        elif stages["interest"]:
            return "interest"
        elif stages["awareness"]:
            return "awareness"
        else:
            return "no_engagement"

    def _compute_purchase_intent_score(self, events: List[Dict[str, Any]]) -> float:
        """Compute purchase intent score (0-1) - predictive signal"""
        if not events:
            return 0.0

        intent_score = 0.0

        # Intent signals with weights
        for event in events:
            event_type = event.get("interactionType", event.get("eventType", ""))

            if event_type == "product_viewed":
                intent_score += 0.1
            elif event_type == "search_submitted":
                intent_score += 0.15
            elif event_type == "product_added_to_cart":
                intent_score += 0.3
            elif event_type == "cart_viewed":
                intent_score += 0.2
            elif event_type == "checkout_started":
                intent_score += 0.4
            elif event_type == "checkout_completed":
                intent_score += 1.0

        return round(min(1.0, intent_score), 3)

    def _compute_session_value(
        self, events: List[Dict[str, Any]], order_data: List[Dict[str, Any]]
    ) -> Optional[float]:
        """Compute session monetary value if purchase occurred"""

        # Check if session had a purchase
        has_purchase = any(
            self.adapter_factory.is_purchase_event(event) for event in events
        )

        if not has_purchase or not order_data:
            return None

        # Find order value within session timeframe
        if not events:
            return None

        sorted_events = sorted(events, key=lambda e: e.get("timestamp", ""))
        session_start = self._parse_datetime(sorted_events[0].get("timestamp"))
        session_end = self._parse_datetime(sorted_events[-1].get("timestamp"))

        if not session_start or not session_end:
            return None

        # Look for orders within session window (+ 30min buffer)
        session_end_buffered = session_end + timedelta(minutes=30)

        for order in order_data:
            order_date = self._parse_datetime(order.get("orderDate"))
            if order_date and session_start <= order_date <= session_end_buffered:
                return float(order.get("totalAmount", 0.0))

        return None

    def _compute_session_type(self, events: List[Dict[str, Any]]) -> str:
        """Classify session type - helps Gorse understand user intent"""

        if not events:
            return "empty"

        event_types = [
            event.get("interactionType", event.get("eventType", "")) for event in events
        ]

        # Count event type occurrences
        search_count = sum(1 for t in event_types if "search" in t)
        view_count = sum(1 for t in event_types if "viewed" in t)
        cart_count = sum(1 for t in event_types if "cart" in t)
        checkout_count = sum(1 for t in event_types if "checkout" in t)

        # Classify based on dominant behavior
        if checkout_count > 0:
            return "converter"
        elif cart_count > 0:
            return "cart_builder"
        elif search_count >= 2:
            return "searcher"
        elif view_count >= 5:
            return "browser"
        elif view_count >= 1:
            return "casual_browser"
        else:
            return "inactive"

    def _is_bounce_session(self, events: List[Dict[str, Any]]) -> bool:
        """Determine if session is a bounce (single interaction)"""
        return len(events) <= 1

    def _compute_traffic_source(self, events: List[Dict[str, Any]]) -> str:
        """Determine primary traffic source - important for recommendation context"""
        if not events:
            return "direct"

        # Get referrer from first event
        first_event = events[0]
        event_data = first_event.get("eventData", {})

        referrer = ""
        if "context" in event_data and "document" in event_data["context"]:
            referrer = event_data["context"]["document"].get("referrer", "")
        elif "referrer" in event_data:
            referrer = str(event_data.get("referrer", ""))

        if not referrer or referrer == "":
            return "direct"

        referrer_lower = referrer.lower()

        if any(search in referrer_lower for search in ["google", "bing", "yahoo"]):
            return "search"
        elif any(
            social in referrer_lower
            for social in ["facebook", "instagram", "twitter", "tiktok"]
        ):
            return "social"
        elif "email" in referrer_lower:
            return "email"
        else:
            return "referral"

    def _is_returning_visitor(self, customer_id: Optional[str]) -> bool:
        """Simple returning visitor check based on customer ID presence"""
        return customer_id is not None

    def _parse_datetime(self, datetime_str: Any) -> Optional[datetime]:
        """Parse datetime from various formats"""
        if not datetime_str:
            return None

        if isinstance(datetime_str, datetime):
            return datetime_str

        if isinstance(datetime_str, str):
            try:
                return parse_iso_timestamp(datetime_str)
            except:
                return None

        return None

    def _get_minimal_default_features(
        self, session_data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Return minimal default features when computation fails"""
        return {
            "shop_id": context.get("shop", {}).get("id", ""),
            "session_id": session_data.get("session_id", ""),
            "customer_id": session_data.get("customer_id"),
            "session_duration_minutes": 0,
            "interaction_count": 0,
            "interaction_intensity": 0.0,
            "unique_products_viewed": 0,
            "browse_depth_score": 0.0,
            "conversion_funnel_stage": "no_engagement",
            "purchase_intent_score": 0.0,
            # Guarantee NOT NULL default
            "session_value": 0.0,
            "session_type": "empty",
            "bounce_session": True,
            "traffic_source": "direct",
            "returning_visitor": False,
            "last_computed_at": now_utc(),
        }
