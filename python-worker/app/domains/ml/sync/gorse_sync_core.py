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

            # 🔥 STEP 1: Create shop-specific views for Gorse
            await self.create_shop_gorse_views(shop_id)

            # Get last sync timestamp for incremental processing
            last_sync_timestamp = None
            if incremental:
                last_sync_timestamp = await self.pipeline._get_last_sync_timestamp(
                    shop_id
                )
                if last_sync_timestamp:
                    logger.info(f"Using incremental sync since: {last_sync_timestamp}")
                else:
                    logger.info("No previous sync found, performing full sync")

            if incremental:
                # For incremental syncs, use individual transactions for better performance
                # Each operation is atomic but independent
                await self._sync_all_incremental(shop_id, last_sync_timestamp)
            else:
                # For full syncs, use a single transaction to ensure consistency
                await self._sync_all_full_transaction(shop_id)

            logger.info(f"Completed Gorse sync for shop: {shop_id}")

        except Exception as e:
            logger.error(f"Failed to sync shop {shop_id}: {str(e)}")
            raise

    async def _sync_all_incremental(
        self, shop_id: str, last_sync_timestamp: Optional[datetime]
    ):
        """
        Perform incremental sync with individual transactions for each operation.
        This provides better performance for incremental updates while maintaining atomicity per operation.
        """
        try:
            # 1. Sync Users (combining multiple feature tables)
            await self.pipeline.user_sync.sync_users(
                shop_id, incremental=True, since_timestamp=last_sync_timestamp
            )

            # 2. Sync Items (combining multiple feature tables)
            await self.pipeline.item_sync.sync_items(
                shop_id, incremental=True, since_timestamp=last_sync_timestamp
            )

            # 3. Sync Feedback (from events, orders, and interaction features)
            await self.pipeline.feedback_sync.sync_feedback(shop_id)

        except Exception as e:
            logger.error(f"Failed incremental sync for shop {shop_id}: {str(e)}")
            raise

    async def _sync_all_full_transaction(self, shop_id: str):
        """
        Perform full sync within a single database transaction to ensure consistency.
        If any operation fails, the entire sync is rolled back.
        """
        db = await self.pipeline._get_database()

        try:
            # Start a database transaction
            async with db.tx() as transaction:
                logger.info(f"Starting full sync transaction for shop: {shop_id}")

                # Store the original database client and replace with transaction
                original_db = self.pipeline._db_client
                self.pipeline._db_client = transaction

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
                    await self.pipeline.feedback_sync.sync_feedback(shop_id)

                    logger.info(
                        f"Full sync transaction completed successfully for shop: {shop_id}"
                    )

                finally:
                    # Restore the original database client
                    self.pipeline._db_client = original_db

        except Exception as e:
            logger.error(f"Full sync transaction failed for shop {shop_id}: {str(e)}")
            logger.error("All changes have been rolled back")
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

    async def create_shop_gorse_views(self, shop_id: str):
        """
        Create shop-specific database views for Gorse to use
        This allows Gorse to see only the data for a specific shop
        Views automatically reflect data changes - no updates needed!
        """
        try:
            db = await self.pipeline._get_database()

            # Sanitize shop_id for SQL
            sanitized_shop_id = shop_id.replace("'", "''")

            # Check if views already exist
            check_sql = f"""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.views 
                    WHERE table_name = 'shop_{sanitized_shop_id}_items'
                )
                """
            result = await db.query_raw(check_sql)

            if result and result[0]["exists"]:
                logger.info(
                    f"Views already exist for shop {shop_id} - no update needed"
                )
                return  # Views are already current!

            # Create views for Gorse tables
            views_sql = [
                f"""
                    CREATE OR REPLACE VIEW shop_{sanitized_shop_id}_items AS 
                    SELECT 
                        "itemId" as item_id,
                        "categories"::text as categories,
                        "labels"::text as labels,
                        "isHidden" as is_hidden,
                        "updatedAt" as time_stamp,
                        '' as comment
                    FROM "gorse_items" 
                    WHERE "shopId" = '{sanitized_shop_id}'
                    """,
                f"""
                    CREATE OR REPLACE VIEW shop_{sanitized_shop_id}_users AS 
                    SELECT 
                        "userId" as user_id,
                        "labels"::text as labels,
                        '[]'::text as subscribe,
                        '' as comment
                    FROM "gorse_users" 
                    WHERE "shopId" = '{sanitized_shop_id}'
                    """,
                f"""
                    CREATE OR REPLACE VIEW shop_{sanitized_shop_id}_feedback AS 
                    SELECT 
                        "feedbackType" as feedback_type,
                        "userId" as user_id,
                        "itemId" as item_id,
                        1.0 as value,
                        "timestamp" as time_stamp,
                        COALESCE("comment", '') as comment
                    FROM "gorse_feedback" 
                    WHERE "shopId" = '{sanitized_shop_id}'
                    """,
            ]

            for sql in views_sql:
                await db.query_raw(sql)

            logger.info(
                f"Created Gorse views for shop {shop_id} - they will stay current automatically"
            )

        except Exception as e:
            logger.error(f"Failed to create Gorse views for shop {shop_id}: {str(e)}")
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
