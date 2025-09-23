from typing import Optional
from sqlalchemy import select
from app.core.database.models import PipelineWatermark
from app.core.database.session import get_session_context


class PipelineWatermarkRepository:
    def __init__(self, session_factory=None):
        """
        Initializes the repository with a session factory.
        Repository handles its own session management.
        """
        self.session_factory = session_factory or get_session_context

    async def get_by_id(self, pipeline_id: str) -> Optional[PipelineWatermark]:
        """Fetch a single pipeline watermark by its ID."""
        async with self.session_factory() as session:
            statement = select(PipelineWatermark).where(
                PipelineWatermark.id == pipeline_id
            )
            result = await session.execute(statement)
            return result.scalar_one_or_none()

    async def get_by_shop_and_data_type(
        self, shop_id: str, data_type: str
    ) -> Optional[PipelineWatermark]:
        """
        Fetch a pipeline watermark for a given shop and data type.

        Args:
            shop_id: Shopify shop ID (foreign key on PipelineWatermark.shop_id)
            data_type: Data type key (e.g., "products", "orders", "customers", "collections")

        Returns:
            PipelineWatermark if found, otherwise None.
        """
        async with self.session_factory() as session:
            statement = select(PipelineWatermark).where(
                (PipelineWatermark.shop_id == shop_id)
                & (PipelineWatermark.data_type == data_type)
            )
            result = await session.execute(statement)
            return result.scalar_one_or_none()

    async def upsert_collection_watermark(
        self, shop_id: str, data_type: str, last_dt
    ) -> PipelineWatermark:
        """Insert or update collection watermark window for a shop and data type."""
        async with self.session_factory() as session:
            result = await session.execute(
                select(PipelineWatermark).where(
                    (PipelineWatermark.shop_id == shop_id)
                    & (PipelineWatermark.data_type == data_type)
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.last_collected_at = last_dt
                existing.last_window_end = last_dt
                wm = existing
            else:
                wm = PipelineWatermark(
                    shop_id=shop_id,
                    data_type=data_type,
                    last_collected_at=last_dt,
                    last_window_end=last_dt,
                )
                session.add(wm)

            await session.commit()
            return wm
