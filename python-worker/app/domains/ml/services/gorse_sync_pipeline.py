"""
Optimized Gorse Data Synchronization Pipeline
Designed to achieve 70% of big recommendation engine performance
Uses ALL feature tables to build comprehensive user and item profiles
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from app.core.database.simple_db_client import get_database
from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.shared.decorators import retry_with_exponential_backoff
from prisma.errors import PrismaError, UniqueViolationError
from app.domains.ml.sync.gorse_sync_core import GorseSyncCore
from app.domains.ml.sync.gorse_user_sync import GorseUserSync
from app.domains.ml.sync.gorse_item_sync import GorseItemSync
from app.domains.ml.sync.gorse_feedback_sync import GorseFeedbackSync
from app.domains.ml.transformers.gorse_data_transformers import GorseDataTransformers

logger = get_logger(__name__)


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

        self.core = GorseSyncCore(self)
        self.user_sync = GorseUserSync(self)
        self.item_sync = GorseItemSync(self)
        self.feedback_sync = GorseFeedbackSync(self)
        self.transformers = GorseDataTransformers(self)

    async def sync_all(self, shop_id: str, incremental: bool = True):
        """Main entry point - delegates to core sync module"""
        return await self.core.sync_all(shop_id, incremental)

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
