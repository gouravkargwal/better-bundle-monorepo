"""
Refund models for SQLAlchemy

Represents refund data and attribution adjustments.
"""

from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.types import DECIMAL, BigInteger
from .base import BaseModel, ShopMixin


class RefundData(BaseModel, ShopMixin):
    """Refund data model for tracking refunds"""

    __tablename__ = "refund_data"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Refund identification - matching Prisma schema
    order_id = Column("order_id", BigInteger, nullable=False)
    refund_id = Column("refund_id", String(255), nullable=False, index=True)
    refunded_at = Column("refunded_at", DateTime, nullable=False)

    # Refund details - matching Prisma schema
    note = Column(String, default="", nullable=True)
    restock = Column(Boolean, default=False, nullable=False)
    total_refund_amount = Column("total_refund_amount", DECIMAL(10, 2), nullable=False)
    currency_code = Column("currency_code", String(10), default="USD", nullable=False)

    # Relationships
    shop = relationship("Shop", back_populates="refund_data")
    adjustments = relationship(
        "RefundAttributionAdjustment",
        back_populates="refund",
        cascade="all, delete-orphan",
    )
    line_items = relationship(
        "RefundLineItemData", back_populates="refund", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_refund_data_shop_id_refund_id", "shop_id", "refund_id", unique=True),
        Index("ix_refund_data_shop_id_order_id", "shop_id", "order_id"),
        Index("ix_refund_data_refunded_at", "refunded_at"),
    )

    def __repr__(self) -> str:
        return f"<RefundData(shop_id={self.shop_id}, refund_id={self.refund_id})>"


class RefundLineItemData(BaseModel):
    """Refund line item data model"""

    __tablename__ = "refund_line_item_data"

    # Foreign keys - matching Prisma schema
    refund_id = Column(
        "refund_id", String, ForeignKey("refund_data.id"), nullable=False
    )
    order_id = Column("order_id", BigInteger, nullable=False)
    product_id = Column("product_id", String(255), nullable=True)
    variant_id = Column("variant_id", String(255), nullable=True)

    # Line item details - matching Prisma schema
    quantity = Column(Integer, nullable=False)
    unit_price = Column("unit_price", DECIMAL(10, 2), nullable=False)
    refund_amount = Column("refund_amount", DECIMAL(10, 2), nullable=False)
    properties = Column(JSON, default={}, nullable=True)

    # Relationships
    refund = relationship("RefundData", back_populates="line_items")

    # Indexes
    __table_args__ = (
        Index("ix_refund_line_item_data_refund_id", "refund_id"),
        Index("ix_refund_line_item_data_order_id", "order_id"),
        Index("ix_refund_line_item_data_product_id", "product_id"),
    )

    def __repr__(self) -> str:
        return f"<RefundLineItemData(refund_id={self.refund_id}, product_id={self.product_id})>"


class RefundAttributionAdjustment(BaseModel, ShopMixin):
    """Refund attribution adjustment model"""

    __tablename__ = "refund_attribution_adjustments"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Attribution identification - matching Prisma schema
    order_id = Column("order_id", BigInteger, nullable=False)
    refund_id = Column(
        "refund_id", String, ForeignKey("refund_data.id"), nullable=False
    )

    # Attribution data - matching Prisma schema
    per_extension_refund = Column(
        "per_extension_refund", JSON, default={}, nullable=False
    )
    total_refund_amount = Column("total_refund_amount", DECIMAL(10, 2), nullable=False)
    computed_at = Column("computed_at", DateTime, nullable=False, index=True)
    refund_metadata = Column("metadata", JSON, default={}, nullable=False)

    # Relationships
    refund = relationship("RefundData", back_populates="adjustments")
    shop = relationship("Shop", back_populates="refund_attribution_adjustments")

    # Indexes
    __table_args__ = (
        Index(
            "ix_refund_attribution_adjustment_shop_id_refund_id",
            "shop_id",
            "refund_id",
            unique=True,
        ),
        Index(
            "ix_refund_attribution_adjustment_shop_id_order_id", "shop_id", "order_id"
        ),
        Index("ix_refund_attribution_adjustment_computed_at", "computed_at"),
    )

    def __repr__(self) -> str:
        return f"<RefundAttributionAdjustment(shop_id={self.shop_id}, refund_id={self.refund_id})>"
