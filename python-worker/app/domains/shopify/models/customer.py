"""
Shopify customer model for BetterBundle Python Worker
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.shared.helpers import now_utc


class ShopifyCustomerAddress(BaseModel):
    """Shopify customer address model"""
    
    id: str = Field(..., description="Address ID")
    customer_id: str = Field(..., description="Customer ID")
    
    # Address information
    address1: Optional[str] = Field(None, description="Address line 1")
    address2: Optional[str] = Field(None, description="Address line 2")
    city: Optional[str] = Field(None, description="City")
    province: Optional[str] = Field(None, description="Province/State")
    country: Optional[str] = Field(None, description="Country")
    zip: Optional[str] = Field(None, description="Postal/ZIP code")
    phone: Optional[str] = Field(None, description="Phone number")
    
    # Address metadata
    company: Optional[str] = Field(None, description="Company name")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    
    # Address type
    address_type: str = Field("shipping", description="Address type (shipping, billing)")
    is_default: bool = Field(False, description="Is default address")
    
    # Timestamps
    created_at: datetime = Field(default_factory=now_utc, description="Creation date")
    updated_at: datetime = Field(default_factory=now_utc, description="Last update date")
    
    # Raw data
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="Raw Shopify API response")
    
    class Config:
        json_encoders = {"datetime": lambda v: v.isoformat()}
    
    @property
    def full_address(self) -> str:
        """Get full formatted address"""
        parts = []
        if self.address1:
            parts.append(self.address1)
        if self.address2:
            parts.append(self.address2)
        if self.city:
            parts.append(self.city)
        if self.province:
            parts.append(self.province)
        if self.zip:
            parts.append(self.zip)
        if self.country:
            parts.append(self.country)
        
        return ", ".join(parts) if parts else "No address provided"
    
    @property
    def has_complete_address(self) -> bool:
        """Check if address is complete"""
        required_fields = [self.address1, self.city, self.province, self.country, self.zip]
        return all(field for field in required_fields)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self.dict()


class ShopifyCustomer(BaseModel):
    """Shopify customer model"""
    
    # Core customer information
    id: str = Field(..., description="Customer ID")
    first_name: Optional[str] = Field(None, description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    email: str = Field(..., description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    
    # Customer preferences
    accepts_marketing: bool = Field(False, description="Accepts marketing emails")
    accepts_marketing_updated_at: Optional[datetime] = Field(None, description="Marketing preference update date")
    
    # Customer metadata
    tags: List[str] = Field(default_factory=list, description="Customer tags")
    note: Optional[str] = Field(None, description="Customer note")
    
    # Timestamps
    created_at: datetime = Field(default_factory=now_utc, description="Customer creation date")
    updated_at: datetime = Field(default_factory=now_utc, description="Last update date")
    
    # Customer statistics
    orders_count: int = Field(0, description="Total number of orders")
    total_spent: float = Field(0.0, description="Total amount spent")
    last_order_id: Optional[str] = Field(None, description="Last order ID")
    last_order_name: Optional[str] = Field(None, description="Last order name")
    
    # Addresses
    addresses: List[ShopifyCustomerAddress] = Field(default_factory=list, description="Customer addresses")
    default_address: Optional[ShopifyCustomerAddress] = Field(None, description="Default address")
    
    # BetterBundle specific fields
    bb_last_sync: Optional[datetime] = Field(None, description="Last BetterBundle sync")
    bb_ml_features_computed: bool = Field(False, description="ML features computed")
    
    # Raw data storage
    raw_data: Dict[str, Any] = Field(default_factory=dict, description="Raw Shopify API response")
    
    class Config:
        json_encoders = {"datetime": lambda v: v.isoformat()}
    
    @property
    def full_name(self) -> str:
        """Get customer's full name"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        else:
            return "Unknown Customer"
    
    @property
    def has_name(self) -> bool:
        """Check if customer has a name"""
        return bool(self.first_name or self.last_name)
    
    @property
    def has_phone(self) -> bool:
        """Check if customer has a phone number"""
        return bool(self.phone)
    
    @property
    def has_addresses(self) -> bool:
        """Check if customer has addresses"""
        return len(self.addresses) > 0
    
    @property
    def is_active_customer(self) -> bool:
        """Check if customer is active (has orders)"""
        return self.orders_count > 0
    
    @property
    def average_order_value(self) -> float:
        """Get average order value"""
        if self.orders_count == 0:
            return 0.0
        return self.total_spent / self.orders_count
    
    @property
    def days_since_creation(self) -> int:
        """Get days since customer creation"""
        return (now_utc() - self.created_at).days
    
    @property
    def days_since_update(self) -> int:
        """Get days since last update"""
        return (now_utc() - self.updated_at).days
    
    @property
    def customer_segment(self) -> str:
        """Get customer segment based on behavior"""
        if self.orders_count == 0:
            return "new"
        elif self.orders_count == 1:
            return "first_time"
        elif self.orders_count <= 3:
            return "occasional"
        elif self.orders_count <= 10:
            return "regular"
        else:
            return "loyal"
    
    @property
    def spending_tier(self) -> str:
        """Get spending tier based on total spent"""
        if self.total_spent == 0:
            return "no_spending"
        elif self.total_spent < 100:
            return "low"
        elif self.total_spent < 500:
            return "medium"
        elif self.total_spent < 1000:
            return "high"
        else:
            return "premium"
    
    def get_ml_features(self) -> Dict[str, Any]:
        """Get ML-relevant features for this customer"""
        return {
            "customer_id": self.id,
            "orders_count": self.orders_count,
            "total_spent": self.total_spent,
            "average_order_value": self.average_order_value,
            "days_since_creation": self.days_since_creation,
            "days_since_update": self.days_since_update,
            "has_name": self.has_name,
            "has_phone": self.has_phone,
            "has_addresses": self.has_addresses,
            "is_active_customer": self.is_active_customer,
            "accepts_marketing": self.accepts_marketing,
            "customer_segment": self.customer_segment,
            "spending_tier": self.spending_tier,
            "tag_count": len(self.tags),
            "address_count": len(self.addresses),
        }
    
    def update_from_raw_data(self, raw_data: Dict[str, Any]) -> None:
        """Update model from raw Shopify API data"""
        self.raw_data = raw_data
        self.updated_at = now_utc()
        
        # Update fields from raw data if they exist
        if "customer" in raw_data:
            customer_data = raw_data["customer"]
            for field, value in customer_data.items():
                if hasattr(self, field) and value is not None:
                    setattr(self, field, value)
    
    def add_address(self, address: ShopifyCustomerAddress) -> None:
        """Add an address to the customer"""
        self.addresses.append(address)
        
        # Set as default if it's the first address or marked as default
        if len(self.addresses) == 1 or address.is_default:
            self.default_address = address
    
    def get_address_by_id(self, address_id: str) -> Optional[ShopifyCustomerAddress]:
        """Get address by ID"""
        for address in self.addresses:
            if address.id == address_id:
                return address
        return None
    
    def get_addresses_by_type(self, address_type: str) -> List[ShopifyCustomerAddress]:
        """Get addresses by type"""
        return [address for address in self.addresses if address.address_type == address_type]
    
    def get_shipping_addresses(self) -> List[ShopifyCustomerAddress]:
        """Get shipping addresses"""
        return self.get_addresses_by_type("shipping")
    
    def get_billing_addresses(self) -> List[ShopifyCustomerAddress]:
        """Get billing addresses"""
        return self.get_addresses_by_type("billing")
    
    def has_tag(self, tag: str) -> bool:
        """Check if customer has a specific tag"""
        return tag in self.tags
    
    def add_tag(self, tag: str) -> None:
        """Add a tag to the customer"""
        if tag not in self.tags:
            self.tags.append(tag)
    
    def remove_tag(self, tag: str) -> None:
        """Remove a tag from the customer"""
        if tag in self.tags:
            self.tags.remove(tag)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self.dict()
