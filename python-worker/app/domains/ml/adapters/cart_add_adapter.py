"""
Adapter for product_added_to_cart events
"""
from typing import Dict, Any, Optional
from datetime import datetime

from .base_adapter import BaseInteractionEventAdapter


class CartAddAdapter(BaseInteractionEventAdapter):
    """Adapter for product_added_to_cart events"""
    
    def __init__(self):
        super().__init__("product_added_to_cart")
    
    def extract_product_id(self, event: Dict[str, Any]) -> Optional[str]:
        """Extract product ID from product_added_to_cart event"""
        try:
            metadata = event.get("metadata", {})
            data = metadata.get("data", {})
            
            # Handle nested structure: metadata.data.cartLine.merchandise.product.id
            cart_line = data.get("cartLine", {})
            merchandise = cart_line.get("merchandise", {})
            product = merchandise.get("product", {})
            product_id = product.get("id", "")
            
            if product_id:
                return str(product_id)
            
            # Fallback: try direct structure
            if "cartLine" in metadata:
                cart_line = metadata.get("cartLine", {})
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
                    from datetime import datetime
                    return datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                return timestamp
            return None
        except Exception:
            return None
    
    def extract_metadata(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant metadata from product_added_to_cart event"""
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
                "session_id": self.extract_session_id(event)
            }
        except Exception:
            return {}
