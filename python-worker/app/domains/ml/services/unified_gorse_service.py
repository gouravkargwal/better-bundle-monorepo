"""
Unified Gorse Service
Combines data sync and training into one service that directly pushes to Gorse API
This eliminates the need for bridge tables and ensures training is always triggered
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from app.core.database.session import get_session_context
from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.shared.gorse_api_client import GorseApiClient
from app.domains.ml.transformers.gorse_data_transformers import GorseDataTransformers
from sqlalchemy import select, func
from app.core.database.models import (
    UserFeatures,
    ProductFeatures,
    InteractionFeatures,
    SessionFeatures,
    ProductPairFeatures,
    SearchProductFeatures,
    CollectionFeatures,
    CustomerBehaviorFeatures,
    ProductData,
    CustomerData,
    CollectionData,
    UserSession,
    UserInteraction,
    PurchaseAttribution,
    PipelineWatermark,
)

logger = get_logger(__name__)


class UnifiedGorseService:
    """
    Unified service that syncs data from feature tables directly to Gorse API
    This automatically triggers training and eliminates the need for bridge tables
    """

    def __init__(
        self,
        gorse_base_url: str = "http://localhost:8088",
        gorse_api_key: str = "secure_random_key_123",
        batch_size: int = 500,
    ):
        """
        Initialize the unified Gorse service

        Args:
            gorse_base_url: Gorse master server URL
            gorse_api_key: API key for Gorse authentication
            batch_size: Batch size for API calls
        """
        self.gorse_client = GorseApiClient(gorse_base_url, gorse_api_key)
        self.transformers = GorseDataTransformers()
        self.batch_size = batch_size

    def _ensure_aware_utc(self, dt: Optional[datetime]) -> Optional[datetime]:
        """Normalize a datetime to timezone-aware UTC to avoid naive/aware comparison errors."""
        if dt is None:
            return None
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    async def _check_feature_table_has_data(
        self, table_name: str, shop_id: str, since_time: Optional[datetime] = None
    ) -> bool:
        """Check if a feature table has data for the given shop and time range (SQLAlchemy)."""
        try:
            model_map = {
                "user_features": UserFeatures,
                "product_features": ProductFeatures,
                "interaction_features": InteractionFeatures,
                "session_features": SessionFeatures,
                "product_pair_features": ProductPairFeatures,
                "search_product_features": SearchProductFeatures,
                "collection_features": CollectionFeatures,
                "customer_behavior_features": CustomerBehaviorFeatures,
            }

            model = model_map.get(table_name)
            if model is None:
                logger.warning(f"Table {table_name} not found in SQLAlchemy models")
                return False

            async with get_session_context() as session:
                where_clauses = [model.shop_id == shop_id]
                if hasattr(model, "last_computed_at") and since_time is not None:
                    where_clauses.append(model.last_computed_at >= since_time)

                stmt = select(func.count()).select_from(model).where(*where_clauses)
                count = (await session.execute(stmt)).scalar_one()
                has_data = (count or 0) > 0
                logger.info(
                    f"Table {table_name} has {count or 0} records for shop {shop_id}"
                )
                return has_data

        except Exception as e:
            logger.error(
                f"Failed to check data in table {table_name} for shop {shop_id}: {str(e)}"
            )
            return False

    async def _get_last_sync_timestamp(self, shop_id: str) -> Optional[datetime]:
        """Get the last sync timestamp from PipelineWatermark table (consistent with other services)"""
        try:
            async with get_session_context() as session:
                # Get the latest Gorse sync timestamp from PipelineWatermark
                # Use first() instead of scalar_one_or_none() to handle multiple records
                result = await session.execute(
                    select(PipelineWatermark.last_gorse_synced_at)
                    .where(PipelineWatermark.shop_id == shop_id)
                    .where(PipelineWatermark.data_type == "gorse_sync")
                    .order_by(PipelineWatermark.last_gorse_synced_at.desc())
                )
                last_sync = result.scalar_one_or_none()

                if last_sync:
                    # Normalize to timezone-aware UTC to prevent comparison errors
                    last_sync = self._ensure_aware_utc(last_sync)
                    logger.info(f"Found last Gorse sync timestamp: {last_sync}")
                    return last_sync
                else:
                    logger.info("No previous Gorse sync found, using 24 hours ago")
                    return now_utc() - timedelta(hours=24)

        except Exception as e:
            logger.error(
                f"Failed to get last Gorse sync timestamp for shop {shop_id}: {str(e)}"
            )
            return now_utc() - timedelta(hours=24)

    async def _update_gorse_watermark(self, shop_id: str, sync_timestamp: datetime):
        """Update the Gorse sync watermark in PipelineWatermark table (consistent with other services)"""
        try:
            async with get_session_context() as session:
                # Find existing watermark or create new one
                result = await session.execute(
                    select(PipelineWatermark)
                    .where(PipelineWatermark.shop_id == shop_id)
                    .where(PipelineWatermark.data_type == "gorse_sync")
                )
                watermark = result.scalar_one_or_none()

                if watermark:
                    # Update existing watermark
                    watermark.last_gorse_synced_at = sync_timestamp
                    watermark.updated_at = now_utc()
                else:
                    # Create new watermark
                    watermark = PipelineWatermark(
                        shop_id=shop_id,
                        data_type="gorse_sync",
                        last_gorse_synced_at=sync_timestamp,
                        status="completed",
                    )
                    session.add(watermark)

                await session.commit()
                logger.info(f"Updated Gorse sync watermark: {sync_timestamp}")

        except Exception as e:
            logger.error(f"Failed to update Gorse sync watermark: {str(e)}")

    def _get_full_sync_tasks(self, shop_id: str) -> List[tuple]:
        """Get all sync tasks for full sync - only essential Gorse data"""
        return [
            ("users", self._sync_users_to_gorse(shop_id)),
            ("items", self._sync_items_to_gorse(shop_id)),
            ("feedback", self._sync_feedback_to_gorse(shop_id)),
        ]

    async def sync_and_train(self, shop_id: str) -> Dict[str, Any]:
        """
        Unified sync: Process all available data for a shop and sync to Gorse

        Args:
            shop_id: Shop ID to sync data for

        Returns:
            Dict with sync results and training status
        """
        start_time = now_utc()
        job_id = f"unified_sync_{shop_id}_{int(time.time())}"

        logger.info(f"🚀 Starting full sync for shop {shop_id}")

        try:
            results = {
                "job_id": job_id,
                "shop_id": shop_id,
                "start_time": start_time,
                "users_synced": 0,
                "items_synced": 0,
                "feedback_synced": 0,
                "training_triggered": False,
                "errors": [],
            }

            # Get all sync tasks for full sync
            sync_tasks = self._get_full_sync_tasks(shop_id)

            # Execute all sync tasks in parallel
            task_names, task_coroutines = zip(*sync_tasks)
            sync_results = await asyncio.gather(
                *task_coroutines, return_exceptions=True
            )

            # Process results
            for task_name, result in zip(task_names, sync_results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to sync {task_name}: {str(result)}")
                    results[f"{task_name}_synced"] = 0
                    results["errors"].append(f"{task_name}_sync_failed: {str(result)}")
                else:
                    results[f"{task_name}_synced"] = result
                    logger.info(f"Synced {result} {task_name} to Gorse")

            # Training is automatically triggered by Gorse API calls
            results["training_triggered"] = True
            results["end_time"] = now_utc()
            results["duration_seconds"] = (
                results["end_time"] - start_time
            ).total_seconds()

            logger.info(f"Unified sync completed for shop {shop_id}: {results}")
            return results

        except Exception as e:
            logger.error(f"Unified sync failed for shop {shop_id}: {str(e)}")
            results["errors"].append(str(e))
            results["end_time"] = now_utc()
            results["duration_seconds"] = (
                results["end_time"] - start_time
            ).total_seconds()
            return results

    async def _sync_users_to_gorse(self, shop_id: str) -> int:
        """Sync users from feature tables directly to Gorse API"""
        try:
            total_synced = 0
            offset = 0
            async with get_session_context() as session:
                while True:
                    stmt = (
                        select(UserFeatures)
                        .where(UserFeatures.shop_id == shop_id)
                        .order_by(UserFeatures.last_computed_at.asc())
                        .offset(offset)
                        .limit(self.batch_size)
                    )
                    result = await session.execute(stmt)
                    users = result.scalars().all()

                    if not users:
                        break

                    # Transform to Gorse format
                    gorse_users = []
                    for user in users:
                        prefixed_user_id = (
                            f"shop_{shop_id}_{getattr(user, 'customer_id', '')}"
                        )
                        labels = self.transformers.transform_user_features_to_labels(
                            user
                        )
                        gorse_users.append(
                            {"userId": prefixed_user_id, "labels": labels}
                        )

                    # Push to Gorse API
                    if gorse_users:
                        await self.gorse_client.insert_users_batch(gorse_users)
                        total_synced += len(gorse_users)
                        logger.info(
                            f"Synced {len(gorse_users)} users (total: {total_synced})"
                        )

                    if len(users) < self.batch_size:
                        break

                    offset += self.batch_size

            return total_synced

        except Exception as e:
            logger.error(f"Failed to sync users for shop {shop_id}: {str(e)}")
            return 0

    async def _sync_items_to_gorse(self, shop_id: str) -> int:
        """Sync items from feature tables directly to Gorse API"""
        try:
            total_synced = 0
            offset = 0
            async with get_session_context() as session:
                while True:
                    stmt = (
                        select(ProductFeatures)
                        .where(ProductFeatures.shop_id == shop_id)
                        .order_by(ProductFeatures.last_computed_at.asc())
                        .offset(offset)
                        .limit(self.batch_size)
                    )
                    result = await session.execute(stmt)
                    products = result.scalars().all()

                    if not products:
                        break

                    product_ids = [
                        p.product_id for p in products if getattr(p, "product_id", None)
                    ]
                    if product_ids:
                        pd_stmt = select(ProductData).where(
                            ProductData.shop_id == shop_id,
                            ProductData.product_id.in_(product_ids),
                        )
                        pd_res = await session.execute(pd_stmt)
                        product_data = pd_res.scalars().all()
                        product_data_map = {
                            p.product_id: (p.__dict__ if hasattr(p, "__dict__") else p)
                            for p in product_data
                        }
                    else:
                        product_data_map = {}

                    gorse_items = await self._process_items_batch_parallel(
                        products, product_data_map, shop_id
                    )

                    if gorse_items:
                        await self.gorse_client.insert_items_batch(gorse_items)
                        total_synced += len(gorse_items)
                        logger.info(
                            f"Synced {len(gorse_items)} items (total: {total_synced})"
                        )

                    if len(products) < self.batch_size:
                        break

                    offset += self.batch_size

            return total_synced

        except Exception as e:
            logger.error(f"Failed to sync items for shop {shop_id}: {str(e)}")
            return 0

    async def _process_items_batch_parallel(
        self, products: List, product_data_map: Dict, shop_id: str
    ) -> List[Dict[str, Any]]:
        """Process a batch of items in parallel for better performance"""
        try:
            # Create tasks for parallel processing
            tasks = []
            for product in products:
                task = self._process_single_item(product, product_data_map, shop_id)
                tasks.append(task)

            # Execute all tasks in parallel
            gorse_items = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions and return valid items
            valid_items = []
            for item in gorse_items:
                if isinstance(item, dict):
                    valid_items.append(item)
                elif isinstance(item, Exception):
                    logger.error(f"Error processing item: {str(item)}")

            return valid_items

        except Exception as e:
            logger.error(f"Failed to process items batch in parallel: {str(e)}")
            return []

    async def _process_single_item(
        self, product, product_data_map: Dict, shop_id: str
    ) -> Dict[str, Any]:
        """Process a single item (can be run in parallel)"""
        try:
            # Validate product ID
            pid = getattr(product, "product_id", None)
            if not pid or str(pid).strip() == "":
                logger.error(
                    f"Product has empty or None product_id: {pid} | Product: {product}"
                )
                raise ValueError(f"Product has empty or None product_id: {pid}")

            # Apply shop prefix for multi-tenancy
            prefixed_item_id = f"shop_{shop_id}_{pid}"

            # Validate the constructed item ID
            if (
                not prefixed_item_id
                or prefixed_item_id == f"shop_{shop_id}_"
                or prefixed_item_id == f"shop_{shop_id}_None"
            ):
                logger.error(
                    f"Constructed empty item ID: '{prefixed_item_id}' for product: {pid}"
                )
                raise ValueError(f"Constructed empty item ID: '{prefixed_item_id}'")

            # Get product data
            product_info = product_data_map.get(pid, {})

            # Transform product features to Gorse labels
            labels = self.transformers.transform_product_features_to_labels(
                product, product_info
            )

            # Get categories (this could be cached for better performance)
            categories = await self._get_product_categories(pid, shop_id)

            return {
                "itemId": prefixed_item_id,
                "labels": labels,
                "categories": categories,
                "isHidden": self._should_hide_product(product),
            }

        except Exception as e:
            logger.error(f"Failed to process item {pid}: {str(e)}")
            raise e

    async def _sync_feedback_to_gorse(self, shop_id: str) -> int:
        """Sync feedback from interaction features (which contain user-item interactions)"""
        try:
            total_synced = 0
            offset = 0
            async with get_session_context() as session:
                while True:
                    stmt = (
                        select(InteractionFeatures)
                        .where(InteractionFeatures.shop_id == shop_id)
                        .order_by(InteractionFeatures.last_computed_at.asc())
                        .offset(offset)
                        .limit(self.batch_size)
                    )
                    result = await session.execute(stmt)
                    interactions = result.scalars().all()

                    logger.info(
                        f"🔍 GORSE SYNC: Found {len(interactions)} interaction features for shop {shop_id}"
                    )

                    if not interactions:
                        break

                    # Convert interaction features to feedback
                    feedback_batch = []
                    for interaction in interactions:
                        # Create multiple feedback records based on actual interaction counts
                        base_timestamp = (
                            getattr(interaction, "last_computed_at", None) or now_utc()
                        )

                        # Create view feedback records (one for each view)
                        for i in range(getattr(interaction, "view_count", 0)):
                            timestamp_offset = timedelta(microseconds=i * 1000)
                            feedback_batch.append(
                                {
                                    "feedbackType": "view",
                                    "userId": f"shop_{shop_id}_{getattr(interaction, 'customer_id', '')}",
                                    "itemId": f"shop_{shop_id}_{getattr(interaction, 'product_id', '')}",
                                    "timestamp": (
                                        base_timestamp + timestamp_offset
                                    ).isoformat(),
                                }
                            )

                        # Create cart_add feedback records (one for each cart add)
                        for i in range(getattr(interaction, "cart_add_count", 0)):
                            timestamp_offset = timedelta(
                                microseconds=(i + getattr(interaction, "view_count", 0))
                                * 1000
                            )
                            feedback_batch.append(
                                {
                                    "feedbackType": "cart_add",
                                    "userId": f"shop_{shop_id}_{getattr(interaction, 'customer_id', '')}",
                                    "itemId": f"shop_{shop_id}_{getattr(interaction, 'product_id', '')}",
                                    "timestamp": (
                                        base_timestamp + timestamp_offset
                                    ).isoformat(),
                                }
                            )

                        # Create cart_view feedback records (one for each cart view)
                        for i in range(getattr(interaction, "cart_view_count", 0)):
                            timestamp_offset = timedelta(
                                microseconds=(
                                    i
                                    + getattr(interaction, "view_count", 0)
                                    + getattr(interaction, "cart_add_count", 0)
                                )
                                * 1000
                            )
                            feedback_batch.append(
                                {
                                    "feedbackType": "cart_view",
                                    "userId": f"shop_{shop_id}_{getattr(interaction, 'customer_id', '')}",
                                    "itemId": f"shop_{shop_id}_{getattr(interaction, 'product_id', '')}",
                                    "timestamp": (
                                        base_timestamp + timestamp_offset
                                    ).isoformat(),
                                }
                            )

                        # Create cart_remove feedback records (one for each cart remove)
                        for i in range(getattr(interaction, "cart_remove_count", 0)):
                            timestamp_offset = timedelta(
                                microseconds=(
                                    i
                                    + getattr(interaction, "view_count", 0)
                                    + getattr(interaction, "cart_add_count", 0)
                                    + getattr(interaction, "cart_view_count", 0)
                                )
                                * 1000
                            )
                            feedback_batch.append(
                                {
                                    "feedbackType": "cart_remove",
                                    "userId": f"shop_{shop_id}_{getattr(interaction, 'customer_id', '')}",
                                    "itemId": f"shop_{shop_id}_{getattr(interaction, 'product_id', '')}",
                                    "timestamp": (
                                        base_timestamp + timestamp_offset
                                    ).isoformat(),
                                }
                            )

                        # Create purchase feedback records (one for each purchase)
                        for i in range(getattr(interaction, "purchase_count", 0)):
                            timestamp_offset = timedelta(
                                microseconds=(
                                    i
                                    + getattr(interaction, "view_count", 0)
                                    + getattr(interaction, "cart_add_count", 0)
                                    + getattr(interaction, "cart_view_count", 0)
                                    + getattr(interaction, "cart_remove_count", 0)
                                )
                                * 1000
                            )
                            feedback_batch.append(
                                {
                                    "feedbackType": "purchase",
                                    "userId": f"shop_{shop_id}_{getattr(interaction, 'customer_id', '')}",
                                    "itemId": f"shop_{shop_id}_{getattr(interaction, 'product_id', '')}",
                                    "timestamp": (
                                        base_timestamp + timestamp_offset
                                    ).isoformat(),
                                }
                            )

                    # Push feedback to Gorse API
                    if feedback_batch:
                        logger.info(
                            f"📊 Creating {len(feedback_batch)} feedback records from {len(interactions)} interactions"
                        )
                        await self.gorse_client.insert_feedback_batch(feedback_batch)
                        total_synced += len(feedback_batch)

                    if len(interactions) < self.batch_size:
                        break

                    offset += self.batch_size

            logger.info(
                f"Synced {total_synced} feedback records from interaction features"
            )
            return total_synced

        except Exception as e:
            logger.error(f"Failed to sync feedback for shop {shop_id}: {str(e)}")
            return 0

    async def _sync_interaction_features_streaming(
        self, shop_id: str, since_time: Optional[datetime] = None
    ) -> int:
        """Stream interaction features and convert to feedback"""
        try:
            total_synced = 0
            offset = 0

            async with get_session_context() as session:
                while True:
                    where_clauses = [InteractionFeatures.shop_id == shop_id]
                    if since_time is not None:
                        where_clauses.append(
                            InteractionFeatures.last_computed_at >= since_time
                        )

                    stmt = (
                        select(InteractionFeatures)
                        .where(*where_clauses)
                        .order_by(InteractionFeatures.last_computed_at.asc())
                        .offset(offset)
                        .limit(self.batch_size)
                    )
                    result = await session.execute(stmt)
                    interactions = result.scalars().all()

                    if not interactions:
                        break

                    # Process interactions in parallel
                    feedback_batches = await self._process_interactions_batch_parallel(
                        interactions, shop_id
                    )

                    # Push all feedback batches to Gorse API
                    for feedback_batch in feedback_batches:
                        if feedback_batch:
                            await self.gorse_client.insert_feedback_batch(
                                feedback_batch
                            )
                            total_synced += len(feedback_batch)

                    if len(interactions) < self.batch_size:
                        break

                    offset += self.batch_size

            return total_synced

        except Exception as e:
            logger.error(
                f"Failed to sync interaction features for shop {shop_id}: {str(e)}"
            )
            return 0

    async def _sync_customer_behavior_features_streaming(
        self, shop_id: str, since_time: Optional[datetime] = None
    ) -> int:
        """Stream customer behavior features and convert to feedback"""
        try:
            total_synced = 0
            offset = 0

            async with get_session_context() as session:
                while True:
                    where_clauses = [CustomerBehaviorFeatures.shop_id == shop_id]
                    if since_time is not None:
                        where_clauses.append(
                            CustomerBehaviorFeatures.last_computed_at >= since_time
                        )

                    stmt = (
                        select(CustomerBehaviorFeatures)
                        .where(*where_clauses)
                        .order_by(CustomerBehaviorFeatures.last_computed_at.asc())
                        .offset(offset)
                        .limit(self.batch_size)
                    )
                    result = await session.execute(stmt)
                    customer_behaviors = result.scalars().all()

                    if not customer_behaviors:
                        break

                    feedback_batches = (
                        await self._process_customer_behaviors_batch_parallel(
                            customer_behaviors, shop_id
                        )
                    )

                    for feedback_batch in feedback_batches:
                        if feedback_batch:
                            await self.gorse_client.insert_feedback_batch(
                                feedback_batch
                            )
                            total_synced += len(feedback_batch)

                    if len(customer_behaviors) < self.batch_size:
                        break

                    offset += self.batch_size

            return total_synced

        except Exception as e:
            logger.error(
                f"Failed to sync customer behavior features for shop {shop_id}: {str(e)}"
            )
            return 0

    async def _sync_session_features_to_gorse(self, shop_id: str) -> int:
        """Sync session features to Gorse as user session data"""
        try:
            total_synced = 0
            offset = 0
            async with get_session_context() as session_ctx:
                while True:
                    stmt = (
                        select(SessionFeatures)
                        .where(SessionFeatures.shop_id == shop_id)
                        .order_by(SessionFeatures.last_computed_at.asc())
                        .offset(offset)
                        .limit(self.batch_size)
                    )
                    result = await session_ctx.execute(stmt)
                    sessions = result.scalars().all()

                    if not sessions:
                        break

                    session_batch = []
                    for s in sessions:
                        if getattr(s, "customer_id", None):
                            session_data = (
                                self.transformers.transform_session_features_to_gorse(
                                    s, shop_id
                                )
                            )
                            if session_data:
                                session_batch.append(session_data)

                    if session_batch:
                        logger.info(
                            f"Found {len(session_batch)} sessions to sync (session sync not implemented in Gorse yet)"
                        )
                        total_synced += len(session_batch)

                    if len(sessions) < self.batch_size:
                        break

                    offset += self.batch_size

            logger.info(
                f"Processed {total_synced} session features (session sync not implemented in Gorse yet)"
            )
            return total_synced

        except Exception as e:
            logger.error(
                f"Failed to sync session features for shop {shop_id}: {str(e)}"
            )
            return 0

    async def _sync_product_pair_features_to_gorse(self, shop_id: str) -> int:
        """Sync product pair features to Gorse as item-to-item relationships"""
        try:
            total_synced = 0
            offset = 0
            async with get_session_context() as session:
                while True:
                    stmt = (
                        select(ProductPairFeatures)
                        .where(ProductPairFeatures.shop_id == shop_id)
                        .order_by(ProductPairFeatures.last_computed_at.asc())
                        .offset(offset)
                        .limit(self.batch_size)
                    )
                    result = await session.execute(stmt)
                    product_pairs = result.scalars().all()

                    if not product_pairs:
                        break

                    feedback_batch = []
                    for pair in product_pairs:
                        pair_feedback = self.transformers.transform_product_pair_features_to_feedback(
                            pair, shop_id
                        )
                        if pair_feedback:
                            feedback_batch.extend(pair_feedback)

                    if feedback_batch:
                        await self.gorse_client.insert_feedback_batch(feedback_batch)
                        total_synced += len(feedback_batch)

                    if len(product_pairs) < self.batch_size:
                        break

                    offset += self.batch_size

            logger.info(f"Synced {total_synced} product pair relationships to Gorse")
            return total_synced

        except Exception as e:
            logger.error(
                f"Failed to sync product pair features for shop {shop_id}: {str(e)}"
            )
            return 0

    async def _sync_search_product_features_to_gorse(self, shop_id: str) -> int:
        """Sync search product features to Gorse as search-based feedback"""
        try:
            total_synced = 0
            offset = 0
            async with get_session_context() as session:
                while True:
                    stmt = (
                        select(SearchProductFeatures)
                        .where(SearchProductFeatures.shop_id == shop_id)
                        .order_by(SearchProductFeatures.last_computed_at.asc())
                        .offset(offset)
                        .limit(self.batch_size)
                    )
                    result = await session.execute(stmt)
                    search_products = result.scalars().all()

                    if not search_products:
                        break

                    feedback_batch = []
                    for search_product in search_products:
                        search_feedback = self.transformers.transform_search_product_features_to_feedback(
                            search_product, shop_id
                        )
                        if search_feedback:
                            feedback_batch.append(search_feedback)

                    if feedback_batch:
                        await self.gorse_client.insert_feedback_batch(feedback_batch)
                        total_synced += len(feedback_batch)

                    if len(search_products) < self.batch_size:
                        break

                    offset += self.batch_size

            logger.info(f"Synced {total_synced} search-product correlations to Gorse")
            return total_synced

        except Exception as e:
            logger.error(
                f"Failed to sync search product features for shop {shop_id}: {str(e)}"
            )
            return 0

    async def _sync_collection_features_to_gorse(self, shop_id: str) -> int:
        """Sync collection features to Gorse as collection-based items"""
        try:
            total_synced = 0
            offset = 0
            async with get_session_context() as session:
                while True:
                    stmt = (
                        select(CollectionFeatures)
                        .where(CollectionFeatures.shop_id == shop_id)
                        .order_by(CollectionFeatures.last_computed_at.asc())
                        .offset(offset)
                        .limit(self.batch_size)
                    )
                    result = await session.execute(stmt)
                    collections = result.scalars().all()

                    if not collections:
                        break

                    items_batch = []
                    for collection in collections:
                        collection_item = (
                            self.transformers.transform_collection_features_to_item(
                                collection, shop_id
                            )
                        )
                        if collection_item:
                            items_batch.append(collection_item)

                    if items_batch:
                        await self.gorse_client.insert_items_batch(items_batch)
                        total_synced += len(items_batch)

                    if len(collections) < self.batch_size:
                        break

                    offset += self.batch_size

            logger.info(f"Synced {total_synced} collection features to Gorse")
            return total_synced

        except Exception as e:
            logger.error(
                f"Failed to sync collection features for shop {shop_id}: {str(e)}"
            )
            return 0

    async def _sync_customer_behavior_features_to_gorse(self, shop_id: str) -> int:
        """Sync customer behavior features to Gorse as enhanced user features"""
        try:
            total_synced = 0
            offset = 0
            async with get_session_context() as session:
                while True:
                    stmt = (
                        select(CustomerBehaviorFeatures)
                        .where(CustomerBehaviorFeatures.shop_id == shop_id)
                        .order_by(CustomerBehaviorFeatures.last_computed_at.asc())
                        .offset(offset)
                        .limit(self.batch_size)
                    )
                    result = await session.execute(stmt)
                    behaviors = result.scalars().all()

                    if not behaviors:
                        break

                    users_batch = []
                    for behavior in behaviors:
                        enhanced_user = self.transformers.transform_customer_behavior_to_user_features(
                            behavior, shop_id
                        )
                        if enhanced_user:
                            users_batch.append(enhanced_user)

                    if users_batch:
                        await self.gorse_client.insert_users_batch(users_batch)
                        total_synced += len(users_batch)

                    if len(behaviors) < self.batch_size:
                        break

                    offset += self.batch_size

            logger.info(f"Synced {total_synced} customer behavior features to Gorse")
            return total_synced

        except Exception as e:
            logger.error(
                f"Failed to sync customer behavior features for shop {shop_id}: {str(e)}"
            )
            return 0

    async def _process_events_batch_parallel(
        self, events: List, shop_id: str
    ) -> List[List[Dict[str, Any]]]:
        """Process a batch of events in parallel"""
        try:
            # Create tasks for parallel processing
            tasks = []
            for event in events:
                task = self._process_single_event(event, shop_id)
                tasks.append(task)

            # Execute all tasks in parallel
            feedback_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions and collect valid feedback
            valid_feedback = []
            for result in feedback_results:
                if isinstance(result, list):
                    valid_feedback.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"Error processing event: {str(result)}")

            # Split into batches for API calls
            feedback_batches = []
            for i in range(0, len(valid_feedback), self.batch_size):
                batch = valid_feedback[i : i + self.batch_size]
                feedback_batches.append(batch)

            return feedback_batches

        except Exception as e:
            logger.error(f"Failed to process events batch in parallel: {str(e)}")
            return []

    async def _process_orders_batch_parallel(
        self, orders: List, shop_id: str
    ) -> List[List[Dict[str, Any]]]:
        """Process a batch of orders in parallel"""
        try:
            # Create tasks for parallel processing
            tasks = []
            for order in orders:
                task = self._process_single_order(order, shop_id)
                tasks.append(task)

            # Execute all tasks in parallel
            feedback_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Filter out exceptions and collect valid feedback
            valid_feedback = []
            for result in feedback_results:
                if isinstance(result, list):
                    valid_feedback.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"Error processing order: {str(result)}")

            # Split into batches for API calls
            feedback_batches = []
            for i in range(0, len(valid_feedback), self.batch_size):
                batch = valid_feedback[i : i + self.batch_size]
                feedback_batches.append(batch)

            return feedback_batches

        except Exception as e:
            logger.error(f"Failed to process orders batch in parallel: {str(e)}")
            return []

    async def _process_single_event(self, event, shop_id: str) -> List[Dict[str, Any]]:
        """Process a single event (can be run in parallel)"""
        try:
            return self.transformers.transform_behavioral_event_to_feedback(
                event, shop_id
            )
        except Exception as e:
            logger.error(f"Failed to process event {event.eventId}: {str(e)}")
            return []

    async def _process_single_order(self, order, shop_id: str) -> List[Dict[str, Any]]:
        """Process a single order (can be run in parallel)"""
        try:
            return self.transformers.transform_order_to_feedback(order, shop_id)
        except Exception as e:
            logger.error(f"Failed to process order {order.orderId}: {str(e)}")
            return []

    async def _get_product_categories(self, product_id: str, shop_id: str) -> List[str]:
        """Get categories for a product"""
        try:
            # For now, return a simple category based on product type
            # This can be enhanced to use actual collection data
            return [f"shop_{shop_id}", "Products"]

        except Exception as e:
            logger.error(f"Failed to get categories for product {product_id}: {str(e)}")
            return [f"shop_{shop_id}"]

    def _should_hide_product(self, product) -> bool:
        """Determine if product should be hidden in Gorse"""
        # Simple logic - can be enhanced
        try:
            # Handle SQLAlchemy models (snake_case) and dicts (snake_case or camelCase)
            if hasattr(product, "view_count_30d"):
                view_count = getattr(product, "view_count_30d", 0)
                purchase_count = getattr(product, "purchase_count_30d", 0)
                conversion_rate = getattr(product, "overall_conversion_rate", 0)
            else:
                view_count = product.get(
                    "view_count_30d", product.get("viewCount30d", 0)
                )
                purchase_count = product.get(
                    "purchase_count_30d", product.get("purchaseCount30d", 0)
                )
                conversion_rate = product.get(
                    "overall_conversion_rate", product.get("overallConversionRate", 0)
                )

            return view_count == 0 and purchase_count == 0 and conversion_rate == 0
        except Exception as e:
            logger.error(f"Error in _should_hide_product: {e}")
            return False

    async def get_training_status(self, shop_id: str) -> Dict[str, Any]:
        """Get current training status for a shop"""
        try:
            # Check Gorse API for training status
            stats = await self.gorse_client.get_statistics()
            return {"shop_id": shop_id, "gorse_stats": stats, "last_updated": now_utc()}
        except Exception as e:
            logger.error(f"Failed to get training status for shop {shop_id}: {str(e)}")
            return {"error": str(e)}

    async def trigger_manual_training(self, shop_id: str) -> Dict[str, Any]:
        """Manually trigger training for a shop"""
        try:
            # Trigger training via Gorse API
            result = await self.gorse_client.trigger_training()
            return {
                "shop_id": shop_id,
                "training_triggered": True,
                "result": result,
                "timestamp": now_utc(),
            }
        except Exception as e:
            logger.error(f"Failed to trigger training for shop {shop_id}: {str(e)}")
            return {"error": str(e)}
