"""
Unified Gorse Service
Combines data sync and training into one service that directly pushes to Gorse API
This eliminates the need for bridge tables and ensures training is always triggered
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from app.core.database.simple_db_client import get_database
from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.shared.decorators import retry_with_exponential_backoff
from app.shared.gorse_api_client import GorseApiClient
from app.domains.ml.transformers.gorse_data_transformers import GorseDataTransformers

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
        self._db_client = None

    async def _get_database(self):
        """Get database client"""
        if self._db_client is None:
            self._db_client = await get_database()
        return self._db_client

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

    async def _get_last_sync_timestamp(self, shop_id: str) -> Optional[datetime]:
        """Get the last sync timestamp for incremental sync"""
        try:
            db = await self._get_database()

            # Get the most recent timestamp from feature tables
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
                    UNION ALL
                    SELECT MAX("lastComputedAt") as last_computed FROM "ProductPairFeatures" WHERE "shopId" = $1
                    UNION ALL
                    SELECT MAX("lastComputedAt") as last_computed FROM "SearchProductFeatures" WHERE "shopId" = $1
                ) as all_features
                """,
                shop_id,
            )

            if result and result[0] and result[0].get("last_sync"):
                last_sync = result[0]["last_sync"]
                # Handle case where result might be 0 or other non-datetime values
                if last_sync and last_sync != 0:
                    return last_sync
            return None

        except Exception as e:
            # Only log error if it's not a simple "0" result (which is normal for new shops)
            error_msg = str(e)
            if error_msg != "0" and "0" not in error_msg:
                logger.error(
                    f"Failed to get last sync timestamp for shop {shop_id}: {error_msg}"
                )
            return None

    async def sync_and_train(
        self,
        shop_id: str,
        sync_type: str = "all",
        since_hours: int = 24,
        trigger_source: str = "api",
    ) -> Dict[str, Any]:
        """
        Main entry point: Sync data from feature tables directly to Gorse API
        This automatically triggers training

        Args:
            shop_id: Shop ID to sync data for
            sync_type: Type of sync ("all", "incremental", "users", "items", "feedback")
            since_hours: Hours to look back for incremental sync
            trigger_source: Source that triggered the sync

        Returns:
            Dict with sync results and training status
        """
        start_time = now_utc()
        job_id = f"unified_sync_{shop_id}_{int(time.time())}"

        logger.info(f"Starting unified sync and training for shop {shop_id}")

        try:
            # Determine sync scope with proper incremental logic
            since_time = None
            if sync_type == "incremental":
                if since_hours > 0:
                    # Use provided hours
                    since_time = now_utc() - timedelta(hours=since_hours)
                else:
                    # Auto-detect last sync timestamp
                    since_time = await self._get_last_sync_timestamp(shop_id)
                    if since_time:
                        logger.info(f"Auto-detected last sync time: {since_time}")
                    else:
                        logger.info("No previous sync found, doing full sync")
                        sync_type = "all"

            results = {
                "job_id": job_id,
                "shop_id": shop_id,
                "sync_type": sync_type,
                "since_time": since_time,
                "start_time": start_time,
                "users_synced": 0,
                "items_synced": 0,
                "feedback_synced": 0,
                "sessions_synced": 0,
                "product_pairs_synced": 0,
                "search_products_synced": 0,
                "collections_synced": 0,
                "customer_behaviors_synced": 0,
                "training_triggered": False,
                "errors": [],
            }

            # Sync data types in parallel for better performance
            sync_tasks = []

            if sync_type in ["all", "users"]:
                sync_tasks.append(
                    ("users", self._sync_users_to_gorse(shop_id, since_time))
                )

            if sync_type in ["all", "items"]:
                sync_tasks.append(
                    ("items", self._sync_items_to_gorse(shop_id, since_time))
                )

            if sync_type in ["all", "feedback"]:
                sync_tasks.append(
                    ("feedback", self._sync_feedback_to_gorse(shop_id, since_time))
                )

            # Add new feature table sync tasks with graceful skipping
            if sync_type in ["all", "sessions"]:
                # Check if session features exist before adding sync task
                has_session_data = await self._check_feature_table_has_data(
                    "sessionfeatures", shop_id, since_time
                )
                if has_session_data:
                    sync_tasks.append(
                        (
                            "sessions",
                            self._sync_session_features_to_gorse(shop_id, since_time),
                        )
                    )
                else:
                    logger.info(
                        f"Skipping session features sync - no data found for shop {shop_id}"
                    )
                    results["sessions_synced"] = 0

            if sync_type in ["all", "product_pairs"]:
                # Check if product pair features exist before adding sync task
                has_product_pair_data = await self._check_feature_table_has_data(
                    "productpairfeatures", shop_id, since_time
                )
                if has_product_pair_data:
                    sync_tasks.append(
                        (
                            "product_pairs",
                            self._sync_product_pair_features_to_gorse(
                                shop_id, since_time
                            ),
                        )
                    )
                else:
                    logger.info(
                        f"Skipping product pair features sync - no data found for shop {shop_id}"
                    )
                    results["product_pairs_synced"] = 0

            if sync_type in ["all", "search_products"]:
                # Check if search product features exist before adding sync task
                has_search_product_data = await self._check_feature_table_has_data(
                    "searchproductfeatures", shop_id, since_time
                )
                if has_search_product_data:
                    sync_tasks.append(
                        (
                            "search_products",
                            self._sync_search_product_features_to_gorse(
                                shop_id, since_time
                            ),
                        )
                    )
                else:
                    logger.info(
                        f"Skipping search product features sync - no data found for shop {shop_id}"
                    )
                    results["search_products_synced"] = 0

            if sync_type in ["all", "collections"]:
                # Check if collection features exist before adding sync task
                has_collection_data = await self._check_feature_table_has_data(
                    "collectionfeatures", shop_id, since_time
                )
                if has_collection_data:
                    sync_tasks.append(
                        (
                            "collections",
                            self._sync_collection_features_to_gorse(
                                shop_id, since_time
                            ),
                        )
                    )
                else:
                    logger.info(
                        f"Skipping collection features sync - no data found for shop {shop_id}"
                    )
                    results["collections_synced"] = 0

            if sync_type in ["all", "customer_behaviors"]:
                # Check if customer behavior features exist before adding sync task
                has_customer_behavior_data = await self._check_feature_table_has_data(
                    "customerbehaviorfeatures", shop_id, since_time
                )
                if has_customer_behavior_data:
                    sync_tasks.append(
                        (
                            "customer_behaviors",
                            self._sync_customer_behavior_features_to_gorse(
                                shop_id, since_time
                            ),
                        )
                    )
                else:
                    logger.info(
                        f"Skipping customer behavior features sync - no data found for shop {shop_id}"
                    )
                    results["customer_behaviors_synced"] = 0

            # Execute all sync tasks in parallel
            if sync_tasks:
                task_names, task_coroutines = zip(*sync_tasks)
                sync_results = await asyncio.gather(
                    *task_coroutines, return_exceptions=True
                )

                # Process results
                for task_name, result in zip(task_names, sync_results):
                    if isinstance(result, Exception):
                        logger.error(f"Failed to sync {task_name}: {str(result)}")
                        results[f"{task_name}_synced"] = 0
                        results["errors"].append(
                            f"{task_name}_sync_failed: {str(result)}"
                        )
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

    async def _sync_users_to_gorse(
        self, shop_id: str, since_time: Optional[datetime] = None
    ) -> int:
        """Sync users from feature tables directly to Gorse API with streaming"""
        try:
            db = await self._get_database()
            total_synced = 0
            offset = 0

            while True:
                # Stream users in batches to avoid memory issues
                if since_time:
                    users = await db.userfeatures.find_many(
                        where={
                            "shopId": shop_id,
                            "lastComputedAt": {"gte": since_time},
                        },
                        skip=offset,
                        take=self.batch_size,
                        order={"lastComputedAt": "asc"},
                    )
                else:
                    users = await db.userfeatures.find_many(
                        where={"shopId": shop_id},
                        skip=offset,
                        take=self.batch_size,
                        order={"lastComputedAt": "asc"},
                    )

                if not users:
                    break

                # Transform to Gorse format
                gorse_users = []
                for user in users:
                    # Apply shop prefix for multi-tenancy
                    prefixed_user_id = f"shop_{shop_id}_{user.customerId}"

                    # Transform user features to Gorse labels
                    labels = self.transformers.transform_user_features_to_labels(user)

                    gorse_user = {"userId": prefixed_user_id, "labels": labels}
                    gorse_users.append(gorse_user)

                # Push to Gorse API
                if gorse_users:
                    await self.gorse_client.insert_users_batch(gorse_users)
                    total_synced += len(gorse_users)
                    logger.info(
                        f"Synced {len(gorse_users)} users (total: {total_synced})"
                    )

                # Check if we got fewer records than batch size (end of data)
                if len(users) < self.batch_size:
                    break

                offset += self.batch_size

            return total_synced

        except Exception as e:
            logger.error(f"Failed to sync users for shop {shop_id}: {str(e)}")
            return 0

    async def _sync_items_to_gorse(
        self, shop_id: str, since_time: Optional[datetime] = None
    ) -> int:
        """Sync items from feature tables directly to Gorse API with streaming and parallel processing"""
        try:
            db = await self._get_database()
            total_synced = 0
            offset = 0

            while True:
                # Stream products in batches to avoid memory issues
                if since_time:
                    products = await db.productfeatures.find_many(
                        where={
                            "shopId": shop_id,
                            "lastComputedAt": {"gte": since_time},
                        },
                        skip=offset,
                        take=self.batch_size,
                        order={"lastComputedAt": "asc"},
                    )
                else:
                    products = await db.productfeatures.find_many(
                        where={"shopId": shop_id},
                        skip=offset,
                        take=self.batch_size,
                        order={"lastComputedAt": "asc"},
                    )

                if not products:
                    break

                # Get product data for this batch only
                product_ids = [p.productId for p in products]
                product_data = await db.productdata.find_many(
                    where={"shopId": shop_id, "productId": {"in": product_ids}}
                )
                product_data_map = {p.productId: p for p in product_data}

                # Process items in parallel batches
                gorse_items = await self._process_items_batch_parallel(
                    products, product_data_map, shop_id
                )

                # Push to Gorse API
                if gorse_items:
                    await self.gorse_client.insert_items_batch(gorse_items)
                    total_synced += len(gorse_items)
                    logger.info(
                        f"Synced {len(gorse_items)} items (total: {total_synced})"
                    )

                # Check if we got fewer records than batch size (end of data)
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
            # Apply shop prefix for multi-tenancy
            prefixed_item_id = f"shop_{shop_id}_{product.productId}"

            # Get product data
            product_info = product_data_map.get(product.productId, {})

            # Transform product features to Gorse labels
            labels = self.transformers.transform_product_features_to_labels(
                product, product_info
            )

            # Get categories (this could be cached for better performance)
            categories = await self._get_product_categories(product.productId, shop_id)

            return {
                "itemId": prefixed_item_id,
                "labels": labels,
                "categories": categories,
                "isHidden": self._should_hide_product(product),
            }

        except Exception as e:
            logger.error(f"Failed to process item {product.productId}: {str(e)}")
            raise e

    async def _sync_feedback_to_gorse(
        self, shop_id: str, since_time: Optional[datetime] = None
    ) -> int:
        """Sync feedback from interaction features (which contain user-item interactions)"""
        try:
            db = await self._get_database()
            total_synced = 0
            offset = 0

            while True:
                # Stream interaction features in batches
                if since_time:
                    interactions = await db.interactionfeatures.find_many(
                        where={
                            "shopId": shop_id,
                            "lastComputedAt": {"gte": since_time},
                        },
                        skip=offset,
                        take=self.batch_size,
                        order={"lastComputedAt": "asc"},
                    )
                else:
                    interactions = await db.interactionfeatures.find_many(
                        where={"shopId": shop_id},
                        skip=offset,
                        take=self.batch_size,
                        order={"lastComputedAt": "asc"},
                    )

                if not interactions:
                    break

                # Convert interaction features to feedback
                feedback_batch = []
                for interaction in interactions:
                    # Create feedback based on interaction counts
                    if interaction.viewCount > 0:
                        feedback_batch.append(
                            {
                                "feedbackType": "view",
                                "userId": f"shop_{shop_id}_{interaction.customerId}",
                                "itemId": f"shop_{shop_id}_{interaction.productId}",
                                "timestamp": interaction.lastComputedAt.isoformat(),
                            }
                        )

                    if interaction.cartAddCount > 0:
                        feedback_batch.append(
                            {
                                "feedbackType": "cart_add",
                                "userId": f"shop_{shop_id}_{interaction.customerId}",
                                "itemId": f"shop_{shop_id}_{interaction.productId}",
                                "timestamp": interaction.lastComputedAt.isoformat(),
                            }
                        )

                    # Add purchase feedback - this is the most important feedback type
                    if interaction.purchaseCount > 0:
                        feedback_batch.append(
                            {
                                "feedbackType": "purchase",
                                "userId": f"shop_{shop_id}_{interaction.customerId}",
                                "itemId": f"shop_{shop_id}_{interaction.productId}",
                                "timestamp": interaction.lastComputedAt.isoformat(),
                            }
                        )

                # Push feedback to Gorse API
                if feedback_batch:
                    await self.gorse_client.insert_feedback_batch(feedback_batch)
                    total_synced += len(feedback_batch)

                # Check if we got fewer records than batch size (end of data)
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
            db = await self._get_database()
            total_synced = 0
            offset = 0

            while True:
                # Stream interaction features in batches
                if since_time:
                    interactions = await db.interactionfeatures.find_many(
                        where={
                            "shopId": shop_id,
                            "lastComputedAt": {"gte": since_time},
                        },
                        skip=offset,
                        take=self.batch_size,
                        order={"lastComputedAt": "asc"},
                    )
                else:
                    interactions = await db.interactionfeatures.find_many(
                        where={"shopId": shop_id},
                        skip=offset,
                        take=self.batch_size,
                        order={"lastComputedAt": "asc"},
                    )

                if not interactions:
                    break

                # Process interactions in parallel
                feedback_batches = await self._process_interactions_batch_parallel(
                    interactions, shop_id
                )

                # Push all feedback batches to Gorse API
                for feedback_batch in feedback_batches:
                    if feedback_batch:
                        await self.gorse_client.insert_feedback_batch(feedback_batch)
                        total_synced += len(feedback_batch)

                # Check if we got fewer records than batch size (end of data)
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
            db = await self._get_database()
            total_synced = 0
            offset = 0

            while True:
                # Stream customer behavior features in batches
                if since_time:
                    customer_behaviors = await db.customerbehaviorfeatures.find_many(
                        where={
                            "shopId": shop_id,
                            "lastComputedAt": {"gte": since_time},
                        },
                        skip=offset,
                        take=self.batch_size,
                        order={"lastComputedAt": "asc"},
                    )
                else:
                    customer_behaviors = await db.customerbehaviorfeatures.find_many(
                        where={"shopId": shop_id},
                        skip=offset,
                        take=self.batch_size,
                        order={"lastComputedAt": "asc"},
                    )

                if not customer_behaviors:
                    break

                # Process customer behaviors in parallel
                feedback_batches = (
                    await self._process_customer_behaviors_batch_parallel(
                        customer_behaviors, shop_id
                    )
                )

                # Push all feedback batches to Gorse API
                for feedback_batch in feedback_batches:
                    if feedback_batch:
                        await self.gorse_client.insert_feedback_batch(feedback_batch)
                        total_synced += len(feedback_batch)

                # Check if we got fewer records than batch size (end of data)
                if len(customer_behaviors) < self.batch_size:
                    break

                offset += self.batch_size

            return total_synced

        except Exception as e:
            logger.error(
                f"Failed to sync customer behavior features for shop {shop_id}: {str(e)}"
            )
            return 0

    async def _sync_session_features_to_gorse(
        self, shop_id: str, since_time: Optional[datetime] = None
    ) -> int:
        """Sync session features to Gorse as user session data"""
        try:
            db = await self._get_database()
            total_synced = 0
            offset = 0

            while True:
                # Stream session features in batches
                if since_time:
                    sessions = await db.sessionfeatures.find_many(
                        where={
                            "shopId": shop_id,
                            "lastComputedAt": {"gte": since_time},
                        },
                        skip=offset,
                        take=self.batch_size,
                        order={"lastComputedAt": "asc"},
                    )
                else:
                    sessions = await db.sessionfeatures.find_many(
                        where={"shopId": shop_id},
                        skip=offset,
                        take=self.batch_size,
                        order={"lastComputedAt": "asc"},
                    )

                if not sessions:
                    break

                # Convert session features to user session data for Gorse using transformers
                session_batch = []
                for session in sessions:
                    if session.customerId:  # Only process sessions with known customers
                        # Use transformer to convert session features to Gorse format
                        session_data = (
                            self.transformers.transform_session_features_to_gorse(
                                session, shop_id
                            )
                        )
                        if session_data:
                            session_batch.append(session_data)

                # Push session data to Gorse API (if Gorse supports session data)
                if session_batch:
                    # Note: This assumes Gorse has session support, otherwise we can skip
                    logger.info(
                        f"Found {len(session_batch)} sessions to sync (session sync not implemented in Gorse yet)"
                    )
                    total_synced += len(session_batch)

                # Check if we got fewer records than batch size (end of data)
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

    async def _sync_product_pair_features_to_gorse(
        self, shop_id: str, since_time: Optional[datetime] = None
    ) -> int:
        """Sync product pair features to Gorse as item-to-item relationships"""
        try:
            db = await self._get_database()
            total_synced = 0
            offset = 0

            while True:
                # Stream product pair features in batches
                if since_time:
                    product_pairs = await db.productpairfeatures.find_many(
                        where={
                            "shopId": shop_id,
                            "lastComputedAt": {"gte": since_time},
                        },
                        skip=offset,
                        take=self.batch_size,
                        order={"lastComputedAt": "asc"},
                    )
                else:
                    product_pairs = await db.productpairfeatures.find_many(
                        where={"shopId": shop_id},
                        skip=offset,
                        take=self.batch_size,
                        order={"lastComputedAt": "asc"},
                    )

                if not product_pairs:
                    break

                # Convert product pair features to item-to-item feedback using transformers
                feedback_batch = []
                for pair in product_pairs:
                    # Use transformer to convert product pair features to Gorse feedback
                    pair_feedback = (
                        self.transformers.transform_product_pair_features_to_feedback(
                            pair, shop_id
                        )
                    )
                    if pair_feedback:
                        feedback_batch.extend(pair_feedback)

                # Push feedback to Gorse API
                if feedback_batch:
                    await self.gorse_client.insert_feedback_batch(feedback_batch)
                    total_synced += len(feedback_batch)

                # Check if we got fewer records than batch size (end of data)
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

    async def _sync_search_product_features_to_gorse(
        self, shop_id: str, since_time: Optional[datetime] = None
    ) -> int:
        """Sync search product features to Gorse as search-based feedback"""
        try:
            db = await self._get_database()
            total_synced = 0
            offset = 0

            while True:
                # Stream search product features in batches
                if since_time:
                    search_products = await db.searchproductfeatures.find_many(
                        where={
                            "shopId": shop_id,
                            "lastComputedAt": {"gte": since_time},
                        },
                        skip=offset,
                        take=self.batch_size,
                        order={"lastComputedAt": "asc"},
                    )
                else:
                    search_products = await db.searchproductfeatures.find_many(
                        where={"shopId": shop_id},
                        skip=offset,
                        take=self.batch_size,
                        order={"lastComputedAt": "asc"},
                    )

                if not search_products:
                    break

                # Convert search product features to search-based feedback using transformers
                feedback_batch = []
                for search_product in search_products:
                    # Use transformer to convert search product features to Gorse feedback
                    search_feedback = (
                        self.transformers.transform_search_product_features_to_feedback(
                            search_product, shop_id
                        )
                    )
                    if search_feedback:
                        feedback_batch.append(search_feedback)

                # Push feedback to Gorse API
                if feedback_batch:
                    await self.gorse_client.insert_feedback_batch(feedback_batch)
                    total_synced += len(feedback_batch)

                # Check if we got fewer records than batch size (end of data)
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

    async def _sync_collection_features_to_gorse(
        self, shop_id: str, since_time: Optional[datetime] = None
    ) -> int:
        """Sync collection features to Gorse as collection-based items"""
        try:
            db = await self._get_database()
            total_synced = 0
            offset = 0

            while True:
                # Stream collection features in batches
                if since_time:
                    collections = await db.collectionfeatures.find_many(
                        where={
                            "shopId": shop_id,
                            "lastComputedAt": {"gte": since_time},
                        },
                        skip=offset,
                        take=self.batch_size,
                        order={"lastComputedAt": "asc"},
                    )
                else:
                    collections = await db.collectionfeatures.find_many(
                        where={"shopId": shop_id},
                        skip=offset,
                        take=self.batch_size,
                        order={"lastComputedAt": "asc"},
                    )

                if not collections:
                    break

                # Convert collection features to Gorse items using transformers
                items_batch = []
                for collection in collections:
                    # Use transformer to convert collection features to Gorse item
                    collection_item = (
                        self.transformers.transform_collection_features_to_item(
                            collection, shop_id
                        )
                    )
                    if collection_item:
                        items_batch.append(collection_item)

                # Push items to Gorse API
                if items_batch:
                    await self.gorse_client.insert_items_batch(items_batch)
                    total_synced += len(items_batch)

                # Check if we got fewer records than batch size (end of data)
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

    async def _sync_customer_behavior_features_to_gorse(
        self, shop_id: str, since_time: Optional[datetime] = None
    ) -> int:
        """Sync customer behavior features to Gorse as enhanced user features"""
        try:
            db = await self._get_database()
            total_synced = 0
            offset = 0

            while True:
                # Stream customer behavior features in batches
                if since_time:
                    behaviors = await db.customerbehaviorfeatures.find_many(
                        where={
                            "shopId": shop_id,
                            "lastComputedAt": {"gte": since_time},
                        },
                        skip=offset,
                        take=self.batch_size,
                        order={"lastComputedAt": "asc"},
                    )
                else:
                    behaviors = await db.customerbehaviorfeatures.find_many(
                        where={"shopId": shop_id},
                        skip=offset,
                        take=self.batch_size,
                        order={"lastComputedAt": "asc"},
                    )

                if not behaviors:
                    break

                # Convert customer behavior features to enhanced user features using transformers
                users_batch = []
                for behavior in behaviors:
                    # Use transformer to convert behavior features to enhanced user features
                    enhanced_user = (
                        self.transformers.transform_customer_behavior_to_user_features(
                            behavior, shop_id
                        )
                    )
                    if enhanced_user:
                        users_batch.append(enhanced_user)

                # Push enhanced users to Gorse API
                if users_batch:
                    await self.gorse_client.insert_users_batch(users_batch)
                    total_synced += len(users_batch)

                # Check if we got fewer records than batch size (end of data)
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
            db = await self._get_database()

            # Get collection features for this product
            collection_features = await db.collectionfeatures.find_many(
                where={"shopId": shop_id}
            )

            # For now, return a simple category based on product type
            # This can be enhanced to use actual collection data
            return [f"shop_{shop_id}", "Products"]

        except Exception as e:
            logger.error(f"Failed to get categories for product {product_id}: {str(e)}")
            return [f"shop_{shop_id}"]

    def _should_hide_product(self, product) -> bool:
        """Determine if product should be hidden in Gorse"""
        # Simple logic - can be enhanced
        return (
            product.viewCount30d == 0
            and product.purchaseCount30d == 0
            and product.overallConversionRate == 0
        )

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
