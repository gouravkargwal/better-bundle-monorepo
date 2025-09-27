"""
Product data model for SQLAlchemy

Represents product information from Shopify.
"""

from sqlalchemy import Column, String, Float, Boolean, DateTime, Text, Integer
from sqlalchemy.dialects.postgresql import JSON, TIMESTAMP
from sqlalchemy.orm import relationship
from .base import BaseModel, ShopMixin


class ProductData(BaseModel, ShopMixin):
    """Product data model representing Shopify products"""

    __tablename__ = "product_data"

    product_id = Column(String, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    handle = Column(String(255), nullable=False)

    # Core product information (essential for ML)
    description = Column(Text, nullable=True)
    product_type = Column(String(100), default="", nullable=True, index=True)
    vendor = Column(String(255), default="", nullable=True, index=True)
    tags = Column(JSON, default=[], nullable=True)
    status = Column(String, default="ACTIVE", nullable=True, index=True)
    total_inventory = Column(Integer, default=0, nullable=True, index=True)

    # Pricing data (essential for ML)
    price = Column(Float, default=0.0, nullable=False, index=True)
    compare_at_price = Column(Float, default=0.0, nullable=True)
    price_range = Column(JSON, default={}, nullable=True)  # {min: 949.95, max: 949.95}

    # Collections data (critical for ML features)
    collections = Column(JSON, default=[], nullable=True)  # Array of collection IDs

    # Timestamps are provided by TimestampMixin (auto-created created_at and updated_at)

    # SEO data (valuable for content-based ML features)
    seo_title = Column(String(500), nullable=True)
    seo_description = Column(Text, nullable=True)
    template_suffix = Column(String(100), nullable=True)

    # Detailed product data (essential for ML)
    variants = Column(JSON, default=[], nullable=True)
    images = Column(JSON, default=[], nullable=True)
    media = Column(JSON, default=[], nullable=True)
    options = Column(JSON, default=[], nullable=True)
    metafields = Column(
        JSON, default=[], nullable=True
    )  # Store complete metafield data

    # Note: Derived metrics (variant_count, image_count, tag_count) are computed
    # in feature engineering, not stored in database

    # Extras for future use
    extras = Column(JSON, default={}, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False, index=True)

    shop = relationship("Shop", back_populates="product_data")

    def __repr__(self) -> str:
        return f"<ProductData(product_id={self.product_id}, title={self.title})>"
