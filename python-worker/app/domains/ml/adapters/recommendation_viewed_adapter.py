"""
Adapter for recommendation_viewed events
"""

from typing import Dict, Any, Optional
from datetime import datetime

from app.shared.helpers.datetime_utils import parse_iso_timestamp
from .base_adapter import BaseInteractionEventAdapter


class RecommendationViewedAdapter(BaseInteractionEventAdapter):
    """Adapter for recommendation_viewed events"""

    def __init__(self):
        super().__init__("recommendation_viewed")

    def extract_product_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from recommendation_viewed event"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})

            # Get recommendation products
            recommendations = data.get("recommendations", [])

            # Return first product ID if available
            if recommendations:
                first_recommendation = recommendations[0]
                product_id = first_recommendation.get("id", "")
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
        """Extract relevant metadata from recommendation_viewed event"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})

            return {
                "recommendation_type": data.get("type", ""),
                "recommendation_position": data.get("position", ""),
                "recommendation_widget": data.get("widget", ""),
                "recommendation_algorithm": data.get("algorithm", ""),
                "recommendation_confidence": data.get("confidence", 0.0),
                "recommendation_count": len(data.get("recommendations", [])),
                "page_url": data.get("pageUrl", ""),
                "session_id": self.extract_session_id(event),
            }
        except Exception:
            return {}
