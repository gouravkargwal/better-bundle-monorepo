"""
Optimized Gorse Data Synchronization Pipeline
Designed to achieve 70% of big recommendation engine performance
Uses ALL feature tables to build comprehensive user and item profiles
"""

import asyncio
import json
import math
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from app.core.database.simple_db_client import get_database
from app.core.logging import get_logger
from app.shared.helpers import now_utc
from prisma import Json
from prisma.errors import PrismaError, UniqueViolationError

logger = get_logger(__name__)


def retry_with_exponential_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (PrismaError, asyncio.TimeoutError, ConnectionError),
):
    """Decorator for retrying operations with exponential backoff"""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_retries:
                        logger.error(
                            f"Operation {func.__name__} failed after {max_retries} retries: {str(e)}"
                        )
                        raise e

                    # Calculate delay with exponential backoff and jitter
                    delay = min(
                        base_delay * (2**attempt) + random.uniform(0, 1), max_delay
                    )
                    logger.warning(
                        f"Operation {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {str(e)}. Retrying in {delay:.2f}s"
                    )
                    await asyncio.sleep(delay)
                except Exception as e:
                    # Don't retry for non-transient errors
                    logger.error(f"Non-retryable error in {func.__name__}: {str(e)}")
                    raise e

            # This should never be reached, but just in case
            raise last_exception

        return wrapper

    return decorator


