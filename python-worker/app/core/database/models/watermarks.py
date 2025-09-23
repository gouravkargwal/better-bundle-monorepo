"""
Watermark models for SQLAlchemy

Represents processing watermarks for data pipelines.
"""

from sqlalchemy import Column, String, DateTime, Index, ForeignKey, func
from .base import Base, ShopMixin, IDMixin


class PipelineWatermark(Base, IDMixin, ShopMixin):
    """Pipeline watermark model - matches Prisma schema exactly"""

    __tablename__ = "PipelineWatermark"

    # Watermark information - matching Prisma schema exactly
    dataType = Column("dataType", String(50), nullable=False)
    last_collected_at = Column("lastCollectedAt", DateTime, nullable=True)
    last_normalized_at = Column("lastNormalizedAt", DateTime, nullable=True)
    last_features_computed_at = Column(
        "lastFeaturesComputedAt", DateTime, nullable=True
    )
    last_gorse_synced_at = Column("lastGorseSyncedAt", DateTime, nullable=True)

    # Status and error tracking
    status = Column(String(20), nullable=True)
    last_error = Column("lastError", String, nullable=True)
    last_session_id = Column("lastSessionId", String(100), nullable=True)

    # Window information
    last_window_start = Column("lastWindowStart", DateTime, nullable=True)
    last_window_end = Column("lastWindowEnd", DateTime, nullable=True)

    # Only updatedAt exists in Prisma schema, no createdAt
    updated_at = Column(
        "updatedAt", DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Indexes - matching Prisma schema
    __table_args__ = (
        Index(
            "ix_pipeline_watermark_shop_id_data_type",
            "shopId",
            "dataType",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<PipelineWatermark(shopId={self.shopId}, dataType={self.dataType})>"
