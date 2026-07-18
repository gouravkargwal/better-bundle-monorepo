"""
Billing Cycle Model

Monthly billing periods for each shop subscription.
Tracks subscription periods for flat fee billing.
"""

from decimal import Decimal
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    ForeignKey,
    Index,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship
from .base import BaseModel
from .enums import BillingCycleStatus
from .shop_subscription import ShopSubscription


class BillingCycle(BaseModel):
    """
    Billing Cycle

    One record per 30-day billing period per shop.
    For flat fee pricing, this tracks subscription periods
    (monthly intervals for recurring charges).

    Legacy usage-based fields are kept nullable for historical data.
    """

    __tablename__ = "billing_cycles"

    # Foreign keys
    shop_subscription_id = Column(
        String(255),
        ForeignKey("shop_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Cycle identification
    cycle_number = Column(Integer, nullable=False, index=True)

    # Cycle period
    start_date = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    end_date = Column(TIMESTAMP(timezone=True), nullable=False, index=True)

    # ===== FLAT FEE FIELDS =====
    period_fee = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Flat fee charged for this period (from pricing tier)",
    )

    # ===== LEGACY USAGE-BASED FIELDS (DEPRECATED, KEPT NULLABLE) =====
    initial_cap_amount = Column(
        Numeric(10, 2),
        nullable=True,
        comment="[LEGACY] Cap amount at cycle start",
    )
    current_cap_amount = Column(
        Numeric(10, 2),
        nullable=True,
        comment="[LEGACY] Current cap amount (after adjustments)",
    )
    usage_amount = Column(
        Numeric(10, 2),
        nullable=True,
        default=Decimal("0.00"),
        comment="[LEGACY] Total usage in this cycle",
    )
    commission_count = Column(
        Integer,
        nullable=True,
        default=0,
        comment="[LEGACY] Number of commissions in this cycle",
    )

    # Cycle state
    status = Column(
        SQLEnum(BillingCycleStatus, name="billing_cycle_status_enum"),
        nullable=False,
        default=BillingCycleStatus.ACTIVE,
        index=True,
    )

    # Cycle lifecycle
    activated_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    cancelled_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)

    # Cycle metadata
    cycle_metadata = Column(String(1000), nullable=True)  # JSON string

    # Relationships
    shop_subscription = relationship(
        "ShopSubscription", back_populates="billing_cycles"
    )
    commission_records = relationship(
        "CommissionRecord", back_populates="billing_cycle"
    )

    # Indexes
    __table_args__ = (
        Index("ix_billing_cycle_subscription", "shop_subscription_id"),
        Index("ix_billing_cycle_number", "cycle_number"),
        Index("ix_billing_cycle_status", "status"),
        Index("ix_billing_cycle_dates", "start_date", "end_date"),
        Index(
            "ix_billing_cycle_active",
            "shop_subscription_id",
            "status",
        ),
        # Unique constraint: one active cycle per subscription
        Index(
            "ix_billing_cycle_unique_active",
            "shop_subscription_id",
            "status",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        fee_str = f"fee=${self.period_fee}" if self.period_fee else "legacy"
        return (
            f"<BillingCycle(subscription_id={self.shop_subscription_id}, "
            f"cycle={self.cycle_number}, status={self.status.value}, {fee_str})>"
        )

    @property
    def is_active(self) -> bool:
        """Check if cycle is currently active"""
        return self.status == BillingCycleStatus.ACTIVE

    @property
    def is_completed(self) -> bool:
        """Check if cycle is completed"""
        return self.status == BillingCycleStatus.COMPLETED

    @property
    def is_cancelled(self) -> bool:
        """Check if cycle is cancelled"""
        return self.status == BillingCycleStatus.CANCELLED

    @property
    def days_remaining(self) -> int:
        """Calculate days remaining in cycle"""
        now = datetime.utcnow()
        if self.end_date <= now:
            return 0
        return (self.end_date - now).days

    # ===== LEGACY USAGE-BASED PROPERTIES (DEPRECATED) =====

    @property
    def usage_percentage(self) -> float:
        """[LEGACY] Calculate usage percentage of current cap"""
        if not self.current_cap_amount or self.current_cap_amount == 0:
            return 0.0
        return float((self.usage_amount or Decimal("0")) / self.current_cap_amount * 100)

    @property
    def remaining_cap(self) -> Decimal:
        """[LEGACY] Calculate remaining cap amount"""
        remaining = (self.current_cap_amount or Decimal("0")) - (
            self.usage_amount or Decimal("0")
        )
        return max(Decimal("0.00"), remaining)

    @property
    def is_cap_reached(self) -> bool:
        """[LEGACY] Check if current cap is reached"""
        return (self.usage_amount or Decimal("0")) >= (
            self.current_cap_amount or Decimal("0")
        )

    @property
    def has_cap_increase(self) -> bool:
        """[LEGACY] Check if cap was increased during this cycle"""
        return (
            self.initial_cap_amount is not None
            and self.current_cap_amount is not None
            and self.current_cap_amount > self.initial_cap_amount
        )

    @property
    def cap_increase_amount(self) -> Decimal:
        """[LEGACY] Calculate total cap increase amount"""
        if not self.has_cap_increase:
            return Decimal("0.00")
        return (self.current_cap_amount or Decimal("0")) - (
            self.initial_cap_amount or Decimal("0")
        )
