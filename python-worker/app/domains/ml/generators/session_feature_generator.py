"""
Session Feature Generator for ML feature engineering
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json
from app.core.logging import get_logger

from app.shared.helpers import now_utc
from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class SessionFeatureGenerator(BaseFeatureGenerator):
    """Feature generator for individual user sessions to match SessionFeatures schema"""

    async def generate_features(
        self, session_data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate features for a single session to match SessionFeatures schema

        Args:
            session_data: Dictionary containing:
                - sessionId: Unique session identifier
                - customerId: Customer ID (optional, can be None for anonymous)
                - events: List of BehavioralEvents for this session
            context: Additional context data:
                - shop: Shop data
                - order_data: List of OrderData (to match orderValue)

        Returns:
            Dictionary of generated session features matching SessionFeatures schema
        """
        try:
            session_id = session_data.get("sessionId", "")
            customer_id = session_data.get("customerId")
            events = session_data.get("events", [])

            logger.debug(f"Computing session features for session: {session_id}")

            if not events:
                return self._get_empty_session_features(session_data, context)

            features = {}
            shop = context.get("shop", {})
            order_data = context.get("order_data", [])

            # Basic session identification
            features.update(self._compute_basic_session_features(session_data, shop))

            # Session timing
            features.update(self._compute_session_timing(events))

            # Event counts
            features.update(self._compute_event_counts(events))

            # Conversion metrics
            features.update(self._compute_conversion_metrics(events, order_data))

            # Context features (device, referrer, pages)
            context_features = self._compute_context_features(events)
            logger.info(f"🔍 Context features: {context_features}")
            features.update(context_features)

            # Validate and clean features (method doesn't exist, so skip)
            # features = self.validate_features(features)

            # Add lastComputedAt timestamp
            features["lastComputedAt"] = now_utc()

            logger.info(f"🔍 Final session features for {session_id}: {features}")
            logger.debug(
                f"Computed {len(features)} session features for session: {session_id}"
            )
            return features

        except Exception as e:
            logger.error(
                f"Failed to compute session features for session: {session_data.get('sessionId', 'unknown')}: {str(e)}"
            )
            return {}

    def _get_empty_session_features(
        self, session_data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Return empty session features when no events exist"""
        shop = context.get("shop", {})
        return {
            "shopId": shop.get("id", ""),
            "sessionId": session_data.get("sessionId", ""),
            "customerId": session_data.get("customerId"),
            "startTime": None,
            "endTime": None,
            "durationSeconds": 0,
            "eventCount": 0,
            "pageViewCount": 0,
            "productViewCount": 0,
            "collectionViewCount": 0,
            "searchCount": 0,
            "cartAddCount": 0,
            "checkoutStarted": False,
            "checkoutCompleted": False,
            "orderValue": None,
            "referrerDomain": None,
            "landingPage": None,
            "exitPage": None,
        }

    def _compute_basic_session_features(
        self, session_data: Dict[str, Any], shop: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute basic session identification features"""
        return {
            "shopId": shop.get("id", ""),
            "sessionId": session_data.get("sessionId", ""),
            "customerId": session_data.get("customerId"),  # Can be None for anonymous
        }

    def _compute_session_timing(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute session timing features"""
        if not events:
            return {
                "startTime": None,
                "endTime": None,
                "durationSeconds": 0,
            }

        # Sort events by time
        sorted_events = sorted(events, key=lambda e: e.get("timestamp", ""))

        start_time_str = sorted_events[0].get("timestamp")
        end_time_str = sorted_events[-1].get("timestamp")

        # Parse datetime strings
        start_time = None
        end_time = None

        if isinstance(start_time_str, str):
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        elif isinstance(start_time_str, datetime):
            start_time = start_time_str

        if isinstance(end_time_str, str):
            end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
        elif isinstance(end_time_str, datetime):
            end_time = end_time_str

        # Calculate duration in seconds
        duration_seconds = 0
        if start_time and end_time:
            duration_seconds = int((end_time - start_time).total_seconds())

        return {
            "startTime": start_time,
            "endTime": end_time,
            "durationSeconds": duration_seconds,
        }

    def _compute_event_counts(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute event count features"""
        event_count = len(events)
        page_view_count = 0
        product_view_count = 0
        collection_view_count = 0
        search_count = 0
        cart_add_count = 0

        for event in events:
            event_type = event.get("eventType", "")

            if event_type in ["page_viewed", "page_view"]:
                page_view_count += 1
            elif event_type in ["product_viewed", "product_view"]:
                product_view_count += 1
            elif event_type in ["collection_viewed", "collection_view"]:
                collection_view_count += 1
            elif event_type in ["search_submitted", "search"]:
                search_count += 1
            elif event_type in ["product_added_to_cart", "cart_add"]:
                cart_add_count += 1

        return {
            "eventCount": event_count,
            "pageViewCount": page_view_count,
            "productViewCount": product_view_count,
            "collectionViewCount": collection_view_count,
            "searchCount": search_count,
            "cartAddCount": cart_add_count,
        }

    def _compute_conversion_metrics(
        self, events: List[Dict[str, Any]], order_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute conversion-related features"""
        checkout_started = False
        checkout_completed = False
        order_value = None

        # Check for checkout events
        for event in events:
            event_type = event.get("eventType", "")
            if event_type in ["checkout_started", "checkout_begin"]:
                checkout_started = True
            elif event_type in ["checkout_completed", "purchase", "order_completed"]:
                checkout_completed = True

        # Find order value if checkout was completed
        if checkout_completed:
            # Look for order in the same time window
            session_start = None
            session_end = None

            if events:
                sorted_events = sorted(events, key=lambda e: e.get("timestamp", ""))
                start_time_str = sorted_events[0].get("timestamp")
                end_time_str = sorted_events[-1].get("timestamp")

                if isinstance(start_time_str, str):
                    session_start = datetime.fromisoformat(
                        start_time_str.replace("Z", "+00:00")
                    )
                if isinstance(end_time_str, str):
                    session_end = datetime.fromisoformat(
                        end_time_str.replace("Z", "+00:00")
                    )

            # Find matching order
            for order in order_data:
                order_date = order.get("orderDate")
                if isinstance(order_date, str):
                    order_date = datetime.fromisoformat(
                        order_date.replace("Z", "+00:00")
                    )

                # Check if order is within session timeframe (with some buffer)
                if (
                    session_start
                    and session_end
                    and order_date
                    and session_start
                    <= order_date
                    <= session_end + timedelta(minutes=30)
                ):
                    order_value = float(order.get("totalAmount", 0))
                    break

        return {
            "checkoutStarted": checkout_started,
            "checkoutCompleted": checkout_completed,
            "orderValue": order_value,
        }

    def _compute_context_features(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute device and context features"""
        if not events:
            return {
                "referrerDomain": None,
                "landingPage": None,
                "exitPage": None,
            }

        # Sort events by time
        sorted_events = sorted(events, key=lambda e: e.get("timestamp", ""))
        first_event = sorted_events[0]
        last_event = sorted_events[-1]

        # Extract device type from first event
        device_type = None
        event_data = first_event.get("eventData", {})

        if isinstance(event_data, str):
            try:
                event_data = json.loads(event_data)
            except:
                event_data = {}

        # Try to get device type from various possible locations in event data
        user_agent = ""
        if "context" in event_data:
            context = event_data["context"]
            if "navigator" in context:
                user_agent = context["navigator"].get("userAgent", "")
            elif "userAgent" in context:
                user_agent = context.get("userAgent", "")
        elif "userAgent" in event_data:
            user_agent = event_data.get("userAgent", "")
        elif "device" in event_data:
            device_type = event_data["device"].get("type")

        # Classify device type from user agent if not already set
        if not device_type and user_agent:
            device_type = self._classify_device_type(user_agent)

        # Extract referrer domain
        referrer_domain = None
        logger.info(f"🔍 Processing event_data for referrer: {event_data}")
        if "context" in event_data and "document" in event_data["context"]:
            referrer = event_data["context"]["document"].get("referrer", "")
            logger.info(
                f"🔍 Found referrer in context.document: {referrer} (type: {type(referrer)})"
            )
            if isinstance(referrer, str):
                referrer_domain = self._extract_domain(referrer)
                logger.info(
                    f"🔍 Extracted referrer domain from context.document: {referrer_domain} (type: {type(referrer_domain)})"
                )
        elif "referrer" in event_data:
            referrer = event_data.get("referrer", "")
            logger.info(
                f"🔍 Found referrer in event_data: {referrer} (type: {type(referrer)})"
            )
            if isinstance(referrer, str):
                referrer_domain = self._extract_domain(referrer)
                logger.info(
                    f"🔍 Extracted referrer domain from referrer: {referrer_domain} (type: {type(referrer_domain)})"
                )
        else:
            logger.info(f"🔍 No referrer found in event_data")

        # Extract landing page (from first event)
        landing_page = None
        if "context" in event_data and "page" in event_data["context"]:
            url = event_data["context"]["page"].get("url")
            if isinstance(url, str):
                landing_page = url
        elif "page" in event_data:
            url = event_data["page"].get("url")
            if isinstance(url, str):
                landing_page = url
        elif "url" in event_data:
            url = event_data.get("url")
            if isinstance(url, str):
                landing_page = url

        # Extract exit page (from last event)
        exit_page = None
        last_event_data = last_event.get("eventData", {})
        if isinstance(last_event_data, str):
            try:
                last_event_data = json.loads(last_event_data)
            except:
                last_event_data = {}

        if "context" in last_event_data and "page" in last_event_data["context"]:
            url = last_event_data["context"]["page"].get("url")
            if isinstance(url, str):
                exit_page = url
        elif "page" in last_event_data:
            url = last_event_data["page"].get("url")
            if isinstance(url, str):
                exit_page = url
        elif "url" in last_event_data:
            url = last_event_data.get("url")
            if isinstance(url, str):
                exit_page = url

        return {
            "referrerDomain": (
                referrer_domain if isinstance(referrer_domain, str) else None
            ),
            "landingPage": landing_page if isinstance(landing_page, str) else None,
            "exitPage": exit_page if isinstance(exit_page, str) else None,
        }

    def _classify_device_type(self, user_agent: str) -> str:
        """Classify device type from user agent string"""
        user_agent_lower = user_agent.lower()

        if any(
            mobile in user_agent_lower for mobile in ["mobile", "android", "iphone"]
        ):
            return "mobile"
        elif any(tablet in user_agent_lower for tablet in ["ipad", "tablet"]):
            return "tablet"
        else:
            return "desktop"

    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL"""
        if not url:
            return None

        try:
            # Remove protocol
            if "://" in url:
                url = url.split("://", 1)[1]

            # Extract domain (before first slash)
            domain = url.split("/")[0]

            # Remove www prefix
            if domain.startswith("www."):
                domain = domain[4:]

            return domain if domain else None
        except:
            return None
