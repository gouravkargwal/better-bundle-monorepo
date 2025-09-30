"""
Billing models for SQLAlchemy

Represents billing plans, invoices, and events.
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSON, TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.types import DECIMAL
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

    # Plan configuration
    configuration = Column(JSON, default={}, nullable=False)
    effective_from = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    effective_until = Column(DateTime, nullable=True)

    # Trial information
    is_trial_active = Column(Boolean, default=True, nullable=False)
    trial_threshold = Column(DECIMAL(10, 2), default=200.00, nullable=False)
    trial_revenue = Column(DECIMAL(12, 2), default=0.00, nullable=False)

    # Relationships
    events = relationship(
        "BillingEvent", back_populates="plan", cascade="all, delete-orphan"
    )
    invoices = relationship(
        "BillingInvoice", back_populates="plan", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_billing_plan_shop_id", "shop_id", unique=True),
        Index("ix_billing_plan_shop_domain", "shop_domain"),
        Index("ix_billing_plan_status", "status"),
        Index("ix_billing_plan_effective_from", "effective_from"),
    )

    def __repr__(self) -> str:
        return f"<BillingPlan(shop_id={self.shop_id}, name={self.name}, status={self.status})>"


class BillingInvoice(BaseModel, ShopMixin):
    """Billing invoice model for shop invoices"""

    __tablename__ = "billing_invoices"

    # Invoice identification
    plan_id = Column(String, ForeignKey("billing_plans.id"), nullable=False)
    invoice_number = Column(String(50), unique=True, nullable=False)
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

    # Payment information
    paid_at = Column(DateTime, nullable=True, index=True)
    payment_method = Column(String(50), nullable=True)
    payment_reference = Column(String(255), nullable=True)
    billing_metadata = Column(JSON, default={}, nullable=False)
    # Relationships
    plan = relationship("BillingPlan", back_populates="invoices")

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

    # Indexes
    __table_args__ = (
        Index("ix_billing_event_shop_id", "shop_id"),
        Index("ix_billing_event_type", "type"),
        Index("ix_billing_event_occurred_at", "occurred_at"),
        Index("ix_billing_event_processed_at", "processed_at"),
    )

    def __repr__(self) -> str:
        return f"<BillingEvent(shop_id={self.shop_id}, type={self.type})>"
