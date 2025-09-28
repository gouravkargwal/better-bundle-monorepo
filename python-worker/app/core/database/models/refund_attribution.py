"""
Refund attribution model for SQLAlchemy

Represents refund attribution data for revenue adjustment tracking.
"""

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSON, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.types import DECIMAL
from .base import BaseModel, ShopMixin, CustomerMixin


class RefundAttribution(BaseModel, ShopMixin, CustomerMixin):
    """Refund attribution model for revenue adjustment attribution"""

    __tablename__ = "refund_attributions"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Attribution identification - matching Prisma schema
    session_id = Column(
        "session_id", String(255), ForeignKey("user_sessions.id"), nullable=True
    )  # May be null for refunds without session
    order_id = Column("order_id", String(255), nullable=False, index=True)
    refund_id = Column("refund_id", String(255), nullable=False, index=True)

    # Refund details
    refunded_at = Column(
        "refunded_at", TIMESTAMP(timezone=True), nullable=False, index=True
    )
    total_refund_amount = Column("total_refund_amount", DECIMAL(10, 2), nullable=False)
    currency_code = Column("currency_code", String(10), default="USD", nullable=False)

    # Attribution data - similar to PurchaseAttribution
    contributing_extensions = Column("contributing_extensions", JSON, nullable=False)
    attribution_weights = Column("attribution_weights", JSON, nullable=False)
    total_refunded_revenue = Column(
        "total_refunded_revenue", DECIMAL(10, 2), nullable=False
    )
    attributed_refund = Column(
        "attributed_refund", JSON, nullable=False
    )  # Per-extension refund amounts
    total_interactions = Column("total_interactions", Integer, nullable=False)
    interactions_by_extension = Column(
        "interactions_by_extension", JSON, nullable=False
    )

    # Timing - matching Prisma schema
    attribution_algorithm = Column(
        "attribution_algorithm", String(50), default="multi_touch", nullable=False
    )
    attribution_metadata = Column("metadata", JSON, default={}, nullable=False)

    # Relationships
    session = relationship("UserSession", back_populates="refund_attributions")
    shop = relationship("Shop", back_populates="refund_attributions")

    # Indexes
    __table_args__ = (
        Index(
            "ix_refund_attribution_shop_id_refund_id",
            "shop_id",
            "refund_id",
            unique=True,
        ),
        Index("ix_refund_attribution_session_id", "session_id"),
        Index("ix_refund_attribution_order_id", "order_id"),
        Index("ix_refund_attribution_refund_id", "refund_id"),
        Index("ix_refund_attribution_customer_id", "customer_id"),
        Index("ix_refund_attribution_shop_id", "shop_id"),
        Index("ix_refund_attribution_refunded_at", "refunded_at"),
        Index("ix_refund_attribution_shop_id_refunded_at", "shop_id", "refunded_at"),
        Index(
            "ix_refund_attribution_shop_id_customer_id_refunded_at",
            "shop_id",
            "customer_id",
            "refunded_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<RefundAttribution(shop_id={self.shop_id}, refund_id={self.refund_id})>"
        )
