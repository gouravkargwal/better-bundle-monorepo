"""
Adapter for collection_viewed events
"""

from typing import Dict, Any, Optional
from datetime import datetime

from .base_adapter import BaseInteractionEventAdapter


class CollectionViewedAdapter(BaseInteractionEventAdapter):
    """Adapter for collection_viewed events"""

    def __init__(self):
        super().__init__("collection_viewed")

    def extract_product_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from collection_viewed event (returns first product in collection)"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})

            # Get collection products
            collection = data.get("collection", {})
            products = collection.get("products", [])

            # Return first product ID if available
            if products:
                first_product = products[0]
                product_id = first_product.get("id", "")
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
        """Extract relevant metadata from collection_viewed event"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})
            collection = data.get("collection", {})

            return {
                "collection_id": collection.get("id", ""),
                "collection_title": collection.get("title", ""),
                "collection_handle": collection.get("handle", ""),
                "collection_description": collection.get("description", ""),
                "collection_product_count": collection.get("productsCount", 0),
                "collection_url": collection.get("url", ""),
                "session_id": self.extract_session_id(event),
            }
        except Exception:
            return {}
