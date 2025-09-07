"""
Customer Behavior Feature Generator for ML feature engineering
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json
import statistics
from collections import Counter

from app.core.logging import get_logger
from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class CustomerBehaviorFeatureGenerator(BaseFeatureGenerator):
    """Feature generator for customer behavioral patterns to match CustomerBehaviorFeatures schema"""

    async def generate_features(
        self, customer: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate behavioral features for a customer to match CustomerBehaviorFeatures schema

        Args:
            customer: Customer data (from CustomerData table)
            context: Additional context data:
                - shop: Shop data
                - behavioral_events: List of BehavioralEvents for this customer

        Returns:
            Dictionary of generated features matching CustomerBehaviorFeatures schema
        """
        try:
            customer_id = customer.get("customerId", "")
            logger.debug(
                f"Computing customer behavior features for customer: {customer_id}"
            )

            features = {}
            shop = context.get("shop", {})
            behavioral_events = context.get("behavioral_events", [])

            if not behavioral_events:
                return self._get_empty_behavior_features(customer, shop)

            # Basic customer features
            features.update(self._compute_basic_features(customer, shop))

            # Session metrics (aggregate across all sessions)
            features.update(self._compute_session_metrics(behavioral_events))

            # Event counts (aggregate all event types)
            features.update(self._compute_event_counts(behavioral_events))

            # Temporal patterns
            features.update(self._compute_temporal_patterns(behavioral_events))

            # Behavior patterns (unique items, search terms, etc.)
            features.update(self._compute_behavior_patterns(behavioral_events))

            # Conversion metrics (rates between event types)
            features.update(self._compute_conversion_metrics(features))

            # Computed scores (engagement, recency, diversity, behavioral)
            features.update(self._compute_computed_scores(features, behavioral_events))

            # Validate and clean features
            features = self.validate_features(features)

            logger.debug(
                f"Computed {len(features)} behavior features for customer: {customer_id}"
            )
            return features

        except Exception as e:
            logger.error(
                f"Failed to compute behavior features for customer: {customer.get('customerId', 'unknown')}: {str(e)}"
            )
            return {}

    def _get_empty_behavior_features(
        self, customer: Dict[str, Any], shop: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Return empty behavior features when no events exist"""
        return {
            "shopId": shop.get("id", ""),
            "customerId": customer.get("customerId", ""),
            "sessionCount": 0,
            "avgSessionDuration": None,
            "avgEventsPerSession": None,
            "totalEventCount": 0,
            "productViewCount": 0,
            "collectionViewCount": 0,
            "cartAddCount": 0,
            "searchCount": 0,
            "checkoutStartCount": 0,
            "purchaseCount": 0,
            "daysSinceFirstEvent": 0,
            "daysSinceLastEvent": 0,
            "mostActiveHour": None,
            "mostActiveDay": None,
            "uniqueProductsViewed": 0,
            "uniqueCollectionsViewed": 0,
            "searchTerms": None,
            "topCategories": None,
            "deviceType": None,
            "primaryReferrer": None,
            "browseToCartRate": None,
            "cartToPurchaseRate": None,
            "searchToPurchaseRate": None,
            "engagementScore": 0.0,
            "recencyScore": 0.0,
            "diversityScore": 0.0,
            "behavioralScore": 0.0,
        }

    def _compute_basic_features(
        self, customer: Dict[str, Any], shop: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute basic identification features"""
        return {
            "shopId": shop.get("id", ""),
            "customerId": customer.get("customerId", ""),
        }

    def _compute_session_metrics(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute session-level metrics by grouping events into sessions"""
        if not events:
            return {
                "sessionCount": 0,
                "avgSessionDuration": None,
                "avgEventsPerSession": None,
            }

        # Group events into sessions (30-minute timeout)
        sessions = self._group_events_into_sessions(events)

        session_count = len(sessions)
        total_duration = 0
        total_events = len(events)

        for session in sessions:
            if len(session) > 1:
                # Calculate session duration in seconds
                start_time = self._parse_datetime(session[0].get("occurredAt"))
                end_time = self._parse_datetime(session[-1].get("occurredAt"))

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
            "sessionCount": session_count,
            "avgSessionDuration": avg_duration,
            "avgEventsPerSession": avg_events_per_session,
        }

    def _compute_event_counts(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Compute counts for different event types"""
        total_event_count = len(events)
        product_view_count = 0
        collection_view_count = 0
        cart_add_count = 0
        search_count = 0
        checkout_start_count = 0
        purchase_count = 0

        for event in events:
            event_type = event.get("eventType", "").lower()

            if event_type in ["product_viewed", "product_view"]:
                product_view_count += 1
            elif event_type in ["collection_viewed", "collection_view"]:
                collection_view_count += 1
            elif event_type in ["product_added_to_cart", "cart_add", "add_to_cart"]:
                cart_add_count += 1
            elif event_type in ["search_submitted", "search", "search_query"]:
                search_count += 1
            elif event_type in ["checkout_started", "checkout_begin", "begin_checkout"]:
                checkout_start_count += 1
            elif event_type in ["purchase", "checkout_completed", "order_completed"]:
                purchase_count += 1

        return {
            "totalEventCount": total_event_count,
            "productViewCount": product_view_count,
            "collectionViewCount": collection_view_count,
            "cartAddCount": cart_add_count,
            "searchCount": search_count,
            "checkoutStartCount": checkout_start_count,
            "purchaseCount": purchase_count,
        }

    def _compute_temporal_patterns(
        self, events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute temporal behavioral patterns"""
        if not events:
            return {
                "daysSinceFirstEvent": 0,
                "daysSinceLastEvent": 0,
                "mostActiveHour": None,
                "mostActiveDay": None,
            }

        # Sort events by time
        sorted_events = sorted(events, key=lambda e: e.get("occurredAt", ""))

        first_event_time = self._parse_datetime(sorted_events[0].get("occurredAt"))
        last_event_time = self._parse_datetime(sorted_events[-1].get("occurredAt"))
        current_time = datetime.now()

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
            event_time = self._parse_datetime(event.get("occurredAt"))
            if event_time:
                hours.append(event_time.hour)
                days.append(event_time.weekday())  # 0=Monday, 6=Sunday

        most_active_hour = Counter(hours).most_common(1)[0][0] if hours else None
        most_active_day = Counter(days).most_common(1)[0][0] if days else None

        return {
            "daysSinceFirstEvent": days_since_first,
            "daysSinceLastEvent": days_since_last,
            "mostActiveHour": most_active_hour,
            "mostActiveDay": most_active_day,
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
            event_data = event.get("eventData", {})
            if isinstance(event_data, str):
                try:
                    event_data = json.loads(event_data)
                except:
                    event_data = {}

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
            if event.get("eventType") in ["search_submitted", "search"]:
                search_term = event_data.get("query") or event_data.get("searchTerm")
                if search_term:
                    search_terms.append(search_term.lower())

            # Extract product categories
            category = event_data.get("category") or event_data.get("productType")
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

        return {
            "uniqueProductsViewed": len(unique_products),
            "uniqueCollectionsViewed": len(unique_collections),
            "searchTerms": unique_search_terms if unique_search_terms else [],
            "topCategories": top_categories if top_categories else [],
            "deviceType": device_types[0] if device_types else None,
            "primaryReferrer": referrers[0] if referrers else None,
        }

    def _compute_conversion_metrics(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Compute conversion rate metrics"""
        product_views = features.get("productViewCount", 0)
        cart_adds = features.get("cartAddCount", 0)
        purchases = features.get("purchaseCount", 0)
        searches = features.get("searchCount", 0)

        # Browse to cart rate
        browse_to_cart_rate = (cart_adds / product_views) if product_views > 0 else None

        # Cart to purchase rate
        cart_to_purchase_rate = (purchases / cart_adds) if cart_adds > 0 else None

        # Search to purchase rate
        search_to_purchase_rate = (purchases / searches) if searches > 0 else None

        return {
            "browseToCartRate": browse_to_cart_rate,
            "cartToPurchaseRate": cart_to_purchase_rate,
            "searchToPurchaseRate": search_to_purchase_rate,
        }

    def _compute_computed_scores(
        self, features: Dict[str, Any], events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute normalized behavioral scores (0-1)"""

        # Engagement Score (based on activity volume and diversity)
        total_events = features.get("totalEventCount", 0)
        session_count = features.get("sessionCount", 0)
        unique_products = features.get("uniqueProductsViewed", 0)

        # Normalize components (using log scale for large numbers)
        import math

        event_score = min(math.log10(total_events + 1) / 3, 1.0)  # Cap at 1000 events
        session_score = min(session_count / 20.0, 1.0)  # Cap at 20 sessions
        diversity_events = min(unique_products / 50.0, 1.0)  # Cap at 50 unique products

        engagement_score = (event_score + session_score + diversity_events) / 3.0

        # Recency Score (higher for more recent activity)
        days_since_last = features.get("daysSinceLastEvent", 365)
        recency_score = max(
            0, (30 - min(days_since_last, 30)) / 30.0
        )  # Linear decay over 30 days

        # Diversity Score (based on variety of activities)
        diversity_components = []
        if features.get("productViewCount", 0) > 0:
            diversity_components.append(1)
        if features.get("collectionViewCount", 0) > 0:
            diversity_components.append(1)
        if features.get("cartAddCount", 0) > 0:
            diversity_components.append(1)
        if features.get("searchCount", 0) > 0:
            diversity_components.append(1)
        if features.get("purchaseCount", 0) > 0:
            diversity_components.append(1)

        diversity_score = (
            sum(diversity_components) / 5.0
        )  # Max 5 different activity types

        # Behavioral Score (composite of all factors)
        conversion_quality = 0
        if features.get("browseToCartRate"):
            conversion_quality += min(
                features.get("browseToCartRate", 0) / 0.1, 1.0
            )  # Good rate is 10%
        if features.get("cartToPurchaseRate"):
            conversion_quality += min(
                features.get("cartToPurchaseRate", 0) / 0.3, 1.0
            )  # Good rate is 30%
        conversion_quality = conversion_quality / 2.0  # Average of both rates

        behavioral_score = (
            engagement_score * 0.4
            + recency_score * 0.2
            + diversity_score * 0.2
            + conversion_quality * 0.2
        )

        return {
            "engagementScore": engagement_score,
            "recencyScore": recency_score,
            "diversityScore": diversity_score,
            "behavioralScore": behavioral_score,
        }

    def _group_events_into_sessions(
        self, events: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Group events into sessions using 30-minute timeout"""
        if not events:
            return []

        # Sort events by time
        sorted_events = sorted(events, key=lambda e: e.get("occurredAt", ""))

        sessions = []
        current_session = [sorted_events[0]]

        for i in range(1, len(sorted_events)):
            current_event = sorted_events[i]
            previous_event = sorted_events[i - 1]

            current_time = self._parse_datetime(current_event.get("occurredAt"))
            previous_time = self._parse_datetime(previous_event.get("occurredAt"))

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
            return event_data["device"].get("type")

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

        if referrer:
            try:
                if "://" in referrer:
                    domain = referrer.split("://")[1].split("/")[0]
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
