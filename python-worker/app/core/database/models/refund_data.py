"""
RefundData model for storing normalized refund information
"""

from sqlalchemy import Column, String, DateTime, Float, Boolean, JSON, Index
from sqlalchemy.orm import relationship
from app.core.database.models.base import BaseModel, ShopMixin


class RefundData(BaseModel, ShopMixin):
    """
    Model for storing normalized refund data from Shopify orders.

    This table stores refund information in a canonical format, similar to OrderData,
    to avoid the need for refund attribution consumers to process raw Shopify data.
    """

    __tablename__ = "refund_data"

    # Shopify identifiers
    order_id = Column(String, nullable=False, index=True)  # Normalized order ID
    refund_id = Column(String, nullable=False, index=True)  # Normalized refund ID

    # Refund details
    refunded_at = Column(DateTime(timezone=True), nullable=False)
    total_refund_amount = Column(Float, nullable=False)
    currency_code = Column(String, nullable=False, default="USD")
    note = Column(String)
    restock = Column(Boolean, default=False)

    # Refund line items (stored as JSON for flexibility)
    refund_line_items = Column(JSON)

    # Relationships
    shop = relationship("Shop", back_populates="refund_data")

    # Indexes and constraints
    __table_args__ = (
        Index("idx_refund_data_shop_order", "shop_id", "order_id"),
        Index("idx_refund_data_shop_refund", "shop_id", "refund_id"),
        Index("idx_refund_data_refunded_at", "refunded_at"),
        # Enforce uniqueness to prevent duplicate rows on re-normalization
        Index(
            "ux_refund_data_shop_refund",
            "shop_id",
            "refund_id",
            unique=True,
        ),
    )

    def __repr__(self):
        return f"<RefundData(id={self.id}, shop_id={self.shop_id}, order_id={self.order_id}, refund_id={self.refund_id})>"
