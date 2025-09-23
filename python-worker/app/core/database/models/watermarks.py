"""
Watermark models for SQLAlchemy

Represents processing watermarks for data pipelines.
"""

from sqlalchemy import Column, String, DateTime, Index, ForeignKey, func
from .base import Base, ShopMixin, IDMixin


class PipelineWatermark(Base, IDMixin, ShopMixin):
    """Pipeline watermark model - matches Prisma schema exactly"""

    __tablename__ = "pipeline_watermarks"

    # Watermark information - matching Prisma schema exactly
    data_type = Column("data_type", String(50), nullable=False)
    last_collected_at = Column("last_collected_at", DateTime, nullable=True)
    last_normalized_at = Column("last_normalized_at", DateTime, nullable=True)
    last_features_computed_at = Column(
        "last_features_computed_at", DateTime, nullable=True
    )
    last_gorse_synced_at = Column("last_gorse_synced_at", DateTime, nullable=True)

    # Status and error tracking
    status = Column(String(20), nullable=True)
    last_error = Column("last_error", String, nullable=True)
    last_session_id = Column("last_session_id", String(100), nullable=True)

    # Window information
    last_window_start = Column("last_window_start", DateTime, nullable=True)
    last_window_end = Column("last_window_end", DateTime, nullable=True)

    # Only updatedAt exists in Prisma schema, no createdAt
    updated_at = Column(
        "updated_at", DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Indexes - matching Prisma schema
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
