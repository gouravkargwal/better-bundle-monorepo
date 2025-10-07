"""
Adapter for search_submitted events
"""

from typing import Dict, Any, Optional
from datetime import datetime

from app.shared.helpers.datetime_utils import parse_iso_timestamp
from .base_adapter import BaseInteractionEventAdapter


class SearchSubmittedAdapter(BaseInteractionEventAdapter):
    """Adapter for search_submitted events"""

    def __init__(self):
        super().__init__("search_submitted")

    def extract_product_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from search_submitted event (returns first search result)"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})

            # Get search results
            search_results = data.get("results", [])

            # Return first product ID if available
            if search_results:
                first_result = search_results[0]
                product_id = first_result.get("id", "")
                if product_id:
                    return str(product_id)

            return None

        except Exception as e:
            return None

    def extract_customer_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract customer ID from event"""
        return event.get("customerId")

    def extract_timestamp(self, event: Dict[str, Any]) -> Optional[datetime]:
        """Extract timestamp from event"""
        try:
            timestamp = event.get("createdAt") or event.get("timestamp")
            if timestamp:
                if isinstance(timestamp, str):
                    return parse_iso_timestamp(timestamp)
                return timestamp
            return None
        except Exception:
            return None

    def extract_metadata(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant metadata from search_submitted event"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})

            return {
                "search_query": data.get("query", ""),
                "search_filters": data.get("filters", {}),
                "search_sort": data.get("sort", ""),
                "search_results_count": data.get("resultsCount", 0),
                "search_page": data.get("page", 1),
                "search_url": data.get("url", ""),
                "session_id": self.extract_session_id(event),
            }
        except Exception:
            return {}
