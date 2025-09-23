"""
Product data model for SQLAlchemy

Represents product information from Shopify.
"""

from sqlalchemy import Column, String, Float, Boolean, DateTime, Text, Integer
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from .base import BaseModel, ShopMixin


class ProductData(BaseModel, ShopMixin):
    """Product data model representing Shopify products"""

    __tablename__ = "product_data"

    product_id = Column(String, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    handle = Column(String(255), nullable=False)

    description = Column(Text, nullable=True)
    description_html = Column(Text, nullable=True)
    product_type = Column(String(100), default="", nullable=True, index=True)
    vendor = Column(String(255), default="", nullable=True, index=True)
    tags = Column(JSON, default=[], nullable=True)
    status = Column(String, default="ACTIVE", nullable=True, index=True)
    total_inventory = Column(Integer, default=0, nullable=True, index=True)

    price = Column(Float, default=0.0, nullable=False, index=True)
    compare_at_price = Column(Float, default=0.0, nullable=True)
    inventory = Column(Integer, default=0, nullable=True)

    image_url = Column(String(1000), nullable=True)
    image_alt = Column(String(500), nullable=True)

    product_created_at = Column(DateTime, nullable=True)
    product_updated_at = Column(DateTime, nullable=True, index=True)

    online_store_url = Column(String(1000), nullable=True)
    online_store_preview_url = Column(String(1000), nullable=True)

    seo_title = Column(String(500), nullable=True)
    seo_description = Column(Text, nullable=True)
    template_suffix = Column(String(100), nullable=True)

    variants = Column(JSON, default=[], nullable=True)
    images = Column(JSON, default=[], nullable=True)
    media = Column(JSON, default=[], nullable=True)
    options = Column(JSON, default=[], nullable=True)
    collections = Column(JSON, default=[], nullable=True)
    metafields = Column(JSON, default=[], nullable=True)
    extras = Column(JSON, default={}, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False, index=True)

    shop = relationship("Shop", back_populates="product_data")

    def __repr__(self) -> str:
        return f"<ProductData(product_id={self.product_id}, title={self.title})>"
