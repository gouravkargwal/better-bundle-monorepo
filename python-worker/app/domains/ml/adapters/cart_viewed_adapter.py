"""
Adapter for cart_viewed events
"""

from typing import Dict, Any, Optional
from datetime import datetime

from .base_adapter import BaseInteractionEventAdapter


class CartViewedAdapter(BaseInteractionEventAdapter):
    """Adapter for cart_viewed events"""

    def __init__(self):
        super().__init__("cart_viewed")

    def extract_product_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from cart_viewed event (returns first product in cart)"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})

            # Get cart line items
            cart = data.get("cart", {})
            line_items = cart.get("lines", [])

            # Return first product ID if available
            if line_items:
                first_item = line_items[0]
                merchandise = first_item.get("merchandise", {})
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
                    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                return timestamp
            return None
        except Exception:
            return None

    def extract_metadata(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant metadata from cart_viewed event"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})
            cart = data.get("cart", {})

            return {
                "cart_id": cart.get("id", ""),
                "cart_total": cart.get("totalPrice", {}),
                "cart_item_count": cart.get("totalQuantity", 0),
                "cart_line_count": len(cart.get("lines", [])),
                "cart_currency": cart.get("currencyCode", ""),
                "session_id": self.extract_session_id(event),
            }
        except Exception:
            return {}
