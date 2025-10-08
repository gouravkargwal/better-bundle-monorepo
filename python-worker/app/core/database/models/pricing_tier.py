"""
Pricing Tier Model

Defines pricing configuration for each subscription plan.
Allows multi-currency support and flexible pricing.
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
from .subscription_plan import SubscriptionPlan


class PricingTier(BaseModel):
    """
    Pricing Tier

    Defines pricing for a specific subscription plan in a specific currency.
    Links to subscription_plans table.
    """

    __tablename__ = "pricing_tiers"

    # Foreign keys
    subscription_plan_id = Column(
        String(255),
        ForeignKey("subscription_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Currency and pricing
    currency = Column(String(3), nullable=False, index=True)  # ISO 4217 currency code
    trial_threshold_amount = Column(
        Numeric(10, 2), nullable=False, comment="Revenue threshold to complete trial"
    )
    commission_rate = Column(
        Numeric(5, 4),
        nullable=False,
        default=Decimal("0.03"),
        comment="Commission rate (e.g., 0.03 for 3%)",
    )

    # Tier configuration
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    is_default = Column(Boolean, default=False, nullable=False, index=True)

    # Additional pricing rules
    minimum_charge = Column(
        Numeric(10, 2), nullable=True, comment="Minimum charge per billing cycle"
    )
    proration_enabled = Column(Boolean, default=True, nullable=False)

    # Metadata
    tier_metadata = Column(
        String(1000), nullable=True
    )  # JSON string for additional config

    # Timestamps
    effective_from = Column(
        TIMESTAMP(timezone=True), default=datetime.utcnow, nullable=False
    )
    effective_to = Column(TIMESTAMP(timezone=True), nullable=True, index=True)

    # Relationships
    subscription_plan = relationship("SubscriptionPlan", back_populates="pricing_tiers")
    shop_subscriptions = relationship("ShopSubscription", back_populates="pricing_tier")

    # Indexes
    __table_args__ = (
        Index("ix_pricing_tier_plan_currency", "subscription_plan_id", "currency"),
        Index("ix_pricing_tier_currency", "currency"),
        Index("ix_pricing_tier_active", "is_active"),
        Index("ix_pricing_tier_default", "is_default"),
        Index("ix_pricing_tier_effective", "effective_from", "effective_to"),
        # Unique constraint: one default tier per plan per currency
        Index(
            "ix_pricing_tier_unique_default",
            "subscription_plan_id",
            "currency",
            "is_default",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<PricingTier(plan_id={self.subscription_plan_id}, currency={self.currency}, threshold={self.trial_threshold_amount}, commission_rate={self.commission_rate})>"

    @property
    def is_currently_active(self) -> bool:
        """Check if pricing tier is currently active (not expired)"""
        now = datetime.utcnow()
        return (
            self.is_active
            and self.effective_from <= now
            and (self.effective_to is None or self.effective_to > now)
        )

    @property
    def commission_rate_percentage(self) -> float:
        """Get commission rate as percentage (e.g., 3.0 for 3%)"""
        return float(self.commission_rate * 100)
