"""
Adapter for checkout_completed events
"""

from typing import Dict, Any, Optional
from datetime import datetime

from .base_adapter import BaseInteractionEventAdapter


class CheckoutCompletedAdapter(BaseInteractionEventAdapter):
    """Adapter for checkout_completed events"""

    def __init__(self):
        super().__init__("checkout_completed")

    def extract_product_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from checkout_completed event (returns first line item)"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})

            # Get order line items
            order = data.get("order", {})
            line_items = order.get("lineItems", [])

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
        """Extract relevant metadata from checkout_completed event"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})
            order = data.get("order", {})

            return {
                "order_id": order.get("id", ""),
                "order_number": order.get("orderNumber", ""),
                "order_total": order.get("totalPrice", {}),
                "order_item_count": order.get("totalQuantity", 0),
                "order_line_count": len(order.get("lineItems", [])),
                "order_currency": order.get("currencyCode", ""),
                "order_status": order.get("fulfillmentStatus", ""),
                "order_payment_status": order.get("financialStatus", ""),
                "order_customer_email": order.get("email", ""),
                "order_customer_phone": order.get("phone", ""),
                "order_shipping_address": order.get("shippingAddress", {}),
                "order_billing_address": order.get("billingAddress", {}),
                "session_id": self.extract_session_id(event),
            }
        except Exception:
            return {}
