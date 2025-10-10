"""
Shopify Subscription Model

Decouples Shopify-specific data from business logic.
Tracks Shopify subscription integration details.
"""

from datetime import datetime
from sqlalchemy import Column, String, Text, ForeignKey, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship
from .base import BaseModel
from .enums import ShopifySubscriptionStatus
from .shop_subscription import ShopSubscription


class ShopifySubscription(BaseModel):
    """
    Shopify Subscription

    Decouples Shopify-specific data from business logic.
    Tracks Shopify subscription integration details.
    """

    __tablename__ = "shopify_subscriptions"

    # Foreign keys
    shop_subscription_id = Column(
        String(255),
        ForeignKey("shop_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # One Shopify subscription per shop subscription
        index=True,
    )

    # Shopify subscription details
    shopify_subscription_id = Column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
        comment="Shopify subscription GID",
    )
    shopify_line_item_id = Column(
        String(255),
        nullable=True,
        index=True,
        comment="Shopify subscription line item ID",
    )

    # Shopify subscription state
    status = Column(
        SQLEnum(ShopifySubscriptionStatus, name="shopify_subscription_status_enum"),
        nullable=False,
        index=True,
    )

    # Shopify URLs and confirmation
    confirmation_url = Column(Text, nullable=True)
    return_url = Column(Text, nullable=True)

    # Shopify subscription lifecycle
    created_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    activated_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    cancelled_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)

    # Shopify response data
    shopify_response = Column(
        Text, nullable=True
    )  # JSON string of full Shopify response
    shopify_metadata = Column(Text, nullable=True)  # Additional Shopify metadata

    # Error tracking
    last_error = Column(Text, nullable=True)
    last_error_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    error_count = Column(String(10), nullable=False, default="0")

    # Relationships
    shop_subscription = relationship(
        "ShopSubscription", back_populates="shopify_subscription"
    )

    # Indexes
    __table_args__ = (
        Index("ix_shopify_subscription_subscription", "shop_subscription_id"),
        Index("ix_shopify_subscription_shopify_id", "shopify_subscription_id"),
        Index("ix_shopify_subscription_status", "status"),
        Index("ix_shopify_subscription_created", "created_at"),
        Index("ix_shopify_subscription_activated", "activated_at"),
        Index("ix_shopify_subscription_cancelled", "cancelled_at"),
        Index("ix_shopify_subscription_error", "last_error_at"),
    )

    def __repr__(self) -> str:
        return f"<ShopifySubscription(subscription_id={self.shop_subscription_id}, shopify_id={self.shopify_subscription_id}, status={self.status.value})>"

    @property
    def is_pending(self) -> bool:
        """Check if Shopify subscription is pending approval"""
        return self.status == ShopifySubscriptionStatus.PENDING

    @property
    def is_active(self) -> bool:
        """Check if Shopify subscription is active"""
        return self.status == ShopifySubscriptionStatus.ACTIVE

    @property
    def is_declined(self) -> bool:
        """Check if Shopify subscription was declined"""
        return self.status == ShopifySubscriptionStatus.DECLINED

    @property
    def is_cancelled(self) -> bool:
        """Check if Shopify subscription is cancelled"""
        return self.status == ShopifySubscriptionStatus.CANCELLED

    @property
    def is_expired(self) -> bool:
        """Check if Shopify subscription is expired"""
        return self.status == ShopifySubscriptionStatus.EXPIRED

    @property
    def has_errors(self) -> bool:
        """Check if there are any errors"""
        return self.error_count and int(self.error_count) > 0

    @property
    def days_since_created(self) -> int:
        """Calculate days since subscription was created"""
        if not self.created_at:
            return -1
        return (datetime.utcnow() - self.created_at).days

    @property
    def days_since_activated(self) -> int:
        """Calculate days since subscription was activated"""
        if not self.activated_at:
            return -1
        return (datetime.utcnow() - self.activated_at).days
