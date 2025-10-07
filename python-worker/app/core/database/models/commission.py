"""
Commission Record Model

Tracks individual commission calculations for each purchase attribution.
Handles both trial phase (commission tracked but not charged) and
paid phase (commission charged to Shopify).
"""

from decimal import Decimal
from datetime import datetime
from typing import Dict, Any
from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime,
    JSON,
    Index,
    UniqueConstraint,
    ForeignKey,
    Enum as SQLEnum,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from .base import Base
from .enums import BillingPhase, CommissionStatus, ChargeType


class CommissionRecord(Base):
    """
    Commission Record

    Tracks individual commission calculations from purchase attributions.
    Handles both trial tracking and paid billing phases.
    """

    __tablename__ = "commission_records"

    # Primary key
    id = Column(
        String(255), primary_key=True, default=lambda: str(uuid.uuid4()), nullable=False
    )

    # Foreign keys
    shop_id = Column(
        String(255),
        ForeignKey("shops.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    purchase_attribution_id = Column(
        String(255),
        ForeignKey("purchase_attributions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One commission per attribution
        index=True,
    )

    billing_plan_id = Column(
        String(255),
        ForeignKey("billing_plans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Purchase details
    order_id = Column(String(255), nullable=False, index=True)
    order_date = Column(DateTime(timezone=True), nullable=False, index=True)

    # Commission calculation
    attributed_revenue = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Total attributed revenue from the purchase",
    )

    commission_rate = Column(
        Numeric(5, 4),
        nullable=False,
        default=Decimal("0.03"),
        comment="Commission rate (e.g., 0.03 for 3%)",
    )

    commission_earned = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Full commission amount (attributed_revenue * rate)",
    )

    commission_charged = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0"),
        comment="Actual amount charged to Shopify (may be partial or 0 during trial)",
    )

    commission_overflow = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0"),
        comment="Amount that couldn't be charged due to cap",
    )

    # Billing cycle tracking
    billing_cycle_start = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Start of the 30-day billing cycle",
    )

    billing_cycle_end = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="End of the 30-day billing cycle",
    )

    cycle_usage_before = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0"),
        comment="Cycle usage before this commission",
    )

    cycle_usage_after = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0"),
        comment="Cycle usage after this commission",
    )

    capped_amount = Column(
        Numeric(10, 2),
        nullable=False,
        comment="Maximum amount that can be charged in this cycle",
    )

    # Trial-specific tracking
    trial_accumulated = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0"),
        comment="Accumulated trial revenue at time of this commission",
    )

    # Billing phase
    billing_phase = Column(
        SQLEnum(BillingPhase, name="billing_phase_enum"),
        nullable=False,
        default=BillingPhase.TRIAL,
        index=True,
        comment="Whether this is trial or paid phase",
    )

    # Status tracking
    status = Column(
        SQLEnum(CommissionStatus, name="commission_status_enum"),
        nullable=False,
        default=CommissionStatus.TRIAL_PENDING,
        index=True,
        comment="Current status of commission",
    )

    charge_type = Column(
        SQLEnum(ChargeType, name="charge_type_enum"),
        nullable=False,
        default=ChargeType.TRIAL,
        comment="Type of charge (full, partial, etc.)",
    )

    # Shopify integration
    shopify_usage_record_id = Column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        comment="Shopify usage record GID if sent to Shopify",
    )

    shopify_recorded_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the usage was recorded to Shopify",
    )

    shopify_response = Column(JSON, nullable=True, comment="Response from Shopify API")

    # Invoice tracking
    invoice_id = Column(
        String(255),
        ForeignKey("billing_invoices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Invoice this commission was included in",
    )

    invoiced_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="When this was included in an invoice",
    )

    # Currency
    currency = Column(
        String(3), nullable=False, default="USD", comment="Currency code (ISO 4217)"
    )

    # Additional info
    notes = Column(Text, nullable=True, comment="Additional notes or reasons")

    commission_metadata = Column(
        JSON, nullable=True, default=dict, comment="Additional metadata"
    )

    # Error tracking
    error_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of failed attempts to charge",
    )

    last_error = Column(Text, nullable=True, comment="Last error message if failed")

    last_error_at = Column(
        DateTime(timezone=True), nullable=True, comment="When the last error occurred"
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, index=True
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        index=True,
    )

    # Soft delete
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships
    shop = relationship("Shop", back_populates="commission_records")
    purchase_attribution = relationship(
        "PurchaseAttribution", back_populates="commission_record"
    )
    billing_plan = relationship("BillingPlan", back_populates="commission_records")
    invoice = relationship("BillingInvoice", back_populates="commission_records")

    # Indexes for common queries
    __table_args__ = (
        # Composite indexes
        Index(
            "idx_commission_shop_cycle",
            "shop_id",
            "billing_cycle_start",
            "billing_cycle_end",
        ),
        Index("idx_commission_shop_phase_status", "shop_id", "billing_phase", "status"),
        Index("idx_commission_status_created", "status", "created_at"),
        Index("idx_commission_shopify_record", "shopify_usage_record_id"),
        Index("idx_commission_invoice", "invoice_id", "status"),
        # Unique constraint - one commission per purchase attribution
        UniqueConstraint(
            "purchase_attribution_id", name="uq_commission_purchase_attribution"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<CommissionRecord(id={self.id}, "
            f"order_id={self.order_id}, "
            f"earned=${self.commission_earned}, "
            f"charged=${self.commission_charged}, "
            f"phase={self.billing_phase}, "
            f"status={self.status})>"
        )

    # Helper properties
    @property
    def is_trial(self) -> bool:
        """Check if this is a trial commission"""
        return self.billing_phase == BillingPhase.TRIAL

    @property
    def is_charged(self) -> bool:
        """Check if commission was charged to Shopify"""
        return self.commission_charged > 0

    @property
    def has_overflow(self) -> bool:
        """Check if there's overflow due to cap"""
        return self.commission_overflow > 0

    @property
    def is_partial_charge(self) -> bool:
        """Check if this was a partial charge"""
        return (
            self.commission_charged > 0
            and self.commission_charged < self.commission_earned
        )

    @property
    def charge_percentage(self) -> float:
        """Calculate what percentage of earned commission was charged"""
        if self.commission_earned == 0:
            return 0.0
        return float((self.commission_charged / self.commission_earned) * 100)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": str(self.id),
            "shop_id": self.shop_id,
            "purchase_attribution_id": str(self.purchase_attribution_id),
            "billing_plan_id": (
                str(self.billing_plan_id) if self.billing_plan_id else None
            ),
            "order_id": self.order_id,
            "order_date": self.order_date.isoformat() if self.order_date else None,
            "attributed_revenue": float(self.attributed_revenue),
            "commission_rate": float(self.commission_rate),
            "commission_earned": float(self.commission_earned),
            "commission_charged": float(self.commission_charged),
            "commission_overflow": float(self.commission_overflow),
            "billing_cycle_start": (
                self.billing_cycle_start.isoformat()
                if self.billing_cycle_start
                else None
            ),
            "billing_cycle_end": (
                self.billing_cycle_end.isoformat() if self.billing_cycle_end else None
            ),
            "cycle_usage_before": float(self.cycle_usage_before),
            "cycle_usage_after": float(self.cycle_usage_after),
            "capped_amount": float(self.capped_amount),
            "trial_accumulated": float(self.trial_accumulated),
            "billing_phase": self.billing_phase.value,
            "status": self.status.value,
            "charge_type": self.charge_type.value,
            "shopify_usage_record_id": self.shopify_usage_record_id,
            "shopify_recorded_at": (
                self.shopify_recorded_at.isoformat()
                if self.shopify_recorded_at
                else None
            ),
            "invoice_id": str(self.invoice_id) if self.invoice_id else None,
            "invoiced_at": self.invoiced_at.isoformat() if self.invoiced_at else None,
            "currency": self.currency,
            "notes": self.notes,
            "commission_metadata": self.commission_metadata,
            "error_count": self.error_count,
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            # Helper properties
            "is_trial": self.is_trial,
            "is_charged": self.is_charged,
            "has_overflow": self.has_overflow,
            "is_partial_charge": self.is_partial_charge,
            "charge_percentage": self.charge_percentage,
        }
