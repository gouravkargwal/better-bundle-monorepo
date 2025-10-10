"""
Collection data model for SQLAlchemy

Represents collection information from Shopify.
"""

from sqlalchemy import Column, String, Boolean, Text, Integer
from sqlalchemy.dialects.postgresql import JSON, TIMESTAMP
from sqlalchemy.orm import relationship
from .base import BaseModel, ShopMixin


class CollectionData(BaseModel, ShopMixin):
    """Collection data model representing Shopify collections"""

    __tablename__ = "collection_data"

    collection_id = Column(String, nullable=False, index=True)
    title = Column(String(500), nullable=False, index=True)
    handle = Column(String(255), nullable=False, index=True)
    description = Column(Text, default="", nullable=True)
    template_suffix = Column(String(100), default="", nullable=True)
    seo_title = Column(String(500), default="", nullable=True)
    seo_description = Column(Text, default="", nullable=True)
    image_url = Column(String(1000), nullable=True)
    image_alt = Column(String(500), nullable=True)
    product_count = Column(Integer, default=0, nullable=False, index=True)
    is_automated = Column(Boolean, default=False, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    metafields = Column(JSON, default=[], nullable=True)
    products = Column(
        JSON, default=[], nullable=True
    )  # Store products data from GraphQL
    extras = Column(JSON, default={}, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    shop = relationship("Shop", back_populates="collection_data")

    def __repr__(self) -> str:
        return (
            f"<CollectionData(collection_id={self.collection_id}, title={self.title})>"
        )
