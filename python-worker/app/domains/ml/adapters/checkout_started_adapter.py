"""
Adapter for checkout_started events
"""

from typing import Dict, Any, Optional
from datetime import datetime

from .base_adapter import BaseInteractionEventAdapter


class CheckoutStartedAdapter(BaseInteractionEventAdapter):
    """Adapter for checkout_started events"""

    def __init__(self):
        super().__init__("checkout_started")

    def extract_product_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from checkout_started event (returns first line item)"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})

            # Get checkout line items
            checkout = data.get("checkout", {})
            line_items = checkout.get("lineItems", [])

            # Return first product ID if available
            if line_items:
                first_item = line_items[0]
                variant = first_item.get("variant", {})
                product = variant.get("product", {})
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
        """Extract relevant metadata from checkout_started event"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})
            checkout = data.get("checkout", {})

            return {
                "checkout_id": checkout.get("id", ""),
                "checkout_total": checkout.get("totalPrice", {}),
                "checkout_item_count": checkout.get("totalQuantity", 0),
                "checkout_line_count": len(checkout.get("lineItems", [])),
                "checkout_currency": checkout.get("currencyCode", ""),
                "checkout_email": checkout.get("email", ""),
                "checkout_phone": checkout.get("phone", ""),
                "session_id": self.extract_session_id(event),
            }
        except Exception:
            return {}
