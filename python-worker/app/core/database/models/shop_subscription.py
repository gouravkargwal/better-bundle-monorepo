"""
Simplified Shop Subscription Model

Single table approach: multiple subscription records per shop, only one active.
Pay-as-you-go: a revenue-threshold trial, then usage charges up to a cap.
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
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSONB
from sqlalchemy.orm import relationship
from .base import BaseModel, ShopMixin
from .enums import SubscriptionType, SubscriptionStatus


class ShopSubscription(BaseModel, ShopMixin):
    """
    Unified Shop Subscription Model

    Single active subscription per shop.
    The trial ends on attributed revenue, never on elapsed time.
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

    # ===== PAID SUBSCRIPTION FIELDS =====
    # Per-shop overrides of the plan's pay-as-you-go terms. The cap override is
    # the one that gets used in practice: a merchant who hits the cap has to
    # approve a higher one, and that new value lands here.
    commission_rate_override = Column(
        Numeric(5, 4),
        nullable=True,
        comment="Override commission rate (from subscription_plan.commission_rate)",
    )
    cap_amount_override = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Override monthly cap, e.g. after the merchant approves a raise",
    )
    trial_threshold_override = Column(
        Numeric(10, 2),
        nullable=True,
        comment="Override free attributed revenue before the first charge",
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

    # Fallbacks below are only reached when a subscription has no plan attached,
    # which should not happen — subscription_plan_id is NOT NULL. They exist so
    # a billing calculation can never divide by a None.
    DEFAULT_COMMISSION_RATE = Decimal("0.0300")
    DEFAULT_CAP_AMOUNT = Decimal("299.00")
    DEFAULT_TRIAL_THRESHOLD = Decimal("1000.00")

    @property
    def effective_commission_rate(self) -> Decimal:
        """Share of attributed revenue to charge (override > plan)."""
        if self.commission_rate_override is not None:
            return Decimal(str(self.commission_rate_override))
        plan = self.subscription_plan
        if plan and plan.commission_rate is not None:
            return Decimal(str(plan.commission_rate))
        return self.DEFAULT_COMMISSION_RATE

    @property
    def effective_cap_amount(self) -> Decimal:
        """Maximum chargeable in a cycle (override > plan)."""
        if self.cap_amount_override is not None:
            return Decimal(str(self.cap_amount_override))
        plan = self.subscription_plan
        if plan and plan.cap_amount is not None:
            return Decimal(str(plan.cap_amount))
        return self.DEFAULT_CAP_AMOUNT

    @property
    def effective_trial_threshold(self) -> Decimal:
        """Attributed revenue the shop earns free before the first charge."""
        if self.trial_threshold_override is not None:
            return Decimal(str(self.trial_threshold_override))
        plan = self.subscription_plan
        if plan and plan.trial_revenue_threshold is not None:
            return Decimal(str(plan.trial_revenue_threshold))
        return self.DEFAULT_TRIAL_THRESHOLD

    @property
    def currency(self) -> str:
        """Always returns USD (global pay-as-you-go pricing)"""
        return "USD"
