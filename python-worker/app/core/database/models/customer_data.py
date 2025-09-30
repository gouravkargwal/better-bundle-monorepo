"""
Customer data model for SQLAlchemy

Represents customer information from Shopify.
"""

from sqlalchemy import Column, String, Float, Boolean, DateTime, Integer
from sqlalchemy.dialects.postgresql import JSON, TIMESTAMP
from sqlalchemy.orm import relationship
from .base import BaseModel, ShopMixin


class CustomerData(BaseModel, ShopMixin):
    """Customer data model representing Shopify customers"""

    __tablename__ = "customer_data"

    customer_id = Column(String, nullable=False, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    total_spent = Column(Float, default=0.0, nullable=False, index=True)
    order_count = Column(Integer, default=0, nullable=False)
    last_order_date = Column(DateTime, nullable=True, index=True)
    last_order_id = Column(String(100), nullable=True)
    verified_email = Column(Boolean, default=False, nullable=False, index=True)
    tax_exempt = Column(Boolean, default=False, nullable=False)
    customer_locale = Column(String(10), default="en", nullable=True)
    tags = Column(JSON, default=[], nullable=True)
    state = Column(String(50), default="", nullable=True, index=True)
    default_address = Column(JSON, default={}, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    extras = Column(JSON, default={}, nullable=True)
    shop = relationship("Shop", back_populates="customer_data")

    def __repr__(self) -> str:
        return f"<CustomerData(customer_id={self.customer_id}, email={self.email})>"
