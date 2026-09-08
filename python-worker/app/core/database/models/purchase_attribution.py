"""
Purchase attribution model for SQLAlchemy

Represents purchase attribution data for revenue tracking.
"""

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSON, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.types import DECIMAL
from .base import BaseModel, ShopMixin, CustomerMixin


class PurchaseAttribution(BaseModel, ShopMixin, CustomerMixin):
    """Purchase attribution model for revenue attribution"""

    __tablename__ = "purchase_attributions"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Attribution identification - matching Prisma schema
    # Nullable on purpose.
    #
    # A storefront recommendation is attributed by the impression id stamped on
    # the order line, which needs no session at all — and gets none, because the
    # visitor id is consent-gated and absent on any store without a cookie
    # banner. While this was NOT NULL the engine computed the attribution
    # correctly and then refused to save it, so every product-page sale was
    # measured and immediately discarded.
    session_id = Column(
        "session_id", String(255), ForeignKey("user_sessions.id"), nullable=True
    )
    order_id = Column("order_id", String(255), nullable=False, index=True)

    # Attribution data - matching Prisma schema
    contributing_extensions = Column("contributing_extensions", JSON, nullable=False)
    attribution_weights = Column("attribution_weights", JSON, nullable=False)
    total_revenue = Column("total_revenue", DECIMAL(10, 2), nullable=False)
    attributed_revenue = Column("attributed_revenue", JSON, nullable=False)
    total_interactions = Column("total_interactions", Integer, nullable=False)
    interactions_by_extension = Column(
        "interactions_by_extension", JSON, nullable=False
    )

    # Timing - matching Prisma schema
    purchase_at = Column(
        "purchase_at", TIMESTAMP(timezone=True), nullable=False, index=True
    )
    attribution_algorithm = Column(
        "attribution_algorithm", String(50), default="multi_touch", nullable=False
    )
    attribution_metadata = Column("metadata", JSON, default={}, nullable=False)

    # Relationships
    session = relationship("UserSession", back_populates="attributions")
    shop = relationship("Shop", back_populates="purchase_attributions")
    # One commission per attribution — the uniqueness is enforced on the
    # commission side by uq_commission_purchase_attribution.
    commission_record = relationship(
        "CommissionRecord",
        back_populates="purchase_attribution",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Indexes
    __table_args__ = (
        Index(
            "ix_purchase_attribution_shop_id_order_id",
            "shop_id",
            "order_id",
            unique=True,
        ),
        Index("ix_purchase_attribution_session_id", "session_id"),
        Index("ix_purchase_attribution_order_id", "order_id"),
        Index("ix_purchase_attribution_customer_id", "customer_id"),
        Index("ix_purchase_attribution_shop_id", "shop_id"),
        Index("ix_purchase_attribution_purchase_at", "purchase_at"),
        Index("ix_purchase_attribution_shop_id_purchase_at", "shop_id", "purchase_at"),
        Index(
            "ix_purchase_attribution_shop_id_customer_id_purchase_at",
            "shop_id",
            "customer_id",
            "purchase_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PurchaseAttribution(shop_id={self.shop_id}, order_id={self.order_id})>"
        )
