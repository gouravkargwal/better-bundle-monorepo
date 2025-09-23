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

    __tablename__ = "raw_orders"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Raw data - matching Prisma schema
    payload = Column(JSON, nullable=False)
    extracted_at = Column("extracted_at", DateTime, nullable=False, default=func.now())

    # Shopify identifiers - matching Prisma schema
    shopify_id = Column("shopify_id", String(100), nullable=True)
    shopify_created_at = Column("shopify_created_at", DateTime, nullable=True)
    shopify_updated_at = Column("shopify_updated_at", DateTime, nullable=True)

    # Source information - matching Prisma schema
    source = Column(String, nullable=True, default="webhook", index=True)
    format = Column(String, nullable=True, default="rest", index=True)
    received_at = Column("received_at", DateTime, nullable=True, default=func.now())

    # Indexes
    __table_args__ = (
        Index("ix_raw_order_shop_id_shopify_id", "shop_id", "shopify_id"),
        Index(
            "ix_raw_order_shop_id_shopify_updated_at", "shop_id", "shopify_updated_at"
        ),
        Index(
            "ix_raw_order_shop_id_shopify_created_at", "shop_id", "shopify_created_at"
        ),
        Index("ix_raw_order_shop_id_source", "shop_id", "source"),
        Index("ix_raw_order_shop_id_format", "shop_id", "format"),
    )

    def __repr__(self) -> str:
        return f"<RawOrder(shop_id={self.shop_id}, shopify_id={self.shopify_id})>"


class RawProduct(Base, IDMixin, ShopMixin):
    """Raw product data model"""

    __tablename__ = "raw_products"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Raw data - matching Prisma schema
    payload = Column(JSON, nullable=False)
    extracted_at = Column("extracted_at", DateTime, nullable=False, default=func.now())

    # Shopify identifiers - matching Prisma schema
    shopify_id = Column("shopify_id", String(100), nullable=True)
    shopify_created_at = Column("shopify_created_at", DateTime, nullable=True)
    shopify_updated_at = Column("shopify_updated_at", DateTime, nullable=True)

    # Source information - matching Prisma schema
    source = Column(String, nullable=True, default="webhook", index=True)
    format = Column(String, nullable=True, default="rest", index=True)
    received_at = Column("received_at", DateTime, nullable=True, default=func.now())

    # Indexes
    __table_args__ = (
        Index("ix_raw_product_shop_id_shopify_id", "shop_id", "shopify_id"),
        Index(
            "ix_raw_product_shop_id_shopify_updated_at", "shop_id", "shopify_updated_at"
        ),
        Index(
            "ix_raw_product_shop_id_shopify_created_at", "shop_id", "shopify_created_at"
        ),
        Index("ix_raw_product_shop_id_source", "shop_id", "source"),
        Index("ix_raw_product_shop_id_format", "shop_id", "format"),
    )

    def __repr__(self) -> str:
        return f"<RawProduct(shop_id={self.shop_id}, shopify_id={self.shopify_id})>"


class RawCustomer(Base, IDMixin, ShopMixin):
    """Raw customer data model"""

    __tablename__ = "raw_customers"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Raw data - matching Prisma schema
    payload = Column(JSON, nullable=False)
    extracted_at = Column("extracted_at", DateTime, nullable=False, default=func.now())

    # Shopify identifiers - matching Prisma schema
    shopify_id = Column("shopify_id", String(100), nullable=True)
    shopify_created_at = Column("shopify_created_at", DateTime, nullable=True)
    shopify_updated_at = Column("shopify_updated_at", DateTime, nullable=True)

    # Source information - matching Prisma schema
    source = Column(String, nullable=True, default="webhook", index=True)
    format = Column(String, nullable=True, default="rest", index=True)
    received_at = Column("received_at", DateTime, nullable=True, default=func.now())

    # Indexes
    __table_args__ = (
        Index("ix_raw_customer_shop_id_shopify_id", "shop_id", "shopify_id"),
        Index(
            "ix_raw_customer_shop_id_shopify_updated_at",
            "shop_id",
            "shopify_updated_at",
        ),
        Index(
            "ix_raw_customer_shop_id_shopify_created_at",
            "shop_id",
            "shopify_created_at",
        ),
        Index("ix_raw_customer_shop_id_source", "shop_id", "source"),
        Index("ix_raw_customer_shop_id_format", "shop_id", "format"),
    )

    def __repr__(self) -> str:
        return f"<RawCustomer(shop_id={self.shop_id}, shopify_id={self.shopify_id})>"


class RawCollection(Base, IDMixin, ShopMixin):
    """Raw collection data model"""

    __tablename__ = "raw_collections"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Raw data - matching Prisma schema
    payload = Column(JSON, nullable=False)
    extracted_at = Column("extracted_at", DateTime, nullable=False, default=func.now())

    # Shopify identifiers - matching Prisma schema
    shopify_id = Column("shopify_id", String(100), nullable=True)
    shopify_created_at = Column("shopify_created_at", DateTime, nullable=True)
    shopify_updated_at = Column("shopify_updated_at", DateTime, nullable=True)

    # Source information - matching Prisma schema
    source = Column(String, nullable=True, default="webhook", index=True)
    format = Column(String, nullable=True, default="rest", index=True)
    received_at = Column("received_at", DateTime, nullable=True, default=func.now())

    # Indexes
    __table_args__ = (
        Index("ix_raw_collection_shop_id_shopify_id", "shop_id", "shopify_id"),
        Index(
            "ix_raw_collection_shop_id_shopify_updated_at",
            "shop_id",
            "shopify_updated_at",
        ),
        Index(
            "ix_raw_collection_shop_id_shopify_created_at",
            "shop_id",
            "shopify_created_at",
        ),
        Index("ix_raw_collection_shop_id_source", "shop_id", "source"),
        Index("ix_raw_collection_shop_id_format", "shop_id", "format"),
    )

    def __repr__(self) -> str:
        return f"<RawCollection(shop_id={self.shop_id}, shopify_id={self.shopify_id})>"
