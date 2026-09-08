"""
Subscription Plan Model

Master table defining available subscription plans (templates).
Admin-controlled, rarely changes.
"""

from datetime import datetime
from decimal import Decimal
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    Integer,
    Numeric,
    Index,
    Enum as SQLEnum,
)
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

    # Pay-as-you-go pricing.
    #
    # The merchant is charged `commission_rate` of the revenue attributed to
    # recommendations, never more than `cap_amount` in a 30-day cycle. Shopify
    # requires the cap up front — it is what the merchant approves, and usage
    # records beyond it are rejected by the platform.
    commission_rate = Column(
        Numeric(5, 4),
        nullable=False,
        default=Decimal("0.0300"),
        server_default="0.0300",
        comment="Share of attributed revenue charged, e.g. 0.0300 = 3%",
    )
    cap_amount = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("299.00"),
        server_default="299.00",
        comment="Maximum chargeable per 30-day cycle (Shopify cappedAmount)",
    )
    trial_revenue_threshold = Column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("1000.00"),
        server_default="1000.00",
        comment="Attributed revenue earned free before the first charge",
    )

    # Metadata
    plan_metadata = Column(Text, nullable=True)  # JSON string for additional config

    # Timestamps are provided by BaseModel (TimestampMixin)
    # Additional business timestamps
    effective_from = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    effective_to = Column(TIMESTAMP(timezone=True), nullable=True, index=True)

    # Relationships
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
        return (
            f"<SubscriptionPlan(name={self.name}, type={self.plan_type.value}, "
            f"active={self.is_active}, rate={self.commission_rate}, "
            f"cap=${self.cap_amount}, "
            f"trial_threshold=${self.trial_revenue_threshold})>"
        )

    @property
    def is_currently_active(self) -> bool:
        """Check if plan is currently active (not expired)"""
        now = datetime.utcnow()
        return (
            self.is_active
            and self.effective_from <= now
            and (self.effective_to is None or self.effective_to > now)
        )
