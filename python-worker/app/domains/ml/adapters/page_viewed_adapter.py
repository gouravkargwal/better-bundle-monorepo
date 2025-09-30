"""
Adapter for page_viewed events
"""

from typing import Dict, Any, Optional
from datetime import datetime

from .base_adapter import BaseInteractionEventAdapter


class PageViewedAdapter(BaseInteractionEventAdapter):
    """Adapter for page_viewed events"""

    def __init__(self):
        super().__init__("page_viewed")

    def extract_product_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from page_viewed event (if it's a product page)"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})

            # Check if it's a product page
            page_type = data.get("pageType", "")
            if page_type == "product":
                # Handle product page structure
                product = data.get("product", {})
                product_id = product.get("id", "")
                if product_id:
                    return str(product_id)

            # Check URL-based extraction for product pages
            page_url = data.get("url", "")
            if "/products/" in page_url:
                # Extract product handle from URL
                url_parts = page_url.split("/products/")
                if len(url_parts) > 1:
                    product_handle = url_parts[1].split("?")[0].split("#")[0]
                    # Note: This would need product lookup by handle to get ID
                    # For now, return None as we need the actual product ID
                    pass

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
                    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                return timestamp
            return None
        except Exception:
            return None

    def extract_metadata(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant metadata from page_viewed event"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})

            return {
                "page_type": data.get("pageType", ""),
                "page_url": data.get("url", ""),
                "page_title": data.get("title", ""),
                "referrer": data.get("referrer", ""),
                "user_agent": data.get("userAgent", ""),
                "viewport": data.get("viewport", {}),
                "session_id": self.extract_session_id(event),
            }
        except Exception:
            return {}
