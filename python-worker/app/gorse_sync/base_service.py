# gorse_sync/base_service.py

from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select, func, and_

from app.shared.gorse_api_client import GorseApiClient
from app.domains.ml.transformers.gorse_data_transformers import GorseDataTransformers
from app.core.logging import get_logger

logger = get_logger(__name__)


class BaseGorseSyncService:
    """Base class for Gorse synchronization services."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        gorse_client: GorseApiClient,
        transformers: GorseDataTransformers,
        batch_size: int = 500,
    ):
        self.session_factory = session_factory
        self.gorse_client = gorse_client
        self.transformers = transformers
        self.batch_size = batch_size

    async def _check_feature_table_has_data(
        self, table_name: str, shop_id: str, since_time: Optional[datetime] = None
    ) -> bool:
        """Check if a feature table has data for the given shop and time range"""
        try:
            db = await self._get_database()

            # Get the table model
            table_model = getattr(db, table_name.lower(), None)
            if not table_model:
                logger.warning(f"Table {table_name} not found in database")
                return False

            # Check if there's any data
            if since_time:
                count = await table_model.count(
                    where={
                        "shopId": shop_id,
                        "lastComputedAt": {"gte": since_time},
                    }
                )
            else:
                count = await table_model.count(where={"shopId": shop_id})

            has_data = count > 0
            logger.info(f"Table {table_name} has {count} records for shop {shop_id}")
            return has_data

        except Exception as e:
            logger.error(
                f"Failed to check data in table {table_name} for shop {shop_id}: {str(e)}"
            )
            return False
