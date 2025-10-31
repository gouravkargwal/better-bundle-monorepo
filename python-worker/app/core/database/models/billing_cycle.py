"""
Billing Cycle Model

Monthly billing periods for each shop subscription.
Tracks usage, caps, and cycle state.
"""

from decimal import Decimal
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Boolean,
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
    Tracks usage, caps, and cycle state.
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

    # Cap management (supports mid-cycle cap increases)
    initial_cap_amount = Column(
        Numeric(10, 2), nullable=False, comment="Cap amount at cycle start"
    )
    current_cap_amount = Column(
        Numeric(10, 2), nullable=False, comment="Current cap amount (after adjustments)"
    )

    # Usage tracking
    usage_amount = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total usage in this cycle",
    )
    commission_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of commissions in this cycle",
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
        return f"<BillingCycle(subscription_id={self.shop_subscription_id}, cycle={self.cycle_number}, status={self.status.value}, usage={self.usage_amount})>"

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
    def usage_percentage(self) -> float:
        """Calculate usage percentage of current cap"""
        if not self.current_cap_amount or self.current_cap_amount == 0:
            return 0.0
        return float((self.usage_amount / self.current_cap_amount) * 100)

    @property
    def remaining_cap(self) -> Decimal:
        """Calculate remaining cap amount"""
        remaining = self.current_cap_amount - self.usage_amount
        return max(Decimal("0.00"), remaining)

    @property
    def is_cap_reached(self) -> bool:
        """Check if current cap is reached"""
        return self.usage_amount >= self.current_cap_amount

    @property
    def is_near_cap(self, threshold: float = 0.8) -> bool:
        """Check if usage is near cap (default 80%)"""
        return self.usage_percentage >= (threshold * 100)

    @property
    def days_remaining(self) -> int:
        """Calculate days remaining in cycle"""
        now = datetime.utcnow()
        if self.end_date <= now:
            return 0
        return (self.end_date - now).days

    @property
    def has_cap_increase(self) -> bool:
        """Check if cap was increased during this cycle"""
        return self.current_cap_amount > self.initial_cap_amount

    @property
    def cap_increase_amount(self) -> Decimal:
        """Calculate total cap increase amount"""
        if not self.has_cap_increase:
            return Decimal("0.00")
        return self.current_cap_amount - self.initial_cap_amount
