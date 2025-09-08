"""
User synchronization logic for Gorse pipeline
Handles user data fetching, processing, and syncing
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from app.core.logging import get_logger
from app.shared.helpers import now_utc
from prisma import Json

logger = get_logger(__name__)


class GorseUserSync:
    """User synchronization operations"""

    def __init__(self, pipeline):
        self.pipeline = pipeline

    def _get_prefixed_user_id(self, user_id: str, shop_id: str) -> str:
        """
        Generate shop-prefixed user ID for multi-tenancy
        Format: shop_{shop_id}_{user_id}
        """
        if not shop_id:
            return user_id
        return f"shop_{shop_id}_{user_id}"

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
            return await self.pipeline.core._generic_batch_processor(
                shop_id=shop_id,
                batch_size=self.pipeline.user_batch_size,
                fetch_batch_func=lambda shop_id, offset, limit: self._fetch_user_batch(
                    shop_id, offset, limit, since_timestamp if incremental else None
                ),
                process_batch_func=self._process_user_batch,
                entity_name="users",
                additional_processor=self._sync_anonymous_users,
            )

        # For full sync, don't use transactions to avoid timeout issues
        # For incremental sync, use transactions for consistency
        if incremental:
            # Use transaction if not already in one
            if self.pipeline.core._is_in_transaction():
                await _sync_users_operation()
            else:
                await self.pipeline.core._execute_with_transaction(
                    "sync_users", _sync_users_operation
                )
        else:
            # Full sync without transaction to avoid timeout
            await _sync_users_operation()

    async def _fetch_user_batch(
        self,
        shop_id: str,
        offset: int,
        limit: int,
        last_sync_timestamp: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch a batch of users with their features - robust approach handling missing data"""
        try:
            db = await self.pipeline._get_database()

            # Step 1: Get core user data from UserFeatures (what definitely exists)
            core_users = await self._fetch_core_users(
                shop_id, limit, offset, last_sync_timestamp
            )

            if not core_users:
                logger.info(f"No core users found for shop {shop_id}")
                return []

            # Step 2: Get customer behavior data (if exists)
            behavior_data = await self._fetch_behavior_data(
                shop_id, core_users, last_sync_timestamp
            )

            # Step 3: Get session data (if exists)
            session_data = await self._fetch_session_data(
                shop_id, core_users, last_sync_timestamp
            )

            # Step 4: Get interaction data (if exists)
            interaction_data = await self._fetch_interaction_data(
                shop_id, core_users, last_sync_timestamp
            )

            # Step 5: Merge all data safely
            enriched_users = []
            for user in core_users:
                customer_id = user.get("customerId")
                if not customer_id:
                    continue

                # Start with core user data
                enriched_user = dict(user)

                # Add behavior data if available
                if customer_id in behavior_data:
                    enriched_user.update(behavior_data[customer_id])

                # Add session data if available
                if customer_id in session_data:
                    enriched_user.update(session_data[customer_id])

                # Add interaction data if available
                if customer_id in interaction_data:
                    enriched_user.update(interaction_data[customer_id])

                enriched_users.append(enriched_user)

            logger.info(
                f"Enriched {len(enriched_users)} users with available feature data"
            )
            return enriched_users

        except Exception as e:
            logger.error(f"Failed to fetch user batch: {str(e)}")
            raise

    async def _fetch_core_users(
        self,
        shop_id: str,
        limit: int,
        offset: int,
        last_sync_timestamp: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch core user data from UserFeatures - this is what definitely exists"""
        try:
            db = await self.pipeline._get_database()

            if last_sync_timestamp:
                users = await db.userfeatures.find_many(
                    where={
                        "shopId": shop_id,
                        "lastComputedAt": {"gte": last_sync_timestamp},
                    },
                    order={"customerId": "asc"},
                    skip=offset,
                    take=limit,
                )
            else:
                users = await db.userfeatures.find_many(
                    where={"shopId": shop_id},
                    order={"customerId": "asc"},
                    skip=offset,
                    take=limit,
                )

            return [user.model_dump() for user in users]

        except Exception as e:
            logger.error(f"Failed to fetch core users: {str(e)}")
            return []

    async def _fetch_behavior_data(
        self,
        shop_id: str,
        core_users: List[Dict],
        last_sync_timestamp: Optional[datetime] = None,
    ) -> Dict[str, Dict]:
        """Fetch customer behavior data if it exists"""
        try:
            if not core_users:
                return {}

            db = await self.pipeline._get_database()
            customer_ids = [
                user["customerId"] for user in core_users if user.get("customerId")
            ]

            if not customer_ids:
                return {}

            if last_sync_timestamp:
                behavior_features = await db.customerbehaviorfeatures.find_many(
                    where={
                        "shopId": shop_id,
                        "customerId": {"in": customer_ids},
                        "lastComputedAt": {"gte": last_sync_timestamp},
                    }
                )
            else:
                behavior_features = await db.customerbehaviorfeatures.find_many(
                    where={"shopId": shop_id, "customerId": {"in": customer_ids}}
                )

            return {bf.customerId: bf.model_dump() for bf in behavior_features}

        except Exception as e:
            logger.warning(f"Failed to fetch behavior data: {str(e)}")
            return {}

    async def _fetch_session_data(
        self,
        shop_id: str,
        core_users: List[Dict],
        last_sync_timestamp: Optional[datetime] = None,
    ) -> Dict[str, Dict]:
        """Fetch session data if it exists"""
        try:
            if not core_users:
                return {}

            db = await self.pipeline._get_database()
            customer_ids = [
                user["customerId"] for user in core_users if user.get("customerId")
            ]

            if not customer_ids:
                return {}

            if last_sync_timestamp:
                session_features = await db.sessionfeatures.find_many(
                    where={
                        "shopId": shop_id,
                        "customerId": {"in": customer_ids},
                        "lastComputedAt": {"gte": last_sync_timestamp},
                    }
                )
            else:
                session_features = await db.sessionfeatures.find_many(
                    where={"shopId": shop_id, "customerId": {"in": customer_ids}}
                )

            return {sf.customerId: sf.model_dump() for sf in session_features}

        except Exception as e:
            logger.warning(f"Failed to fetch session data: {str(e)}")
            return {}

    async def _fetch_interaction_data(
        self,
        shop_id: str,
        core_users: List[Dict],
        last_sync_timestamp: Optional[datetime] = None,
    ) -> Dict[str, Dict]:
        """Fetch interaction data if it exists"""
        try:
            if not core_users:
                return {}

            db = await self.pipeline._get_database()
            customer_ids = [
                user["customerId"] for user in core_users if user.get("customerId")
            ]

            if not customer_ids:
                return {}

            # For aggregation, we need to use raw SQL as Prisma doesn't support complex aggregations
            if last_sync_timestamp:
                query = """
                    SELECT 
                        "customerId",
                        COUNT("productId") as "totalInteractions",
                        SUM("viewCount") as "totalProductViews",
                        SUM("cartAddCount") as "totalCartAdds",
                        SUM("purchaseCount") as "totalPurchases",
                        AVG("interactionScore") as "avgInteractionScore",
                        AVG("affinityScore") as "avgAffinityScore"
                    FROM "InteractionFeatures" 
                    WHERE "shopId" = $1 AND "customerId" = ANY($2) AND "lastComputedAt" >= $3::timestamp
                    GROUP BY "customerId"
                """
                result = await db.query_raw(
                    query, shop_id, customer_ids, last_sync_timestamp
                )
            else:
                query = """
                    SELECT 
                        "customerId",
                        COUNT("productId") as "totalInteractions",
                        SUM("viewCount") as "totalProductViews",
                        SUM("cartAddCount") as "totalCartAdds",
                        SUM("purchaseCount") as "totalPurchases",
                        AVG("interactionScore") as "avgInteractionScore",
                        AVG("affinityScore") as "avgAffinityScore"
                    FROM "InteractionFeatures" 
                    WHERE "shopId" = $1 AND "customerId" = ANY($2)
                    GROUP BY "customerId"
                """
                result = await db.query_raw(query, shop_id, customer_ids)

            return {row["customerId"]: dict(row) for row in result} if result else {}

        except Exception as e:
            logger.warning(f"Failed to fetch interaction data: {str(e)}")
            return {}

    async def _fetch_interaction_aggregates(
        self, shop_id: str, user_ids: List[str]
    ) -> Dict[str, Dict]:
        """Fetch interaction aggregates for a batch of users"""
        if not user_ids:
            return {}

        try:
            db = await self.pipeline._get_database()

            # Filter out None values and ensure all are strings
            valid_user_ids = [str(uid) for uid in user_ids if uid is not None]

            if not valid_user_ids:
                return {}

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

            result = await db.query_raw(query, shop_id, valid_user_ids)

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
            db = await self.pipeline._get_database()

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
                labels = self.pipeline.transformers._build_comprehensive_user_labels(
                    user
                )
                # Use prefixed user ID for multi-tenancy
                prefixed_user_id = self._get_prefixed_user_id(
                    user["customerId"], shop_id
                )
                user_data = {
                    "userId": prefixed_user_id,
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
        await self.pipeline._generic_bulk_upsert(
            data_list=gorse_users_data,
            table_accessor=lambda db: db.gorseusers,
            id_field="userId",
            entity_name="users",
            table_name="gorse_users",
        )

    async def _sync_anonymous_users(self, shop_id: str):
        """
        Sync anonymous session users from SessionFeatures
        """
        db = await self.pipeline._get_database()
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
            # Use prefixed user ID for multi-tenancy
            base_user_id = f"session_{session['sessionId']}"
            prefixed_user_id = self._get_prefixed_user_id(base_user_id, shop_id)

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
                    "userId": prefixed_user_id,
                    "shopId": shop_id,
                    "labels": Json(labels),
                }
            )

        # Bulk upsert anonymous users
        if gorse_users_data:
            await self._bulk_upsert_gorse_users(gorse_users_data)

        return len(sessions)
