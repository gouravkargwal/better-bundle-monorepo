"""
User session model for SQLAlchemy

Represents user sessions and their relationships.
"""

from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Integer,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from .base import BaseModel, ShopMixin, CustomerMixin


class UserSession(BaseModel, ShopMixin, CustomerMixin):
    """User session model for tracking user sessions"""

    __tablename__ = "user_sessions"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Session identification - matching Prisma schema
    browser_session_id = Column("browser_session_id", String(255), nullable=False)
    status = Column(String(50), default="active", nullable=False, index=True)
    last_active = Column("last_active", DateTime, nullable=False, default=func.now())
    expires_at = Column("expires_at", DateTime, nullable=True, index=True)

    # Session metadata - matching Prisma schema
    user_agent = Column("user_agent", String, nullable=True)
    ip_address = Column("ip_address", String(45), nullable=True)
    referrer = Column(String, nullable=True)
    extensions_used = Column("extensions_used", JSON, default=[], nullable=False)
    total_interactions = Column(
        "total_interactions", Integer, default=0, nullable=False
    )

    # Relationships
    shop = relationship("Shop", back_populates="user_sessions")
    attributions = relationship(
        "PurchaseAttribution", back_populates="session", cascade="all, delete-orphan"
    )
    interactions = relationship(
        "UserInteraction", back_populates="session", cascade="all, delete-orphan"
    )

    # Indexes
    __table_args__ = (
        Index(
            "ix_user_session_shop_id_customer_id_browser_session_id",
            "shopId",
            "customer_id",
            "browser_session_id",
            unique=True,
        ),
        Index("ix_user_session_shop_id", "shopId"),
        Index("ix_user_session_customer_id", "customer_id"),
        Index("ix_user_session_status", "status"),
        Index("ix_user_session_expires_at", "expires_at"),
        Index("ix_user_session_shop_id_status", "shopId", "status"),
        Index(
            "ix_user_session_shop_id_customer_id_status",
            "shopId",
            "customer_id",
            "status",
        ),
    )

    def __repr__(self) -> str:
        return f"<UserSession(shop_id={self.shopId}, customer_id={self.customer_id}, browser_session_id={self.browser_session_id})>"
