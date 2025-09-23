"""
Extension activity model for SQLAlchemy

Represents extension activity tracking.
"""

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import relationship
from .base import BaseModel, ShopMixin
from .enums import AppBlockTarget


class ExtensionActivity(BaseModel, ShopMixin):
    """Extension activity model for tracking extension usage"""

    __tablename__ = "extension_activities"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Extension identification
    extension_type = Column(String, nullable=False, index=True)  # AppBlockTarget enum
    extension_uid = Column(String(255), nullable=False)
    extension_name = Column(String(100), nullable=False)

    # App block information (for Venus extensions)
    app_block_target = Column(String, nullable=True)
    page_url = Column(String(500), nullable=True)
    app_block_location = Column(String(100), nullable=True)

    # Activity tracking
    last_seen = Column(DateTime, nullable=False, default=func.now(), index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    shop = relationship("Shop", back_populates="extension_activities")

    # Indexes
    __table_args__ = (
        Index(
            "ix_extension_activity_shop_id_extension_type_extension_uid",
            "shop_id",
            "extension_type",
            "extension_uid",
            unique=True,
        ),
        Index("ix_extension_activity_shop_id", "shop_id"),
        Index("ix_extension_activity_extension_type", "extension_type"),
        Index("ix_extension_activity_last_seen", "last_seen"),
        Index("ix_extension_activity_shop_id_last_seen", "shop_id", "last_seen"),
        Index(
            "ix_extension_activity_extension_type_last_seen",
            "extension_type",
            "last_seen",
        ),
    )

    def __repr__(self) -> str:
        return f"<ExtensionActivity(shop_id={self.shop_id}, extension_type={self.extension_type}, extension_uid={self.extension_uid})>"
