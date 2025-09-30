"""
Identity models for SQLAlchemy

Represents user identity linking and computation tracking.
"""

from sqlalchemy import Column, String, Index, func, ForeignKey
from sqlalchemy.dialects.postgresql import TIMESTAMP
from .base import BaseModel, ShopMixin


class UserIdentityLink(BaseModel, ShopMixin):
    """User identity link model for cross-session customer linking"""

    __tablename__ = "user_identity_links"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Identity information
    client_id = Column(String, nullable=False, index=True)
    customer_id = Column(String, nullable=False, index=True)
    linked_at = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())

    # Indexes
    __table_args__ = (
        Index(
            "ix_user_identity_link_shop_id_client_id_customer_id",
            "shop_id",
            "client_id",
            "customer_id",
            unique=True,
        ),
        Index("ix_user_identity_link_shop_id_client_id", "shop_id", "client_id"),
        Index("ix_user_identity_link_shop_id_customer_id", "shop_id", "customer_id"),
    )

    def __repr__(self) -> str:
        return f"<UserIdentityLink(shop_id={self.shop_id}, client_id={self.client_id}, customer_id={self.customer_id})>"
