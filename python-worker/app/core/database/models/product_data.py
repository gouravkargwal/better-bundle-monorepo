"""
Product data model for SQLAlchemy

Represents product information from Shopify.
"""

from sqlalchemy import (
    Column,
    String,
    Float,
    Boolean,
    DateTime,
    Text,
    Integer,
    ForeignKey,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from .base import BaseModel, ShopMixin


class ProductData(BaseModel, ShopMixin):
    """Product data model representing Shopify products"""

    __tablename__ = "ProductData"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Product identification - matching Prisma schema
    product_id = Column("productId", String, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    handle = Column(String(255), nullable=False)

    # Product details - matching Prisma schema
    description = Column(Text, nullable=True)
    description_html = Column("descriptionHtml", Text, nullable=True)
    product_type = Column(
        "productType", String(100), default="", nullable=True, index=True
    )
    vendor = Column(String(255), default="", nullable=True, index=True)
    tags = Column(JSON, default=[], nullable=True)
    status = Column(String, default="ACTIVE", nullable=True, index=True)

    # Inventory and pricing - matching Prisma schema
    total_inventory = Column(
        "totalInventory", Integer, default=0, nullable=True, index=True
    )
    price = Column(Float, default=0.0, nullable=False, index=True)
    compare_at_price = Column("compareAtPrice", Float, default=0.0, nullable=True)
    inventory = Column(Integer, default=0, nullable=True)

    # Media - matching Prisma schema
    image_url = Column("imageUrl", String(1000), nullable=True)
    image_alt = Column("imageAlt", String(500), nullable=True)

    # Timestamps - matching Prisma schema
    product_created_at = Column("productCreatedAt", DateTime, nullable=True)
    product_updated_at = Column("productUpdatedAt", DateTime, nullable=True, index=True)

    # URLs - matching Prisma schema
    online_store_url = Column("onlineStoreUrl", String(1000), nullable=True)
    online_store_preview_url = Column(
        "onlineStorePreviewUrl", String(1000), nullable=True
    )

    # SEO - matching Prisma schema
    seo_title = Column("seoTitle", String(500), nullable=True)
    seo_description = Column("seoDescription", Text, nullable=True)
    template_suffix = Column("templateSuffix", String(100), nullable=True)

    # Product data - matching Prisma schema
    variants = Column(JSON, default=[], nullable=True)
    images = Column(JSON, default=[], nullable=True)
    media = Column(JSON, default=[], nullable=True)
    options = Column(JSON, default=[], nullable=True)
    collections = Column(JSON, default=[], nullable=True)
    metafields = Column(JSON, default=[], nullable=True)
    extras = Column(JSON, default={}, nullable=True)

    # Status - matching Prisma schema
    is_active = Column("isActive", Boolean, default=True, nullable=False, index=True)

    # Relationships
    shop = relationship("Shop", back_populates="product_data")

    def __repr__(self) -> str:
        return f"<ProductData(product_id={self.product_id}, title={self.title})>"
