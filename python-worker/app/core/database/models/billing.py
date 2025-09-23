"""
Billing models for SQLAlchemy

Represents billing plans, invoices, and events.
"""

from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.types import DECIMAL
from .base import BaseModel, ShopMixin
from .enums import (
    BillingPlanType,
    BillingPlanStatus,
    BillingCycle,
    InvoiceStatus,
    BillingEventType,
)


class BillingPlan(BaseModel, ShopMixin):
    """Billing plan model for shop billing plans"""

    __tablename__ = "billing_plans"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Plan identification - matching Prisma schema
    shop_domain = Column("shop_domain", String(255), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    type = Column(String, nullable=False)  # BillingPlanType enum
    status = Column(
        String, default=BillingPlanStatus.ACTIVE, nullable=False, index=True
    )

    # Plan configuration - matching Prisma schema
    configuration = Column(JSON, default={}, nullable=False)
    effective_from = Column("effective_from", DateTime, nullable=False, index=True)
    effective_until = Column("effective_until", DateTime, nullable=True)

    # Trial information - matching Prisma schema
    is_trial_active = Column("is_trial_active", Boolean, default=True, nullable=False)
    trial_threshold = Column(
        "trial_threshold", DECIMAL(10, 2), default=200.00, nullable=False
    )
    trial_revenue = Column(
        "trial_revenue", DECIMAL(12, 2), default=0.00, nullable=False
    )

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

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Invoice identification - matching Prisma schema
    plan_id = Column("plan_id", String, ForeignKey("billing_plans.id"), nullable=False)
    invoice_number = Column("invoice_number", String(50), unique=True, nullable=False)
    status = Column(String, default=InvoiceStatus.PENDING, nullable=False, index=True)

    # Financial details - matching Prisma schema
    subtotal = Column(DECIMAL(10, 2), nullable=False)
    taxes = Column(DECIMAL(10, 2), nullable=False)
    discounts = Column(DECIMAL(10, 2), nullable=False)
    total = Column(DECIMAL(10, 2), nullable=False)
    currency = Column(String(3), nullable=False)

    # Billing period - matching Prisma schema
    period_start = Column("period_start", DateTime, nullable=False)
    period_end = Column("period_end", DateTime, nullable=False)
    metrics_id = Column("metrics_id", String(255), nullable=False)
    due_date = Column("due_date", DateTime, nullable=False, index=True)

    # Payment information - matching Prisma schema
    paid_at = Column("paid_at", DateTime, nullable=True, index=True)
    payment_method = Column("payment_method", String(50), nullable=True)
    payment_reference = Column("payment_reference", String(255), nullable=True)

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

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Foreign key to BillingPlan - matching Prisma schema
    plan_id = Column(
        "plan_id", String, ForeignKey("billing_plans.id"), nullable=False, index=True
    )

    # Event identification - matching Prisma schema
    type = Column(String, nullable=False, index=True)  # BillingEventType enum
    data = Column(JSON, default={}, nullable=False)
    billing_metadata = Column("billing_metadata", JSON, default={}, nullable=False)

    # Timing - matching Prisma schema
    occurred_at = Column("occurred_at", DateTime, nullable=False, index=True)
    processed_at = Column("processed_at", DateTime, nullable=False, index=True)

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
