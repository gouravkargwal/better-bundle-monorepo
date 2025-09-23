"""
User interaction model for SQLAlchemy

Represents user interactions with extensions.
"""

from sqlalchemy import Column, String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from .base import BaseModel, ShopMixin, CustomerMixin


class UserInteraction(BaseModel, ShopMixin, CustomerMixin):
    """User interaction model for tracking user interactions"""

    __tablename__ = "user_interactions"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Interaction identification - matching Prisma schema
    session_id = Column(
        "session_id", String(255), ForeignKey("user_sessions.id"), nullable=False
    )
    extension_type = Column("extension_type", String(50), nullable=False, index=True)
    interaction_type = Column(
        "interaction_type", String(50), nullable=False, index=True
    )

    # Interaction data - matching Prisma schema
    interaction_metadata = Column("metadata", JSON, default={}, nullable=False)

    # Relationships
    session = relationship("UserSession", back_populates="interactions")
    shop = relationship("Shop", back_populates="user_interactions")

    # Indexes
    __table_args__ = (
        Index("ix_user_interaction_session_id", "session_id"),
        Index("ix_user_interaction_customer_id", "customer_id"),
        Index("ix_user_interaction_shop_id", "shopId"),
        Index("ix_user_interaction_extension_type", "extension_type"),
        Index("ix_user_interaction_interaction_type", "interaction_type"),
        Index("ix_user_interaction_created_at", "createdAt"),
        Index("ix_user_interaction_shop_id_extension_type", "shopId", "extension_type"),
        Index(
            "ix_user_interaction_shop_id_interaction_type",
            "shopId",
            "interaction_type",
        ),
        Index(
            "ix_user_interaction_shop_id_customer_id_created_at",
            "shopId",
            "customer_id",
            "createdAt",
        ),
    )

    def __repr__(self) -> str:
        return f"<UserInteraction(shop_id={self.shopId}, extension_type={self.extension_type}, interaction_type={self.interaction_type})>"
