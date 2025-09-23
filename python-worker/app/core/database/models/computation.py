"""
Computation models for SQLAlchemy

Represents feature computation tracking and job management.
"""

from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from .base import BaseModel, ShopMixin


class FeatureComputation(BaseModel, ShopMixin):
    """Feature computation model for tracking computation jobs"""

    __tablename__ = "FeatureComputation"

    # Foreign key to Shop
    # shop_id provided by ShopMixin

    # Job information
    job_id = Column(String, nullable=False)
    status = Column(String, default="pending", nullable=False, index=True)
    feature_count = Column(Integer, default=0, nullable=False)
    job_metadata = Column(JSON, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    shop = relationship("Shop", back_populates="feature_computations")

    # Indexes
    __table_args__ = (
        Index("ix_feature_computation_shop_id_status", "shopId", "status"),
        Index("ix_feature_computation_shop_id_created_at", "shopId", "createdAt"),
        Index(
            "ix_feature_computation_shop_id_status_created_at",
            "shopId",
            "status",
            "createdAt",
        ),
    )

    def __repr__(self) -> str:
        return f"<FeatureComputation(shop_id={self.shopId}, job_id={self.job_id}, status={self.status})>"
