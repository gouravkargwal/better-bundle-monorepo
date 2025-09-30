"""
Watermark models for SQLAlchemy

Represents processing watermarks for data pipelines.
"""

from sqlalchemy import Column, String, Index, func
from .base import Base, ShopMixin, IDMixin, TimestampMixin
from sqlalchemy.dialects.postgresql import TIMESTAMP


class PipelineWatermark(Base, IDMixin, ShopMixin, TimestampMixin):
    """Pipeline watermark model - matches Prisma schema exactly"""

    __tablename__ = "pipeline_watermarks"

    # Watermark information
    data_type = Column(String(50), nullable=False)
    last_collected_at = Column(TIMESTAMP(timezone=True), nullable=True)
    last_normalized_at = Column(TIMESTAMP(timezone=True), nullable=True)
    last_features_computed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    last_gorse_synced_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Status and error tracking
    status = Column(String(20), nullable=True)
    last_error = Column(String, nullable=True)
    last_session_id = Column(String(100), nullable=True)

    # Window information
    last_window_start = Column(TIMESTAMP(timezone=True), nullable=True)
    last_window_end = Column(TIMESTAMP(timezone=True), nullable=True)

    # Only updatedAt exists in Prisma schema, no createdAt
    updated_at = Column(
        TIMESTAMP(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_pipeline_watermark_shop_id_data_type",
            "shop_id",
            "data_type",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PipelineWatermark(shop_id={self.shop_id}, data_type={self.data_type})>"
        )
