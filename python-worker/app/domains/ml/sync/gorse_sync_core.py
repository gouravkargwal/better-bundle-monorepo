"""
Core synchronization logic for Gorse pipeline
Handles main orchestration and transaction management
"""

import asyncio
from datetime import datetime
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class GorseSyncCore:
    """Core synchronization orchestration and transaction management"""

    def __init__(self, pipeline):
        self.pipeline = pipeline

    async def sync_all(self, shop_id: str, incremental: bool = True):
        """
        Main entry point - syncs all data for a shop to Gorse with transactional integrity

        For full syncs, wraps all operations in a database transaction to ensure consistency.
        For incremental syncs, uses individual transactions per operation for better performance.

        Args:
            shop_id: Shop ID to sync
            incremental: Whether to use incremental sync (default: True)
        """

        try:
            logger.info(
                f"Starting Gorse sync for shop: {shop_id} (incremental: {incremental})"
            )

            # Both incremental and full sync now use missing data detection (no time filtering)
            if incremental:
                logger.info(
                    f"Starting incremental sync for shop: {shop_id} (missing data detection)"
                )
                # For incremental syncs, use individual transactions for better performance
                await self._sync_all_incremental(shop_id)
            else:
                logger.info(
                    f"Starting full sync for shop: {shop_id} (missing data detection)"
                )
                # For full syncs, use individual transactions to avoid timeout issues
                await self._sync_all_full_transaction(shop_id)

            logger.info(f"Completed Gorse sync for shop: {shop_id}")

        except Exception as e:
            logger.error(f"Failed to sync shop {shop_id}: {str(e)}")
            raise

    async def _sync_all_incremental(self, shop_id: str):
        """
        Perform incremental sync based on missing data detection (not time-based).
        This syncs only data that exists in source tables but is missing from Gorse bridge tables.
        """
        try:
            # 1. Sync Users (combining multiple feature tables)
            # No time filtering - based on missing data detection
            await self.pipeline.user_sync.sync_users(
                shop_id, incremental=True, since_timestamp=None
            )

            # 2. Sync Items (combining multiple feature tables)
            # No time filtering - based on missing data detection
            await self.pipeline.item_sync.sync_items(
                shop_id, incremental=True, since_timestamp=None
            )

            # 3. Sync Feedback (from events, orders, and interaction features)
            # For incremental sync, sync all data (no time limits - based on missing data)
            await self.pipeline.feedback_sync.sync_feedback(shop_id, since_hours=0)

        except Exception as e:
            logger.error(f"Failed incremental sync for shop {shop_id}: {str(e)}")
            raise

    async def _sync_all_full_transaction(self, shop_id: str):
        """
        Perform full sync with individual transactions for each operation.
        Each sync operation handles its own transaction to avoid timeout issues.
        """
        logger.info(f"Starting full sync for shop: {shop_id}")

        try:
            # 1. Sync Users (combining multiple feature tables)
            await self.pipeline.user_sync.sync_users(
                shop_id, incremental=False, since_timestamp=None
            )

            # 2. Sync Items (combining multiple feature tables)
            await self.pipeline.item_sync.sync_items(
                shop_id, incremental=False, since_timestamp=None
            )

            # 3. Sync Feedback (from events, orders, and interaction features)
            # For full sync, look at all historical data (since_hours=0 means all data)
            await self.pipeline.feedback_sync.sync_feedback(shop_id, since_hours=0)

            logger.info(f"Full sync completed successfully for shop: {shop_id}")

        except Exception as e:
            logger.error(f"Full sync failed for shop {shop_id}: {str(e)}")
            raise

    async def _execute_with_transaction(
        self, operation_name: str, operation_func, *args, **kwargs
    ):
        """
        Execute an operation within a database transaction for atomicity.
        This is used for individual sync operations to ensure they are atomic.
        """
        db = await self.pipeline._get_database()

        try:
            async with db.tx() as transaction:
                logger.debug(f"Starting transaction for {operation_name}")

                # Store the original database client and replace with transaction
                original_db = self.pipeline._db_client
                self.pipeline._db_client = transaction

                try:
                    result = await operation_func(*args, **kwargs)
                    logger.debug(
                        f"Transaction completed successfully for {operation_name}"
                    )
                    return result

                finally:
                    # Restore the original database client
                    self.pipeline._db_client = original_db

        except Exception as e:
            logger.error(f"Transaction failed for {operation_name}: {str(e)}")
            raise

    def _is_in_transaction(self) -> bool:
        """
        Check if we're currently within a database transaction.
        This helps avoid nested transactions which can cause issues.
        """
        return (
            hasattr(self.pipeline._db_client, "_transaction")
            and self.pipeline._db_client._transaction is not None
        )

    async def _generic_batch_processor(
        self,
        shop_id: str,
        batch_size: int,
        fetch_batch_func: callable,
        process_batch_func: callable,
        entity_name: str,
        additional_processor: callable = None,
    ) -> int:
        """Generic batch processing pattern for syncing data"""
        try:
            logger.info(
                f"Starting {entity_name} sync for shop {shop_id} with batch size {batch_size}"
            )

            total_synced = 0
            offset = 0

            while True:
                # Fetch batch
                batch_data = await fetch_batch_func(shop_id, offset, batch_size)

                if not batch_data:
                    break  # No more data to process

                # Process this batch
                batch_count = await process_batch_func(shop_id, batch_data)
                total_synced += batch_count
                offset += len(batch_data)

                logger.debug(
                    f"Processed {entity_name} batch: {len(batch_data)} items, total: {total_synced}"
                )

            # Run additional processing if provided
            additional_count = 0
            if additional_processor:
                additional_count = await additional_processor(shop_id)
                if additional_count:
                    logger.info(
                        f"Additional {entity_name} processing: {additional_count} items"
                    )

            logger.info(f"Synced {total_synced} {entity_name} for shop {shop_id}")
            return total_synced

        except Exception as e:
            logger.error(f"Failed to sync {entity_name}: {str(e)}")
            raise


async def run_gorse_sync(
    shop_id: str,
    batch_size: int = 1000,
    user_batch_size: int = 500,
    item_batch_size: int = 500,
):
    """
    Main entry point to run Gorse synchronization with configurable batch sizes
    """
    from app.domains.ml.services.gorse_sync_pipeline import GorseSyncPipeline

    pipeline = GorseSyncPipeline(
        batch_size=batch_size,
        user_batch_size=user_batch_size,
        item_batch_size=item_batch_size,
    )
    await pipeline.sync_all(shop_id)
