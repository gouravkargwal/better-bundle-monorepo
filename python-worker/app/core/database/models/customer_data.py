"""
Customer data model for SQLAlchemy

Represents customer information from Shopify.
"""

from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from .base import BaseModel, ShopMixin


class CustomerData(BaseModel, ShopMixin):
    """Customer data model representing Shopify customers"""

    __tablename__ = "CustomerData"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Customer identification - matching Prisma schema
    customer_id = Column("customerId", String, nullable=False, index=True)
    email = Column(String(255), nullable=True, index=True)
    first_name = Column("firstName", String(100), nullable=True)
    last_name = Column("lastName", String(100), nullable=True)

    # Customer metrics - matching Prisma schema
    total_spent = Column("totalSpent", Float, default=0.0, nullable=False, index=True)
    order_count = Column("orderCount", Integer, default=0, nullable=False)
    last_order_date = Column("lastOrderDate", DateTime, nullable=True, index=True)

    # Customer data - matching Prisma schema
    tags = Column(JSON, default=[], nullable=True)
    created_at_shopify = Column("createdAtShopify", DateTime, nullable=True)
    last_order_id = Column("lastOrderId", String(100), nullable=True)
    location = Column(JSON, default={}, nullable=True)
    metafields = Column(JSON, default=[], nullable=True)
    state = Column(String(50), default="", nullable=True, index=True)
    verified_email = Column(
        "verifiedEmail", Boolean, default=False, nullable=False, index=True
    )
    tax_exempt = Column("taxExempt", Boolean, default=False, nullable=False)
    default_address = Column("defaultAddress", JSON, default={}, nullable=True)
    addresses = Column(JSON, default=[], nullable=True)
    currency_code = Column("currencyCode", String(10), default="USD", nullable=True)
    customer_locale = Column("customerLocale", String(10), default="en", nullable=True)

    # Status - matching Prisma schema
    is_active = Column("isActive", Boolean, default=True, nullable=False)
    extras = Column(JSON, default={}, nullable=True)

    # Relationships
    shop = relationship("Shop", back_populates="customer_data")

    def __repr__(self) -> str:
        return f"<CustomerData(customer_id={self.customer_id}, email={self.email})>"
