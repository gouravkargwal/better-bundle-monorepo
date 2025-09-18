"""
Adapter for customer_linked events
"""

from typing import Dict, Any, Optional
from datetime import datetime

from .base_adapter import BaseInteractionEventAdapter


class CustomerLinkedAdapter(BaseInteractionEventAdapter):
    """Adapter for customer_linked events"""

    def __init__(self):
        super().__init__("customer_linked")

    def extract_product_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from customer_linked event (no product associated)"""
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
        """Extract relevant metadata from customer_linked event"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})
            customer = data.get("customer", {})

            return {
                "customer_id": customer.get("id", ""),
                "customer_email": customer.get("email", ""),
                "customer_phone": customer.get("phone", ""),
                "customer_first_name": customer.get("firstName", ""),
                "customer_last_name": customer.get("lastName", ""),
                "customer_created_at": customer.get("createdAt", ""),
                "customer_accepts_marketing": customer.get("acceptsMarketing", False),
                "customer_orders_count": customer.get("ordersCount", 0),
                "customer_total_spent": customer.get("totalSpent", {}),
                "session_id": self.extract_session_id(event),
            }
        except Exception:
            return {}
