"""
Collection data model for SQLAlchemy

Represents collection information from Shopify.
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from .base import BaseModel, ShopMixin


class CollectionData(BaseModel, ShopMixin):
    """Collection data model representing Shopify collections"""

    __tablename__ = "CollectionData"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Collection identification - matching Prisma schema
    collection_id = Column("collectionId", String, nullable=False, index=True)
    title = Column(String(500), nullable=False, index=True)
    handle = Column(String(255), nullable=False, index=True)

    # Collection details - matching Prisma schema
    description = Column(Text, default="", nullable=True)
    template_suffix = Column("templateSuffix", String(100), default="", nullable=True)
    seo_title = Column("seoTitle", String(500), default="", nullable=True)
    seo_description = Column("seoDescription", Text, default="", nullable=True)

    # Media - matching Prisma schema
    image_url = Column("imageUrl", String(1000), nullable=True)
    image_alt = Column("imageAlt", String(500), nullable=True)

    # Collection metrics - matching Prisma schema
    product_count = Column(
        "productCount", Integer, default=0, nullable=False, index=True
    )
    is_automated = Column(
        "isAutomated", Boolean, default=False, nullable=False, index=True
    )
    is_active = Column("isActive", Boolean, default=True, nullable=False)

    # Additional data - matching Prisma schema
    metafields = Column(JSON, default=[], nullable=True)
    extras = Column(JSON, default={}, nullable=True)

    # Relationships
    shop = relationship("Shop", back_populates="collection_data")

    def __repr__(self) -> str:
        return (
            f"<CollectionData(collection_id={self.collection_id}, title={self.title})>"
        )
