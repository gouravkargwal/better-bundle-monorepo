from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.core.logging import get_logger
from app.shared.gorse_api_client import GorseApiClient
from app.domains.ml.transformers.gorse_data_transformers import GorseDataTransformers
from app.core.database.models import UserFeatures, CustomerBehaviorFeatures

logger = get_logger(__name__)


class UserService:
    """
    Service that syncs user-related feature data directly to the Gorse API.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        gorse_base_url: str = "http://localhost:8088",
        gorse_api_key: str = "secure_random_key_123",
        batch_size: int = 500,
    ):
        """
        Initialize the user sync service.

        Args:
            session_factory: An SQLAlchemy async_sessionmaker for creating DB sessions.
            gorse_base_url: Gorse master server URL.
            gorse_api_key: API key for Gorse authentication.
            batch_size: Batch size for API calls.
        """
        self.session_factory = session_factory
        self.gorse_client = GorseApiClient(gorse_base_url, gorse_api_key)
        self.transformers = GorseDataTransformers()
        self.batch_size = batch_size

    async def sync_users(
        self, shop_id: str, since_time: Optional[datetime] = None
    ) -> int:
        """Syncs base user features from the UserFeatures table to Gorse."""
        total_synced = 0
        offset = 0
        logger.info(f"Starting sync of UserFeatures for shop '{shop_id}'.")

        try:
            async with self.session_factory() as session:
                while True:
                    # 1. Build the SQLAlchemy query
                    stmt = select(UserFeatures).where(UserFeatures.shop_id == shop_id)
                    if since_time:
                        stmt = stmt.where(UserFeatures.last_computed_at >= since_time)

                    stmt = (
                        stmt.order_by(UserFeatures.last_computed_at.asc())
                        .offset(offset)
                        .limit(self.batch_size)
                    )

                    # 2. Execute and fetch the batch
                    result = await session.execute(stmt)
                    users = result.scalars().all()

                    if not users:
                        break

                    # 3. Transform data for Gorse
                    gorse_users = []
                    for user in users:
                        prefixed_user_id = f"shop_{shop_id}_{user.customer_id}"
                        labels = self.transformers.transform_user_features_to_labels(
                            user
                        )
                        gorse_users.append(
                            {"userId": prefixed_user_id, "labels": labels}
                        )

                    # 4. Push the batch to Gorse
                    if gorse_users:
                        await self.gorse_client.insert_users_batch(gorse_users)
                        total_synced += len(gorse_users)
                        logger.info(
                            f"Synced {len(gorse_users)} users (total for this run: {total_synced})"
                        )

                    if len(users) < self.batch_size:
                        break
                    offset += self.batch_size

            logger.info(
                f"Completed sync of UserFeatures. Total synced: {total_synced}."
            )
            return total_synced
        except Exception as e:
            logger.error(f"Failed to sync users for shop {shop_id}: {e}", exc_info=True)
            return 0

    async def sync_customer_behaviors(
        self, shop_id: str, since_time: Optional[datetime] = None
    ) -> int:
        """Syncs behavioral features to update Gorse users with enhanced labels."""
        total_synced = 0
        offset = 0
        logger.info(f"Starting sync of CustomerBehaviorFeatures for shop '{shop_id}'.")

        try:
            async with self.session_factory() as session:
                while True:
                    # 1. Build the SQLAlchemy query
                    stmt = select(CustomerBehaviorFeatures).where(
                        CustomerBehaviorFeatures.shop_id == shop_id
                    )
                    if since_time:
                        stmt = stmt.where(
                            CustomerBehaviorFeatures.last_computed_at >= since_time
                        )

                    stmt = (
                        stmt.order_by(CustomerBehaviorFeatures.last_computed_at.asc())
                        .offset(offset)
                        .limit(self.batch_size)
                    )

                    # 2. Execute and fetch the batch
                    result = await session.execute(stmt)
                    behaviors = result.scalars().all()

                    if not behaviors:
                        break

                    # 3. Transform data into Gorse user format
                    users_batch = []
                    for behavior in behaviors:
                        enhanced_user = self.transformers.transform_customer_behavior_to_user_features(
                            behavior, shop_id
                        )
                        if enhanced_user:
                            users_batch.append(enhanced_user)

                    # 4. Push the batch of updated users to Gorse
                    if users_batch:
                        await self.gorse_client.insert_users_batch(users_batch)
                        total_synced += len(users_batch)
                        logger.info(
                            f"Synced {len(users_batch)} customer behaviors (total for this run: {total_synced})"
                        )

                    if len(behaviors) < self.batch_size:
                        break
                    offset += self.batch_size

            logger.info(
                f"Completed sync of CustomerBehaviorFeatures. Total synced: {total_synced}."
            )
            return total_synced
        except Exception as e:
            logger.error(
                f"Failed to sync customer behavior features for shop {shop_id}: {e}",
                exc_info=True,
            )
            return 0
