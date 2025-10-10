"""
Billing Cycle Adjustment Model

Tracks mid-cycle cap increases and other adjustments.
Provides full audit trail for compliance and dispute resolution.
"""

from decimal import Decimal
from datetime import datetime
from sqlalchemy import Column, String, Numeric, Text, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship
from .base import BaseModel
from .enums import AdjustmentReason
from .billing_cycle import BillingCycle


class BillingCycleAdjustment(BaseModel):
    """
    Billing Cycle Adjustment

    Tracks mid-cycle cap increases and other adjustments.
    Provides full audit trail for compliance and dispute resolution.
    """

    __tablename__ = "billing_cycle_adjustments"

    # Foreign keys
    billing_cycle_id = Column(
        String(255),
        ForeignKey("billing_cycles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Adjustment details
    old_cap_amount = Column(
        Numeric(10, 2), nullable=False, comment="Cap amount before adjustment"
    )
    new_cap_amount = Column(
        Numeric(10, 2), nullable=False, comment="Cap amount after adjustment"
    )
    adjustment_amount = Column(
        Numeric(10, 2), nullable=False, comment="Amount of adjustment (new - old)"
    )

    # Adjustment reason and context
    adjustment_reason = Column(
        SQLEnum(AdjustmentReason, name="adjustment_reason_enum"),
        nullable=False,
        index=True,
    )
    reason_description = Column(Text, nullable=True)

    # Who made the adjustment
    adjusted_by = Column(String(255), nullable=True, index=True)  # User ID or system
    adjusted_by_type = Column(String(50), nullable=True)  # 'user', 'admin', 'system'

    # Adjustment metadata
    adjustment_metadata = Column(String(1000), nullable=True)  # JSON string

    # Timestamps
    adjusted_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)

    # Relationships
    billing_cycle = relationship("BillingCycle", back_populates="cycle_adjustments")

    # Indexes
    __table_args__ = (
        Index("ix_billing_cycle_adjustment_cycle", "billing_cycle_id"),
        Index("ix_billing_cycle_adjustment_reason", "adjustment_reason"),
        Index("ix_billing_cycle_adjustment_by", "adjusted_by"),
        Index("ix_billing_cycle_adjustment_at", "adjusted_at"),
        Index("ix_billing_cycle_adjustment_type", "adjusted_by_type"),
    )

    def __repr__(self) -> str:
        return f"<BillingCycleAdjustment(cycle_id={self.billing_cycle_id}, reason={self.adjustment_reason.value}, amount={self.adjustment_amount})>"

    @property
    def is_cap_increase(self) -> bool:
        """Check if this is a cap increase"""
        return self.adjustment_reason == AdjustmentReason.CAP_INCREASE

    @property
    def is_plan_upgrade(self) -> bool:
        """Check if this is a plan upgrade"""
        return self.adjustment_reason == AdjustmentReason.PLAN_UPGRADE

    @property
    def is_admin_adjustment(self) -> bool:
        """Check if this is an admin adjustment"""
        return self.adjustment_reason == AdjustmentReason.ADMIN_ADJUSTMENT

    @property
    def is_promotional(self) -> bool:
        """Check if this is a promotional adjustment"""
        return self.adjustment_reason == AdjustmentReason.PROMOTION

    @property
    def adjustment_percentage(self) -> float:
        """Calculate adjustment as percentage of old cap"""
        if not self.old_cap_amount or self.old_cap_amount == 0:
            return 0.0
        return float((self.adjustment_amount / self.old_cap_amount) * 100)
