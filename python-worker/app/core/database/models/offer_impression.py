"""
OfferImpression model for SQLAlchemy

Tracks every offer shown to a customer and its outcome (accepted/declined/ignored).
This is the single source of truth for the incrementality dashboard.
Replaces the legacy user_interactions table for offer-related events.
"""

from sqlalchemy import Column, String, Boolean, Index, Numeric
from sqlalchemy.dialects.postgresql import JSON, TIMESTAMP
from sqlalchemy.orm import relationship
from .base import BaseModel, ShopMixin, CustomerMixin


class OfferImpression(BaseModel, ShopMixin, CustomerMixin):
    """Tracks a single offer impression and its outcome"""

    __tablename__ = "offer_impressions"

    session_id = Column(String(255), nullable=True, index=True)
    surface = Column(String(20), nullable=False)  # 'apollo' | 'mercury'
    offer_type = Column(String(20), nullable=False)  # 'upsell' | 'cross_sell' | 'bundle' | 'control'
    offer_id = Column(String(255), nullable=True)  # product/bundle ID; NULL for control
    variant_id = Column(String(255), nullable=True)
    is_control = Column(Boolean, nullable=False, default=False)
    outcome = Column(String(20), nullable=False, default='shown')  # 'shown' | 'accepted' | 'declined' | 'ignored'
    outcome_at = Column(TIMESTAMP(timezone=True), nullable=True)
    revenue_added = Column(Numeric(10, 2), nullable=True)
    # Mapped to the DB column "metadata"; the bare attribute name is reserved by
    # SQLAlchemy's Declarative API and raised InvalidRequestError on import.
    offer_metadata = Column("metadata", JSON, nullable=True)
    impression_group_id = Column(String, nullable=True, index=True)

    # Relationships
    shop = relationship("Shop", back_populates="offer_impressions")

    __table_args__ = (
        Index("ix_oi_shop_date", "shop_id", "created_at"),
        Index("ix_oi_funnel", "shop_id", "surface", "created_at"),
        Index("ix_oi_control", "shop_id", "is_control", "created_at"),
        Index("ix_oi_offers", "shop_id", "offer_id", "outcome"),
        Index("ix_oi_impression_group", "impression_group_id"),
    )

    def __repr__(self) -> str:
        return f"<OfferImpression(shop_id={self.shop_id}, surface={self.surface}, outcome={self.outcome})>"
