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

    # Contact information
    email = Column(String(255), nullable=True)

    # Analysis tracking
    last_analysis_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)

    # Relationships
    collection_data = relationship(
        "CollectionData", back_populates="shop", cascade="all, delete-orphan"
    )
    collection_features = relationship(
        "CollectionFeatures", back_populates="shop", cascade="all, delete-orphan"
    )
    customer_behavior_features = relationship(
        "CustomerBehaviorFeatures", back_populates="shop", cascade="all, delete-orphan"
    )
    customer_data = relationship(
        "CustomerData", back_populates="shop", cascade="all, delete-orphan"
    )
    interaction_features = relationship(
        "InteractionFeatures", back_populates="shop", cascade="all, delete-orphan"
    )
    order_data = relationship(
        "OrderData", back_populates="shop", cascade="all, delete-orphan"
    )
    product_data = relationship(
        "ProductData", back_populates="shop", cascade="all, delete-orphan"
    )
    product_features = relationship(
        "ProductFeatures", back_populates="shop", cascade="all, delete-orphan"
    )
    product_pair_features = relationship(
        "ProductPairFeatures", back_populates="shop", cascade="all, delete-orphan"
    )
    search_product_features = relationship(
        "SearchProductFeatures", back_populates="shop", cascade="all, delete-orphan"
    )
    session_features = relationship(
        "SessionFeatures", back_populates="shop", cascade="all, delete-orphan"
    )
    user_features = relationship(
        "UserFeatures", back_populates="shop", cascade="all, delete-orphan"
    )
    purchase_attributions = relationship(
        "PurchaseAttribution", back_populates="shop", cascade="all, delete-orphan"
    )
    refund_attributions = relationship(
        "RefundAttribution", back_populates="shop", cascade="all, delete-orphan"
    )
    user_interactions = relationship(
        "UserInteraction", back_populates="shop", cascade="all, delete-orphan"
    )
    user_sessions = relationship(
        "UserSession", back_populates="shop", cascade="all, delete-orphan"
    )
    extension_activities = relationship(
        "ExtensionActivity", back_populates="shop", cascade="all, delete-orphan"
    )

    # Table constraints
    __table_args__ = (UniqueConstraint("shop_domain", name="shop_domain_unique"),)

    def __repr__(self) -> str:
        return f"<Shop(domain={self.shop_domain}, plan={self.plan_type})>"
