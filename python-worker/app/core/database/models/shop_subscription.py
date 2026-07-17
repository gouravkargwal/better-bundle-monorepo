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

    # ===== TRIAL FIELDS =====
    trial_duration_days = Column(Integer, nullable=True)

    # ===== PAID SUBSCRIPTION FIELDS =====
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

    # ===== TABLE ARGS =====
    # Partial unique enforced at DB level (must be created via raw SQL / alembic):
    #   CREATE UNIQUE INDEX ix_shop_subscription_one_active_per_shop
    #       ON shop_subscriptions(shop_id) WHERE status != 'CANCELLED';
    #
    # Note: status, shop_id, is_active, and shopify_subscription_id already get
    # indexes from their Column(index=True) declarations above — do not redeclare
    # them here with the same auto-generated names, or CREATE TABLE fails with
    # DuplicateTableError on the second copy and the whole table creation rolls back.

    # ===== COMPUTED PROPERTIES =====

    @property
    def is_trial(self) -> bool:
        return self.status == SubscriptionStatus.TRIAL

    @property
    def is_paid(self) -> bool:
        return self.status == SubscriptionStatus.ACTIVE
