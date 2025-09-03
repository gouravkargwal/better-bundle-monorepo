"""
Shopify Shop model for BetterBundle Python Worker
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator

from app.shared.helpers import now_utc


class ShopifyShop(BaseModel):
    """Shopify shop data model"""
    
    # Core shop information
    id: str = Field(..., description="Shop ID")
    name: str = Field(..., description="Shop name")
    domain: str = Field(..., description="Shop domain")
    email: Optional[str] = Field(None, description="Shop email")
    phone: Optional[str] = Field(None, description="Shop phone")
    
    # Business information
    address1: Optional[str] = Field(None, description="Shop address line 1")
    address2: Optional[str] = Field(None, description="Shop address line 2")
    city: Optional[str] = Field(None, description="Shop city")
    province: Optional[str] = Field(None, description="Shop province/state")
    country: Optional[str] = Field(None, description="Shop country")
    zip: Optional[str] = Field(None, description="Shop postal code")
    
    # Currency and locale
    currency: str = Field(..., description="Shop currency code")
    primary_locale: str = Field(..., description="Primary locale")
    timezone: Optional[str] = Field(None, description="Shop timezone")
    
    # Plan and status
    plan_name: Optional[str] = Field(None, description="Shopify plan name")
    plan_display_name: Optional[str] = Field(None, description="Plan display name")
    shop_owner: Optional[str] = Field(None, description="Shop owner name")
    
    # Features and capabilities
    has_storefront: bool = Field(False, description="Has online store")
    has_discounts: bool = Field(False, description="Has discount capabilities")
    has_gift_cards: bool = Field(False, description="Has gift card capabilities")
    has_marketing: bool = Field(False, description="Has marketing features")
    has_multi_location: bool = Field(False, description="Has multiple locations")
    
    # Analytics and tracking
    google_analytics_account: Optional[str] = Field(None, description="Google Analytics account")
    google_analytics_domain: Optional[str] = Field(None, description="Google Analytics domain")
    
    # SEO and marketing
    seo_title: Optional[str] = Field(None, description="SEO title")
    seo_description: Optional[str] = Field(None, description="SEO description")
    meta_description: Optional[str] = Field(None, description="Meta description")
    
    # Social media
    facebook_account: Optional[str] = Field(None, description="Facebook account")
    instagram_account: Optional[str] = Field(None, description="Instagram account")
    twitter_account: Optional[str] = Field(None, description="Twitter account")
    
    # Technical information
    myshopify_domain: str = Field(..., description="Myshopify domain")
    primary_location_id: Optional[str] = Field(None, description="Primary location ID")
    
    # Timestamps
    created_at: datetime = Field(default_factory=now_utc, description="Shop creation date")
    updated_at: datetime = Field(default_factory=now_utc, description="Last update date")
    
    # BetterBundle specific fields
    bb_installed_at: Optional[datetime] = Field(None, description="When BetterBundle was installed")
    bb_last_sync: Optional[datetime] = Field(None, description="Last data sync")
    bb_sync_frequency: str = Field("daily", description="Sync frequency")
    bb_ml_enabled: bool = Field(True, description="ML features enabled")
    
    # Raw data storage
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="Raw Shopify API response")
    
    class Config:
        json_encoders = {"datetime": lambda v: v.isoformat()}
    
    @validator('domain')
    def validate_domain(cls, v):
        """Validate shop domain format"""
        if not v or '.' not in v:
            raise ValueError("Invalid domain format")
        return v.lower()
    
    @validator('currency')
    def validate_currency(cls, v):
        """Validate currency code format"""
        if not v or len(v) != 3:
            raise ValueError("Currency must be 3 characters")
        return v.upper()
    
    @property
    def is_active(self) -> bool:
        """Check if shop is active"""
        return self.plan_name is not None and self.plan_name != "frozen"
    
    @property
    def has_online_store(self) -> bool:
        """Check if shop has online store"""
        return self.has_storefront
    
    @property
    def location_count(self) -> int:
        """Get number of locations"""
        return 1 if not self.has_multi_location else 2  # Default to 1, can be enhanced
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self.dict()
    
    def update_from_raw_data(self, raw_data: Dict[str, Any]) -> None:
        """Update model from raw Shopify API data"""
        self.raw_data = raw_data
        self.updated_at = now_utc()
        
        # Update fields from raw data if they exist
        if 'shop' in raw_data:
            shop_data = raw_data['shop']
            for field, value in shop_data.items():
                if hasattr(self, field) and value is not None:
                    setattr(self, field, value)
    
    def get_ml_features(self) -> Dict[str, Any]:
        """Get ML-relevant features for this shop"""
        return {
            "shop_id": self.id,
            "has_storefront": self.has_storefront,
            "has_discounts": self.has_discounts,
            "has_gift_cards": self.has_gift_cards,
            "has_marketing": self.has_marketing,
            "has_multi_location": self.has_multi_location,
            "plan_level": self._get_plan_level(),
            "country_code": self.country,
            "currency_code": self.currency,
            "timezone_offset": self._get_timezone_offset(),
            "days_since_creation": self._get_days_since_creation(),
            "days_since_bb_install": self._get_days_since_bb_install(),
        }
    
    def _get_plan_level(self) -> int:
        """Get plan level as integer for ML"""
        plan_levels = {
            "basic": 1,
            "shopify": 2,
            "advanced": 3,
            "plus": 4,
            "enterprise": 5
        }
        return plan_levels.get(self.plan_name, 0)
    
    def _get_timezone_offset(self) -> Optional[int]:
        """Get timezone offset in hours for ML"""
        if not self.timezone:
            return None
        
        # Simple timezone offset mapping (can be enhanced)
        tz_offsets = {
            "UTC": 0,
            "America/New_York": -5,
            "America/Chicago": -6,
            "America/Denver": -7,
            "America/Los_Angeles": -8,
            "Europe/London": 0,
            "Europe/Paris": 1,
            "Asia/Tokyo": 9,
        }
        return tz_offsets.get(self.timezone, 0)
    
    def _get_days_since_creation(self) -> int:
        """Get days since shop creation"""
        if not self.created_at:
            return 0
        return (now_utc() - self.created_at).days
    
    def _get_days_since_bb_install(self) -> Optional[int]:
        """Get days since BetterBundle installation"""
        if not self.bb_installed_at:
            return None
        return (now_utc() - self.bb_installed_at).days
