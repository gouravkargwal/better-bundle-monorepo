"""
Shopify customer event model for BetterBundle Python Worker
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.shared.helpers import now_utc


class ShopifyCustomerEvent(BaseModel):
    """Shopify customer event model"""

    # Core event information
    id: str = Field(..., description="Event ID")
    event_type: str = Field(..., description="Type of event")
    marketing_channel: Optional[str] = Field(None, description="Marketing channel")

    # Event details
    description: Optional[str] = Field(None, description="Event description")
    started_at: Optional[datetime] = Field(None, description="Event start date")
    ended_at: Optional[datetime] = Field(None, description="Event end date")

    # Event configuration
    paid: bool = Field(False, description="Is this a paid event")
    budget: Optional[float] = Field(None, description="Event budget")
    budget_type: Optional[str] = Field(None, description="Budget type")
    currency: str = Field("USD", description="Currency for budget")

    # UTM tracking
    utm_campaign: Optional[str] = Field(None, description="UTM campaign")
    utm_source: Optional[str] = Field(None, description="UTM source")
    utm_medium: Optional[str] = Field(None, description="UTM medium")
    utm_term: Optional[str] = Field(None, description="UTM term")
    utm_content: Optional[str] = Field(None, description="UTM content")

    # URLs
    manage_url: Optional[str] = Field(None, description="Management URL")
    preview_url: Optional[str] = Field(None, description="Preview URL")

    # Related entities
    customer_id: Optional[str] = Field(None, description="Related customer ID")
    product_id: Optional[str] = Field(None, description="Related product ID")
    collection_id: Optional[str] = Field(None, description="Related collection ID")

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
        """Check if event is currently active"""
        now = now_utc()
        if self.started_at and self.started_at > now:
            return False
        if self.ended_at and self.ended_at < now:
            return False
        return True

    @property
    def is_scheduled(self) -> bool:
        """Check if event is scheduled for the future"""
        return self.started_at and self.started_at > now_utc()

    @property
    def is_completed(self) -> bool:
        """Check if event is completed"""
        return self.ended_at and self.ended_at < now_utc()

    @property
    def has_budget(self) -> bool:
        """Check if event has a budget"""
        return self.budget is not None and self.budget > 0

    @property
    def has_utm_tracking(self) -> bool:
        """Check if event has UTM tracking"""
        return any(
            [
                self.utm_campaign,
                self.utm_source,
                self.utm_medium,
                self.utm_term,
                self.utm_content,
            ]
        )

    @property
    def has_related_entities(self) -> bool:
        """Check if event has related entities"""
        return any([self.customer_id, self.product_id, self.collection_id])

    @property
    def event_duration_days(self) -> Optional[int]:
        """Get event duration in days"""
        if self.started_at and self.ended_at:
            return (self.ended_at - self.started_at).days
        return None

    @property
    def days_since_start(self) -> Optional[int]:
        """Get days since event start"""
        if self.started_at:
            return (now_utc() - self.started_at).days
        return None

    @property
    def days_until_start(self) -> Optional[int]:
        """Get days until event start"""
        if self.started_at and self.started_at > now_utc():
            return (self.started_at - now_utc()).days
        return None

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
        if "email" in self.event_type.lower():
            return "email_marketing"
        elif "social" in self.event_type.lower():
            return "social_media"
        elif "search" in self.event_type.lower():
            return "search_marketing"
        elif "display" in self.event_type.lower():
            return "display_advertising"
        elif "affiliate" in self.event_type.lower():
            return "affiliate_marketing"
        else:
            return "other"

    @property
    def budget_category(self) -> str:
        """Get budget category"""
        if not self.has_budget:
            return "no_budget"
        elif self.budget < 100:
            return "low"
        elif self.budget < 1000:
            return "medium"
        elif self.budget < 10000:
            return "high"
        else:
            return "very_high"

    def get_ml_features(self) -> Dict[str, Any]:
        """Get ML-relevant features for this event"""
        return {
            "event_id": self.id,
            "event_type": self.event_type,
            "event_category": self.event_category,
            "is_active": self.is_active,
            "is_scheduled": self.is_scheduled,
            "is_completed": self.is_completed,
            "has_budget": self.has_budget,
            "budget_category": self.budget_category,
            "has_utm_tracking": self.has_utm_tracking,
            "has_related_entities": self.has_related_entities,
            "event_duration_days": self.event_duration_days,
            "days_since_start": self.days_since_start,
            "days_until_start": self.days_until_start,
            "days_since_creation": self.days_since_creation,
            "days_since_update": self.days_since_update,
            "paid": self.paid,
            "budget": self.budget or 0,
            "currency": self.currency,
            "marketing_channel": self.marketing_channel or "none",
        }

    def update_from_raw_data(self, raw_data: Dict[str, Any]) -> None:
        """Update model from raw Shopify API data"""
        self.raw_data = raw_data
        self.updated_at = now_utc()

        # Update fields from raw data if they exist
        if "marketingEvent" in raw_data:
            event_data = raw_data["marketingEvent"]
            for field, value in event_data.items():
                if hasattr(self, field) and value is not None:
                    setattr(self, field, value)

    def is_related_to_customer(self, customer_id: str) -> bool:
        """Check if event is related to a specific customer"""
        return self.customer_id == customer_id

    def is_related_to_product(self, product_id: str) -> bool:
        """Check if event is related to a specific product"""
        return self.product_id == product_id

    def is_related_to_collection(self, collection_id: str) -> bool:
        """Check if event is related to a specific collection"""
        return self.collection_id == collection_id

    def has_utm_parameter(self, param_name: str) -> bool:
        """Check if event has a specific UTM parameter"""
        utm_params = {
            "campaign": self.utm_campaign,
            "source": self.utm_source,
            "medium": self.utm_medium,
            "term": self.utm_term,
            "content": self.utm_content,
        }
        return bool(utm_params.get(param_name))

    def get_utm_summary(self) -> Dict[str, Optional[str]]:
        """Get summary of all UTM parameters"""
        return {
            "campaign": self.utm_campaign,
            "source": self.utm_source,
            "medium": self.utm_medium,
            "term": self.utm_term,
            "content": self.utm_content,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self.dict()
