"""
Order data models for SQLAlchemy

Represents order information and line items.
"""

from sqlalchemy import (
    Column,
    String,
    Float,
    Boolean,
    Text,
    ForeignKey,
    Integer,
    Index,
)
from sqlalchemy.dialects.postgresql import JSON, TIMESTAMP
from sqlalchemy.orm import relationship
from .base import BaseModel, ShopMixin


class OrderData(BaseModel, ShopMixin):
    """Order data model representing Shopify orders"""

    __tablename__ = "order_data"
    order_id = Column(String, nullable=False, index=True)
    order_name = Column(String(100), nullable=True)
    customer_id = Column(String(100), nullable=True, index=True)
    customer_phone = Column(String(50), nullable=True)
    customer_display_name = Column(String(255), nullable=True)
    customer_state = Column(String(50), nullable=True, index=True)
    customer_verified_email = Column(Boolean, default=False, nullable=True)
    customer_default_address = Column(JSON, default={}, nullable=True)
    total_amount = Column(Float, default=0.0, nullable=False, index=True)
    subtotal_amount = Column(Float, default=0.0, nullable=True)
    total_tax_amount = Column(Float, default=0.0, nullable=True)
    total_shipping_amount = Column(Float, default=0.0, nullable=True)
    total_refunded_amount = Column(Float, default=0.0, nullable=True)
    total_outstanding_amount = Column(Float, default=0.0, nullable=True)
    order_date = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    processed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    cancelled_at = Column(TIMESTAMP(timezone=True), nullable=True)
    cancel_reason = Column(String(500), default="", nullable=True)
    order_locale = Column(String(10), default="en", nullable=True)
    currency_code = Column(String(10), default="USD", nullable=True, index=True)
    presentment_currency_code = Column(String(10), default="USD", nullable=True)

    confirmed = Column(Boolean, default=False, nullable=False)
    test = Column(Boolean, default=False, nullable=False)
    financial_status = Column(String(50), nullable=True, index=True)
    fulfillment_status = Column(String(50), nullable=True, index=True)
    order_status = Column(String(50), nullable=True, index=True)

    tags = Column(JSON, default=[], nullable=True)
    note = Column(Text, default="", nullable=True)
    note_attributes = Column(JSON, default=[], nullable=True)
    shipping_address = Column(JSON, default={}, nullable=True)
    billing_address = Column(JSON, default={}, nullable=True)
    discount_applications = Column(JSON, default=[], nullable=True)
    metafields = Column(JSON, default=[], nullable=True)
    fulfillments = Column(JSON, default=[], nullable=True)
    transactions = Column(JSON, default=[], nullable=True)
    extras = Column(JSON, default={}, nullable=True)
    shop = relationship("Shop", back_populates="order_data")
    line_items = relationship(
        "LineItemData", back_populates="order", cascade="all, delete-orphan"
    )
    created_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)

    # Whether this order still owes an attribution, decided once when the order
    # is written rather than re-derived on every reconciler pass.
    #
    # NULL means there is nothing to attribute — no recommendation stamp on any
    # line, no click recorded on the cart — and such an order is never looked at
    # again. Only orders carrying evidence get a state.
    #
    # This exists to keep the reconciler's cost proportional to the *backlog*
    # rather than to order volume. It used to find work by joining every order
    # in a 14-day window to its line items and testing
    # `properties::jsonb ? '_bb_rec_impression_id'` — a cast, so unindexable,
    # so a sequential scan of every recent line item, 96 times a day, almost
    # always to discover nothing. With a partial index on 'pending' the query
    # reads only the orders actually stuck, whether the merchant does a hundred
    # orders a month or a hundred thousand.
    # No `index=True`: a plain btree here would hold a row per order forever,
    # almost all of them NULL, which is precisely the unbounded growth the
    # partial index below exists to avoid.
    attribution_state = Column(String(20), nullable=True)

    # Retry accounting, mirroring `product_enrichments`. Without it a single
    # order that can never be attributed is republished every 15 minutes for
    # the whole 14-day window.
    attribution_attempts = Column(
        Integer, nullable=False, default=0, server_default="0"
    )
    attribution_last_error = Column(Text, nullable=True)

    __table_args__ = (
        # Partial, so the index physically contains only the backlog — normally
        # near empty. A plain index on `attribution_state` would carry a row per
        # order forever and defeat the point.
        Index(
            "ix_order_data_attribution_pending",
            "order_date",
            postgresql_where=Column("attribution_state") == "pending",
        ),
    )

    def __repr__(self) -> str:
        return f"<OrderData(order_id={self.order_id}, shop_id={self.shop_id})>"


class LineItemData(BaseModel):
    """Line item data model representing order line items"""

    __tablename__ = "line_item_data"

    order_id = Column(String, ForeignKey("order_data.id"), nullable=False)
    product_id = Column(String, nullable=True)
    variant_id = Column(String, nullable=True)

    title = Column(String, nullable=True)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    original_unit_price = Column(Float, nullable=True)  # From originalUnitPriceSet
    discounted_unit_price = Column(Float, nullable=True)  # From discountedUnitPriceSet
    currency_code = Column(String(10), nullable=True)  # From price sets
    variant_data = Column(
        JSON, default={}, nullable=True
    )  # Complete variant information
    properties = Column(JSON, default={}, nullable=True)

    order = relationship("OrderData", back_populates="line_items")

    def __repr__(self) -> str:
        return f"<LineItemData(order_id={self.order_id}, product_id={self.product_id})>"
