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
    pricing_tier_id = Column(
        String(255),
        ForeignKey("pricing_tiers.id", ondelete="RESTRICT"),
        nullable=False,  # This determines regional pricing!
        index=True,
    )

    # ===== TRIAL-SPECIFIC FIELDS =====
    # These override the pricing_tier defaults when needed
    trial_threshold_override = Column(
        Numeric(10, 2),
        nullable=True,
        comment="[LEGACY] Revenue threshold override for usage-based trial",
    )
    trial_duration_days = Column(
        Integer,
        nullable=True,
        comment="Override trial duration in days (from pricing_tier.trial_days)",
    )

    # ===== PAID SUBSCRIPTION FIELDS =====
    monthly_fee_override = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Override monthly fee for this shop (from pricing_tier.monthly_fee)",
    )
    user_chosen_cap_amount = Column(
        Numeric(10, 2),
        nullable=True,
        comment="[LEGACY] User-chosen cap amount for usage-based billing",
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

    # ===== KEEP ESSENTIAL RELATIONSHIPS =====
    shop = relationship("Shop", back_populates="shop_subscriptions")
    subscription_plan = relationship(
        "SubscriptionPlan", back_populates="shop_subscriptions"
    )
    pricing_tier = relationship("PricingTier", back_populates="shop_subscriptions")

    # Keep operational relationships
    billing_cycles = relationship("BillingCycle", back_populates="shop_subscription")

    # ===== SMART PROPERTIES USING PRICING TIER =====

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
        """Get the effective monthly fee from pricing tier or override"""
        if self.monthly_fee_override:
            return self.monthly_fee_override
        return (
            self.pricing_tier.monthly_fee
            if self.pricing_tier and self.pricing_tier.monthly_fee
            else Decimal("29.00")
        )

    @property
    def effective_trial_days(self) -> int:
        """Get the effective trial duration in days"""
        if self.trial_duration_days:
            return self.trial_duration_days
        return (
            self.pricing_tier.trial_days
            if self.pricing_tier and self.pricing_tier.trial_days
            else 14
        )

    @property
    def effective_trial_threshold(self) -> Decimal:
        """[LEGACY] Get trial threshold from pricing tier or override"""
        if self.trial_threshold_override:
            return self.trial_threshold_override
        return (
            self.pricing_tier.trial_threshold_amount
            if self.pricing_tier and self.pricing_tier.trial_threshold_amount
            else Decimal("75.00")
        )

    @property
    def effective_commission_rate(self) -> Decimal:
        """[LEGACY] Get commission rate from pricing tier"""
        return (
            self.pricing_tier.commission_rate
            if self.pricing_tier and self.pricing_tier.commission_rate
            else Decimal("0.03")
        )

    @property
    def currency(self) -> str:
        """Get currency from pricing tier"""
        return self.pricing_tier.currency if self.pricing_tier else "USD"

    @property
    def region_info(self) -> dict:
        """Get region metadata from pricing tier"""
        if self.pricing_tier and self.pricing_tier.tier_metadata:
            import json
            try:
                return json.loads(self.pricing_tier.tier_metadata)
            except (json.JSONDecodeError, TypeError):
                return {}
        return {}

    @property
    def effective_cap_amount(self) -> Decimal:
        """[LEGACY] Get effective cap - user choice or fall back to trial threshold"""
        if self.is_paid and self.user_chosen_cap_amount:
            return self.user_chosen_cap_amount
        return self.effective_trial_threshold

    @property
    def trial_remaining_days(self) -> int:
        """Calculate remaining trial days"""
        if not self.is_trial or not self.started_at:
            return 0
        trial_end = self.started_at + timedelta(days=self.effective_trial_days)
        now = datetime.utcnow()
        remaining = (trial_end - now).days
        return max(0, remaining)
