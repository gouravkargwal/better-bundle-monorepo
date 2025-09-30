"""
Session Feature Generator for ML feature engineering
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json
from app.core.logging import get_logger
from app.domains.ml.adapters.adapter_factory import InteractionEventAdapterFactory

from app.shared.helpers import now_utc
from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class SessionFeatureGenerator(BaseFeatureGenerator):
    """Feature generator for individual user sessions to match SessionFeatures schema"""

    def __init__(self):
        super().__init__()
        self.adapter_factory = InteractionEventAdapterFactory()

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
            session_id = session_data.get("session_id", "")
            customer_id = session_data.get("customer_id")
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
            features.update(context_features)

            # NEW: Enhanced session features using device/location data
            enhanced_context_features = self._compute_enhanced_context_features(events)
            features.update(enhanced_context_features)

            # Add lastComputedAt timestamp
            features["last_computed_at"] = now_utc()
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
        current_time = now_utc()
        return {
            "shop_id": shop.get("id", ""),
            "session_id": session_data.get("session_id", ""),
            "customer_id": session_data.get("customer_id"),
            "start_time": current_time,
            "end_time": current_time,
            "duration_seconds": 0,
            "event_count": 0,
            "page_view_count": 0,
            "product_view_count": 0,
            "collection_view_count": 0,
            "search_count": 0,
            "cart_add_count": 0,
            "checkout_started": False,
            "checkout_completed": False,
            "order_value": None,
            "referrer_domain": None,
            "landing_page": None,
            "exit_page": None,
        }

    def _compute_basic_session_features(
        self, session_data: Dict[str, Any], shop: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute basic session identification features"""
        return {
            "shop_id": shop.get("id", ""),
            "session_id": session_data.get("session_id", ""),
            "customer_id": session_data.get("customer_id"),  # Can be None for anonymous
        }

    def _compute_session_timing(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute session timing features"""
        if not events:
            return {
                "start_time": None,
                "end_time": None,
                "duration_seconds": 0,
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
            "start_time": start_time,
            "end_time": end_time,
            "duration_seconds": duration_seconds,
        }

    def _compute_event_counts(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute event count features using adapter pattern"""
        event_count = len(events)
        page_view_count = 0
        product_view_count = 0
        collection_view_count = 0
        search_count = 0
        cart_add_count = 0
        cart_view_count = 0
        cart_remove_count = 0

        for event in events:
            # Use adapter factory for event classification
            if self.adapter_factory.is_view_event(event):
                if event.get("eventType", "") in ["page_viewed"]:
                    page_view_count += 1
                elif event.get("eventType", "") in ["product_viewed"]:
                    product_view_count += 1
                elif event.get("eventType", "") in ["collection_viewed"]:
                    collection_view_count += 1
                elif event.get("eventType", "") in ["recommendation_viewed"]:
                    product_view_count += (
                        1  # Count recommendation views as product views
                    )

            elif self.adapter_factory.is_cart_event(event):
                if event.get("eventType", "") in [
                    "product_added_to_cart",
                    "recommendation_add_to_cart",
                ]:
                    cart_add_count += 1
                elif event.get("eventType", "") in ["cart_viewed"]:
                    cart_view_count += 1
                elif event.get("eventType", "") in ["product_removed_from_cart"]:
                    cart_remove_count += 1

            elif self.adapter_factory.is_search_event(event):
                search_count += 1

        return {
            "event_count": event_count,
            "page_view_count": page_view_count,
            "product_view_count": product_view_count,
            "collection_view_count": collection_view_count,
            "search_count": search_count,
            "cart_add_count": cart_add_count,
            "cart_view_count": cart_view_count,
            "cart_remove_count": cart_remove_count,
        }

    def _compute_conversion_metrics(
        self, events: List[Dict[str, Any]], order_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute conversion-related features using adapter pattern"""
        checkout_started = False
        checkout_completed = False
        order_value = None
        cart_viewed = False
        cart_abandoned = False

        # Check for checkout and cart events using adapter pattern
        for event in events:
            event_type = event.get("eventType", "")

            # Use adapter factory for event classification
            if event_type in ["checkout_started", "checkout_begin"]:
                checkout_started = True
            elif self.adapter_factory.is_purchase_event(event):
                checkout_completed = True
            elif (
                self.adapter_factory.is_cart_event(event)
                and event_type == "cart_viewed"
            ):
                cart_viewed = True

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

        # Determine cart abandonment: cart viewed but no checkout completed
        cart_abandoned = cart_viewed and not checkout_completed

        return {
            "checkout_started": checkout_started,
            "checkout_completed": checkout_completed,
            "order_value": order_value,
            "cart_viewed": cart_viewed,
            "cart_abandoned": cart_abandoned,
        }

    def _compute_context_features(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute device and context features"""
        if not events:
            return {
                "referrer_domain": None,
                "landing_page": None,
                "exit_page": None,
            }

        # Sort events by time
        sorted_events = sorted(events, key=lambda e: e.get("timestamp", ""))
        first_event = sorted_events[0]
        last_event = sorted_events[-1]

        # Extract device type from first event
        device_type = None
        event_data = first_event.get("eventData", {})

        # Event data is already parsed from database (no JSON parsing needed)

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
        if "context" in event_data and "document" in event_data["context"]:
            referrer = event_data["context"]["document"].get("referrer", "")
            if isinstance(referrer, str):
                referrer_domain = self._extract_domain(referrer)
        elif "referrer" in event_data:
            referrer = event_data.get("referrer", "")
            if isinstance(referrer, str):
                referrer_domain = self._extract_domain(referrer)

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
        # Event data is already parsed from database (no JSON parsing needed)

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
            "referrer_domain": (
                referrer_domain if isinstance(referrer_domain, str) else None
            ),
            "landing_page": landing_page if isinstance(landing_page, str) else None,
            "exit_page": exit_page if isinstance(exit_page, str) else None,
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

    def _compute_enhanced_context_features(
        self, events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute enhanced context features using device/location data from behavioral events"""
        try:
            if not events:
                return {
                    "device_type": "",
                    "browser_type": "",
                    "os_type": "",
                    "screen_resolution": "",
                    "country": "",
                    "region": "",
                    "city": "",
                    "timezone": "",
                    "language": "",
                    "referrer_type": "direct",
                    "traffic_source": "direct",
                    "device_consistency": 0,
                    "location_consistency": 0,
                }

            # Extract device and location data from events
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

            for event in events:
                event_data = event.get("eventData", {})

                # Device information
                device_type = event_data.get("device_type", "")
                if device_type:
                    device_types.append(device_type)

                browser_type = event_data.get("browser_type", "")
                if browser_type:
                    browser_types.append(browser_type)

                os_type = event_data.get("os_type", "")
                if os_type:
                    os_types.append(os_type)

                screen_resolution = event_data.get("screen_resolution", "")
                if screen_resolution:
                    screen_resolutions.append(screen_resolution)

                # Location information
                country = event_data.get("country", "")
                if country:
                    countries.append(country)

                region = event_data.get("region", "")
                if region:
                    regions.append(region)

                city = event_data.get("city", "")
                if city:
                    cities.append(city)

                timezone = event_data.get("timezone", "")
                if timezone:
                    timezones.append(timezone)

                language = event_data.get("language", "")
                if language:
                    languages.append(language)

                referrer = event_data.get("referrer", "")
                if referrer:
                    referrers.append(referrer)

            # Get most common values
            from collections import Counter

            most_common_device = (
                Counter(device_types).most_common(1)[0][0] if device_types else ""
            )
            most_common_browser = (
                Counter(browser_types).most_common(1)[0][0] if browser_types else ""
            )
            most_common_os = Counter(os_types).most_common(1)[0][0] if os_types else ""
            most_common_screen = (
                Counter(screen_resolutions).most_common(1)[0][0]
                if screen_resolutions
                else ""
            )
            most_common_country = (
                Counter(countries).most_common(1)[0][0] if countries else ""
            )
            most_common_region = (
                Counter(regions).most_common(1)[0][0] if regions else ""
            )
            most_common_city = Counter(cities).most_common(1)[0][0] if cities else ""
            most_common_timezone = (
                Counter(timezones).most_common(1)[0][0] if timezones else ""
            )
            most_common_language = (
                Counter(languages).most_common(1)[0][0] if languages else ""
            )

            # Device consistency (0-100)
            device_consistency = 0
            if device_types:
                device_counts = Counter(device_types)
                total_devices = len(device_types)
                most_common_count = device_counts.most_common(1)[0][1]
                device_consistency = int((most_common_count / total_devices) * 100)

            # Location consistency (0-100)
            location_consistency = 0
            if countries:
                country_counts = Counter(countries)
                total_countries = len(countries)
                most_common_count = country_counts.most_common(1)[0][1]
                location_consistency = int((most_common_count / total_countries) * 100)

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

            # Traffic source classification
            traffic_source = "direct"
            if referrer_types:
                if "search" in referrer_types:
                    traffic_source = "search"
                elif "social" in referrer_types:
                    traffic_source = "social"
                elif "email" in referrer_types:
                    traffic_source = "email"
                elif "other" in referrer_types:
                    traffic_source = "referral"

            return {
                "device_type": most_common_device,
                "browser_type": most_common_browser,
                "os_type": most_common_os,
                "screen_resolution": most_common_screen,
                "country": most_common_country,
                "region": most_common_region,
                "city": most_common_city,
                "timezone": most_common_timezone,
                "language": most_common_language,
                "referrer_type": most_common_referrer_type,
                "traffic_source": traffic_source,
                "device_consistency": device_consistency,
                "location_consistency": location_consistency,
            }
        except Exception as e:
            logger.error(f"Error computing enhanced context features: {str(e)}")
            return {
                "device_type": "",
                "browser_type": "",
                "os_type": "",
                "screen_resolution": "",
                "country": "",
                "region": "",
                "city": "",
                "timezone": "",
                "language": "",
                "referrer_type": "direct",
                "traffic_source": "direct",
                "device_consistency": 0,
                "location_consistency": 0,
            }
