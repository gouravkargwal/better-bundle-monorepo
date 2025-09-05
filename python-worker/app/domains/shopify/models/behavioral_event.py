"""
Behavioral Event model for Shopify Web Pixel events
"""

from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class BehavioralEvent(BaseModel):
    """Model representing a behavioral event from Shopify Web Pixels"""

    event_id: str = Field(..., alias="eventId", description="Unique event identifier")
    shop_id: str = Field(..., alias="shopId", description="Shop identifier")
    customer_id: Optional[str] = Field(
        None, alias="customerId", description="Customer identifier"
    )
    event_type: str = Field(
        ..., alias="eventType", description="Type of behavioral event"
    )
    occurred_at: datetime = Field(
        ..., alias="occurredAt", description="When the event occurred"
    )
    event_data: Optional[Dict[str, Any]] = Field(
        None, alias="eventData", description="Event-specific data"
    )

    class Config:
        allow_population_by_field_name = True
        json_encoders = {datetime: lambda v: v.isoformat()}

    @property
    def is_page_viewed(self) -> bool:
        """Check if this is a page viewed event"""
        return self.event_type == "page_viewed"

    @property
    def is_product_viewed(self) -> bool:
        """Check if this is a product viewed event"""
        return self.event_type == "product_viewed"

    @property
    def is_product_added_to_cart(self) -> bool:
        """Check if this is a product added to cart event"""
        return self.event_type == "product_added_to_cart"

    @property
    def is_collection_viewed(self) -> bool:
        """Check if this is a collection viewed event"""
        return self.event_type == "collection_viewed"

    @property
    def is_search_submitted(self) -> bool:
        """Check if this is a search submitted event"""
        return self.event_type == "search_submitted"

    @property
    def is_checkout_started(self) -> bool:
        """Check if this is a checkout started event"""
        return self.event_type == "checkout_started"

    @property
    def is_checkout_completed(self) -> bool:
        """Check if this is a checkout completed event"""
        return self.event_type == "checkout_completed"

    def get_product_id(self) -> Optional[str]:
        """Extract product ID from event data if available"""
        if not self.event_data:
            return None

        # For product_viewed events
        if self.is_product_viewed:
            product_variant = self.event_data.get("productVariant", {})
            return product_variant.get("productId")

        # For product_added_to_cart events
        if self.is_product_added_to_cart:
            product_variant = self.event_data.get("productVariant", {})
            return product_variant.get("productId")

        # For checkout events
        if self.is_checkout_started or self.is_checkout_completed:
            checkout = self.event_data.get("checkout", {})
            products = checkout.get("products", [])
            if products:
                return products[0].get("productId")

        return None

    def get_product_variant_id(self) -> Optional[str]:
        """Extract product variant ID from event data if available"""
        if not self.event_data:
            return None

        # For product_viewed events
        if self.is_product_viewed:
            product_variant = self.event_data.get("productVariant", {})
            return product_variant.get("id")

        # For product_added_to_cart events
        if self.is_product_added_to_cart:
            product_variant = self.event_data.get("productVariant", {})
            return product_variant.get("id")

        return None

    def get_collection_id(self) -> Optional[str]:
        """Extract collection ID from event data if available"""
        if not self.event_data:
            return None

        if self.is_collection_viewed:
            return self.event_data.get("collectionId")

        return None

    def get_search_query(self) -> Optional[str]:
        """Extract search query from event data if available"""
        if not self.event_data:
            return None

        if self.is_search_submitted:
            return self.event_data.get("query")

        return None

    def get_page_url(self) -> Optional[str]:
        """Extract page URL from event data if available"""
        if not self.event_data:
            return None

        if self.is_page_viewed:
            return self.event_data.get("url")

        return None

    def get_cart_value(self) -> Optional[float]:
        """Extract cart value from event data if available"""
        if not self.event_data:
            return None

        # For product_added_to_cart events
        if self.is_product_added_to_cart:
            cart = self.event_data.get("cart", {})
            lines = cart.get("lines", [])
            total = 0.0
            for line in lines:
                price = line.get("price", 0.0)
                quantity = line.get("quantity", 1)
                total += price * quantity
            return total

        # For checkout events
        if self.is_checkout_started or self.is_checkout_completed:
            checkout = self.event_data.get("checkout", {})
            return checkout.get("totalPrice")

        return None

    def get_product_price(self) -> Optional[float]:
        """Extract product price from event data if available"""
        if not self.event_data:
            return None

        # For product_viewed events
        if self.is_product_viewed:
            product_variant = self.event_data.get("productVariant", {})
            return product_variant.get("price")

        # For product_added_to_cart events
        if self.is_product_added_to_cart:
            product_variant = self.event_data.get("productVariant", {})
            return product_variant.get("price")

        return None

    def get_quantity(self) -> Optional[int]:
        """Extract quantity from event data if available"""
        if not self.event_data:
            return None

        if self.is_product_added_to_cart:
            return self.event_data.get("quantity", 1)

        return None
