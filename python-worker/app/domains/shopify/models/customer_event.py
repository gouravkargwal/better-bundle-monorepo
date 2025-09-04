"""
Shopify customer event model for BetterBundle Python Worker
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.shared.helpers import now_utc


class ShopifyCustomerEvent(BaseModel):
    """Shopify customer event model - simplified for customer-based events"""

    # Core event information
    id: str = Field(..., description="Event ID")
    event_type: str = Field(..., description="Type of event (__typename from GraphQL)")
    description: Optional[str] = Field(None, description="Event description")

    # Related entities
    customer_id: Optional[str] = Field(None, description="Related customer ID")

    # Timestamps
    created_at: datetime = Field(
        default_factory=now_utc, description="Event creation date"
    )
    updated_at: datetime = Field(
        default_factory=now_utc, description="Last update date"
    )

    # BetterBundle specific fields
    bb_last_sync: Optional[datetime] = Field(None, description="Last BetterBundle sync")
    bb_ml_features_computed: bool = Field(False, description="ML features computed")

    # Raw data storage
    raw_data: Dict[str, Any] = Field(
        default_factory=dict, description="Raw Shopify API response"
    )

    class Config:
        json_encoders = {"datetime": lambda v: v.isoformat()}

    @property
    def is_active(self) -> bool:
        """Check if event is currently active (always true for customer events)"""
        return True

    @property
    def has_related_entities(self) -> bool:
        """Check if event has related entities"""
        return bool(self.customer_id)

    @property
    def days_since_creation(self) -> int:
        """Get days since event creation"""
        return (now_utc() - self.created_at).days

    @property
    def days_since_update(self) -> int:
        """Get days since last update"""
        return (now_utc() - self.updated_at).days

    @property
    def event_category(self) -> str:
        """Get event category based on type"""
        if "order" in self.event_type.lower():
            return "order_event"
        elif "customer" in self.event_type.lower():
            return "customer_event"
        elif "product" in self.event_type.lower():
            return "product_event"
        else:
            return "other"

    def get_ml_features(self) -> Dict[str, Any]:
        """Get ML-relevant features for this event"""
        return {
            "event_id": self.id,
            "event_type": self.event_type,
            "event_category": self.event_category,
            "is_active": self.is_active,
            "has_related_entities": self.has_related_entities,
            "days_since_creation": self.days_since_creation,
            "days_since_update": self.days_since_update,
            "customer_id": self.customer_id or "none",
        }

    def update_from_raw_data(self, raw_data: Dict[str, Any]) -> None:
        """Update model from raw Shopify API data"""
        self.raw_data = raw_data
        self.updated_at = now_utc()

        # Update fields from raw data if they exist
        if "customer_event" in raw_data:
            event_data = raw_data["customer_event"]
            for field, value in event_data.items():
                if hasattr(self, field) and value is not None:
                    setattr(self, field, value)

    def is_related_to_customer(self, customer_id: str) -> bool:
        """Check if event is related to a specific customer"""
        return self.customer_id == customer_id

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self.dict()
