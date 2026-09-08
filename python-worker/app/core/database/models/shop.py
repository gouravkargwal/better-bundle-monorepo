"""
Shop model for SQLAlchemy

Represents a Shopify shop with all its configuration and relationships.
"""

from sqlalchemy import Column, String, Boolean, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import relationship
from .base import BaseModel


class Shop(BaseModel):
    """Shop model representing a Shopify store"""

    __tablename__ = "shops"

    # Core shop information
    shop_domain = Column(String(255), nullable=False, index=True)
    custom_domain = Column(String(255), nullable=True)
    access_token = Column(String(1000), nullable=False)

    # Plan and billing information
    plan_type = Column(String(50), default="Free", nullable=False, index=True)
    currency_code = Column(String(10), nullable=True)
    money_format = Column(String(100), nullable=True)

    # Status flags
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    onboarding_completed = Column(Boolean, default=False, nullable=False)
    setup_guide_visited = Column(Boolean, default=False, nullable=False)
    shopify_plus = Column(Boolean, default=False, nullable=False, index=True)

    # ✅ PATTERN 1: Service Suspension Fields
    suspended_at = Column(TIMESTAMP(timezone=True), nullable=True)
    suspension_reason = Column(String(255), nullable=True)
    service_impact = Column(
        String(50), nullable=True
    )  # 'suspended', 'active', 'limited'

    # Contact information
    email = Column(String(255), nullable=True)

    # Holdout testing (incrementality)
    holdout_disabled = Column(Boolean, default=False, nullable=False)

    # Analysis tracking
    last_analysis_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)

    # Relationships
    collection_data = relationship(
        "CollectionData", back_populates="shop", cascade="all, delete-orphan"
    )
    customer_data = relationship(
        "CustomerData", back_populates="shop", cascade="all, delete-orphan"
    )
    order_data = relationship(
        "OrderData", back_populates="shop", cascade="all, delete-orphan"
    )
    product_data = relationship(
        "ProductData", back_populates="shop", cascade="all, delete-orphan"
    )
    purchase_attributions = relationship(
        "PurchaseAttribution", back_populates="shop", cascade="all, delete-orphan"
    )
    offer_impressions = relationship(
        "OfferImpression", back_populates="shop", cascade="all, delete-orphan"
    )
    shop_subscriptions = relationship(
        "ShopSubscription", back_populates="shop", cascade="all, delete-orphan"
    )

    # Table constraints
    __table_args__ = (UniqueConstraint("shop_domain", name="shop_domain_unique"),)

    def __repr__(self) -> str:
        return f"<Shop(domain={self.shop_domain}, plan={self.plan_type})>"
