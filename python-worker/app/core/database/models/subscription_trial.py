"""
Subscription Trial Model

Separate trial lifecycle management.
Tracks trial progress and completion.
"""

from decimal import Decimal
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Numeric,
    Boolean,
    ForeignKey,
    Index,
    Enum as SQLEnum,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship
from .base import BaseModel
from .enums import TrialStatus
from .shop_subscription import ShopSubscription


class SubscriptionTrial(BaseModel):
    """
    Subscription Trial

    Separate trial lifecycle management.
    Tracks trial progress and completion.
    """

    __tablename__ = "subscription_trials"

    # Foreign keys
    shop_subscription_id = Column(
        String(255),
        ForeignKey("shop_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One trial per subscription
        index=True,
    )

    # Trial configuration
    threshold_amount = Column(
        Numeric(10, 2), nullable=False, comment="Revenue threshold to complete trial"
    )
    trial_duration_days = Column(
        String(10), nullable=True, comment="Maximum trial duration in days (optional)"
    )

    # ❌ REMOVED: accumulated_revenue - always calculate from commission_records
    commission_saved = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total commission saved during trial",
    )

    # Trial state
    status = Column(
        SQLEnum(TrialStatus, name="trial_status_enum"),
        nullable=False,
        default=TrialStatus.ACTIVE,
        index=True,
    )

    # Trial lifecycle
    started_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    expired_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)

    # Trial metadata
    trial_metadata = Column(String(1000), nullable=True)  # JSON string

    # Relationships
    shop_subscription = relationship(
        "ShopSubscription", back_populates="subscription_trial"
    )

    # Indexes
    __table_args__ = (
        Index("ix_subscription_trial_subscription", "shop_subscription_id"),
        Index("ix_subscription_trial_status", "status"),
        Index("ix_subscription_trial_started", "started_at"),
        Index("ix_subscription_trial_completed", "completed_at"),
    )

    def __repr__(self) -> str:
        return f"<SubscriptionTrial(subscription_id={self.shop_subscription_id}, status={self.status.value})>"

    @property
    def is_active(self) -> bool:
        """Check if trial is currently active"""
        return self.status == TrialStatus.ACTIVE

    @property
    def is_completed(self) -> bool:
        """Check if trial is completed"""
        return self.status == TrialStatus.COMPLETED

    @property
    def is_expired(self) -> bool:
        """Check if trial is expired"""
        return self.status == TrialStatus.EXPIRED

    def get_progress_percentage(self, actual_revenue: Decimal) -> float:
        """Calculate trial progress percentage based on actual revenue"""
        if not self.threshold_amount or self.threshold_amount == 0:
            return 0.0
        return min(100.0, float((actual_revenue / self.threshold_amount) * 100))

    def get_remaining_revenue(self, actual_revenue: Decimal) -> Decimal:
        """Calculate remaining revenue until trial completion based on actual revenue"""
        if not self.is_active:
            return Decimal("0.00")
        remaining = self.threshold_amount - actual_revenue
        return max(Decimal("0.00"), remaining)

    def is_threshold_reached(self, actual_revenue: Decimal) -> bool:
        """Check if trial threshold has been reached based on actual revenue"""
        return actual_revenue >= self.threshold_amount

    def can_be_completed(self) -> bool:
        """Check if trial can be completed (is active and not already completed)"""
        return self.status == TrialStatus.ACTIVE and self.completed_at is None

    @property
    def days_remaining(self) -> int:
        """Calculate days remaining in trial (if duration limit set)"""
        if not self.trial_duration_days:
            return -1  # No duration limit

        try:
            duration_days = int(self.trial_duration_days)
            now = datetime.utcnow()
            trial_end = self.started_at + datetime.timedelta(days=duration_days)

            if trial_end <= now:
                return 0

            return (trial_end - now).days
        except (ValueError, TypeError):
            return -1  # Invalid duration format
