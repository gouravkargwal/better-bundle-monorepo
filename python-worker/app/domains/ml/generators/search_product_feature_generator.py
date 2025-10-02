"""
Optimized Search Product Feature Generator for State-of-the-Art Gorse Integration
Focuses on search-to-product relevance signals that actually improve recommendation quality
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import statistics
from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.domains.ml.adapters.adapter_factory import InteractionEventAdapterFactory
from .base_feature_generator import BaseFeatureGenerator

logger = get_logger(__name__)


class SearchProductFeatureGenerator(BaseFeatureGenerator):
    """State-of-the-art search-product feature generator optimized for Gorse search recommendations"""

    def __init__(self):
        super().__init__()
        self.adapter_factory = InteractionEventAdapterFactory()

    async def generate_features(
        self, search_product_data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate optimized search-product features for Gorse

        Args:
            search_product_data: Dictionary containing searchQuery and productId
            context: Additional context data (shop, behavioral_events)

        Returns:
            Dictionary with minimal, high-signal search-product features for Gorse
        """
        try:
            search_query = search_product_data.get("searchQuery", "").lower().strip()
            product_id = search_product_data.get("productId", "")

            logger.debug(
                f"Computing optimized search-product features for: '{search_query}' + {product_id}"
            )

            if not search_query or not product_id:
                return self._get_minimal_default_features(search_product_data, context)

            behavioral_events = context.get("behavioral_events", [])

            if not behavioral_events:
                return self._get_minimal_default_features(search_product_data, context)

            # Core Gorse-optimized search-product features
            features = {
                "shop_id": context.get("shop", {}).get("id", ""),
                "search_query": search_query,
                "product_id": product_id,
                # === CORE SEARCH RELEVANCE SIGNALS ===
                # These are the most predictive for search-based recommendations
                "search_click_rate": self._compute_search_click_rate(
                    search_query, product_id, behavioral_events
                ),
                "search_conversion_rate": self._compute_search_conversion_rate(
                    search_query, product_id, behavioral_events
                ),
                "search_relevance_score": self._compute_search_relevance_score(
                    search_query, product_id, behavioral_events
                ),
                # === PERFORMANCE METRICS ===
                # High-level patterns Gorse can use for search result ranking
                "total_search_interactions": self._compute_total_search_interactions(
                    search_query, product_id, behavioral_events
                ),
                "search_to_purchase_count": self._compute_search_to_purchase_count(
                    search_query, product_id, behavioral_events
                ),
                # === TEMPORAL SIGNALS ===
                # Recent search performance is most predictive
                "days_since_last_search_interaction": self._compute_days_since_last_interaction(
                    search_query, product_id, behavioral_events
                ),
                "search_recency_score": self._compute_search_recency_score(
                    search_query, product_id, behavioral_events
                ),
                # === QUERY-PRODUCT MATCH QUALITY ===
                # Critical for understanding search intent alignment
                "semantic_match_score": self._compute_semantic_match_score(
                    search_query, product_id, context
                ),
                "search_intent_alignment": self._compute_search_intent_alignment(
                    search_query, product_id, behavioral_events
                ),
                "last_computed_at": now_utc(),
            }

            return features

        except Exception as e:
            logger.error(
                f"Failed to compute optimized search-product features: {str(e)}"
            )
            return self._get_minimal_default_features(search_product_data, context)

    def _compute_search_click_rate(
        self, search_query: str, product_id: str, events: List[Dict[str, Any]]
    ) -> float:
        """Compute click rate for this product when searched - core relevance signal"""
        search_impressions = 0
        search_clicks = 0

        # Track search sessions that led to product interactions
        search_sessions = self._get_search_sessions(search_query, events)

        for session in search_sessions:
            # Count search impressions (when query was submitted)
            search_impressions += 1

            # Check if this session had a click on our product
            for event in session:
                if self.adapter_factory.extract_product_id(
                    event
                ) == product_id and event.get("interactionType") in [
                    "product_viewed",
                    "product_added_to_cart",
                ]:
                    search_clicks += 1
                    break  # Only count once per session

        if search_impressions == 0:
            return 0.0

        click_rate = search_clicks / search_impressions
        return round(min(1.0, click_rate), 3)

    def _compute_search_conversion_rate(
        self, search_query: str, product_id: str, events: List[Dict[str, Any]]
    ) -> float:
        """Compute conversion rate for search → product → purchase flow"""
        search_clicks = 0
        search_conversions = 0

        search_sessions = self._get_search_sessions(search_query, events)

        for session in search_sessions:
            has_product_interaction = False
            has_purchase = False

            for event in session:
                event_product_id = self.adapter_factory.extract_product_id(event)

                if event_product_id == product_id:
                    if event.get("interactionType") in [
                        "product_viewed",
                        "product_added_to_cart",
                    ]:
                        has_product_interaction = True
                    elif self.adapter_factory.is_purchase_event(event):
                        has_purchase = True

            if has_product_interaction:
                search_clicks += 1
                if has_purchase:
                    search_conversions += 1

        if search_clicks == 0:
            return 0.0

        conversion_rate = search_conversions / search_clicks
        return round(min(1.0, conversion_rate), 3)

    def _compute_search_relevance_score(
        self, search_query: str, product_id: str, events: List[Dict[str, Any]]
    ) -> float:
        """Compute overall relevance score combining multiple signals"""
        click_rate = self._compute_search_click_rate(search_query, product_id, events)
        conversion_rate = self._compute_search_conversion_rate(
            search_query, product_id, events
        )

        # Weighted combination: clicks matter more for discovery, conversions for quality
        relevance_score = (click_rate * 0.4) + (conversion_rate * 0.6)
        return round(relevance_score, 3)

    def _compute_total_search_interactions(
        self, search_query: str, product_id: str, events: List[Dict[str, Any]]
    ) -> int:
        """Count total interactions for this search-product pair"""
        interaction_count = 0

        search_sessions = self._get_search_sessions(search_query, events)

        for session in search_sessions:
            for event in session:
                if self.adapter_factory.extract_product_id(
                    event
                ) == product_id and event.get("interactionType") in [
                    "product_viewed",
                    "product_added_to_cart",
                    "checkout_completed",
                ]:
                    interaction_count += 1

        return interaction_count

    def _compute_search_to_purchase_count(
        self, search_query: str, product_id: str, events: List[Dict[str, Any]]
    ) -> int:
        """Count direct search → purchase conversions"""
        purchase_count = 0

        search_sessions = self._get_search_sessions(search_query, events)

        for session in search_sessions:
            has_purchase = False
            for event in session:
                if self.adapter_factory.extract_product_id(
                    event
                ) == product_id and self.adapter_factory.is_purchase_event(event):
                    has_purchase = True
                    break

            if has_purchase:
                purchase_count += 1

        return purchase_count

    def _compute_days_since_last_interaction(
        self, search_query: str, product_id: str, events: List[Dict[str, Any]]
    ) -> Optional[int]:
        """Days since last search-product interaction - recency signal"""
        last_interaction_time = None

        search_sessions = self._get_search_sessions(search_query, events)

        for session in search_sessions:
            for event in session:
                if self.adapter_factory.extract_product_id(event) == product_id:
                    event_time = self._parse_datetime(event.get("timestamp"))
                    if event_time:
                        if (
                            not last_interaction_time
                            or event_time > last_interaction_time
                        ):
                            last_interaction_time = event_time

        if not last_interaction_time:
            return None

        return (now_utc() - last_interaction_time).days

    def _compute_search_recency_score(
        self, search_query: str, product_id: str, events: List[Dict[str, Any]]
    ) -> float:
        """Compute recency score for search-product pair (0-1)"""
        days_since_last = self._compute_days_since_last_interaction(
            search_query, product_id, events
        )

        if days_since_last is None:
            return 0.0

        # Exponential decay: 1.0 for today, 0.5 for 7 days ago, 0.1 for 30 days ago
        recency_score = max(0.0, 1.0 - (days_since_last / 30.0))
        return round(recency_score, 3)

    def _compute_semantic_match_score(
        self, search_query: str, product_id: str, context: Dict[str, Any]
    ) -> float:
        """Compute semantic match between query and product - simplified approach"""
        # Get product information from context
        products = context.get("products", [])
        product_info = next(
            (p for p in products if p.get("product_id") == product_id), None
        )

        if not product_info:
            return 0.0

        # Simple keyword matching approach (can be enhanced with embeddings later)
        query_words = set(search_query.lower().split())

        # Check product title
        title = (product_info.get("title", "") or "").lower()
        title_words = set(title.split())

        # Check product type/category
        product_type = (product_info.get("productType", "") or "").lower()
        type_words = set(product_type.split())

        # Check tags
        tags = product_info.get("tags", [])
        tag_words = set()
        for tag in tags:
            if isinstance(tag, str):
                tag_words.update(tag.lower().split())

        # Combine all product text
        all_product_words = title_words | type_words | tag_words

        # Calculate overlap
        if not query_words or not all_product_words:
            return 0.0

        overlap = len(query_words & all_product_words)
        max_possible_overlap = len(query_words)

        match_score = overlap / max_possible_overlap
        return round(min(1.0, match_score), 3)

    def _compute_search_intent_alignment(
        self, search_query: str, product_id: str, events: List[Dict[str, Any]]
    ) -> str:
        """Determine how well product aligns with search intent"""
        click_rate = self._compute_search_click_rate(search_query, product_id, events)
        conversion_rate = self._compute_search_conversion_rate(
            search_query, product_id, events
        )

        # Classify intent alignment
        if conversion_rate >= 0.3:  # 30%+ conversion rate
            return "high_intent"
        elif conversion_rate >= 0.1:  # 10-30% conversion rate
            return "medium_intent"
        elif click_rate >= 0.2:  # 20%+ click rate but low conversion
            return "browsing_intent"
        elif click_rate > 0:  # Some clicks but very low conversion
            return "low_intent"
        else:
            return "no_intent"

    def _get_search_sessions(
        self, search_query: str, events: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Get sessions that contain the specified search query"""
        # Group events by session
        sessions = self._group_events_by_session(events)

        # Filter sessions that contain our search query
        search_sessions = []
        for session in sessions:
            has_search_query = False
            for event in session:
                if (
                    event.get("interactionType") in ["search_submitted", "search"]
                    and self._extract_search_query(event) == search_query
                ):
                    has_search_query = True
                    break

            if has_search_query:
                search_sessions.append(session)

        return search_sessions

    def _group_events_by_session(
        self, events: List[Dict[str, Any]]
    ) -> List[List[Dict[str, Any]]]:
        """Group events into sessions with 30-minute timeout"""
        if not events:
            return []

        # Sort events by time
        sorted_events = sorted(events, key=lambda e: e.get("timestamp", ""))

        sessions = []
        current_session = [sorted_events[0]]

        for i in range(1, len(sorted_events)):
            current_event = sorted_events[i]
            previous_event = sorted_events[i - 1]

            # Check time gap
            current_time = self._parse_datetime(current_event.get("timestamp"))
            previous_time = self._parse_datetime(previous_event.get("timestamp"))

            if current_time and previous_time:
                time_gap_minutes = (current_time - previous_time).total_seconds() / 60

                # New session if > 30 minutes gap or different customer
                if time_gap_minutes > 30 or current_event.get(
                    "customer_id"
                ) != previous_event.get("customer_id"):
                    sessions.append(current_session)
                    current_session = [current_event]
                else:
                    current_session.append(current_event)
            else:
                current_session.append(current_event)

        sessions.append(current_session)
        return sessions

    def _extract_search_query(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract search query from event"""
        return self.adapter_factory.extract_search_query(event)

    def _parse_datetime(self, datetime_str: Any) -> Optional[datetime]:
        """Parse datetime from various formats"""
        if not datetime_str:
            return None

        if isinstance(datetime_str, datetime):
            return datetime_str

        if isinstance(datetime_str, str):
            try:
                return datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
            except:
                return None

        return None

    def _get_minimal_default_features(
        self, search_product_data: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Return minimal default features when computation fails"""
        return {
            "shop_id": context.get("shop", {}).get("id", ""),
            "search_query": search_product_data.get("searchQuery", "").lower().strip(),
            "product_id": search_product_data.get("productId", ""),
            "search_click_rate": 0.0,
            "search_conversion_rate": 0.0,
            "search_relevance_score": 0.0,
            "total_search_interactions": 0,
            "search_to_purchase_count": 0,
            "days_since_last_search_interaction": None,
            "search_recency_score": 0.0,
            "semantic_match_score": 0.0,
            "search_intent_alignment": "no_intent",
            "last_computed_at": now_utc(),
        }
