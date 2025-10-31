"""
Simplified Shop Subscription Model

Single table approach: multiple subscription records per shop, only one active.
Combines trial, paid subscription, and Shopify billing into one unified model.
"""

from decimal import Decimal
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
    Unified Shop Subscription Model - keeps essential relationships
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
    trial_threshold_override = Column(Numeric(10, 2), nullable=True)
    trial_duration_days = Column(Integer, nullable=True)

    # ===== PAID SUBSCRIPTION FIELDS =====
    user_chosen_cap_amount = Column(Numeric(10, 2), nullable=True)
    auto_renew = Column(Boolean, default=True, nullable=False)

    # ===== SHOPIFY INTEGRATION (MOVED HERE) =====
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
    def effective_trial_threshold(self) -> Decimal:
        """Get trial threshold from pricing tier or override"""
        if self.trial_threshold_override:
            return self.trial_threshold_override
        return (
            self.pricing_tier.trial_threshold_amount
            if self.pricing_tier
            else Decimal("75.00")
        )

    @property
    def effective_commission_rate(self) -> Decimal:
        """Get commission rate from pricing tier"""
        return (
            self.pricing_tier.commission_rate if self.pricing_tier else Decimal("0.03")
        )

    @property
    def currency(self) -> str:
        """Get currency from pricing tier"""
        return self.pricing_tier.currency if self.pricing_tier else "USD"

    @property
    def region_info(self) -> dict:
        """Get region metadata from pricing tier"""
        if self.pricing_tier and self.pricing_tier.metadata:
            return self.pricing_tier.metadata
        return {}

    @property
    def effective_cap_amount(self) -> Decimal:
        """Get effective cap - user choice or fall back to trial threshold"""
        if self.is_paid and self.user_chosen_cap_amount:
            return self.user_chosen_cap_amount
        return self.effective_trial_threshold
