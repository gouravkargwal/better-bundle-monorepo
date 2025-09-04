"""
Shopify order model for BetterBundle Python Worker
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.shared.helpers import now_utc


class ShopifyOrderLineItem(BaseModel):
    """Shopify order line item model"""

    id: str = Field(..., description="Line item ID")
    order_id: str = Field(..., description="Parent order ID")
    quantity: int = Field(..., description="Quantity ordered")
    title: str = Field(..., description="Product title")

    # Variant information
    variant_id: Optional[str] = Field(None, description="Variant ID")
    variant_title: Optional[str] = Field(None, description="Variant title")
    sku: Optional[str] = Field(None, description="SKU")
    barcode: Optional[str] = Field(None, description="Barcode")

    # Product information
    product_id: Optional[str] = Field(None, description="Product ID")
    product_title: Optional[str] = Field(None, description="Product title")
    vendor: Optional[str] = Field(None, description="Product vendor")
    product_type: Optional[str] = Field(None, description="Product type")
    product_tags: List[str] = Field(default_factory=list, description="Product tags")

    # Pricing
    price: float = Field(..., description="Unit price")
    total_discount: float = Field(0.0, description="Total discount for this line item")

    # Timestamps
    created_at: datetime = Field(default_factory=now_utc, description="Creation date")
    updated_at: datetime = Field(
        default_factory=now_utc, description="Last update date"
    )

    # Raw data
    raw_data: Dict[str, Any] = Field(
        default_factory=dict, description="Raw Shopify API response"
    )

    class Config:
        json_encoders = {"datetime": lambda v: v.isoformat()}

    @property
    def total_price(self) -> float:
        """Get total price for this line item"""
        return self.price * self.quantity

    @property
    def final_price(self) -> float:
        """Get final price after discounts"""
        return self.total_price - self.total_discount

    @property
    def discount_percentage(self) -> float:
        """Get discount percentage"""
        if self.total_price == 0:
            return 0.0
        return (self.total_discount / self.total_price) * 100


class ShopifyOrder(BaseModel):
    """Shopify order model"""

    # Core order information
    id: str = Field(..., description="Order ID")
    name: Optional[str] = Field(None, description="Order name/number")
    email: Optional[str] = Field(None, description="Customer email")
    phone: Optional[str] = Field(None, description="Customer phone")

    # Order status
    status: str = Field("open", description="Order status")
    financial_status: str = Field("pending", description="Financial status")
    fulfillment_status: Optional[str] = Field(None, description="Fulfillment status")

    # Timestamps
    created_at: datetime = Field(
        default_factory=now_utc, description="Order creation date"
    )
    updated_at: datetime = Field(
        default_factory=now_utc, description="Last update date"
    )
    processed_at: Optional[datetime] = Field(None, description="Processing date")
    cancelled_at: Optional[datetime] = Field(None, description="Cancellation date")

    # Cancellation
    cancel_reason: Optional[str] = Field(None, description="Cancellation reason")

    # Financial information
    total_price: float = Field(0.0, description="Total order price")
    subtotal_price: float = Field(0.0, description="Subtotal before taxes and shipping")
    total_tax: float = Field(0.0, description="Total tax amount")
    total_shipping_price: float = Field(0.0, description="Total shipping cost")
    total_discounts: float = Field(0.0, description="Total discounts applied")
    currency: str = Field("USD", description="Order currency")

    # Customer information
    customer_id: Optional[str] = Field(None, description="Customer ID")
    customer_first_name: Optional[str] = Field(None, description="Customer first name")
    customer_last_name: Optional[str] = Field(None, description="Customer last name")
    customer_email: Optional[str] = Field(None, description="Customer email")
    customer_phone: Optional[str] = Field(None, description="Customer phone")
    customer_tags: List[str] = Field(default_factory=list, description="Customer tags")

    # Addresses
    shipping_address: Optional[Dict[str, Any]] = Field(
        None, description="Shipping address"
    )
    billing_address: Optional[Dict[str, Any]] = Field(
        None, description="Billing address"
    )

    # Order metadata
    tags: List[str] = Field(default_factory=list, description="Order tags")
    note: Optional[str] = Field(None, description="Order note")
    confirmed: bool = Field(False, description="Order confirmed")
    test: bool = Field(False, description="Test order")

    # Financial details
    total_refunded: float = Field(0.0, description="Total refunded amount")
    total_outstanding: float = Field(0.0, description="Total outstanding amount")
    customer_locale: Optional[str] = Field(None, description="Customer locale")
    currency_code: str = Field("USD", description="Order currency code")
    presentment_currency_code: Optional[str] = Field(
        None, description="Presentment currency code"
    )

    # Discounts and metafields
    discount_applications: List[Dict[str, Any]] = Field(
        default_factory=list, description="Discount applications"
    )
    metafields: List[Dict[str, Any]] = Field(
        default_factory=list, description="Order metafields"
    )

    # Line items
    line_items: List[ShopifyOrderLineItem] = Field(
        default_factory=list, description="Order line items"
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
    def is_cancelled(self) -> bool:
        """Check if order is cancelled"""
        return self.cancelled_at is not None

    @property
    def is_processed(self) -> bool:
        """Check if order is processed"""
        return self.processed_at is not None

    @property
    def is_fulfilled(self) -> bool:
        """Check if order is fulfilled"""
        return self.fulfillment_status == "fulfilled"

    @property
    def is_paid(self) -> bool:
        """Check if order is paid"""
        return self.financial_status == "paid"

    @property
    def total_items(self) -> int:
        """Get total number of items ordered"""
        return sum(item.quantity for item in self.line_items)

    @property
    def unique_products(self) -> int:
        """Get number of unique products ordered"""
        return len(self.line_items)

    @property
    def average_item_price(self) -> float:
        """Get average price per item"""
        if self.total_items == 0:
            return 0.0
        return self.subtotal_price / self.total_items

    @property
    def discount_percentage(self) -> float:
        """Get overall discount percentage"""
        if self.subtotal_price == 0:
            return 0.0
        return (self.total_discounts / self.subtotal_price) * 100

    @property
    def tax_percentage(self) -> float:
        """Get tax percentage"""
        if self.subtotal_price == 0:
            return 0.0
        return (self.total_tax / self.subtotal_price) * 100

    @property
    def shipping_percentage(self) -> float:
        """Get shipping percentage"""
        if self.subtotal_price == 0:
            return 0.0
        return (self.total_shipping_price / self.subtotal_price) * 100

    @property
    def days_since_creation(self) -> int:
        """Get days since order creation"""
        return (now_utc() - self.created_at).days

    @property
    def days_since_update(self) -> int:
        """Get days since last update"""
        return (now_utc() - self.updated_at).days

    def get_ml_features(self) -> Dict[str, Any]:
        """Get ML-relevant features for this order"""
        return {
            "order_id": self.id,
            "order_name": self.name or "",
            "total_price": self.total_price,
            "subtotal_price": self.subtotal_price,
            "total_tax": self.total_tax,
            "total_shipping_price": self.total_shipping_price,
            "total_discounts": self.total_discounts,
            "total_refunded": self.total_refunded,
            "total_outstanding": self.total_outstanding,
            "total_items": self.total_items,
            "unique_products": self.unique_products,
            "average_item_price": self.average_item_price,
            "discount_percentage": self.discount_percentage,
            "tax_percentage": self.tax_percentage,
            "shipping_percentage": self.shipping_percentage,
            "days_since_creation": self.days_since_creation,
            "days_since_update": self.days_since_update,
            "is_cancelled": self.is_cancelled,
            "is_processed": self.is_processed,
            "is_fulfilled": self.is_fulfilled,
            "is_paid": self.is_paid,
            "is_confirmed": self.confirmed,
            "is_test": self.test,
            "status": self.status,
            "financial_status": self.financial_status,
            "fulfillment_status": self.fulfillment_status or "none",
            "currency": self.currency,
            "currency_code": self.currency_code,
            "presentment_currency_code": self.presentment_currency_code or "",
            "customer_locale": self.customer_locale or "",
            "customer_tags": self.customer_tags,
            "order_tags": self.tags,
            "order_note": self.note or "",
            "discount_applications_count": len(self.discount_applications),
            "metafields_count": len(self.metafields),
            # Address features
            "shipping_city": (
                self.shipping_address.get("city", "") if self.shipping_address else ""
            ),
            "shipping_province": (
                self.shipping_address.get("province", "")
                if self.shipping_address
                else ""
            ),
            "shipping_country": (
                self.shipping_address.get("country", "")
                if self.shipping_address
                else ""
            ),
            "shipping_province_code": (
                self.shipping_address.get("provinceCode", "")
                if self.shipping_address
                else ""
            ),
            "shipping_country_code": (
                self.shipping_address.get("countryCodeV2", "")
                if self.shipping_address
                else ""
            ),
        }

    def update_from_raw_data(self, raw_data: Dict[str, Any]) -> None:
        """Update model from raw Shopify API data"""
        self.raw_data = raw_data
        self.updated_at = now_utc()

        # Update fields from raw data if they exist
        if "order" in raw_data:
            order_data = raw_data["order"]
            for field, value in order_data.items():
                if hasattr(self, field) and value is not None:
                    setattr(self, field, value)

    def add_line_item(self, line_item: ShopifyOrderLineItem) -> None:
        """Add a line item to the order"""
        self.line_items.append(line_item)

    def get_line_item_by_id(self, line_item_id: str) -> Optional[ShopifyOrderLineItem]:
        """Get line item by ID"""
        for item in self.line_items:
            if item.id == line_item_id:
                return item
        return None

    def get_line_items_by_product(self, product_id: str) -> List[ShopifyOrderLineItem]:
        """Get line items for a specific product"""
        return [item for item in self.line_items if item.product_id == product_id]

    def get_line_items_by_variant(self, variant_id: str) -> List[ShopifyOrderLineItem]:
        """Get line items for a specific variant"""
        return [item for item in self.line_items if item.variant_id == variant_id]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self.dict()
