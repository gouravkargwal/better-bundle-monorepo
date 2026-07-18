"""
Simplified Shop Subscription Model

Single table approach: multiple subscription records per shop, only one active.
Supports flat fee pricing with trial periods.
"""

from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy import (
    Column,
    String,
    Boolean,
    ForeignKey,
    Enum as SQLEnum,
    Numeric,
    Text,
    Integer,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB
from sqlalchemy.orm import relationship
from .base import BaseModel, ShopMixin
from .enums import SubscriptionType, SubscriptionStatus


class ShopSubscription(BaseModel, ShopMixin):
    """
    Unified Shop Subscription Model

    Single active subscription per shop.
    Supports flat fee pricing: trial period → recurring monthly charge.
    """

    __tablename__ = "shop_subscriptions"

    # ===== SUBSCRIPTION TYPE & STATUS =====
    subscription_type = Column(
        SQLEnum(SubscriptionType, name="subscription_type_enum"),
        nullable=False,
        default=SubscriptionType.TRIAL,
        index=True,
    )

    status = Column(
        SQLEnum(SubscriptionStatus, name="subscription_status_enum"),
        nullable=False,
        default=SubscriptionStatus.ACTIVE,
        index=True,
    )

    # ===== KEEP ESSENTIAL FOREIGN KEYS =====
    subscription_plan_id = Column(
        String(255),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,  # This is required for plan configuration
        index=True,
    )

    # ===== TRIAL-SPECIFIC FIELDS =====
    # These override the subscription_plan defaults when needed
    trial_duration_days = Column(
        Integer,
        nullable=True,
        comment="Override trial duration in days (from subscription_plan.trial_days)",
    )

    # ===== PAID SUBSCRIPTION FIELDS =====
    monthly_fee_override = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Override monthly fee for this shop (from subscription_plan.monthly_fee)",
    )
    auto_renew = Column(Boolean, default=True, nullable=False)

    # ===== SHOPIFY INTEGRATION =====
    shopify_subscription_id = Column(String(255), nullable=True, index=True)
    shopify_line_item_id = Column(String(255), nullable=True)
    shopify_status = Column(String(50), nullable=True)
    confirmation_url = Column(Text, nullable=True)

    # ===== LIFECYCLE TIMESTAMPS =====
    started_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    cancelled_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)

    # ===== STATE & METADATA =====
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    shop_subscription_metadata = Column(JSONB, nullable=True)

    # ===== RELATIONSHIPS =====
    shop = relationship("Shop", back_populates="shop_subscriptions")
    subscription_plan = relationship(
        "SubscriptionPlan", back_populates="shop_subscriptions"
    )

    # Keep operational relationships
    billing_cycles = relationship("BillingCycle", back_populates="shop_subscription")

    # ===== SMART PROPERTIES =====

    @property
    def is_trial(self) -> bool:
        """Check if subscription is in trial phase"""
        return self.subscription_type == SubscriptionType.TRIAL

    @property
    def is_paid(self) -> bool:
        """Check if subscription is in paid phase"""
        return self.subscription_type == SubscriptionType.PAID

    @property
    def effective_monthly_fee(self) -> Decimal:
        """Get the effective monthly fee (override > plan fee after discount)"""
        if self.monthly_fee_override:
            return self.monthly_fee_override
        plan = self.subscription_plan
        if plan and plan.monthly_fee:
            fee = Decimal(str(plan.monthly_fee))
            if plan.discount_percentage:
                fee = fee * (1 - Decimal(str(plan.discount_percentage)) / 100)
            return fee
        return Decimal("149.50")  # Default: $299 with 50% discount

    @property
    def effective_trial_days(self) -> int:
        """Get the effective trial duration in days"""
        if self.trial_duration_days:
            return self.trial_duration_days
        return (
            self.subscription_plan.trial_days
            if self.subscription_plan and self.subscription_plan.trial_days
            else 14
        )

    @property
    def currency(self) -> str:
        """Always returns USD (global flat fee pricing)"""
        return "USD"

    @property
    def trial_remaining_days(self) -> int:
        """Calculate remaining trial days"""
        if not self.is_trial or not self.started_at:
            return 0
        trial_end = self.started_at + timedelta(days=self.effective_trial_days)
        now = datetime.utcnow()
        remaining = (trial_end - now).days
        return max(0, remaining)
