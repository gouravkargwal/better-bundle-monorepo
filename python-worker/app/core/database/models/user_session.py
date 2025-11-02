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

    browser_session_id = Column(
        String(255), nullable=True
    )  # Made nullable as fallback only
    status = Column(String(50), default="active", nullable=False, index=True)
    client_id = Column(String, nullable=True, index=True)  # ✅ NEW: Shopify client ID
    last_active = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        default=func.timezone("UTC", func.current_timestamp()),
    )
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
            "ix_active_by_customer",
            "shop_id",
            "customer_id",
            "status",
            "expires_at",
            postgresql_where="customer_id IS NOT NULL AND status = 'active'",
        ),
        # Priority 2: Look up by client_id (cross-device linking)
        Index(
            "ix_active_by_client_id",
            "shop_id",
            "client_id",
            "status",
            "expires_at",
            postgresql_where="client_id IS NOT NULL AND status = 'active'",
        ),
        # Priority 3: Look up by browser_session_id (same device/tab)
        Index(
            "ix_active_by_browser_session",
            "shop_id",
            "browser_session_id",
            "status",
            "expires_at",
            postgresql_where="browser_session_id IS NOT NULL AND status = 'active'",
        ),
        # Support queries
        Index("ix_shop_id", "shop_id"),
        Index("ix_customer_id", "customer_id"),
        Index("ix_status", "status"),
        Index("ix_expires_at", "expires_at"),
        Index("ix_shop_status", "shop_id", "status"),
        Index("ix_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<UserSession(shop_id={self.shop_id}, customer_id={self.customer_id}, browser_session_id={self.browser_session_id})>"
