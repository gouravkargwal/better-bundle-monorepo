"""
Raw data models for SQLAlchemy

Represents raw data from Shopify webhooks and API calls.
"""

from sqlalchemy import Column, String, DateTime, Index, func
from sqlalchemy.dialects.postgresql import JSON
from .base import Base, IDMixin, ShopMixin


class RawOrder(Base, IDMixin, ShopMixin):
    """Raw order data model"""

    __tablename__ = "raw_orders"

    payload = Column(JSON, nullable=False)
    extracted_at = Column(DateTime, nullable=False, default=func.now())
    shopify_id = Column(String(100), nullable=True)
    shopify_created_at = Column(DateTime, nullable=True)
    shopify_updated_at = Column(DateTime, nullable=True)
    source = Column(String, nullable=True, default="webhook", index=True)
    format = Column(String, nullable=True, default="rest", index=True)
    received_at = Column(DateTime, nullable=True, default=func.now())

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

    payload = Column(JSON, nullable=False)
    extracted_at = Column(DateTime, nullable=False, default=func.now())
    shopify_id = Column(String(100), nullable=True)
    shopify_created_at = Column(DateTime, nullable=True)
    shopify_updated_at = Column(DateTime, nullable=True)
    source = Column(String, nullable=True, default="webhook", index=True)
    format = Column(String, nullable=True, default="rest", index=True)
    received_at = Column(DateTime, nullable=True, default=func.now())

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
    payload = Column(JSON, nullable=False)
    extracted_at = Column(DateTime, nullable=False, default=func.now())
    shopify_id = Column(String(100), nullable=True)
    shopify_created_at = Column(DateTime, nullable=True)
    shopify_updated_at = Column(DateTime, nullable=True)
    source = Column(String, nullable=True, default="webhook", index=True)
    format = Column(String, nullable=True, default="rest", index=True)
    received_at = Column(DateTime, nullable=True, default=func.now())

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
    payload = Column(JSON, nullable=False)
    extracted_at = Column(DateTime, nullable=False, default=func.now())
    shopify_id = Column(String(100), nullable=True)
    shopify_created_at = Column(DateTime, nullable=True)
    shopify_updated_at = Column(DateTime, nullable=True)
    source = Column(String, nullable=True, default="webhook", index=True)
    format = Column(String, nullable=True, default="rest", index=True)
    received_at = Column(DateTime, nullable=True, default=func.now())

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
