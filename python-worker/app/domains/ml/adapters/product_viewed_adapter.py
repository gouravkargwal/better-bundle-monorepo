"""
Adapter for product_viewed events
"""

from typing import Dict, Any, Optional
from datetime import datetime

from .base_adapter import BaseInteractionEventAdapter


class ProductViewedAdapter(BaseInteractionEventAdapter):
    """Adapter for product_viewed events"""

    def __init__(self):
        super().__init__("product_viewed")

    def extract_product_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from product_viewed event"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})

            # Handle nested structure: metadata.data.productVariant.product.id
            product_variant = data.get("productVariant", {})
            product = product_variant.get("product", {})
            product_id = product.get("id", "")

            if product_id:
                return str(product_id)

            # Fallback: try direct structure
            if "productVariant" in metadata:
                product_variant = metadata.get("productVariant", {})
                product = product_variant.get("product", {})
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
            # Try different timestamp fields
            timestamp = event.get("createdAt") or event.get("timestamp")
            if timestamp:
                if isinstance(timestamp, str):
                    from datetime import datetime

                    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                return timestamp
            return None
        except Exception:
            return None

    def extract_metadata(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant metadata from product_viewed event"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})
            product_variant = data.get("productVariant", {})
            product = product_variant.get("product", {})

            return {
                "product_title": product.get("title", ""),
                "product_price": product.get("price", 0),
                "product_type": product.get("type", ""),
                "product_vendor": product.get("vendor", ""),
                "product_url": product.get("url", ""),
                "variant_id": product_variant.get("id", ""),
                "page_url": metadata.get("page_url", ""),
                "referrer": metadata.get("referrer", ""),
                "user_agent": metadata.get("user_agent", ""),
                "session_id": self.extract_session_id(event),
            }
        except Exception:
            return {}
