"""
Search Product Feature Generator for ML feature engineering
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import json
import statistics

from app.core.logging import get_logger
from app.shared.helpers import now_utc
from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class SearchProductFeatureGenerator(BaseFeatureGenerator):
    """Feature generator for search query + product performance to match SearchProductFeatures schema"""

    async def generate_features(
        self, search_product_data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate features for a search query + product combination to match SearchProductFeatures schema

        Args:
            search_product_data: Dictionary containing:
                - searchQuery: The search query string
                - productId: The product ID being analyzed
            context: Additional context data:
                - shop: Shop data
                - behavioral_events: List of BehavioralEvents for search analysis

        Returns:
            Dictionary of generated features matching SearchProductFeatures schema
        """
        try:
            search_query = search_product_data.get("searchQuery", "")
            product_id = search_product_data.get("productId", "")

            logger.debug(
                f"Computing search-product features for query: '{search_query}' + product: {product_id}"
            )

            features = {}
            shop = context.get("shop", {})
            behavioral_events = context.get("behavioral_events", [])

            if not behavioral_events:
                return self._get_empty_search_product_features(
                    search_product_data, shop
                )

            # Basic identification features
            features.update(self._compute_basic_features(search_product_data, shop))

            # Search performance metrics from behavioral events
            features.update(
                self._compute_search_metrics(
                    search_query, product_id, behavioral_events
                )
            )

            # Conversion rates calculated from metrics
            features.update(self._compute_conversion_rates(features))

            # Temporal tracking
            features.update(
                self._compute_temporal_features(
                    search_query, product_id, behavioral_events
                )
            )

            # Validate and clean features
            features = self.validate_features(features)

            # Add lastComputedAt timestamp
            features["lastComputedAt"] = now_utc()

            logger.debug(
                f"Computed {len(features)} search-product features for '{search_query}' + {product_id}"
            )
            return features

        except Exception as e:
            logger.error(
                f"Failed to compute search-product features for {search_product_data.get('searchQuery', 'unknown')} + {search_product_data.get('productId', 'unknown')}: {str(e)}"
            )
            return {}

    def _get_empty_search_product_features(
        self, search_product_data: Dict[str, Any], shop: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Return empty search-product features when no events exist"""
        return {
            "shopId": shop.get("id", ""),
            "searchQuery": search_product_data.get("searchQuery", ""),
            "productId": search_product_data.get("productId", ""),
            "impressionCount": 0,
            "clickCount": 0,
            "purchaseCount": 0,
            "avgPosition": None,
            "clickThroughRate": None,
            "conversionRate": None,
            "lastOccurrence": None,
        }

    def _extract_session_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract session ID from event record"""
        # clientId is now stored directly in the event record
        return event.get("clientId")

    def _compute_basic_features(
        self, search_product_data: Dict[str, Any], shop: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compute basic identification features"""
        return {
            "shopId": shop.get("id", ""),
            "searchQuery": search_product_data.get("searchQuery", ""),
            "productId": search_product_data.get("productId", ""),
        }

    def _compute_search_metrics(
        self, search_query: str, product_id: str, events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute search performance metrics from behavioral events"""
        impression_count = 0
        click_count = 0
        purchase_count = 0
        positions = []

        # Group events by session to track search → view → purchase flows
        sessions = self._group_events_by_session(events)

        for session in sessions:
            # Find search events with this query in the session
            search_events = []
            for event in session:
                if (
                    event.get("eventType") in ["search_submitted", "search"]
                    and self._extract_search_query(event) == search_query
                ):
                    search_events.append(event)

            if not search_events:
                continue  # No search for this query in this session

            # Find product interactions after any search event in this session
            for i, event in enumerate(session):
                event_type = event.get("eventType", "")
                event_product_id = self._extract_product_id(event)

                if event_product_id == product_id:
                    # Check if this event happened after a search in the same session
                    event_time = self._parse_datetime(event.get("occurredAt"))

                    # Find if there was a search before this event in the session
                    search_before = False
                    for search_event in search_events:
                        search_time = self._parse_datetime(
                            search_event.get("occurredAt")
                        )
                        if search_time and event_time and search_time <= event_time:
                            search_before = True
                            break

                    if search_before:
                        if event_type in ["product_viewed", "product_view"]:
                            # This counts as both impression and click
                            impression_count += 1
                            click_count += 1

                            # Extract position if available
                            position = self._extract_search_position(event)
                            if position:
                                positions.append(position)

                        elif event_type in [
                            "search_result_shown",
                            "product_impression",
                        ]:
                            # Pure impression (shown but not clicked)
                            impression_count += 1

                            position = self._extract_search_position(event)
                            if position:
                                positions.append(position)

                        elif event_type in [
                            "purchase",
                            "checkout_completed",
                            "order_completed",
                        ]:
                            # Purchase after search
                            purchase_count += 1

        # Calculate average position
        avg_position = statistics.mean(positions) if positions else None

        return {
            "impressionCount": impression_count,
            "clickCount": click_count,
            "purchaseCount": purchase_count,
            "avgPosition": avg_position,
        }

    def _compute_conversion_rates(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Compute conversion rates from metrics"""
        impressions = features.get("impressionCount", 0)
        clicks = features.get("clickCount", 0)
        purchases = features.get("purchaseCount", 0)

        # Click-through rate (clicks / impressions)
        click_through_rate = (clicks / impressions) if impressions > 0 else None

        # Conversion rate (purchases / clicks)
        conversion_rate = (purchases / clicks) if clicks > 0 else None

        return {
            "clickThroughRate": click_through_rate,
            "conversionRate": conversion_rate,
        }

    def _compute_temporal_features(
        self, search_query: str, product_id: str, events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compute temporal features"""
        last_occurrence = None

        # Find the most recent event related to this search query + product combination
        for event in reversed(sorted(events, key=lambda e: e.get("occurredAt", ""))):
            event_type = event.get("eventType", "")

            # Check if this event is related to our search query + product
            is_search_event = (
                event_type in ["search_submitted", "search"]
                and self._extract_search_query(event) == search_query
            )

            is_product_event = self._extract_product_id(
                event
            ) == product_id and event_type in [
                "product_viewed",
                "product_view",
                "purchase",
                "checkout_completed",
            ]

            if is_search_event or is_product_event:
                last_occurrence = self._parse_datetime(event.get("occurredAt"))
                break

        return {
            "lastOccurrence": last_occurrence,
        }

    def _group_events_by_session(
        self, events: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Group events into sessions using session timeout and customer/session ID"""
        if not events:
            return []

        # Sort events by time
        sorted_events = sorted(events, key=lambda e: e.get("occurredAt", ""))

        sessions = []
        current_session = [sorted_events[0]]
        current_customer_id = sorted_events[0].get("customerId")

        for i in range(1, len(sorted_events)):
            current_event = sorted_events[i]
            previous_event = sorted_events[i - 1]

            # Check if same customer/session
            same_customer = current_event.get("customerId") == current_customer_id

            # Check time gap
            current_time = self._parse_datetime(current_event.get("occurredAt"))
            previous_time = self._parse_datetime(previous_event.get("occurredAt"))

            time_gap_minutes = 0
            if current_time and previous_time:
                time_gap_minutes = (current_time - previous_time).total_seconds() / 60

            # New session if different customer or > 30 minutes gap
            if not same_customer or time_gap_minutes > 30:
                sessions.append(current_session)
                current_session = [current_event]
                current_customer_id = current_event.get("customerId")
            else:
                current_session.append(current_event)

        sessions.append(current_session)
        return sessions

    def _extract_search_query(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract search query from search event"""
        event_data = event.get("eventData", {})
        if isinstance(event_data, str):
            try:
                event_data = json.loads(event_data)
            except:
                event_data = {}

        # Try different possible field names for search query
        query = (
            event_data.get("query")
            or event_data.get("searchQuery")
            or event_data.get("searchTerm")
            or event_data.get("q")
        )

        return query.lower().strip() if query else None

    def _extract_product_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from event"""
        event_data = event.get("eventData", {})
        if isinstance(event_data, str):
            try:
                event_data = json.loads(event_data)
            except:
                event_data = {}

        return (
            event_data.get("productId")
            or event_data.get("product_id")
            or event_data.get("id")
        )

    def _extract_search_position(self, event: Dict[str, Any]) -> Optional[int]:
        """Extract search result position from event"""
        event_data = event.get("eventData", {})
        if isinstance(event_data, str):
            try:
                event_data = json.loads(event_data)
            except:
                event_data = {}

        # Try different field names for position
        position = (
            event_data.get("position")
            or event_data.get("searchPosition")
            or event_data.get("rank")
            or event_data.get("index")
        )

        try:
            return int(position) if position is not None else None
        except (ValueError, TypeError):
            return None

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
