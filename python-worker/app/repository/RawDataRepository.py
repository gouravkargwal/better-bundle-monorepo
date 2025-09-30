from typing import Optional
from sqlalchemy import select, func
from datetime import datetime

from app.core.database.session import get_session_context
from app.core.database.models import RawOrder, RawProduct, RawCustomer, RawCollection


class RawDataRepository:
    def __init__(self, session_factory=None):
        self.session_factory = session_factory or get_session_context

    async def get_raw_count(self, shop_id: str, data_type: str) -> int:
        """Return count of raw records for a given shop and data type."""
        model = {
            "products": RawProduct,
            "orders": RawOrder,
            "customers": RawCustomer,
            "collections": RawCollection,
        }.get(data_type)

        if model is None:
            return 0

        async with self.session_factory() as session:
            result = await session.execute(
                select(func.count()).select_from(model).where(model.shop_id == shop_id)
            )
            return int(result.scalar_one())

    async def get_latest_shopify_timestamp(
        self, shop_id: str, data_type: str
    ) -> Optional[datetime]:
        """Return the latest shopify_updated_at timestamp for a given shop and data type."""
        model = {
            "products": RawProduct,
            "orders": RawOrder,
            "customers": RawCustomer,
            "collections": RawCollection,
        }.get(data_type)

        if model is None:
            return None

        # Prefer updated timestamp across types
        timestamp_column = getattr(model, "shopify_updated_at", None)
        if timestamp_column is None:
            return None

        async with self.session_factory() as session:
            result = await session.execute(
                select(timestamp_column)
                .where(model.shop_id == shop_id)
                .order_by(timestamp_column.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
