"""
Unified Gorse Service - UPDATED TO USE OPTIMIZED TRANSFORMERS
Combines data sync and training into one service that directly pushes to Gorse API
This eliminates the need for bridge tables and ensures training is always triggered
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from app.core.database.session import get_session_context
from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.shared.gorse_api_client import GorseApiClient
from app.domains.ml.transformers import GorseTransformerFactory

from sqlalchemy import select
from app.core.database.models import (
    UserFeatures,
    ProductFeatures,
    CollectionFeatures,
    OrderData,
)

logger = get_logger(__name__)


class UnifiedGorseService:
    """
    Unified service that syncs data from feature tables directly to Gorse API
    Now uses optimized transformer architecture with categorical labels
    """

    def __init__(
        self,
        gorse_base_url: str = "http://localhost:8088",
        gorse_api_key: str = "secure_random_key_123",
        batch_size: int = 500,
    ):
        """
        Initialize the unified Gorse service with optimized transformers

        Args:
            gorse_base_url: Gorse master server URL
            gorse_api_key: API key for Gorse authentication
            batch_size: Batch size for API calls
        """
        self.gorse_client = GorseApiClient(gorse_base_url, gorse_api_key)
        self.batch_size = batch_size

        # NEW: Get transformers from factory (singleton pattern)
        self.user_transformer = GorseTransformerFactory.get_user_transformer()
        self.item_transformer = GorseTransformerFactory.get_item_transformer()
        self.feedback_transformer = GorseTransformerFactory.get_feedback_transformer()
        self.collection_transformer = (
            GorseTransformerFactory.get_collection_transformer()
        )

    def _ensure_aware_utc(self, dt: Optional[datetime]) -> Optional[datetime]:
        """Normalize a datetime to timezone-aware UTC to avoid naive/aware comparison errors."""
        if dt is None:
            return None
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _get_full_sync_tasks(self, shop_id: str) -> List[tuple]:
        """Get all sync tasks for full sync - only essential Gorse data"""
        return [
            ("users", self._sync_users_to_gorse(shop_id)),
            ("items", self._sync_items_to_gorse(shop_id)),
            ("collections", self._sync_collections_to_gorse(shop_id)),
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

        try:
            results = {
                "job_id": job_id,
                "shop_id": shop_id,
                "start_time": start_time,
                "users_synced": 0,
                "items_synced": 0,
                "collections_synced": 0,
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

            # Training is automatically triggered by Gorse API calls
            results["training_triggered"] = True
            results["end_time"] = now_utc()
            results["duration_seconds"] = (
                results["end_time"] - start_time
            ).total_seconds()

            # Log summary with label statistics
            logger.info(
                f"Gorse sync completed for shop {shop_id}: "
                f"{results['users_synced']} users, "
                f"{results['items_synced']} items, "
                f"{results['collections_synced']} collections, "
                f"{results['feedback_synced']} feedback items "
                f"in {results['duration_seconds']:.2f}s"
            )

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
        """
        Sync users from feature tables directly to Gorse API
        NOW USES OPTIMIZED TRANSFORMER WITH CATEGORICAL LABELS
        """
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

                    # NEW: Transform using optimized transformer
                    gorse_users = self.user_transformer.transform_batch_to_gorse_users(
                        users, shop_id
                    )

                    # Push to Gorse API
                    if gorse_users:
                        # Convert to Gorse API format
                        api_users = []
                        for user in gorse_users:
                            api_users.append(
                                {
                                    "UserId": user["UserId"],
                                    "Labels": user["Labels"],
                                    "Comment": user.get("Comment", ""),
                                }
                            )

                        await self.gorse_client.insert_users_batch(api_users)
                        total_synced += len(api_users)

                        # Log label statistics for first batch
                        if offset == 0 and api_users:
                            avg_labels = sum(len(u["Labels"]) for u in api_users) / len(
                                api_users
                            )
                            logger.info(
                                f"Users have avg {avg_labels:.1f} labels "
                                f"(reduced from 100+ numeric fields)"
                            )

                    if len(users) < self.batch_size:
                        break

                    offset += self.batch_size

            logger.info(f"Synced {total_synced} users with optimized labels to Gorse")
            return total_synced

        except Exception as e:
            logger.error(f"Failed to sync users for shop {shop_id}: {str(e)}")
            return 0

    async def _sync_items_to_gorse(self, shop_id: str) -> int:
        """
        Sync items from feature tables directly to Gorse API
        NOW USES OPTIMIZED TRANSFORMER WITH CATEGORICAL LABELS
        """
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

                    # NEW: Transform using optimized transformer
                    gorse_items = self.item_transformer.transform_batch_to_gorse_items(
                        products, shop_id
                    )

                    # Push to Gorse API
                    if gorse_items:
                        await self.gorse_client.insert_items_batch(gorse_items)
                        total_synced += len(gorse_items)

                        # Log label statistics for first batch
                        if offset == 0 and gorse_items:
                            avg_labels = sum(
                                len(i["Labels"]) for i in gorse_items
                            ) / len(gorse_items)
                            logger.info(
                                f"Items have avg {avg_labels:.1f} labels "
                                f"(reduced from 100+ numeric fields)"
                            )

                    if len(products) < self.batch_size:
                        break

                    offset += self.batch_size

            logger.info(f"Synced {total_synced} items with optimized labels to Gorse")
            return total_synced

        except Exception as e:
            logger.error(f"Failed to sync items for shop {shop_id}: {str(e)}")
            return 0

    async def _sync_collections_to_gorse(self, shop_id: str) -> int:
        """
        Sync collections from feature tables directly to Gorse API
        Collections are treated as items in Gorse
        """
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

                    # Transform using optimized transformer
                    gorse_collections = (
                        self.collection_transformer.transform_batch_to_gorse_items(
                            collections, shop_id
                        )
                    )

                    # Push to Gorse API as items
                    if gorse_collections:
                        await self.gorse_client.insert_items_batch(gorse_collections)
                        total_synced += len(gorse_collections)

                    if len(collections) < self.batch_size:
                        break

                    offset += self.batch_size

            logger.info(f"Synced {total_synced} collections to Gorse")
            return total_synced

        except Exception as e:
            logger.error(f"Failed to sync collections for shop {shop_id}: {str(e)}")
            return 0

    async def _sync_feedback_to_gorse(self, shop_id: str) -> int:
        """
        Sync feedback from orders to Gorse API
        Creates purchase and refund feedback
        """
        try:
            total_synced = 0
            offset = 0

            async with get_session_context() as session:
                while True:
                    stmt = (
                        select(OrderData)
                        .where(OrderData.shop_id == shop_id)
                        .order_by(OrderData.order_date.asc())
                        .offset(offset)
                        .limit(self.batch_size)
                    )
                    result = await session.execute(stmt)
                    orders = result.scalars().all()

                    if not orders:
                        break

                    # Transform orders to feedback using optimized transformer
                    all_feedback = (
                        self.feedback_transformer.transform_batch_orders_to_feedback(
                            orders, shop_id
                        )
                    )

                    # Push to Gorse API
                    if all_feedback:
                        await self.gorse_client.insert_feedback_batch(all_feedback)
                        total_synced += len(all_feedback)

                    if len(orders) < self.batch_size:
                        break

                    offset += self.batch_size

            logger.info(f"Synced {total_synced} feedback items to Gorse")
            return total_synced

        except Exception as e:
            logger.error(f"Failed to sync feedback for shop {shop_id}: {str(e)}")
            return 0

    async def get_training_status(self, shop_id: str) -> Dict[str, Any]:
        """Get current training status for a shop"""
        try:
            # Check Gorse API for training status
            stats = await self.gorse_client.get_statistics()
            return {
                "shop_id": shop_id,
                "gorse_stats": stats,
                "last_updated": now_utc(),
                "transformer_version": "2.0.0-optimized",
            }
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
