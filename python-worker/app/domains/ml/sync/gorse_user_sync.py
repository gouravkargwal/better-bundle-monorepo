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

        # Use transaction if not already in one
        if self.pipeline.core._is_in_transaction():
            await _sync_users_operation()
        else:
            await self.pipeline.core._execute_with_transaction(
                "sync_users", _sync_users_operation
            )

    async def _fetch_user_batch(
        self,
        shop_id: str,
        offset: int,
        limit: int,
        last_sync_timestamp: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch a batch of users with all their feature data (incremental if timestamp provided)"""
        try:
            db = await self.pipeline._get_database()

            # Build incremental query if timestamp provided
            if last_sync_timestamp:
                base_query = """
                        SELECT 
                            COALESCE(uf."customerId", cbf."customerId") as "customerId",
                            uf.*,
                            cbf."engagementScore", cbf."recencyScore", cbf."diversityScore", cbf."behavioralScore",
                            cbf."sessionCount", cbf."productViewCount", cbf."cartAddCount",
                            cbf."searchCount", cbf."uniqueProductsViewed", cbf."uniqueCollectionsViewed",
                            cbf."deviceType", cbf."primaryReferrer", cbf."browseToCartRate", 
                            cbf."cartToPurchaseRate", cbf."searchToPurchaseRate", cbf."mostActiveHour", cbf."mostActiveDay"
                        FROM "UserFeatures" uf
                        FULL OUTER JOIN "CustomerBehaviorFeatures" cbf 
                            ON uf."customerId" = cbf."customerId" AND uf."shopId" = cbf."shopId"
                        WHERE COALESCE(uf."shopId", cbf."shopId") = $1
                            AND (uf."lastComputedAt" > $4::timestamp OR cbf."lastComputedAt" > $4::timestamp)
                        ORDER BY "customerId"
                        LIMIT $2 OFFSET $3
                    """
                result = await db.query_raw(
                    base_query, shop_id, limit, offset, last_sync_timestamp
                )
            else:
                # Full sync query
                base_query = """
                        SELECT 
                            COALESCE(uf."customerId", cbf."customerId") as "customerId",
                            uf.*,
                            cbf."engagementScore", cbf."recencyScore", cbf."diversityScore", cbf."behavioralScore",
                            cbf."sessionCount", cbf."productViewCount", cbf."cartAddCount",
                            cbf."searchCount", cbf."uniqueProductsViewed", cbf."uniqueCollectionsViewed",
                            cbf."deviceType", cbf."primaryReferrer", cbf."browseToCartRate", 
                            cbf."cartToPurchaseRate", cbf."searchToPurchaseRate", cbf."mostActiveHour", cbf."mostActiveDay"
                        FROM "UserFeatures" uf
                        FULL OUTER JOIN "CustomerBehaviorFeatures" cbf 
                            ON uf."customerId" = cbf."customerId" AND uf."shopId" = cbf."shopId"
                        WHERE COALESCE(uf."shopId", cbf."shopId") = $1
                        ORDER BY "customerId"
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
            db = await self.pipeline._get_database()

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
