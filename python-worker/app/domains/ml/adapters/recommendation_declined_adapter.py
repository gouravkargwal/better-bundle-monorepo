"""
Adapter for recommendation_declined events
"""

from typing import Dict, Any, Optional
from datetime import datetime

from app.shared.helpers.datetime_utils import parse_iso_timestamp
from .base_adapter import BaseInteractionEventAdapter
from app.core.logging import get_logger

logger = get_logger(__name__)


class RecommendationDeclinedAdapter(BaseInteractionEventAdapter):
    """Adapter for recommendation_declined events"""

    def __init__(self):
        super().__init__("recommendation_declined")

    def extract_product_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from recommendation_declined event"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})

            # Get declined product
            product = data.get("product", {})
            product_id = product.get("id", "")

            if product_id:
                return str(product_id)

            return None
        except Exception as e:
            logger.error(
                f"Failed to extract product ID from recommendation_declined event: {str(e)}"
            )
            return None

    def extract_metadata(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant metadata from recommendation_declined event"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})
            product = data.get("product", {})

            return {
                "product_title": product.get("title", ""),
                "product_price": product.get("price", 0),
                "product_type": product.get("type", ""),
                "product_vendor": product.get("vendor", ""),
                "recommendation_type": data.get("type", ""),
                "recommendation_position": data.get("position", ""),
                "recommendation_widget": data.get("widget", ""),
                "recommendation_algorithm": data.get("algorithm", ""),
                "recommendation_confidence": data.get("confidence", 0.0),
                "decline_reason": data.get("decline_reason", "user_declined"),
                "session_id": self.extract_session_id(event),
            }
        except Exception as e:
            logger.error(
                f"Failed to extract metadata from recommendation_declined event: {str(e)}"
            )
            return {}

    def extract_session_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract session ID from recommendation_declined event"""
        try:
            return event.get("session_id", "")
        except Exception:
            return None

    def extract_timestamp(self, event: Dict[str, Any]) -> Optional[datetime]:
        """Extract timestamp from recommendation_declined event"""
        try:
            timestamp_str = event.get("created_at", "")
            if timestamp_str:
                return parse_iso_timestamp(timestamp_str)
            return None
        except Exception as e:
            logger.error(
                f"Failed to extract timestamp from recommendation_declined event: {str(e)}"
            )
            return None

    def extract_customer_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract customer ID from recommendation_declined event"""
        try:
            return event.get("customer_id", "")
        except Exception:
            return None

    def extract_shop_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract shop ID from recommendation_declined event"""
        try:
            return event.get("shop_id", "")
        except Exception:
            return None
