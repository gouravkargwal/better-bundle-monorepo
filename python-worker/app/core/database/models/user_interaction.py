"""
User interaction model for SQLAlchemy

Represents user interactions with extensions.
"""

from sqlalchemy import Column, String, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from .base import BaseModel, ShopMixin, CustomerMixin


class UserInteraction(BaseModel, ShopMixin, CustomerMixin):
    """User interaction model for tracking user interactions"""

    __tablename__ = "user_interactions"

    session_id = Column(String(255), ForeignKey("user_sessions.id"), nullable=False)
    extension_type = Column(String(50), nullable=False, index=True)
    interaction_type = Column(String(50), nullable=False, index=True)
    interaction_metadata = Column(JSON, default={}, nullable=False)

    # Relationships
    session = relationship("UserSession", back_populates="interactions")
    shop = relationship("Shop", back_populates="user_interactions")

    # Indexes
    __table_args__ = (
        Index("ix_user_interaction_session_id", "session_id"),
        Index("ix_user_interaction_customer_id", "customer_id"),
        Index("ix_user_interaction_shop_id", "shop_id"),
        Index("ix_user_interaction_extension_type", "extension_type"),
        Index("ix_user_interaction_interaction_type", "interaction_type"),
        Index("ix_user_interaction_created_at", "created_at"),
        Index(
            "ix_user_interaction_shop_id_extension_type", "shop_id", "extension_type"
        ),
        Index(
            "ix_user_interaction_shop_id_interaction_type",
            "shop_id",
            "interaction_type",
        ),
        Index(
            "ix_user_interaction_shop_id_customer_id_created_at",
            "shop_id",
            "customer_id",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return f"<UserInteraction(shop_id={self.shop_id}, extension_type={self.extension_type}, interaction_type={self.interaction_type})>"
