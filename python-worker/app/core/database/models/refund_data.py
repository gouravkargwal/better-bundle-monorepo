"""
RefundData model for storing normalized refund information.

Recovered from the pipeline removed in c6f6af7. The billing half of that
original design (`RefundAttribution`) is deliberately not restored: refunds
adjust what we *recommend*, not what we *bill*.

`refund_line_items` is the reason this table exists. The order-level
`order_data.total_refunded_amount` says money came back but not which product
came back with it, and "which product" is the entire signal the recommender
needs.
"""

from sqlalchemy import Column, String, Float, Boolean, JSON, Index
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship

from app.core.database.models.base import BaseModel, ShopMixin


class RefundData(BaseModel, ShopMixin):
    """Normalized refund data from Shopify orders."""

    __tablename__ = "refund_data"

    # `order_id` holds the internal `order_data.id`, not the Shopify order id,
    # so it joins against `line_item_data.order_id` the same way line items do.
    order_id = Column(String, nullable=False, index=True)
    refund_id = Column(String, nullable=False, index=True)

    refunded_at = Column(TIMESTAMP(timezone=True), nullable=False)
    total_refund_amount = Column(Float, nullable=False)
    currency_code = Column(String, nullable=False, default="USD")
    note = Column(String)
    restock = Column(Boolean, default=False)

    # [{product_id, variant_id, quantity, refund_amount}, ...]
    refund_line_items = Column(JSON)

    shop = relationship("Shop", back_populates="refund_data")

    __table_args__ = (
        Index("idx_refund_data_shop_order", "shop_id", "order_id"),
        Index("idx_refund_data_refunded_at", "refunded_at"),
        # Re-normalizing the same order must not duplicate its refunds.
        Index("ux_refund_data_shop_refund", "shop_id", "refund_id", unique=True),
    )

    def __repr__(self):
        return (
            f"<RefundData(shop_id={self.shop_id}, order_id={self.order_id}, "
            f"refund_id={self.refund_id})>"
        )
