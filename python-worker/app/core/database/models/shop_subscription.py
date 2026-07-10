"""
Simplified Shop Subscription Model

One record per active subscription per shop.
status alone drives all business logic — no subscription_type needed.

Status flow:
  TRIAL → ACTIVE → SUSPENDED / CANCELLED / EXPIRED

PENDING_APPROVAL has been removed — the merchant stays in TRIAL until the
APP_SUBSCRIPTIONS_UPDATE webhook confirms ACTIVE. The UI checks
confirmation_url to determine if billing setup has been initiated.
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
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB
from sqlalchemy.orm import relationship
from .base import BaseModel, ShopMixin
from .enums import SubscriptionStatus


class ShopSubscription(BaseModel, ShopMixin):
    """
    Unified Shop Subscription.

    DB enforces one non-CANCELLED subscription per shop via partial unique index:
        CREATE UNIQUE INDEX ... ON shop_subscriptions(shop_id)
        WHERE status != 'CANCELLED';
    """

    __tablename__ = "shop_subscriptions"

    # ===== STATUS — single source of truth =====
    status = Column(
        SQLEnum(SubscriptionStatus, name="subscription_status_enum"),
        nullable=False,
        default=SubscriptionStatus.TRIAL,
        index=True,
    )

    # ===== PLAN / PRICING =====
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

    # ===== TRIAL FIELDS =====
    trial_threshold_override = Column(Numeric(10, 2), nullable=True)
    trial_duration_days = Column(Integer, nullable=True)
    # Running total of attributed revenue during trial (updated atomically).
    # Single source of truth — avoids re-summing commission_records every check.
    trial_revenue = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Accumulated attributed revenue during trial phase",
    )

    # ===== PAID SUBSCRIPTION FIELDS =====
    user_chosen_cap_amount = Column(Numeric(10, 2), nullable=True)
    auto_renew = Column(Boolean, default=True, nullable=False)

    # ===== SHOPIFY INTEGRATION =====
    shopify_subscription_id = Column(String(255), nullable=True, index=True)
    shopify_line_item_id = Column(String(255), nullable=True)
    shopify_status = Column(String(50), nullable=True)
    confirmation_url = Column(Text, nullable=True)

    # ===== LIFECYCLE TIMESTAMPS =====
    started_at = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    cancelled_at = Column(TIMESTAMP(timezone=True), nullable=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # ===== FLAGS =====
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    shop_subscription_metadata = Column(JSONB, nullable=True)

    # ===== RELATIONSHIPS =====
    shop = relationship("Shop", back_populates="shop_subscriptions")
    subscription_plan = relationship(
        "SubscriptionPlan", back_populates="shop_subscriptions"
    )
    pricing_tier = relationship("PricingTier", back_populates="shop_subscriptions")
    billing_cycles = relationship("BillingCycle", back_populates="shop_subscription")

    # ===== TABLE ARGS =====
    # Partial unique enforced at DB level (must be created via raw SQL / alembic):
    #   CREATE UNIQUE INDEX ix_shop_subscription_one_active_per_shop
    #       ON shop_subscriptions(shop_id) WHERE status != 'CANCELLED';
    __table_args__ = (
        Index("ix_shop_subscriptions_status", "status"),
        Index("ix_shop_subscriptions_shop_id", "shop_id"),
        Index("ix_shop_subscriptions_is_active", "is_active"),
        Index("ix_shop_subscriptions_shopify_subscription_id", "shopify_subscription_id"),
    )

    # ===== COMPUTED PROPERTIES =====

    @property
    def is_trial(self) -> bool:
        return self.status == SubscriptionStatus.TRIAL

    @property
    def is_paid(self) -> bool:
        return self.status == SubscriptionStatus.ACTIVE

    @property
    def effective_trial_threshold(self) -> Decimal:
        if self.trial_threshold_override:
            return self.trial_threshold_override
        return (
            self.pricing_tier.trial_threshold_amount
            if self.pricing_tier
            else Decimal("75.00")
        )

    @property
    def trial_threshold_reached(self) -> bool:
        return self.trial_revenue >= self.effective_trial_threshold

    @property
    def trial_progress_percentage(self) -> float:
        threshold = self.effective_trial_threshold
        if not threshold or threshold == 0:
            return 0.0
        return min(100.0, float((self.trial_revenue / threshold) * 100))

    @property
    def effective_commission_rate(self) -> Decimal:
        return (
            self.pricing_tier.commission_rate if self.pricing_tier else Decimal("0.03")
        )

    @property
    def currency(self) -> str:
        return self.pricing_tier.currency if self.pricing_tier else "USD"

    @property
    def effective_cap_amount(self) -> Decimal:
        if self.status == SubscriptionStatus.ACTIVE and self.user_chosen_cap_amount:
            return self.user_chosen_cap_amount
        return self.effective_trial_threshold
