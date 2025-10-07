"""
Adapter for recommendation_add_to_cart events
"""

from typing import Dict, Any, Optional
from datetime import datetime

from app.shared.helpers.datetime_utils import parse_iso_timestamp
from .base_adapter import BaseInteractionEventAdapter


class RecommendationAddToCartAdapter(BaseInteractionEventAdapter):
    """Adapter for recommendation_add_to_cart events"""

    def __init__(self):
        super().__init__("recommendation_add_to_cart")

    def extract_product_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from recommendation_add_to_cart event"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})

            # Get product from cart line
            cart_line = data.get("cartLine", {})
            merchandise = cart_line.get("merchandise", {})
            product = merchandise.get("product", {})
            product_id = product.get("id", "")

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
        """Extract relevant metadata from recommendation_add_to_cart event"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})
            cart_line = data.get("cartLine", {})
            merchandise = cart_line.get("merchandise", {})
            product = merchandise.get("product", {})

            return {
                "product_title": product.get("title", ""),
                "product_price": product.get("price", 0),
                "product_type": product.get("type", ""),
                "product_vendor": product.get("vendor", ""),
                "product_url": product.get("url", ""),
                "variant_id": merchandise.get("id", ""),
                "quantity": cart_line.get("quantity", 1),
                "cart_line_cost": cart_line.get("cost", {}),
                "recommendation_type": data.get("type", ""),
                "recommendation_position": data.get("position", ""),
                "recommendation_widget": data.get("widget", ""),
                "recommendation_algorithm": data.get("algorithm", ""),
                "recommendation_confidence": data.get("confidence", 0.0),
                "page_url": data.get("pageUrl", ""),
                "session_id": self.extract_session_id(event),
            }
        except Exception:
            return {}