class GorseSyncPipeline:
    """
    Synchronizes data from ALL feature tables to Gorse-compatible format
    """

    def __init__(
        self,
        batch_size: int = 1000,
        user_batch_size: int = 500,
        item_batch_size: int = 500,
    ):
        self._db_client = None
        # Performance configurations
        self.batch_size = batch_size  # General batch size
        self.user_batch_size = user_batch_size  # Users processing batch
        self.item_batch_size = item_batch_size  # Items processing batch
        self.feedback_batch_size = 2000  # Feedback bulk insert batch
        self.max_parallel_workers = (
            10  # Maximum parallel workers for concurrent operations
        )

    @retry_with_exponential_backoff(max_retries=3, base_delay=0.5)
    async def _get_database(self):
        """Get or initialize the database client with retry logic"""
        if self._db_client is None:
            self._db_client = await get_database()
        return self._db_client

    @retry_with_exponential_backoff(max_retries=2, base_delay=0.5)
    async def _get_last_sync_timestamp(self, shop_id: str) -> Optional[datetime]:
        """Get the last sync timestamp by checking feature table updates"""
        try:
            db = await self._get_database()
            # Check the most recent feature computation across all feature tables
            result = await db.query_raw(
                """
                SELECT MAX(last_computed) as last_sync FROM (
                    SELECT MAX("lastComputedAt") as last_computed FROM "UserFeatures" WHERE "shopId" = $1
                    UNION ALL
                    SELECT MAX("lastComputedAt") as last_computed FROM "ProductFeatures" WHERE "shopId" = $1
                    UNION ALL
                    SELECT MAX("lastComputedAt") as last_computed FROM "CustomerBehaviorFeatures" WHERE "shopId" = $1
                    UNION ALL
                    SELECT MAX("lastComputedAt") as last_computed FROM "CollectionFeatures" WHERE "shopId" = $1
                    UNION ALL
                    SELECT MAX("lastComputedAt") as last_computed FROM "InteractionFeatures" WHERE "shopId" = $1
                    UNION ALL
                    SELECT MAX("lastComputedAt") as last_computed FROM "SessionFeatures" WHERE "shopId" = $1
                ) as all_features
                """,
                shop_id,
            )

            if result and result[0]["last_sync"]:
                return result[0]["last_sync"]
            return None
        except (PrismaError, asyncio.TimeoutError, ConnectionError) as e:
            logger.warning(
                f"Database error getting last sync timestamp for shop {shop_id}: {str(e)}"
            )
            raise  # Let the retry decorator handle this
        except Exception as e:
            logger.error(
                f"Unexpected error getting last sync timestamp for shop {shop_id}: {str(e)}"
            )
            return None

    async def _is_first_sync(self, shop_id: str) -> bool:
        """Check if this is the first sync by checking if any feature data exists"""
        try:
            db = await self._get_database()
            result = await db.query_raw(
                """
                SELECT COUNT(*) as count FROM (
                    SELECT 1 FROM "UserFeatures" WHERE "shopId" = $1 LIMIT 1
                    UNION ALL
                    SELECT 1 FROM "ProductFeatures" WHERE "shopId" = $1 LIMIT 1
                    UNION ALL
                    SELECT 1 FROM "CustomerBehaviorFeatures" WHERE "shopId" = $1 LIMIT 1
                ) as any_features
                """,
                shop_id,
            )
            return result[0]["count"] == 0 if result else True
        except Exception as e:
            logger.warning(
                f"Could not check first sync status for shop {shop_id}: {str(e)}"
            )
            return True

    async def _generic_bulk_upsert(
        self,
        data_list: List[Dict[str, Any]],
        table_accessor: callable,
        id_field: str,
        entity_name: str,
        table_name: str,
        chunk_size: int = 100,
    ):
        """Generic bulk upsert method using raw SQL for better performance"""
        if not data_list:
            return

        try:
            db = await self._get_database()

            # Use raw SQL with ON CONFLICT for true bulk upsert
            # This is much more efficient than individual Prisma upserts
            if table_name == "gorse_users":
                await self._bulk_upsert_users_raw_sql(db, data_list, chunk_size)
            elif table_name == "gorse_items":
                await self._bulk_upsert_items_raw_sql(db, data_list, chunk_size)
            else:
                # Fallback to original method for other tables
                await self._fallback_bulk_upsert(
                    data_list, table_accessor, id_field, entity_name, chunk_size
                )

            logger.info(
                f"Successfully upserted {len(data_list)} {entity_name} records using bulk SQL"
            )

        except Exception as e:
            logger.error(f"Failed to bulk upsert {entity_name}: {str(e)}")
            raise

    @retry_with_exponential_backoff(max_retries=2, base_delay=1.0)
    async def _bulk_upsert_users_raw_sql(
        self, db, data_list: List[Dict[str, Any]], chunk_size: int
    ):
        """Bulk upsert users using raw SQL with ON CONFLICT"""
        for i in range(0, len(data_list), chunk_size):
            chunk = data_list[i : i + chunk_size]

            # Build VALUES clause for bulk insert
            values_list = []
            params = []
            param_count = 1

            for user_data in chunk:
                values_list.append(
                    f"(${param_count}, ${param_count + 1}, ${param_count + 2}, ${param_count + 3})"
                )
                params.extend(
                    [
                        user_data["userId"],
                        user_data["shopId"],
                        user_data["labels"],
                        user_data.get("updatedAt", datetime.utcnow()),
                    ]
                )
                param_count += 4

            values_clause = ", ".join(values_list)

            query = f"""
                INSERT INTO gorse_users ("userId", "shopId", labels, "updatedAt")
                VALUES {values_clause}
                ON CONFLICT ("userId") DO UPDATE SET
                    "shopId" = EXCLUDED."shopId",
                    labels = EXCLUDED.labels,
                    "updatedAt" = EXCLUDED."updatedAt"
            """

            await db.query_raw(query, *params)

    @retry_with_exponential_backoff(max_retries=2, base_delay=1.0)
    async def _bulk_upsert_items_raw_sql(
        self, db, data_list: List[Dict[str, Any]], chunk_size: int
    ):
        """Bulk upsert items using raw SQL with ON CONFLICT"""
        for i in range(0, len(data_list), chunk_size):
            chunk = data_list[i : i + chunk_size]

            # Build VALUES clause for bulk insert
            values_list = []
            params = []
            param_count = 1

            for item_data in chunk:
                values_list.append(
                    f"(${param_count}, ${param_count + 1}, ${param_count + 2}, ${param_count + 3}, ${param_count + 4})"
                )
                params.extend(
                    [
                        item_data["itemId"],
                        item_data["shopId"],
                        item_data["categories"],
                        item_data["labels"],
                        item_data.get("isHidden", False),
                    ]
                )
                param_count += 5

            values_clause = ", ".join(values_list)

            query = f"""
                INSERT INTO gorse_items ("itemId", "shopId", categories, labels, "isHidden")
                VALUES {values_clause}
                ON CONFLICT ("itemId") DO UPDATE SET
                    "shopId" = EXCLUDED."shopId",
                    categories = EXCLUDED.categories,
                    labels = EXCLUDED.labels,
                    "isHidden" = EXCLUDED."isHidden",
                    "updatedAt" = NOW()
            """

            await db.query_raw(query, *params)

    async def _fallback_bulk_upsert(
        self,
        data_list: List[Dict[str, Any]],
        table_accessor: callable,
        id_field: str,
        entity_name: str,
        chunk_size: int,
    ):
        """Fallback method using original Prisma upsert approach"""
        db = await self._get_database()
        table = table_accessor(db)

        # Process in smaller chunks with parallel processing
        semaphore = asyncio.Semaphore(self.max_parallel_workers)

        async def upsert_chunk(chunk):
            async with semaphore:
                return await asyncio.gather(
                    *[
                        table.upsert(
                            where={id_field: item_data[id_field]},
                            data={
                                "create": item_data,
                                "update": item_data,
                            },
                        )
                        for item_data in chunk
                    ],
                    return_exceptions=True,
                )

        # Process all chunks in parallel
        chunk_tasks = []
        for i in range(0, len(data_list), chunk_size):
            chunk = data_list[i : i + chunk_size]
            chunk_tasks.append(upsert_chunk(chunk))

        # Wait for all chunks to complete
        results = await asyncio.gather(*chunk_tasks, return_exceptions=True)

        # Count successful operations
        successful_ops = 0
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Chunk upsert failed: {str(result)}")
            else:
                successful_ops += len(
                    [r for r in result if not isinstance(r, Exception)]
                )

        logger.debug(
            f"Fallback upserted {successful_ops}/{len(data_list)} {entity_name} records"
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

            # Get last sync timestamp for incremental processing
            last_sync_timestamp = None
            if incremental:
                last_sync_timestamp = await self._get_last_sync_timestamp(shop_id)
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
            await self.sync_users(
                shop_id, incremental=True, since_timestamp=last_sync_timestamp
            )

            # 2. Sync Items (combining multiple feature tables)
            await self.sync_items(
                shop_id, incremental=True, since_timestamp=last_sync_timestamp
            )

            # 3. Sync Feedback (from events, orders, and interaction features)
            await self.sync_feedback(shop_id)

        except Exception as e:
            logger.error(f"Failed incremental sync for shop {shop_id}: {str(e)}")
            raise

    async def _sync_all_full_transaction(self, shop_id: str):
        """
        Perform full sync within a single database transaction to ensure consistency.
        If any operation fails, the entire sync is rolled back.
        """
        db = await self._get_database()

        try:
            # Start a database transaction
            async with db.tx() as transaction:
                logger.info(f"Starting full sync transaction for shop: {shop_id}")

                # Store the original database client and replace with transaction
                original_db = self._db_client
                self._db_client = transaction

                try:
                    # 1. Sync Users (combining multiple feature tables)
                    await self.sync_users(
                        shop_id, incremental=False, since_timestamp=None
                    )

                    # 2. Sync Items (combining multiple feature tables)
                    await self.sync_items(
                        shop_id, incremental=False, since_timestamp=None
                    )

                    # 3. Sync Feedback (from events, orders, and interaction features)
                    await self.sync_feedback(shop_id)

                    logger.info(
                        f"Full sync transaction completed successfully for shop: {shop_id}"
                    )

                finally:
                    # Restore the original database client
                    self._db_client = original_db

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
        db = await self._get_database()

        try:
            async with db.tx() as transaction:
                logger.debug(f"Starting transaction for {operation_name}")

                # Store the original database client and replace with transaction
                original_db = self._db_client
                self._db_client = transaction

                try:
                    result = await operation_func(*args, **kwargs)
                    logger.debug(
                        f"Transaction completed successfully for {operation_name}"
                    )
                    return result

                finally:
                    # Restore the original database client
                    self._db_client = original_db

        except Exception as e:
            logger.error(f"Transaction failed for {operation_name}: {str(e)}")
            raise

    def _is_in_transaction(self) -> bool:
        """
        Check if we're currently within a database transaction.
        This helps avoid nested transactions which can cause issues.
        """
        return (
            hasattr(self._db_client, "_transaction")
            and self._db_client._transaction is not None
        )

    async def sync_users(
        self,
        shop_id: str,
        incremental: bool = True,
        since_timestamp: Optional[datetime] = None,
    ):
        """
        Sync users combining UserFeatures, CustomerBehaviorFeatures, and InteractionFeatures
        Uses batch processing to handle large datasets efficiently with transactional integrity

        Args:
            shop_id: Shop ID to sync
            incremental: Whether to use incremental sync
            since_timestamp: Timestamp for incremental sync
        """

        async def _sync_users_operation():
            return await self._generic_batch_processor(
                shop_id=shop_id,
                batch_size=self.user_batch_size,
                fetch_batch_func=lambda shop_id, offset, limit: self._fetch_user_batch(
                    shop_id, offset, limit, since_timestamp if incremental else None
                ),
                process_batch_func=self._process_user_batch,
                entity_name="users",
                additional_processor=self._sync_anonymous_users,
            )

        # Use transaction if not already in one
        if self._is_in_transaction():
            await _sync_users_operation()
        else:
            await self._execute_with_transaction("sync_users", _sync_users_operation)

    async def _fetch_user_batch(
        self,
        shop_id: str,
        offset: int,
        limit: int,
        last_sync_timestamp: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch a batch of users with all their feature data (incremental if timestamp provided)"""
        try:
            db = await self._get_database()

            # Build incremental query if timestamp provided
            if last_sync_timestamp:
                base_query = """
                    SELECT 
                        uf.*,
                        cbf."engagementScore", cbf."recencyScore", cbf."diversityScore", cbf."behavioralScore",
                        cbf."sessionCount", cbf."productViewCount", cbf."cartAddCount", cbf."purchaseCount" as cbf_purchase_count,
                        cbf."searchCount", cbf."uniqueProductsViewed", cbf."uniqueCollectionsViewed",
                        cbf."deviceType", cbf."primaryReferrer", cbf."browseToCartRate", 
                        cbf."cartToPurchaseRate", cbf."searchToPurchaseRate", cbf."mostActiveHour", cbf."mostActiveDay"
                    FROM "UserFeatures" uf
                    LEFT JOIN "CustomerBehaviorFeatures" cbf 
                        ON uf."customerId" = cbf."customerId" AND uf."shopId" = cbf."shopId"
                    WHERE uf."shopId" = $1 
                        AND (uf."lastComputedAt" > $4::timestamp OR cbf."lastComputedAt" > $4::timestamp)
                    ORDER BY uf."customerId"
                    LIMIT $2 OFFSET $3
                """
                result = await db.query_raw(
                    base_query, shop_id, limit, offset, last_sync_timestamp
                )
            else:
                # Full sync query
                base_query = """
                    SELECT 
                        uf.*,
                        cbf."engagementScore", cbf."recencyScore", cbf."diversityScore", cbf."behavioralScore",
                        cbf."sessionCount", cbf."productViewCount", cbf."cartAddCount", cbf."purchaseCount" as cbf_purchase_count,
                        cbf."searchCount", cbf."uniqueProductsViewed", cbf."uniqueCollectionsViewed",
                        cbf."deviceType", cbf."primaryReferrer", cbf."browseToCartRate", 
                        cbf."cartToPurchaseRate", cbf."searchToPurchaseRate", cbf."mostActiveHour", cbf."mostActiveDay"
                    FROM "UserFeatures" uf
                    LEFT JOIN "CustomerBehaviorFeatures" cbf 
                        ON uf."customerId" = cbf."customerId" AND uf."shopId" = cbf."shopId"
                    WHERE uf."shopId" = $1
                    ORDER BY uf."customerId"
                    LIMIT $2 OFFSET $3
                """
                result = await db.query_raw(base_query, shop_id, limit, offset)
            batch_users = [dict(row) for row in result] if result else []

            if batch_users:
                # Fetch aggregated interaction and session data for this batch
                user_ids = [user["customerId"] for user in batch_users]
                interaction_data = await self._fetch_interaction_aggregates(
                    shop_id, user_ids
                )
                session_data = await self._fetch_session_aggregates(shop_id, user_ids)

                # Merge the aggregated data back into users
                for user in batch_users:
                    customer_id = user["customerId"]
                    user.update(interaction_data.get(customer_id, {}))
                    user.update(session_data.get(customer_id, {}))

            return batch_users

        except Exception as e:
            logger.error(f"Failed to fetch user batch: {str(e)}")
            raise

    async def _fetch_interaction_aggregates(
        self, shop_id: str, user_ids: List[str]
    ) -> Dict[str, Dict]:
        """Fetch interaction aggregates for a batch of users"""
        if not user_ids:
            return {}

        try:
            db = await self._get_database()

            # Use ANY for safer array parameterization
            query = """
                SELECT 
                    "customerId",
                    SUM("interactionScore") as total_interaction_score,
                    AVG("affinityScore") as avg_affinity_score
                FROM "InteractionFeatures" 
                WHERE "shopId" = $1 AND "customerId" = ANY($2)
                GROUP BY "customerId"
            """

            result = await db.query_raw(query, shop_id, user_ids)

            return (
                {
                    row["customerId"]: {
                        "total_interaction_score": float(
                            row["total_interaction_score"] or 0
                        ),
                        "avg_affinity_score": float(row["avg_affinity_score"] or 0),
                    }
                    for row in result
                }
                if result
                else {}
            )

        except Exception as e:
            logger.error(f"Failed to fetch interaction aggregates: {str(e)}")
            return {}

    async def _fetch_session_aggregates(
        self, shop_id: str, user_ids: List[str]
    ) -> Dict[str, Dict]:
        """Fetch session aggregates for a batch of users"""
        if not user_ids:
            return {}

        try:
            db = await self._get_database()

            # Use ANY for safer array parameterization
            query = """
                SELECT 
                    "customerId",
                    COUNT(*) FILTER (WHERE "checkoutCompleted" = true) as completed_sessions,
                    AVG("durationSeconds") as avg_session_duration
                FROM "SessionFeatures" 
                WHERE "shopId" = $1 AND "customerId" = ANY($2)
                GROUP BY "customerId"
            """

            result = await db.query_raw(query, shop_id, user_ids)

            return (
                {
                    row["customerId"]: {
                        "completed_sessions": int(row.get("completed_sessions") or 0),
                        "avg_session_duration": float(row["avg_session_duration"] or 0),
                    }
                    for row in result
                }
                if result
                else {}
            )

        except Exception as e:
            logger.error(f"Failed to fetch session aggregates: {str(e)}")
            return {}

    async def _process_user_batch(
        self, shop_id: str, users: List[Dict[str, Any]]
    ) -> int:
        """Process a batch of users with bulk operations"""
        if not users:
            return 0

        try:
            # Prepare bulk data for Gorse users
            gorse_users_data = []

            for user in users:
                labels = self._build_comprehensive_user_labels(user)
                user_data = {
                    "userId": user["customerId"],
                    "shopId": shop_id,
                    "labels": Json(labels),
                }
                gorse_users_data.append(user_data)

            # Bulk upsert to GorseUsers table
            await self._bulk_upsert_gorse_users(gorse_users_data)

            return len(users)

        except Exception as e:
            logger.error(f"Failed to process user batch: {str(e)}")
            raise

    async def _bulk_upsert_gorse_users(self, gorse_users_data: List[Dict[str, Any]]):
        """Bulk upsert users to GorseUsers table"""
        await self._generic_bulk_upsert(
            data_list=gorse_users_data,
            table_accessor=lambda db: db.gorseusers,
            id_field="userId",
            entity_name="users",
            table_name="GorseUsers",
        )

    async def sync_items(
        self,
        shop_id: str,
        incremental: bool = True,
        since_timestamp: Optional[datetime] = None,
    ):
        """
        Sync items combining ProductFeatures, CollectionFeatures
        Uses batch processing to handle large datasets efficiently with transactional integrity

        Args:
            shop_id: Shop ID to sync
            incremental: Whether to use incremental sync
            since_timestamp: Timestamp for incremental sync
        """

        async def _sync_items_operation():
            return await self._generic_batch_processor(
                shop_id=shop_id,
                batch_size=self.item_batch_size,
                fetch_batch_func=lambda shop_id, offset, limit: self._fetch_item_batch(
                    shop_id, offset, limit, since_timestamp if incremental else None
                ),
                process_batch_func=self._process_item_batch,
                entity_name="items",
            )

        # Use transaction if not already in one
        if self._is_in_transaction():
            await _sync_items_operation()
        else:
            await self._execute_with_transaction("sync_items", _sync_items_operation)

    async def _fetch_item_batch(
        self,
        shop_id: str,
        offset: int,
        limit: int,
        last_sync_timestamp: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch a batch of items with their core feature data (incremental if timestamp provided)"""
        try:
            db = await self._get_database()

            # Build incremental query if timestamp provided
            if last_sync_timestamp:
                base_query = """
                    SELECT 
                        pf.*,
                        pd."status", pd."productType", pd."vendor", pd."tags", 
                        pd."collections", pd."totalInventory", pd."compareAtPrice",
                        cf."productCount" as collection_product_count,
                        cf."performanceScore" as collection_performance_score,
                        cf."conversionRate" as collection_conversion_rate
                    FROM "ProductFeatures" pf
                    JOIN "ProductData" pd 
                        ON pf."productId" = pd."productId" AND pf."shopId" = pd."shopId"
                    LEFT JOIN "CollectionFeatures" cf
                        ON cf."shopId" = pf."shopId"
                        AND cf."collectionId" = ANY(
                            SELECT jsonb_array_elements_text(pd."collections"::jsonb)
                        )
                    WHERE pf."shopId" = $1 AND pd."isActive" = true 
                        AND pf."lastComputedAt" > $4::timestamp
                    ORDER BY pf."productId"
                    LIMIT $2 OFFSET $3
                """
                result = await db.query_raw(
                    base_query, shop_id, limit, offset, last_sync_timestamp
                )
            else:
                # Full sync query
                base_query = """
                    SELECT 
                        pf.*,
                        pd."status", pd."productType", pd."vendor", pd."tags", 
                        pd."collections", pd."totalInventory", pd."compareAtPrice",
                        cf."productCount" as collection_product_count,
                        cf."performanceScore" as collection_performance_score,
                        cf."conversionRate" as collection_conversion_rate
                    FROM "ProductFeatures" pf
                    JOIN "ProductData" pd 
                        ON pf."productId" = pd."productId" AND pf."shopId" = pd."shopId"
                    LEFT JOIN "CollectionFeatures" cf
                        ON cf."shopId" = pf."shopId"
                        AND cf."collectionId" = ANY(
                            SELECT jsonb_array_elements_text(pd."collections"::jsonb)
                        )
                    WHERE pf."shopId" = $1 AND pd."isActive" = true
                    ORDER BY pf."productId"
                    LIMIT $2 OFFSET $3
                """
                result = await db.query_raw(base_query, shop_id, limit, offset)
            batch_items = [dict(row) for row in result] if result else []

            if batch_items:
                # Fetch aggregated product pair and search data for this batch
                product_ids = [item["productId"] for item in batch_items]
                product_aggregates = await self._fetch_product_aggregates(
                    shop_id, product_ids
                )

                # Merge the aggregated data back into items
                for item in batch_items:
                    product_id = item["productId"]
                    item.update(product_aggregates.get(product_id, {}))

            return batch_items

        except Exception as e:
            logger.error(f"Failed to fetch item batch: {str(e)}")
            raise

    async def _fetch_product_aggregates(
        self, shop_id: str, product_ids: List[str]
    ) -> Dict[str, Dict]:
        """Fetch product pair and search aggregates for a batch of products"""
        if not product_ids:
            return {}

        try:
            db = await self._get_database()

            # Create parameterized queries for batch
            placeholders = ",".join([f"${i+2}" for i in range(len(product_ids))])

            # Fetch product pair features
            pair_query = f"""
                SELECT 
                    CASE WHEN "productId1" IN ({placeholders}) THEN "productId1" ELSE "productId2" END as product_id,
                    AVG("liftScore") as avg_lift_score,
                    COUNT(DISTINCT CASE 
                        WHEN "productId1" IN ({placeholders}) THEN "productId2" 
                        ELSE "productId1" END) FILTER (WHERE "coPurchaseCount" > 0) as frequently_bought_with_count
                FROM "ProductPairFeatures" 
                WHERE "shopId" = $1 
                    AND ("productId1" IN ({placeholders}) OR "productId2" IN ({placeholders}))
                GROUP BY CASE WHEN "productId1" IN ({placeholders}) THEN "productId1" ELSE "productId2" END
            """

            # Fetch search features
            search_query = f"""
                SELECT 
                    "productId",
                    AVG("clickThroughRate") as search_ctr,
                    AVG("conversionRate") as search_conversion_rate
                FROM "SearchProductFeatures" 
                WHERE "shopId" = $1 AND "productId" IN ({placeholders})
                GROUP BY "productId"
            """

            # Execute both queries concurrently
            pair_result, search_result = await asyncio.gather(
                db.query_raw(
                    pair_query,
                    shop_id,
                    *product_ids,
                    *product_ids,
                    *product_ids,
                    *product_ids,
                ),
                db.query_raw(search_query, shop_id, *product_ids),
            )

            # Combine results
            aggregates = {}

            # Add product pair data
            if pair_result:
                for row in pair_result:
                    product_id = row["product_id"]
                    aggregates[product_id] = {
                        "avg_lift_score": float(row["avg_lift_score"] or 0),
                        "frequently_bought_with_count": int(
                            row["frequently_bought_with_count"] or 0
                        ),
                    }

            # Add search data
            if search_result:
                for row in search_result:
                    product_id = row["productId"]
                    if product_id not in aggregates:
                        aggregates[product_id] = {}
                    aggregates[product_id].update(
                        {
                            "search_ctr": float(row["search_ctr"] or 0),
                            "search_conversion_rate": float(
                                row["search_conversion_rate"] or 0
                            ),
                        }
                    )

            # Fill in missing products with defaults
            for product_id in product_ids:
                if product_id not in aggregates:
                    aggregates[product_id] = {
                        "avg_lift_score": 0.0,
                        "frequently_bought_with_count": 0,
                        "search_ctr": 0.0,
                        "search_conversion_rate": 0.0,
                    }

            return aggregates

        except Exception as e:
            logger.error(f"Failed to fetch product aggregates: {str(e)}")
            return {
                product_id: {
                    "avg_lift_score": 0.0,
                    "frequently_bought_with_count": 0,
                    "search_ctr": 0.0,
                    "search_conversion_rate": 0.0,
                }
                for product_id in product_ids
            }

    async def _process_item_batch(
        self, shop_id: str, items: List[Dict[str, Any]]
    ) -> int:
        """Process a batch of items with bulk operations"""
        if not items:
            return 0

        try:
            # Prepare bulk data for Gorse items
            gorse_items_data = []

            for item in items:
                labels = self._build_comprehensive_item_labels(item)
                categories = await self._get_product_categories(item, shop_id)
                is_hidden = self._should_hide_product(item)

                item_data = {
                    "itemId": item["productId"],
                    "shopId": shop_id,
                    "categories": Json(categories),
                    "labels": Json(labels),
                    "isHidden": is_hidden,
                }
                gorse_items_data.append(item_data)

            # Bulk upsert to GorseItems table
            await self._bulk_upsert_gorse_items(gorse_items_data)

            return len(items)

        except Exception as e:
            logger.error(f"Failed to process item batch: {str(e)}")
            raise

    async def _bulk_upsert_gorse_items(self, gorse_items_data: List[Dict[str, Any]]):
        """Bulk upsert items to GorseItems table"""
        await self._generic_bulk_upsert(
            data_list=gorse_items_data,
            table_accessor=lambda db: db.gorseitems,
            id_field="itemId",
            entity_name="items",
            table_name="GorseItems",
        )

    async def sync_feedback(self, shop_id: str, since_hours: int = 24):
        """
        Sync feedback data from multiple sources to Gorse using streaming processing
        Processes behavioral events, orders, interactions, and sessions without loading all data into memory
        with transactional integrity
        """

        async def _sync_feedback_operation():
            logger.info(
                f"Starting streaming feedback sync for shop {shop_id} (last {since_hours} hours) with batch size {self.feedback_batch_size}"
            )
            since_time = now_utc() - timedelta(hours=since_hours)

            total_synced = 0

            # Create streaming generators for each feedback source
            feedback_streams = [
                self._stream_behavioral_events(shop_id, since_time),
                self._stream_orders(shop_id, since_time),
                self._stream_interaction_features(shop_id, since_time),
                self._stream_session_feedback(shop_id, since_time),
            ]

            # Process feedback streams concurrently using asyncio.gather
            # Each stream yields batches of feedback that we process immediately
            stream_tasks = [
                self._process_feedback_stream(stream) for stream in feedback_streams
            ]

            # Wait for all streams to complete and sum up the results
            stream_results = await asyncio.gather(*stream_tasks)
            total_synced = sum(stream_results)

            logger.info(
                f"Streaming sync completed: {total_synced} feedback records synced for shop {shop_id}"
            )
            return total_synced

        # Use transaction if not already in one
        if self._is_in_transaction():
            await _sync_feedback_operation()
        else:
            await self._execute_with_transaction(
                "sync_feedback", _sync_feedback_operation
            )

    async def _process_feedback_stream(self, feedback_stream) -> int:
        """
        Process a single feedback stream, yielding batches and inserting them immediately
        Returns the total number of records processed from this stream
        """
        total_synced = 0
        batch_buffer = []

        try:
            async for feedback_batch in feedback_stream:
                # Add to buffer
                batch_buffer.extend(feedback_batch)

                # Process buffer when it reaches batch size
                if len(batch_buffer) >= self.feedback_batch_size:
                    # Deduplicate the batch
                    unique_batch = self._deduplicate_feedback(batch_buffer)

                    # Insert the batch
                    batch_count = await self._bulk_insert_gorse_feedback(unique_batch)
                    total_synced += batch_count

                    logger.debug(
                        f"Processed streaming batch: {len(unique_batch)} records, total: {total_synced}"
                    )

                    # Clear buffer
                    batch_buffer = []

            # Process any remaining records in buffer
            if batch_buffer:
                unique_batch = self._deduplicate_feedback(batch_buffer)
                batch_count = await self._bulk_insert_gorse_feedback(unique_batch)
                total_synced += batch_count

                logger.debug(
                    f"Processed final streaming batch: {len(unique_batch)} records, total: {total_synced}"
                )

        except Exception as e:
            logger.error(f"Error processing feedback stream: {str(e)}")
            raise

        return total_synced

    @retry_with_exponential_backoff(max_retries=2, base_delay=1.0)
    async def _bulk_insert_gorse_feedback(
        self, feedback_batch: List[Dict[str, Any]]
    ) -> int:
        """Bulk insert feedback records to GorseFeedback table using true bulk operations"""
        if not feedback_batch:
            return 0

        try:
            db = await self._get_database()

            # Convert feedback to Gorse schema format
            gorse_feedback_data = []
            for feedback in feedback_batch:
                gorse_feedback_record = {
                    "feedbackType": feedback["feedback_type"],
                    "userId": feedback["user_id"],
                    "itemId": feedback["item_id"],
                    "timestamp": feedback["timestamp"],
                    "shopId": feedback["shop_id"],
                    "comment": feedback.get("comment"),
                }
                gorse_feedback_data.append(gorse_feedback_record)

            # Use Prisma's create_many for true bulk insert with skip_duplicates
            # This is much more efficient than individual inserts
            try:
                result = await db.gorsefeedback.create_many(
                    data=gorse_feedback_data,
                    skip_duplicates=True,  # Skip records that violate unique constraints
                )
                total_inserted = result.count
                logger.debug(
                    f"Bulk inserted {total_inserted} feedback records using create_many"
                )
                return total_inserted

            except (PrismaError, asyncio.TimeoutError, ConnectionError) as bulk_error:
                # Fallback to chunked processing if bulk insert fails
                logger.warning(
                    f"Bulk insert failed, falling back to chunked processing: {str(bulk_error)}"
                )
                return await self._fallback_chunked_feedback_insert(gorse_feedback_data)
            except Exception as bulk_error:
                # For non-transient errors, don't retry
                logger.error(f"Non-retryable error in bulk insert: {str(bulk_error)}")
                raise

        except (PrismaError, asyncio.TimeoutError, ConnectionError) as e:
            logger.error(f"Database error in bulk insert Gorse feedback: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in bulk insert Gorse feedback: {str(e)}")
            raise

    async def _fallback_chunked_feedback_insert(
        self, gorse_feedback_data: List[Dict[str, Any]]
    ) -> int:
        """Fallback method for chunked feedback insertion when bulk insert fails"""
        chunk_size = 200  # Process 200 feedback records at a time
        total_inserted = 0

        for i in range(0, len(gorse_feedback_data), chunk_size):
            chunk = gorse_feedback_data[i : i + chunk_size]

            # Use asyncio.gather for concurrent inserts within each chunk
            insert_tasks = []
            for feedback_data in chunk:
                insert_tasks.append(self._safe_insert_feedback(feedback_data))

            # Execute all inserts in this chunk concurrently
            results = await asyncio.gather(*insert_tasks, return_exceptions=True)

            # Count successful insertions
            successful_inserts = sum(1 for result in results if result is True)
            total_inserted += successful_inserts

            logger.debug(
                f"Processed feedback chunk: {successful_inserts}/{len(chunk)} inserted"
            )

        return total_inserted

    async def _safe_insert_feedback(self, feedback_data: Dict[str, Any]) -> bool:
        """Safely insert a single feedback record, handling duplicates"""
        try:
            db = await self._get_database()

            await db.gorsefeedback.create(data=feedback_data)
            return True

        except Exception as e:
            # If it's a unique constraint violation, it's likely a duplicate, so we can skip it
            error_str = str(e).lower()
            if "unique constraint" in error_str or "duplicate" in error_str:
                logger.debug(
                    f"Skipped duplicate Gorse feedback: {feedback_data['feedbackType']} "
                    f"for user {feedback_data['userId']} on item {feedback_data['itemId']}"
                )
                return False
            else:
                # Re-raise if it's not a duplicate error
                logger.error(f"Failed to insert feedback: {str(e)}")
                logger.debug(f"Problematic feedback data: {feedback_data}")
                return False

    def _build_comprehensive_user_labels(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build comprehensive Gorse user labels from all feature tables
        """
        try:
            labels = {
                # From UserFeatures
                "total_purchases": int(user.get("totalPurchases") or 0),
                "total_spent": float(user.get("totalSpent") or 0),
                "avg_order_value": float(user.get("avgOrderValue") or 0),
                "lifetime_value": float(user.get("lifetimeValue") or 0),
                "days_since_last_order": user.get("daysSinceLastOrder"),
                "order_frequency_per_month": float(
                    user.get("orderFrequencyPerMonth") or 0
                ),
                "distinct_products_purchased": int(
                    user.get("distinctProductsPurchased") or 0
                ),
                "distinct_categories_purchased": int(
                    user.get("distinctCategoriesPurchased") or 0
                ),
                "preferred_category": user.get("preferredCategory", "unknown"),
                "preferred_vendor": user.get("preferredVendor", "unknown"),
                "price_preference": user.get("pricePointPreference", "mid"),
                "discount_sensitivity": float(user.get("discountSensitivity") or 0),
                # From CustomerBehaviorFeatures
                "engagement_score": float(user.get("engagementScore") or 0),
                "recency_score": float(user.get("recencyScore") or 0),
                "diversity_score": float(user.get("diversityScore") or 0),
                "behavioral_score": float(user.get("behavioralScore") or 0),
                "session_count": int(user.get("sessionCount") or 0),
                "product_view_count": int(user.get("productViewCount") or 0),
                "cart_add_count": int(user.get("cartAddCount") or 0),
                "search_count": int(user.get("searchCount") or 0),
                "unique_products_viewed": int(user.get("uniqueProductsViewed") or 0),
                "unique_collections_viewed": int(
                    user.get("uniqueCollectionsViewed") or 0
                ),
                "browse_to_cart_rate": (
                    float(user.get("browseToCartRate", 0))
                    if user.get("browseToCartRate")
                    else 0
                ),
                "cart_to_purchase_rate": (
                    float(user.get("cartToPurchaseRate", 0))
                    if user.get("cartToPurchaseRate")
                    else 0
                ),
                "search_to_purchase_rate": (
                    float(user.get("searchToPurchaseRate", 0))
                    if user.get("searchToPurchaseRate")
                    else 0
                ),
                "most_active_hour": user.get("mostActiveHour"),
                "most_active_day": user.get("mostActiveDay"),
                "device_type": user.get("deviceType", "unknown"),
                "primary_referrer": user.get("primaryReferrer", "direct"),
                # From aggregated InteractionFeatures
                "total_interaction_score": float(
                    user.get("total_interaction_score") or 0
                ),
                "avg_affinity_score": float(user.get("avg_affinity_score") or 0),
                # From aggregated SessionFeatures
                "completed_sessions": int(user.get("completed_sessions") or 0),
                "avg_session_duration": float(user.get("avg_session_duration") or 0),
                # Computed segments
                "customer_segment": self._calculate_customer_segment(user),
                "is_active": bool((user.get("daysSinceLastOrder") or 365) < 30),
                "is_high_value": bool((user.get("lifetimeValue") or 0) > 500),
                "is_frequent_buyer": bool(
                    (user.get("orderFrequencyPerMonth") or 0) > 1
                ),
                # Optimized features for better recommendations
                "purchase_power": min(float(user.get("totalSpent") or 0) / 5000, 1.0),
                "purchase_frequency": min(
                    int(user.get("totalPurchases") or 0) / 50, 1.0
                ),
                "recency_tier": self._calculate_recency_tier(
                    user.get("daysSinceLastOrder")
                ),
                "is_active_30d": int((user.get("daysSinceLastOrder") or 999) < 30),
                "is_active_7d": int((user.get("daysSinceLastOrder") or 999) < 7),
                "engagement_level": min(
                    (
                        (user.get("productViewCount") or 0)
                        + (user.get("cartAddCount") or 0) * 3
                    )
                    / 100,
                    1.0,
                ),
                "category_diversity": min(
                    (user.get("distinctCategoriesPurchased") or 0) / 5, 1.0
                ),
                "price_tier": self._encode_price_tier(user.get("pricePointPreference")),
                "discount_affinity": min(
                    float(user.get("discountSensitivity") or 0) * 2, 1.0
                ),
                "conversion_score": self._calculate_conversion_score(user),
                "lifecycle_stage": self._encode_lifecycle_stage(user),
                "customer_value_tier": self._calculate_value_tier(
                    float(user.get("totalSpent") or 0),
                    int(user.get("totalPurchases") or 0),
                ),
            }

            # Remove None values
            return {k: v for k, v in labels.items() if v is not None}
        except Exception as e:
            logger.error(
                f"Error building user labels for user {user.get('customerId', 'unknown')}: {str(e)}"
            )
            logger.error(f"User data keys: {list(user.keys())}")
            logger.error(f"User data sample: {dict(list(user.items())[:10])}")

            raise

    def _build_comprehensive_item_labels(
        self, product: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build comprehensive Gorse item labels from all feature tables
        """
        labels = {
            # From ProductFeatures
            "view_count_30d": int(product.get("viewCount30d", 0)),
            "unique_viewers_30d": int(product.get("uniqueViewers30d", 0)),
            "cart_add_count_30d": int(product.get("cartAddCount30d", 0)),
            "purchase_count_30d": int(product.get("purchaseCount30d", 0)),
            "unique_purchasers_30d": int(product.get("uniquePurchasers30d", 0)),
            "view_to_cart_rate": (
                float(product.get("viewToCartRate", 0))
                if product.get("viewToCartRate")
                else 0
            ),
            "cart_to_purchase_rate": (
                float(product.get("cartToPurchaseRate", 0))
                if product.get("cartToPurchaseRate")
                else 0
            ),
            "overall_conversion_rate": (
                float(product.get("overallConversionRate", 0))
                if product.get("overallConversionRate")
                else 0
            ),
            "days_since_last_purchase": product.get("daysSinceLastPurchase"),
            "days_since_first_purchase": product.get("daysSinceFirstPurchase"),
            "avg_selling_price": (
                float(product.get("avgSellingPrice", 0))
                if product.get("avgSellingPrice")
                else 0
            ),
            "price_variance": (
                float(product.get("priceVariance", 0))
                if product.get("priceVariance")
                else 0
            ),
            "inventory_turnover": (
                float(product.get("inventoryTurnover", 0))
                if product.get("inventoryTurnover")
                else 0
            ),
            "stock_velocity": (
                float(product.get("stockVelocity", 0))
                if product.get("stockVelocity")
                else 0
            ),
            "price_tier": product.get("priceTier", "mid"),
            "popularity_score": float(product.get("popularityScore", 0)),
            "trending_score": float(product.get("trendingScore", 0)),
            "variant_complexity": (
                float(product.get("variantComplexity", 0))
                if product.get("variantComplexity")
                else 0
            ),
            "image_richness": (
                float(product.get("imageRichness", 0))
                if product.get("imageRichness")
                else 0
            ),
            "tag_diversity": (
                float(product.get("tagDiversity", 0))
                if product.get("tagDiversity")
                else 0
            ),
            # From ProductData
            "product_type": product.get("productType", "unknown"),
            "vendor": product.get("vendor", "unknown"),
            "in_stock": bool(product.get("totalInventory", 0) > 0),
            "has_discount": bool(
                product.get("compareAtPrice")
                and float(product.get("compareAtPrice", 0))
                > float(product.get("avgSellingPrice", 0))
            ),
            # Collection features (from CollectionFeatures table)
            "collection_count": (
                len(product.get("collections", []))
                if isinstance(product.get("collections"), list)
                else 0
            ),
            "collection_quality_score": float(
                product.get("collection_performance_score", 0.5)
            ),
            "cross_collection_score": float(
                product.get("collection_conversion_rate", 0.0)
            ),
            "is_in_manual_collections": bool(product.get("collections")),
            "is_in_automated_collections": False,  # Would need to check CollectionData.isAutomated
            # From aggregated ProductPairFeatures
            "avg_lift_score": float(product.get("avg_lift_score", 0)),
            "frequently_bought_with_count": int(
                product.get("frequently_bought_with_count", 0)
            ),
            # From aggregated SearchProductFeatures
            "search_ctr": float(product.get("search_ctr", 0)),
            "search_conversion_rate": float(product.get("search_conversion_rate", 0)),
            # Computed flags
            "is_new": bool(
                product.get("days_since_first_purchase", 365) < 30
                if product.get("days_since_first_purchase")
                else False
            ),
            "is_bestseller": bool(product.get("purchase_count_30d", 0) > 10),
            "is_trending": bool(product.get("trending_score", 0) > 0.7),
            "needs_restock": bool(
                product.get("total_inventory", 1) < 10
                and product.get("stock_velocity", 0) > 0.5
            ),
            # Optimized features for better recommendations
            "performance_score": self._calculate_performance_score(product),
            "freshness_score": self._calculate_freshness_score(product),
            "price_bucket": self._bucket_price(
                float(product.get("avgSellingPrice") or product.get("price") or 0)
            ),
            "has_discount": int(bool(product.get("compareAtPrice"))),
            "stock_level": min(int(product.get("totalInventory", 0)) / 100, 1.0),
        }

        # Add tags if available
        if product.get("tags"):
            tags = product["tags"]
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except:
                    tags = []
            if isinstance(tags, list) and tags:
                labels["tags"] = "|".join(tags[:5])  # Limit to 5 tags

        # Remove None values
        return {k: v for k, v in labels.items() if v is not None}

    async def _get_product_categories(
        self, product: Dict[str, Any], shop_id: str
    ) -> List[str]:
        """
        Get categories from collections and CollectionFeatures
        """
        categories = []

        # Get from product collections
        collections = product.get("collections", "[]")
        if isinstance(collections, str):
            try:
                collections = json.loads(collections)
            except:
                collections = []

        for collection in collections:
            if isinstance(collection, dict):
                collection_id = collection.get("id")
                if collection_id:
                    categories.append(str(collection_id))
            elif isinstance(collection, str):
                categories.append(collection)

        # Also get high-performance collections from CollectionFeatures
        db = await self._get_database()
        query = """
            SELECT "collectionId" 
            FROM "CollectionFeatures" 
            WHERE "shopId" = $1 
                AND "performanceScore" > 0.5
            LIMIT 3
        """

        result = await db.query_raw(query, shop_id)
        top_collections = [dict(row) for row in result] if result else []
        for coll in top_collections:
            if coll["collectionId"] not in categories:
                categories.append(coll["collectionId"])

        return categories

    async def _sync_anonymous_users(self, shop_id: str):
        """
        Sync anonymous session users from SessionFeatures
        """
        db = await self._get_database()
        query = """
            SELECT 
                "sessionId",
                COUNT(*) as session_count,
                AVG("durationSeconds") as avg_duration,
                SUM("productViewCount") as total_views,
                SUM("cartAddCount") as total_cart_adds,
                SUM(CASE WHEN "checkoutCompleted" THEN 1 ELSE 0 END) as purchases,
                MAX("deviceType") as device_type,
                MAX("referrerDomain") as referrer
            FROM "SessionFeatures"
            WHERE "shopId" = $1 
                AND "customerId" IS NULL
                AND "endTime" > $2::timestamp
            GROUP BY "sessionId"
        """

        since_time = now_utc() - timedelta(days=30)
        result = await db.query_raw(query, shop_id, since_time)
        sessions = [dict(row) for row in result] if result else []

        # Convert sessions to Gorse user format for bulk upsert
        gorse_users_data = []
        for session in sessions:
            user_id = f"session_{session['sessionId']}"

            labels = {
                "session_count": int(session.get("session_count") or 0),
                "avg_session_duration": float(session["avg_duration"] or 0),
                "product_view_count": int(session["total_views"] or 0),
                "cart_add_count": int(session["total_cart_adds"] or 0),
                "purchase_count": int(session["purchases"] or 0),
                "device_type": session["device_type"] or "unknown",
                "referrer": session["referrer"] or "direct",
                "is_anonymous": True,
                "customer_segment": "anonymous",
            }

            gorse_users_data.append(
                {
                    "userId": user_id,
                    "shopId": shop_id,
                    "labels": Json(labels),
                }
            )

        # Bulk upsert anonymous users
        if gorse_users_data:
            await self._bulk_upsert_gorse_users(gorse_users_data)

        return len(sessions)

    async def _process_behavioral_events(
        self, shop_id: str, since_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Process behavioral events into feedback
        """
        db = await self._get_database()
        query = """
            SELECT * FROM "BehavioralEvents" 
            WHERE "shopId" = $1 
                AND "occurredAt" >= $2::timestamp
            ORDER BY "occurredAt" ASC
        """

        result = await db.query_raw(query, shop_id, since_time)
        events = [dict(row) for row in result] if result else []

        feedback_list = []
        for event in events:
            feedback = self._convert_event_to_feedback(event)
            if feedback:
                feedback_list.extend(feedback)

        return feedback_list

    async def _stream_behavioral_events(self, shop_id: str, since_time: datetime):
        """
        Stream behavioral events in batches to avoid loading all data into memory
        """
        db = await self._get_database()
        batch_size = 1000  # Process events in smaller batches
        offset = 0

        while True:
            query = """
                SELECT * FROM "BehavioralEvents" 
                WHERE "shopId" = $1 
                    AND "occurredAt" >= $2::timestamp
                ORDER BY "occurredAt" ASC
                LIMIT $3 OFFSET $4
            """

            result = await db.query_raw(query, shop_id, since_time, batch_size, offset)
            events = [dict(row) for row in result] if result else []

            if not events:
                break  # No more events to process

            # Convert events to feedback
            feedback_batch = []
            for event in events:
                feedback = self._convert_event_to_feedback(event)
                if feedback:
                    feedback_batch.extend(feedback)

            yield feedback_batch
            offset += batch_size

    async def _process_orders(
        self, shop_id: str, since_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Process orders into purchase feedback
        """
        db = await self._get_database()
        query = """
            SELECT * FROM "OrderData" 
            WHERE "shopId" = $1 
                AND "orderDate" >= $2::timestamp
        """

        result = await db.query_raw(query, shop_id, since_time)
        orders = [dict(row) for row in result] if result else []

        feedback_list = []
        for order in orders:
            feedback = self._convert_order_to_feedback(order)
            if feedback:
                feedback_list.extend(feedback)

        return feedback_list

    async def _stream_orders(self, shop_id: str, since_time: datetime):
        """
        Stream orders in batches to avoid loading all data into memory
        """
        db = await self._get_database()
        batch_size = 500  # Process orders in smaller batches
        offset = 0

        while True:
            query = """
                SELECT * FROM "OrderData" 
                WHERE "shopId" = $1 
                    AND "orderDate" >= $2::timestamp
                ORDER BY "orderDate" ASC
                LIMIT $3 OFFSET $4
            """

            result = await db.query_raw(query, shop_id, since_time, batch_size, offset)
            orders = [dict(row) for row in result] if result else []

            if not orders:
                break  # No more orders to process

            # Convert orders to feedback
            feedback_batch = []
            for order in orders:
                feedback = self._convert_order_to_feedback(order)
                if feedback:
                    feedback_batch.extend(feedback)

            yield feedback_batch
            offset += batch_size

    async def _process_interaction_features(
        self, shop_id: str, since_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Process InteractionFeatures for weighted feedback
        """
        db = await self._get_database()
        query = """
            SELECT * FROM "InteractionFeatures" 
            WHERE "shopId" = $1 
                AND "lastComputedAt" >= $2::timestamp
                AND "interactionScore" > 0
        """

        result = await db.query_raw(query, shop_id, since_time)
        interactions = [dict(row) for row in result] if result else []

        feedback_list = []
        for interaction in interactions:
            # Create synthetic feedback based on interaction score
            if interaction["lastViewDate"]:
                feedback_list.append(
                    {
                        "feedback_type": "interaction",
                        "user_id": interaction["customerId"],
                        "item_id": interaction["productId"],
                        "timestamp": interaction["lastViewDate"],
                        "shop_id": shop_id,
                        "comment": json.dumps(
                            {
                                "weight": float(interaction["interactionScore"]),
                                "affinity": float(interaction["affinityScore"] or 0),
                            }
                        ),
                    }
                )

        return feedback_list

    async def _stream_interaction_features(self, shop_id: str, since_time: datetime):
        """
        Stream interaction features in batches to avoid loading all data into memory
        """
        db = await self._get_database()
        batch_size = 1000  # Process interactions in smaller batches
        offset = 0

        while True:
            query = """
                SELECT * FROM "InteractionFeatures" 
                WHERE "shopId" = $1 
                    AND "lastComputedAt" >= $2::timestamp
                    AND "interactionScore" > 0
                ORDER BY "lastComputedAt" ASC
                LIMIT $3 OFFSET $4
            """

            result = await db.query_raw(query, shop_id, since_time, batch_size, offset)
            interactions = [dict(row) for row in result] if result else []

            if not interactions:
                break  # No more interactions to process

            # Convert interactions to feedback
            feedback_batch = []
            for interaction in interactions:
                # Create synthetic feedback based on interaction score
                if interaction["lastViewDate"]:
                    feedback_batch.append(
                        {
                            "feedback_type": "interaction",
                            "user_id": interaction["customerId"],
                            "item_id": interaction["productId"],
                            "timestamp": interaction["lastViewDate"],
                            "shop_id": shop_id,
                            "comment": json.dumps(
                                {
                                    "weight": float(interaction["interactionScore"]),
                                    "affinity": float(
                                        interaction["affinityScore"] or 0
                                    ),
                                }
                            ),
                        }
                    )

            yield feedback_batch
            offset += batch_size

    async def _process_session_feedback(
        self, shop_id: str, since_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        Process SessionFeatures for session-based feedback
        """
        db = await self._get_database()
        query = """
            SELECT 
                sf.*,
                be."eventData"
            FROM "SessionFeatures" sf
            LEFT JOIN "BehavioralEvents" be 
                ON sf."sessionId" = be."clientId" 
                AND be."eventType" = 'product_viewed'
            WHERE sf."shopId" = $1 
                AND sf."endTime" >= $2::timestamp
                AND sf."productViewCount" > 0
        """

        result = await db.query_raw(query, shop_id, since_time)
        sessions = [dict(row) for row in result] if result else []

        feedback_list = []
        processed_sessions = set()

        for session in sessions:
            if session["sessionId"] in processed_sessions:
                continue
            processed_sessions.add(session["sessionId"])

            user_id = session["customerId"] or f"session_{session['sessionId']}"

            # Create session-level feedback if converted
            if session["checkoutCompleted"]:
                feedback_list.append(
                    {
                        "feedback_type": "session_conversion",
                        "user_id": user_id,
                        "item_id": "session_conversion",  # Special item for session conversions
                        "timestamp": session["endTime"],
                        "shop_id": shop_id,
                        "comment": json.dumps(
                            {
                                "weight": 10.0,
                                "order_value": float(session["orderValue"] or 0),
                                "duration": session["durationSeconds"],
                            }
                        ),
                    }
                )

        return feedback_list

    async def _stream_session_feedback(self, shop_id: str, since_time: datetime):
        """
        Stream session feedback in batches to avoid loading all data into memory
        """
        db = await self._get_database()
        batch_size = 500  # Process sessions in smaller batches
        offset = 0

        while True:
            query = """
                SELECT 
                    sf.*,
                    be."eventData"
                FROM "SessionFeatures" sf
                LEFT JOIN "BehavioralEvents" be 
                    ON sf."sessionId" = be."clientId" 
                    AND be."eventType" = 'product_viewed'
                WHERE sf."shopId" = $1 
                    AND sf."endTime" >= $2::timestamp
                    AND sf."productViewCount" > 0
                ORDER BY sf."endTime" ASC
                LIMIT $3 OFFSET $4
            """

            result = await db.query_raw(query, shop_id, since_time, batch_size, offset)
            sessions = [dict(row) for row in result] if result else []

            if not sessions:
                break  # No more sessions to process

            # Convert sessions to feedback
            feedback_batch = []
            processed_sessions = set()

            for session in sessions:
                if session["sessionId"] in processed_sessions:
                    continue
                processed_sessions.add(session["sessionId"])

                user_id = session["customerId"] or f"session_{session['sessionId']}"

                # Create session-level feedback if converted
                if session["checkoutCompleted"]:
                    feedback_batch.append(
                        {
                            "feedback_type": "session_conversion",
                            "user_id": user_id,
                            "item_id": "session_conversion",  # Special item for session conversions
                            "timestamp": session["endTime"],
                            "shop_id": shop_id,
                            "comment": json.dumps(
                                {
                                    "weight": 10.0,
                                    "order_value": float(session["orderValue"] or 0),
                                    "duration": session["durationSeconds"],
                                }
                            ),
                        }
                    )

            yield feedback_batch
            offset += batch_size

    def _convert_event_to_feedback(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert behavioral event to feedback"""
        feedback_list = []

        event_type = event.get("eventType", "")
        event_data = event.get("eventData", {})

        if isinstance(event_data, str):
            try:
                event_data = json.loads(event_data)
            except:
                event_data = {}

        # Determine user ID
        user_id = event.get("customerId")
        if not user_id:
            client_id = event_data.get("clientId")
            if client_id:
                user_id = f"session_{client_id}"
            else:
                return []

        # Map event types to feedback with optimized weights
        feedback_mapping = {
            "product_viewed": ("view", 1.0),
            "product_added_to_cart": ("cart_add", 5.0),  # Increased
            "collection_viewed": ("collection_view", 0.5),
            "search_submitted": ("search", 0.3),
            "checkout_started": ("checkout_start", 7.0),  # Increased
            "checkout_completed": ("purchase", 10.0),  # Maximum weight
        }

        if event_type in feedback_mapping:
            feedback_type, base_weight = feedback_mapping[event_type]

            product_id = self._extract_product_id_from_event(event_type, event_data)

            if product_id:
                # Apply time decay to weight
                timestamp = event.get("occurredAt")
                decayed_weight = base_weight * self._apply_time_decay(timestamp)

                feedback_list.append(
                    {
                        "feedback_type": feedback_type,
                        "user_id": user_id,
                        "item_id": product_id,
                        "timestamp": timestamp,
                        "shop_id": event.get("shopId"),
                        "comment": json.dumps({"weight": decayed_weight}),
                    }
                )

        return feedback_list

    def _should_hide_product(self, product: Dict[str, Any]) -> bool:
        """Determine if product should be hidden in Gorse"""
        # Hide products with low performance or out of stock
        total_inventory = product.get("totalInventory", 1)
        conversion_rate = product.get("overallConversionRate", 0)

        return not bool(total_inventory > 0) or (  # Out of stock
            conversion_rate is not None and float(conversion_rate) < 0.01
        )  # Very low conversion

    def _calculate_customer_segment(self, user: Dict[str, Any]) -> str:
        """Calculate customer segment based on user data"""
        lifetime_value = float(user.get("lifetimeValue") or 0)
        order_frequency = float(user.get("orderFrequencyPerMonth") or 0)

        if lifetime_value > 1000 and order_frequency > 2:
            return "vip"
        elif lifetime_value > 500 or order_frequency > 1:
            return "loyal"
        elif user.get("totalPurchases", 0) > 0:
            return "returning"
        else:
            return "new"

    def _extract_product_id_from_event(
        self, event_type: str, event_data: Dict[str, Any]
    ) -> str:
        """Extract product ID from event data"""
        # Different event types may store product ID in different places
        product_id = event_data.get("productId") or event_data.get("product_id")
        if not product_id and "product" in event_data:
            product_id = event_data["product"].get("id")
        return product_id

    def _convert_order_to_feedback(self, order: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert order data to feedback"""
        feedback_list = []

        try:
            # Extract user ID (prefer customerId, fallback to email)
            user_id = order.get("customerId")
            if not user_id:
                user_id = order.get("customerEmail")

            if not user_id:
                logger.warning(f"No user ID found for order {order.get('orderId')}")
                return []

            # Extract line items (JSON array of products)
            line_items = order.get("lineItems", [])
            if isinstance(line_items, str):
                try:
                    line_items = json.loads(line_items)
                except:
                    line_items = []

            if not line_items:
                logger.debug(f"No line items found for order {order.get('orderId')}")
                return []

            # Get order metadata
            order_date = order.get("orderDate")
            shop_id = order.get("shopId")
            order_id = order.get("orderId")
            total_amount = float(order.get("totalAmount", 0))

            # Process each line item to create purchase feedback
            for item in line_items:
                try:
                    # Extract product ID from line item
                    product_id = None

                    # Try different possible structures for line items
                    if isinstance(item, dict):
                        # Check for variant -> product -> id structure
                        if "variant" in item and item["variant"]:
                            variant = item["variant"]
                            if isinstance(variant, dict) and "product" in variant:
                                product = variant["product"]
                                if isinstance(product, dict):
                                    product_id = product.get("id")

                        # Fallback: check for direct product_id or productId
                        if not product_id:
                            product_id = item.get("product_id") or item.get("productId")

                        # Another fallback: check for id field
                        if not product_id:
                            product_id = item.get("id")

                    if not product_id:
                        logger.debug(f"No product ID found in line item: {item}")
                        continue

                    # Extract quantity and price for weight calculation
                    quantity = int(item.get("quantity", 1))
                    line_total = 0

                    # Try to get line item value
                    if "variant" in item and item["variant"]:
                        variant = item["variant"]
                        if isinstance(variant, dict):
                            price = float(variant.get("price", 0))
                            line_total = price * quantity

                    # Calculate weight based on purchase value and quantity
                    base_weight = 10.0  # Strong weight for purchases

                    # Bonus for high-value orders
                    if total_amount > 100:
                        base_weight *= 1.2

                    # Apply time decay
                    decayed_weight = base_weight * self._apply_time_decay(order_date)

                    # Create feedback record
                    feedback = {
                        "feedback_type": "purchase",
                        "user_id": user_id,
                        "item_id": str(product_id),
                        "timestamp": order_date,
                        "shop_id": shop_id,
                        "comment": json.dumps(
                            {
                                "weight": decayed_weight,
                                "order_id": order_id,
                                "quantity": quantity,
                                "line_total": line_total,
                                "total_order_value": total_amount,
                            }
                        ),
                    }

                    feedback_list.append(feedback)

                except Exception as item_error:
                    logger.error(f"Failed to process line item: {str(item_error)}")
                    logger.debug(f"Problematic line item: {item}")
                    continue

            if feedback_list:
                logger.debug(
                    f"Created {len(feedback_list)} purchase feedback records from order {order_id}"
                )

            return feedback_list

        except Exception as e:
            logger.error(f"Failed to convert order to feedback: {str(e)}")
            logger.debug(f"Order data: {order}")
            return []

    def _deduplicate_feedback(
        self, feedback_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Remove duplicate feedback entries"""
        seen = set()
        unique_feedback = []

        for feedback in feedback_list:
            key = (
                feedback.get("user_id"),
                feedback.get("item_id"),
                feedback.get("feedback_type"),
                feedback.get("timestamp"),
            )
            if key not in seen:
                seen.add(key)
                unique_feedback.append(feedback)

        return unique_feedback

    # === Optimization Methods ===

    def _calculate_recency_tier(self, days_since_last: Optional[int]) -> int:
        """Calculate recency tier (0-4)"""
        if days_since_last is None:
            return 0
        if days_since_last < 7:
            return 4
        elif days_since_last < 30:
            return 3
        elif days_since_last < 90:
            return 2
        elif days_since_last < 180:
            return 1
        else:
            return 0

    def _encode_price_tier(self, price_pref: Optional[str]) -> int:
        """Encode price tier as number"""
        tiers = {"budget": 0, "mid": 1, "premium": 2, "luxury": 3}
        return tiers.get(price_pref, 1)

    def _calculate_conversion_score(self, user: Dict[str, Any]) -> float:
        """Calculate user's conversion propensity"""
        browse_to_cart = float(user.get("browseToCartRate") or 0)
        cart_to_purchase = float(user.get("cartToPurchaseRate") or 0)

        # Weight purchase conversion higher
        return min(browse_to_cart * 0.3 + cart_to_purchase * 0.7, 1.0)

    def _encode_lifecycle_stage(self, user: Dict[str, Any]) -> int:
        """Encode customer lifecycle stage"""
        total_spent = float(user.get("totalSpent") or 0)
        days_since_last = user.get("daysSinceLastOrder") or 999
        frequency = float(user.get("orderFrequencyPerMonth") or 0)

        if total_spent > 1000 and days_since_last < 30:
            return 5  # Champions
        elif frequency > 1 and days_since_last < 60:
            return 4  # Loyal
        elif total_spent > 100 and days_since_last < 90:
            return 3  # Potential
        elif days_since_last < 180:
            return 2  # At risk
        elif total_spent > 0:
            return 1  # Lost
        else:
            return 0  # New

    def _calculate_value_tier(self, total_spent: float, total_purchases: int) -> int:
        """Calculate customer value tier"""
        if total_spent > 2000 or total_purchases > 20:
            return 3  # High value
        elif total_spent > 500 or total_purchases > 5:
            return 2  # Medium value
        elif total_spent > 0:
            return 1  # Low value
        else:
            return 0  # No value yet

    def _calculate_performance_score(self, product: Dict[str, Any]) -> float:
        """Calculate unified product performance score"""
        views = int(product.get("viewCount30d", 0))
        purchases = int(product.get("purchaseCount30d", 0))
        conversion = float(product.get("overallConversionRate") or 0)

        # Log scale for views, linear for purchases
        view_score = min(math.log10(views + 1) / 3, 1.0) if views > 0 else 0
        purchase_score = min(purchases / 20, 1.0)

        # Weighted combination
        return view_score * 0.2 + purchase_score * 0.5 + conversion * 30

    def _calculate_freshness_score(self, product: Dict[str, Any]) -> float:
        """Calculate product freshness with decay"""
        days_since = product.get("daysSinceFirstPurchase")
        if not days_since:
            return 1.0

        # Exponential decay over 90 days
        return max(0, 1.0 - (days_since / 90) ** 2)

    def _bucket_price(self, price: float) -> int:
        """Bucket price into categories"""
        if price < 25:
            return 0
        elif price < 75:
            return 1
        elif price < 150:
            return 2
        elif price < 300:
            return 3
        else:
            return 4

    def _apply_time_decay(self, timestamp: Any) -> float:
        """Apply time decay to feedback weight"""
        if not timestamp:
            return 1.0

        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except:
                return 1.0

        days_old = (now_utc() - timestamp).days

        # Exponential decay with 30-day half-life
        return 0.5 ** (days_old / 30)

    def _extract_simple_categories(self, product: Dict[str, Any]) -> List[str]:
        """Extract simplified categories"""
        categories = []

        # Just use product type as main category
        if product.get("productType"):
            categories.append(str(product["productType"]))

        # Add collections if available
        collections = product.get("collections", [])
        if isinstance(collections, str):
            try:
                collections = json.loads(collections)
            except:
                collections = []

        # Limit to 3 categories
        for coll in collections[:2]:
            if isinstance(coll, dict) and coll.get("id"):
                categories.append(str(coll["id"]))

        return categories


async def run_gorse_sync(
    shop_id: str,
    batch_size: int = 1000,
    user_batch_size: int = 500,
    item_batch_size: int = 500,
):
    """
    Main entry point to run Gorse synchronization with configurable batch sizes
    """
    pipeline = GorseSyncPipeline(
        batch_size=batch_size,
        user_batch_size=user_batch_size,
        item_batch_size=item_batch_size,
    )
    await pipeline.sync_all(shop_id)
