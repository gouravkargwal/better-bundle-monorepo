"""
User session model for SQLAlchemy

Represents user sessions and their relationships.
"""

from sqlalchemy import (
    Column,
    String,
    Integer,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import JSON, TIMESTAMP
from sqlalchemy.orm import relationship
from .base import BaseModel, ShopMixin, CustomerMixin


class UserSession(BaseModel, ShopMixin, CustomerMixin):
    """User session model for tracking user sessions"""

    __tablename__ = "user_sessions"

    browser_session_id = Column(String(255), nullable=False)
    status = Column(String(50), default="active", nullable=False, index=True)
    last_active = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    user_agent = Column(String, nullable=True)
    ip_address = Column(String(45), nullable=True)
    referrer = Column(String, nullable=True)
    extensions_used = Column(JSON, default=[], nullable=False)
    total_interactions = Column(Integer, default=0, nullable=False)

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
            "shop_id",
            "customer_id",
            "browser_session_id",
            unique=True,
        ),
        Index("ix_user_session_shop_id", "shop_id"),
        Index("ix_user_session_customer_id", "customer_id"),
        Index("ix_user_session_status", "status"),
        Index("ix_user_session_expires_at", "expires_at"),
        Index("ix_user_session_shop_id_status", "shop_id", "status"),
        Index(
            "ix_user_session_shop_id_customer_id_status",
            "shop_id",
            "customer_id",
            "status",
        ),
    )

    def __repr__(self) -> str:
        return f"<UserSession(shop_id={self.shop_id}, customer_id={self.customer_id}, browser_session_id={self.browser_session_id})>"
