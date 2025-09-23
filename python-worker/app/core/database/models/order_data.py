"""
Order data models for SQLAlchemy

Represents order information and line items.
"""

from sqlalchemy import (
    Column,
    String,
    Float,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Integer,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from .base import BaseModel, ShopMixin


class OrderData(BaseModel, ShopMixin):
    """Order data model representing Shopify orders"""

    __tablename__ = "OrderData"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Order identification - matching Prisma schema
    order_id = Column("orderId", String, nullable=False, index=True)
    order_name = Column("orderName", String(100), nullable=True)

    # Customer information - matching Prisma schema
    customer_id = Column("customerId", String(100), nullable=True, index=True)
    customer_email = Column("customerEmail", String(255), nullable=True, index=True)
    customer_phone = Column("customerPhone", String(50), nullable=True)
    customer_display_name = Column("customerDisplayName", String(255), nullable=True)
    customer_state = Column("customerState", String(50), nullable=True, index=True)
    customer_verified_email = Column(
        "customerVerifiedEmail", Boolean, default=False, nullable=True
    )
    customer_created_at = Column("customerCreatedAt", DateTime, nullable=True)
    customer_updated_at = Column("customerUpdatedAt", DateTime, nullable=True)
    customer_default_address = Column(
        "customerDefaultAddress", JSON, default={}, nullable=True
    )

    # Financial information - matching Prisma schema
    total_amount = Column("totalAmount", Float, default=0.0, nullable=False, index=True)
    subtotal_amount = Column("subtotalAmount", Float, default=0.0, nullable=True)
    total_tax_amount = Column("totalTaxAmount", Float, default=0.0, nullable=True)
    total_shipping_amount = Column(
        "totalShippingAmount", Float, default=0.0, nullable=True
    )
    total_refunded_amount = Column(
        "totalRefundedAmount", Float, default=0.0, nullable=True
    )
    total_outstanding_amount = Column(
        "totalOutstandingAmount", Float, default=0.0, nullable=True
    )

    # Order timing - matching Prisma schema
    order_date = Column("orderDate", DateTime, nullable=False, index=True)
    processed_at = Column("processedAt", DateTime, nullable=True)
    cancelled_at = Column("cancelledAt", DateTime, nullable=True)

    # Order details - matching Prisma schema
    cancel_reason = Column("cancelReason", String(500), default="", nullable=True)
    order_locale = Column("orderLocale", String(10), default="en", nullable=True)
    currency_code = Column(
        "currencyCode", String(10), default="USD", nullable=True, index=True
    )
    presentment_currency_code = Column(
        "presentmentCurrencyCode", String(10), default="USD", nullable=True
    )

    # Status flags - matching Prisma schema
    confirmed = Column(Boolean, default=False, nullable=False)
    test = Column(Boolean, default=False, nullable=False)
    financial_status = Column("financialStatus", String(50), nullable=True, index=True)
    fulfillment_status = Column(
        "fulfillmentStatus", String(50), nullable=True, index=True
    )
    order_status = Column("orderStatus", String(50), nullable=True, index=True)

    # Additional data - matching Prisma schema
    tags = Column(JSON, default=[], nullable=True)
    note = Column(Text, default="", nullable=True)
    note_attributes = Column("noteAttributes", JSON, default=[], nullable=True)
    shipping_address = Column("shippingAddress", JSON, default={}, nullable=True)
    billing_address = Column("billingAddress", JSON, default={}, nullable=True)
    discount_applications = Column(
        "discountApplications", JSON, default=[], nullable=True
    )
    metafields = Column(JSON, default=[], nullable=True)
    fulfillments = Column(JSON, default=[], nullable=True)
    transactions = Column(JSON, default=[], nullable=True)
    extras = Column(JSON, default={}, nullable=True)

    # Relationships
    shop = relationship("Shop", back_populates="order_data")
    line_items = relationship(
        "LineItemData", back_populates="order", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<OrderData(order_id={self.order_id}, shop_id={self.shopId})>"


class LineItemData(BaseModel):
    """Line item data model representing order line items"""

    __tablename__ = "line_item_data"

    # Foreign keys
    order_id = Column(String, ForeignKey("OrderData.id"), nullable=False)
    product_id = Column(String, nullable=True)
    variant_id = Column(String, nullable=True)

    # Line item details
    title = Column(String, nullable=True)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    properties = Column(JSON, default={}, nullable=True)

    # Relationships
    order = relationship("OrderData", back_populates="line_items")

    def __repr__(self) -> str:
        return f"<LineItemData(order_id={self.order_id}, product_id={self.product_id})>"
