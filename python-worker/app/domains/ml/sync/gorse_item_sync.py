"""
Item synchronization logic for Gorse pipeline
Handles product/item data fetching, processing, and syncing
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.core.logging import get_logger
from prisma import Json

logger = get_logger(__name__)


class GorseItemSync:
    """Item synchronization operations"""

    def __init__(self, pipeline):
        self.pipeline = pipeline

    def _get_prefixed_item_id(self, item_id: str, shop_id: str) -> str:
        """
        Generate shop-prefixed item ID for multi-tenancy
        Format: shop_{shop_id}_{item_id}
        """
        if not shop_id:
            return item_id
        return f"shop_{shop_id}_{item_id}"

    async def sync_items(
        self,
        shop_id: str,
        incremental: bool = True,
        since_timestamp: Optional[datetime] = None,
    ):
        """
        Sync items from ProductFeatures table only (with CollectionFeatures for context)
        Uses batch processing to handle large datasets efficiently with transactional integrity
        Only processes items that have been computed by the feature engineering pipeline

        Args:
            shop_id: Shop ID to sync
            incremental: Whether to use incremental sync
            since_timestamp: Timestamp for incremental sync
        """

        async def _sync_items_operation():
            return await self.pipeline.core._generic_batch_processor(
                shop_id=shop_id,
                batch_size=self.pipeline.item_batch_size,
                fetch_batch_func=lambda shop_id, offset, limit: self._fetch_item_batch(
                    shop_id, offset, limit, since_timestamp if incremental else None
                ),
                process_batch_func=self._process_item_batch,
                entity_name="items",
            )

        # Use transaction if not already in one
        if self.pipeline.core._is_in_transaction():
            await _sync_items_operation()
        else:
            await self.pipeline.core._execute_with_transaction(
                "sync_items", _sync_items_operation
            )

    async def _fetch_item_batch(
        self,
        shop_id: str,
        offset: int,
        limit: int,
        last_sync_timestamp: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch a batch of items from ProductFeatures table only (incremental if timestamp provided)"""
        try:
            db = await self.pipeline._get_database()

            # Build incremental query if timestamp provided
            if last_sync_timestamp:
                base_query = """
                        SELECT 
                            pf.*,
                            -- Default values for missing ProductData fields
                            pd.status,
                            pd."productType",
                            pd.vendor,
                            pd.tags,
                            pd.collections,
                            pd."totalInventory",
                            pd."compareAtPrice",
                            pd.price,
                            pd."productCreatedAt",
                            -- Default collection feature values (will be NULL if no collections exist)
                            NULL as collection_product_count,
                            NULL as collection_performance_score,
                            NULL as collection_conversion_rate
                        FROM "ProductFeatures" pf
                        LEFT JOIN "ProductData" pd ON pf."productId" = pd."productId" AND pf."shopId" = pd."shopId"
                        WHERE pf."shopId" = $1 
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
                            -- Default values for missing ProductData fields
                            pd.status,
                            pd."productType",
                            pd.vendor,
                            pd.tags,
                            pd.collections,
                            pd."totalInventory",
                            pd."compareAtPrice",
                            pd.price,
                            pd."productCreatedAt",
                            -- Default collection feature values (will be NULL if no collections exist)
                            NULL as collection_product_count,
                            NULL as collection_performance_score,
                            NULL as collection_conversion_rate
                        FROM "ProductFeatures" pf
                        LEFT JOIN "ProductData" pd ON pf."productId" = pd."productId" AND pf."shopId" = pd."shopId"
                        WHERE pf."shopId" = $1
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
            db = await self.pipeline._get_database()

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
                labels = self.pipeline.transformers._build_comprehensive_item_labels(
                    item
                )
                categories = await self._get_product_categories(item, shop_id)
                is_hidden = self._should_hide_product(item)

                # Use prefixed item ID for multi-tenancy
                prefixed_item_id = self._get_prefixed_item_id(
                    item["productId"], shop_id
                )
                item_data = {
                    "itemId": prefixed_item_id,
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
        await self.pipeline._generic_bulk_upsert(
            data_list=gorse_items_data,
            table_accessor=lambda db: db.gorseitems,
            id_field="itemId",
            entity_name="items",
            table_name="gorse_items",
        )

    async def _get_product_categories(
        self, product: Dict[str, Any], shop_id: str
    ) -> List[str]:
        """
        Get categories with shopId as primary category for multi-tenancy
        Format: ["shop_{shop_id}", "collection_abc", "collection_def", ...]
        """
        categories = []

        # 1. Add shopId as primary category for multi-tenancy
        if shop_id:
            categories.append(f"shop_{shop_id}")

        # 2. Get from product collections
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

        # 3. Also get high-performance collections from CollectionFeatures
        db = await self.pipeline._get_database()
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

    def _should_hide_product(self, product: Dict[str, Any]) -> bool:
        """Determine if product should be hidden in Gorse"""
        total_inventory = product.get("totalInventory")
        conversion_rate = product.get("overallConversionRate")
        view_count = product.get("viewCount30d", 0)

        # Hide if out of stock
        if total_inventory is None or total_inventory <= 0:
            return True

        # Hide for very low conversion if there are sufficient views to make a decision
        if (
            view_count > 50
            and conversion_rate is not None
            and float(conversion_rate) < 0.01
        ):
            return True

        return False
