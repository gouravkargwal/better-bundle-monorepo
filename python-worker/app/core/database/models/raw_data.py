"""
Raw data models for SQLAlchemy

Represents raw data from Shopify webhooks and API calls.
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from .base import Base, IDMixin, ShopMixin


class RawOrder(Base, IDMixin, ShopMixin):
    """Raw order data model"""

    __tablename__ = "RawOrder"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Raw data - matching Prisma schema
    payload = Column(JSON, nullable=False)
    extractedAt = Column("extractedAt", DateTime, nullable=False, default=func.now())

    # Shopify identifiers - matching Prisma schema
    shopifyId = Column("shopifyId", String(100), nullable=True)
    shopifyCreatedAt = Column("shopifyCreatedAt", DateTime, nullable=True)
    shopifyUpdatedAt = Column("shopifyUpdatedAt", DateTime, nullable=True)

    # Source information - matching Prisma schema
    source = Column(String, nullable=True, default="webhook", index=True)
    format = Column(String, nullable=True, default="rest", index=True)
    receivedAt = Column("receivedAt", DateTime, nullable=True, default=func.now())

    # Indexes
    __table_args__ = (
        Index("ix_raw_order_shop_id_shopify_id", "shopId", "shopifyId"),
        Index("ix_raw_order_shop_id_shopify_updated_at", "shopId", "shopifyUpdatedAt"),
        Index("ix_raw_order_shop_id_shopify_created_at", "shopId", "shopifyCreatedAt"),
        Index("ix_raw_order_shop_id_source", "shopId", "source"),
        Index("ix_raw_order_shop_id_format", "shopId", "format"),
    )

    def __repr__(self) -> str:
        return f"<RawOrder(shopId={self.shopId}, shopifyId={self.shopifyId})>"


class RawProduct(Base, IDMixin, ShopMixin):
    """Raw product data model"""

    __tablename__ = "RawProduct"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Raw data - matching Prisma schema
    payload = Column(JSON, nullable=False)
    extractedAt = Column("extractedAt", DateTime, nullable=False, default=func.now())

    # Shopify identifiers - matching Prisma schema
    shopifyId = Column("shopifyId", String(100), nullable=True)
    shopifyCreatedAt = Column("shopifyCreatedAt", DateTime, nullable=True)
    shopifyUpdatedAt = Column("shopifyUpdatedAt", DateTime, nullable=True)

    # Source information - matching Prisma schema
    source = Column(String, nullable=True, default="webhook", index=True)
    format = Column(String, nullable=True, default="rest", index=True)
    receivedAt = Column("receivedAt", DateTime, nullable=True, default=func.now())

    # Indexes
    __table_args__ = (
        Index("ix_raw_product_shop_id_shopify_id", "shopId", "shopifyId"),
        Index(
            "ix_raw_product_shop_id_shopify_updated_at", "shopId", "shopifyUpdatedAt"
        ),
        Index(
            "ix_raw_product_shop_id_shopify_created_at", "shopId", "shopifyCreatedAt"
        ),
        Index("ix_raw_product_shop_id_source", "shopId", "source"),
        Index("ix_raw_product_shop_id_format", "shopId", "format"),
    )

    def __repr__(self) -> str:
        return f"<RawProduct(shopId={self.shopId}, shopifyId={self.shopifyId})>"


class RawCustomer(Base, IDMixin, ShopMixin):
    """Raw customer data model"""

    __tablename__ = "RawCustomer"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Raw data - matching Prisma schema
    payload = Column(JSON, nullable=False)
    extractedAt = Column("extractedAt", DateTime, nullable=False, default=func.now())

    # Shopify identifiers - matching Prisma schema
    shopifyId = Column("shopifyId", String(100), nullable=True)
    shopifyCreatedAt = Column("shopifyCreatedAt", DateTime, nullable=True)
    shopifyUpdatedAt = Column("shopifyUpdatedAt", DateTime, nullable=True)

    # Source information - matching Prisma schema
    source = Column(String, nullable=True, default="webhook", index=True)
    format = Column(String, nullable=True, default="rest", index=True)
    receivedAt = Column("receivedAt", DateTime, nullable=True, default=func.now())

    # Indexes
    __table_args__ = (
        Index("ix_raw_customer_shop_id_shopify_id", "shopId", "shopifyId"),
        Index(
            "ix_raw_customer_shop_id_shopify_updated_at",
            "shopId",
            "shopifyUpdatedAt",
        ),
        Index(
            "ix_raw_customer_shop_id_shopify_created_at",
            "shopId",
            "shopifyCreatedAt",
        ),
        Index("ix_raw_customer_shop_id_source", "shopId", "source"),
        Index("ix_raw_customer_shop_id_format", "shopId", "format"),
    )

    def __repr__(self) -> str:
        return f"<RawCustomer(shopId={self.shopId}, shopifyId={self.shopifyId})>"


class RawCollection(Base, IDMixin, ShopMixin):
    """Raw collection data model"""

    __tablename__ = "RawCollection"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Raw data - matching Prisma schema
    payload = Column(JSON, nullable=False)
    extractedAt = Column("extractedAt", DateTime, nullable=False, default=func.now())

    # Shopify identifiers - matching Prisma schema
    shopifyId = Column("shopifyId", String(100), nullable=True)
    shopifyCreatedAt = Column("shopifyCreatedAt", DateTime, nullable=True)
    shopifyUpdatedAt = Column("shopifyUpdatedAt", DateTime, nullable=True)

    # Source information - matching Prisma schema
    source = Column(String, nullable=True, default="webhook", index=True)
    format = Column(String, nullable=True, default="rest", index=True)
    receivedAt = Column("receivedAt", DateTime, nullable=True, default=func.now())

    # Indexes
    __table_args__ = (
        Index("ix_raw_collection_shop_id_shopify_id", "shopId", "shopifyId"),
        Index(
            "ix_raw_collection_shop_id_shopify_updated_at",
            "shopId",
            "shopifyUpdatedAt",
        ),
        Index(
            "ix_raw_collection_shop_id_shopify_created_at",
            "shopId",
            "shopifyCreatedAt",
        ),
        Index("ix_raw_collection_shop_id_source", "shopId", "source"),
        Index("ix_raw_collection_shop_id_format", "shopId", "format"),
    )

    def __repr__(self) -> str:
        return f"<RawCollection(shopId={self.shopId}, shopifyId={self.shopifyId})>"
