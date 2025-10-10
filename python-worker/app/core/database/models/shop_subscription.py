"""
Shop Subscription Model

Links a shop to a subscription plan and tracks the subscription state.
One active subscription per shop at a time.
"""

from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Boolean,
    ForeignKey,
    Index,
    Enum as SQLEnum,
    UniqueConstraint,
    Numeric,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship
from .base import BaseModel, ShopMixin
from .enums import SubscriptionStatus
from .subscription_plan import SubscriptionPlan
from .pricing_tier import PricingTier


class ShopSubscription(BaseModel, ShopMixin):
    """
    Shop Subscription

    Links a shop to a subscription plan and tracks the subscription state.
    One active subscription per shop at a time.
    """

    __tablename__ = "shop_subscriptions"

    # Foreign keys
    subscription_plan_id = Column(
        String(255),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    pricing_tier_id = Column(
        String(255),
        ForeignKey("pricing_tiers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # Subscription state
    status = Column(
        SQLEnum(SubscriptionStatus, name="subscription_status_enum"),
        nullable=False,
        default=SubscriptionStatus.TRIAL,
        index=True,
    )

    # Subscription lifecycle
    start_date = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    end_date = Column(TIMESTAMP(timezone=True), nullable=True, index=True)

    # State flags
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    auto_renew = Column(Boolean, default=True, nullable=False)

    # Subscription metadata
    subscription_metadata = Column(String(2000), nullable=True)  # JSON string

    # User-chosen cap amount
    user_chosen_cap_amount = Column(Numeric(10, 2), nullable=True)

    # Timestamps
    activated_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    suspended_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    cancelled_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)

    # Relationships
    shop = relationship("Shop", back_populates="shop_subscriptions")
    subscription_plan = relationship(
        "SubscriptionPlan", back_populates="shop_subscriptions"
    )
    pricing_tier = relationship("PricingTier", back_populates="shop_subscriptions")
    subscription_trial = relationship(
        "SubscriptionTrial",
        back_populates="shop_subscription",
        uselist=False,
        cascade="all, delete-orphan",
    )
    billing_cycles = relationship(
        "BillingCycle", back_populates="shop_subscription", cascade="all, delete-orphan"
    )
    shopify_subscription = relationship(
        "ShopifySubscription",
        back_populates="shop_subscription",
        uselist=False,
        cascade="all, delete-orphan",
    )
    billing_invoices = relationship(
        "BillingInvoice",
        back_populates="shop_subscription",
        cascade="all, delete-orphan",
    )

    # Indexes and constraints
    __table_args__ = (
        Index("ix_shop_subscription_shop", "shop_id"),
        Index("ix_shop_subscription_plan", "subscription_plan_id"),
        Index("ix_shop_subscription_tier", "pricing_tier_id"),
        Index("ix_shop_subscription_status", "status"),
        Index("ix_shop_subscription_active", "is_active"),
        Index("ix_shop_subscription_dates", "start_date", "end_date"),
        # Unique constraint: one active subscription per shop
        UniqueConstraint(
            "shop_id",
            name="uq_shop_subscription_active",
        ),
    )

    def __repr__(self) -> str:
        return f"<ShopSubscription(shop_id={self.shop_id}, plan_id={self.subscription_plan_id}, status={self.status.value})>"

    @property
    def is_trial(self) -> bool:
        """Check if subscription is in trial phase"""
        return self.status == SubscriptionStatus.TRIAL

    @property
    def is_active_subscription(self) -> bool:
        """Check if subscription is active (not trial, not cancelled)"""
        return (
            self.is_active
            and self.status == SubscriptionStatus.ACTIVE
            and (self.end_date is None or self.end_date > datetime.utcnow())
        )

    @property
    def is_pending_approval(self) -> bool:
        """Check if subscription is pending approval"""
        return self.status == SubscriptionStatus.PENDING_APPROVAL

    @property
    def is_suspended(self) -> bool:
        """Check if subscription is suspended"""
        return self.status == SubscriptionStatus.SUSPENDED

    @property
    def is_cancelled(self) -> bool:
        """Check if subscription is cancelled"""
        return self.status == SubscriptionStatus.CANCELLED

    @property
    def days_remaining(self) -> int:
        """Calculate days remaining in subscription"""
        if not self.end_date:
            return -1  # No end date (perpetual)

        now = datetime.utcnow()
        if self.end_date <= now:
            return 0

        return (self.end_date - now).days
