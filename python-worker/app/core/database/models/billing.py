"""
Billing models for SQLAlchemy

Represents billing plans, invoices, and events.
"""

from datetime import UTC, datetime
from decimal import Decimal
from sqlalchemy import Column, String, Boolean, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSON, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.types import DECIMAL, Integer
from .base import BaseModel, ShopMixin
from .enums import BillingPlanStatus, InvoiceStatus


class BillingPlan(BaseModel, ShopMixin):
    """Billing plan model for shop billing plans"""

    __tablename__ = "billing_plans"

    # Plan identification
    shop_domain = Column("shop_domain", String(255), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String, nullable=False)  # BillingPlanType enum
    status = Column(
        String, default=BillingPlanStatus.ACTIVE, nullable=False, index=True
    )

    # Trial information
    is_trial_active = Column(Boolean, default=True, nullable=False, index=True)
    trial_threshold = Column(DECIMAL(10, 2), default=200.00, nullable=False)
    trial_revenue = Column(DECIMAL(12, 2), default=0.00, nullable=False)
    trial_usage_records_count = Column(Integer, default=0, nullable=False)
    trial_completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    # Relationships

    # ✅ PATTERN 1: Shopify Subscription (Created After Trial)
    subscription_id = Column(String(255), nullable=True, index=True)
    subscription_line_item_id = Column(String(255), nullable=True)
    subscription_status = Column(
        String(50), default="none"
    )  # 'none', 'PENDING', 'ACTIVE', 'DECLINED', 'CANCELLED'
    subscription_confirmation_url = Column(Text, nullable=True)
    subscription_created_at = Column(TIMESTAMP(timezone=True), nullable=True)
    subscription_activated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    configuration = Column(JSON, nullable=True)

    billing_metadata = Column(JSON, nullable=True)

    # Timestamps
    effective_from = Column(TIMESTAMP(timezone=True), default=datetime.now(UTC))
    effective_to = Column(TIMESTAMP(timezone=True), nullable=True, index=True)

    # ✅ PATTERN 1: State Flags
    requires_subscription_approval = Column(Boolean, default=False, index=True)

    events = relationship(
        "BillingEvent", back_populates="plan", cascade="all, delete-orphan"
    )
    invoices = relationship(
        "BillingInvoice", back_populates="plan", cascade="all, delete-orphan"
    )

    shop = relationship("Shop", back_populates="billing_plans")

    # Indexes
    __table_args__ = (
        Index("ix_billing_plan_shop_id", "shop_id", unique=True),
        Index("ix_billing_plan_shop_domain", "shop_domain"),
        Index("ix_billing_plan_status", "status"),
        Index("ix_billing_plan_effective_from", "effective_from"),
    )

    def __repr__(self) -> str:
        return f"<BillingPlan(shop_id={self.shop_id}, name={self.name}, status={self.status})>"

    @property
    def is_in_trial_phase(self) -> bool:
        """Check if currently in trial phase (no subscription yet)"""
        return (
            self.is_trial_active
            and self.subscription_id is None
            and self.subscription_status in ["none", None]
        )

    @property
    def is_awaiting_subscription_approval(self) -> bool:
        """Check if waiting for user to approve subscription"""
        return (
            not self.is_trial_active
            and self.requires_subscription_approval
            and self.subscription_status == "PENDING"
        )

    @property
    def has_active_subscription(self) -> bool:
        """Check if has active Shopify subscription"""
        return self.subscription_id is not None and self.subscription_status == "ACTIVE"

    @property
    def trial_progress_percentage(self) -> float:
        """Calculate trial progress percentage"""
        if not self.trial_threshold or self.trial_threshold == 0:
            return 0.0
        return min(
            100.0, (float(self.trial_revenue) / float(self.trial_threshold)) * 100
        )

    @property
    def trial_remaining_revenue(self) -> Decimal:
        """Calculate remaining revenue until trial completion"""
        if not self.is_trial_active:
            return Decimal("0.00")
        remaining = self.trial_threshold - self.trial_revenue
        return max(Decimal("0.00"), remaining)


class BillingInvoice(BaseModel, ShopMixin):
    """Billing invoice model for shop invoices"""

    __tablename__ = "billing_invoices"

    # Invoice identification
    plan_id = Column(String, ForeignKey("billing_plans.id"), nullable=False)
    invoice_number = Column(String(100), unique=True, nullable=False)
    status = Column(String, default=InvoiceStatus.PENDING, nullable=False, index=True)

    # Financial details
    subtotal = Column(DECIMAL(10, 2), nullable=False)
    taxes = Column(DECIMAL(10, 2), nullable=False)
    discounts = Column(DECIMAL(10, 2), nullable=False)
    total = Column(DECIMAL(10, 2), nullable=False)
    currency = Column(String(3), nullable=False)

    # Billing period
    period_start = Column(TIMESTAMP(timezone=True), nullable=False)
    period_end = Column(TIMESTAMP(timezone=True), nullable=False)
    metrics_id = Column(String(255), nullable=False)
    due_date = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    paid_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Payment information
    shopify_charge_id = Column(String(255), nullable=True, index=True)
    payment_method = Column(String(50), nullable=True)
    payment_reference = Column(String(255), nullable=True)
    billing_metadata = Column(JSON, default={}, nullable=False)
    # Relationships
    plan = relationship("BillingPlan", back_populates="invoices")
    shop = relationship("Shop", back_populates="billing_invoices")
    # Indexes
    __table_args__ = (
        Index("ix_billing_invoice_shop_id", "shop_id"),
        Index("ix_billing_invoice_plan_id", "plan_id"),
        Index("ix_billing_invoice_status", "status"),
        Index("ix_billing_invoice_due_date", "due_date"),
        Index("ix_billing_invoice_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<BillingInvoice(shop_id={self.shop_id}, invoice_number={self.invoice_number}, status={self.status})>"


class BillingEvent(BaseModel, ShopMixin):
    """Billing event model for tracking billing events"""

    __tablename__ = "billing_events"

    # Foreign key to BillingPlan
    plan_id = Column(String, ForeignKey("billing_plans.id"), nullable=False, index=True)

    # Event identification
    type = Column(String, nullable=False, index=True)  # BillingEventType enum
    data = Column(JSON, default={}, nullable=False)
    billing_metadata = Column(JSON, default={}, nullable=False)

    # Timing
    occurred_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    processed_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)

    # Relationships
    plan = relationship("BillingPlan", back_populates="events")
    shop = relationship("Shop", back_populates="billing_events")
    # Indexes
    __table_args__ = (
        Index("ix_billing_event_shop_id", "shop_id"),
        Index("ix_billing_event_type", "type"),
        Index("ix_billing_event_occurred_at", "occurred_at"),
        Index("ix_billing_event_processed_at", "processed_at"),
    )

    def __repr__(self) -> str:
        return f"<BillingEvent(shop_id={self.shop_id}, type={self.type})>"
