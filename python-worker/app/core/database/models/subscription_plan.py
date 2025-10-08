"""
Subscription Plan Model

Master table defining available subscription plans (templates).
Admin-controlled, rarely changes.
"""

from datetime import datetime
from sqlalchemy import Column, String, Text, Boolean, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship
from .base import BaseModel
from .enums import SubscriptionPlanType


class SubscriptionPlan(BaseModel):
    """
    Subscription Plan Template

    Master table defining available subscription plans.
    These are templates that shops can subscribe to.
    """

    __tablename__ = "subscription_plans"

    # Plan identification
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    plan_type = Column(
        SQLEnum(SubscriptionPlanType, name="subscription_plan_type_enum"),
        nullable=False,
        index=True,
    )

    # Plan configuration
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_default = Column(Boolean, default=False, nullable=False, index=True)

    # Commission settings (defaults, can be overridden by pricing tiers)
    default_commission_rate = Column(String(10), nullable=True)  # e.g., "0.03" for 3%

    # Metadata
    plan_metadata = Column(Text, nullable=True)  # JSON string for additional config

    # Timestamps are provided by BaseModel (TimestampMixin)
    # Additional business timestamps
    effective_from = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    effective_to = Column(TIMESTAMP(timezone=True), nullable=True, index=True)

    # Relationships
    pricing_tiers = relationship(
        "PricingTier", back_populates="subscription_plan", cascade="all, delete-orphan"
    )
    shop_subscriptions = relationship(
        "ShopSubscription", back_populates="subscription_plan"
    )

    # Indexes
    __table_args__ = (
        Index("ix_subscription_plan_name", "name"),
        Index("ix_subscription_plan_type", "plan_type"),
        Index("ix_subscription_plan_active", "is_active"),
        Index("ix_subscription_plan_default", "is_default"),
        Index("ix_subscription_plan_effective", "effective_from", "effective_to"),
    )

    def __repr__(self) -> str:
        return f"<SubscriptionPlan(name={self.name}, type={self.plan_type.value}, active={self.is_active})>"

    @property
    def is_currently_active(self) -> bool:
        """Check if plan is currently active (not expired)"""
        now = datetime.utcnow()
        return (
            self.is_active
            and self.effective_from <= now
            and (self.effective_to is None or self.effective_to > now)
        )
