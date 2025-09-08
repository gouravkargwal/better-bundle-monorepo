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

        # For full sync, don't use transactions to avoid timeout issues
        # For incremental sync, use transactions for consistency
        if incremental:
            # Use transaction if not already in one
            if self.pipeline.core._is_in_transaction():
                await _sync_items_operation()
            else:
                await self.pipeline.core._execute_with_transaction(
                    "sync_items", _sync_items_operation
                )
        else:
            # Full sync without transaction to avoid timeout
            await _sync_items_operation()

    async def _fetch_item_batch(
        self,
        shop_id: str,
        offset: int,
        limit: int,
        last_sync_timestamp: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch a batch of items with their features - robust approach handling missing data"""
        try:
            # Step 1: Get core product data from ProductFeatures (what definitely exists)
            core_products = await self._fetch_core_products(
                shop_id, limit, offset, last_sync_timestamp
            )

            if not core_products:
                logger.info(f"No core products found for shop {shop_id}")
                return []

            # Step 2: Get product data (if exists)
            product_data = await self._fetch_product_data(
                shop_id, core_products, last_sync_timestamp
            )

            # Step 3: Get collection data (if exists)
            collection_data = await self._fetch_collection_data(
                shop_id, core_products, last_sync_timestamp
            )

            # Step 4: Get product pair data (if exists)
            product_pair_data = await self._fetch_product_pair_data(
                shop_id, core_products, last_sync_timestamp
            )

            # Step 5: Get search product data (if exists)
            search_data = await self._fetch_search_product_data(
                shop_id, core_products, last_sync_timestamp
            )

            # Step 6: Merge all data safely
            enriched_products = []
            for product in core_products:
                product_id = product.get("productId")
                if not product_id:
                    continue

                # Start with core product data
                enriched_product = dict(product)

                # Add product data if available
                if product_id in product_data:
                    enriched_product.update(product_data[product_id])

                # Add collection data if available
                if product_id in collection_data:
                    enriched_product.update(collection_data[product_id])

                # Add product pair data if available
                if product_id in product_pair_data:
                    enriched_product.update(product_pair_data[product_id])

                # Add search data if available
                if product_id in search_data:
                    enriched_product.update(search_data[product_id])

                enriched_products.append(enriched_product)

            logger.info(
                f"Enriched {len(enriched_products)} products with available feature data"
            )
            return enriched_products

        except Exception as e:
            logger.error(f"Failed to fetch item batch: {str(e)}")
            raise

    async def _fetch_core_products(
        self,
        shop_id: str,
        limit: int,
        offset: int,
        last_sync_timestamp: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch core product data from ProductFeatures - this is what definitely exists"""
        try:
            db = await self.pipeline._get_database()

            if last_sync_timestamp:
                products = await db.productfeatures.find_many(
                    where={
                        "shopId": shop_id,
                        "lastComputedAt": {"gte": last_sync_timestamp},
                    },
                    order={"productId": "asc"},
                    skip=offset,
                    take=limit,
                )
            else:
                products = await db.productfeatures.find_many(
                    where={"shopId": shop_id},
                    order={"productId": "asc"},
                    skip=offset,
                    take=limit,
                )

            return [product.model_dump() for product in products]

        except Exception as e:
            logger.error(f"Failed to fetch core products: {str(e)}")
            return []

    async def _fetch_product_data(
        self,
        shop_id: str,
        core_products: List[Dict],
        last_sync_timestamp: Optional[datetime] = None,
    ) -> Dict[str, Dict]:
        """Fetch product data if it exists"""
        try:
            if not core_products:
                return {}

            db = await self.pipeline._get_database()
            product_ids = [
                product["productId"]
                for product in core_products
                if product.get("productId")
            ]

            if not product_ids:
                return {}

            if last_sync_timestamp:
                product_data = await db.productdata.find_many(
                    where={
                        "shopId": shop_id,
                        "productId": {"in": product_ids},
                        "updatedAt": {"gte": last_sync_timestamp},
                    }
                )
            else:
                product_data = await db.productdata.find_many(
                    where={"shopId": shop_id, "productId": {"in": product_ids}}
                )

            return {pd.productId: pd.model_dump() for pd in product_data}

        except Exception as e:
            logger.warning(f"Failed to fetch product data: {str(e)}")
            return {}

    async def _fetch_collection_data(
        self,
        shop_id: str,
        core_products: List[Dict],
        last_sync_timestamp: Optional[datetime] = None,
    ) -> Dict[str, Dict]:
        """Fetch collection data if it exists"""
        try:
            if not core_products:
                return {}

            db = await self.pipeline._get_database()

            if last_sync_timestamp:
                collection_features = await db.collectionfeatures.find_many(
                    where={
                        "shopId": shop_id,
                        "lastComputedAt": {"gte": last_sync_timestamp},
                    }
                )
            else:
                collection_features = await db.collectionfeatures.find_many(
                    where={"shopId": shop_id}
                )

            # Since collection features are shop-level, we'll add them to all products
            collection_data = {}
            if collection_features:
                # Use the first collection feature for all products (or you could aggregate them)
                cf = collection_features[0].model_dump()
                for product in core_products:
                    product_id = product.get("productId")
                    if product_id:
                        collection_data[product_id] = cf

            return collection_data

        except Exception as e:
            logger.warning(f"Failed to fetch collection data: {str(e)}")
            return {}

    async def _fetch_product_pair_data(
        self,
        shop_id: str,
        core_products: List[Dict],
        last_sync_timestamp: Optional[datetime] = None,
    ) -> Dict[str, Dict]:
        """Fetch product pair data if it exists"""
        try:
            if not core_products:
                return {}

            db = await self.pipeline._get_database()
            product_ids = [
                product["productId"]
                for product in core_products
                if product.get("productId")
            ]

            if not product_ids:
                return {}

            # For aggregation, we need to use raw SQL as Prisma doesn't support complex aggregations
            if last_sync_timestamp:
                query = """
                    SELECT 
                        "productId1" as "productId",
                        COUNT(DISTINCT "productId2") as "coPurchasePartners",
                        SUM("coPurchaseCount") as "totalCoPurchases",
                        AVG("supportScore") as "avgSupportScore",
                        AVG("liftScore") as "avgLiftScore"
                    FROM "ProductPairFeatures" 
                    WHERE "shopId" = $1 AND "productId1" = ANY($2) AND "lastComputedAt" >= $3::timestamp
                    GROUP BY "productId1"
                    
                    UNION ALL
                    
                    SELECT 
                        "productId2" as "productId",
                        COUNT(DISTINCT "productId1") as "coPurchasePartners",
                        SUM("coPurchaseCount") as "totalCoPurchases",
                        AVG("supportScore") as "avgSupportScore",
                        AVG("liftScore") as "avgLiftScore"
                    FROM "ProductPairFeatures" 
                    WHERE "shopId" = $1 AND "productId2" = ANY($2) AND "lastComputedAt" >= $3::timestamp
                    GROUP BY "productId2"
                """
                result = await db.query_raw(
                    query, shop_id, product_ids, last_sync_timestamp
                )
            else:
                query = """
                    SELECT 
                        "productId1" as "productId",
                        COUNT(DISTINCT "productId2") as "coPurchasePartners",
                        SUM("coPurchaseCount") as "totalCoPurchases",
                        AVG("supportScore") as "avgSupportScore",
                        AVG("liftScore") as "avgLiftScore"
                    FROM "ProductPairFeatures" 
                    WHERE "shopId" = $1 AND "productId1" = ANY($2)
                    GROUP BY "productId1"
                    
                    UNION ALL
                    
                    SELECT 
                        "productId2" as "productId",
                        COUNT(DISTINCT "productId1") as "coPurchasePartners",
                        SUM("coPurchaseCount") as "totalCoPurchases",
                        AVG("supportScore") as "avgSupportScore",
                        AVG("liftScore") as "avgLiftScore"
                    FROM "ProductPairFeatures" 
                    WHERE "shopId" = $1 AND "productId2" = ANY($2)
                    GROUP BY "productId2"
                """
                result = await db.query_raw(query, shop_id, product_ids)

            return {row["productId"]: dict(row) for row in result} if result else {}

        except Exception as e:
            logger.warning(f"Failed to fetch product pair data: {str(e)}")
            return {}

    async def _fetch_search_product_data(
        self,
        shop_id: str,
        core_products: List[Dict],
        last_sync_timestamp: Optional[datetime] = None,
    ) -> Dict[str, Dict]:
        """Fetch search product data if it exists"""
        try:
            if not core_products:
                return {}

            db = await self.pipeline._get_database()
            product_ids = [
                product["productId"]
                for product in core_products
                if product.get("productId")
            ]

            if not product_ids:
                return {}

            # For aggregation, we need to use raw SQL as Prisma doesn't support complex aggregations
            if last_sync_timestamp:
                query = """
                    SELECT 
                        "productId",
                        COUNT(DISTINCT "searchQuery") as "searchQueriesCount",
                        SUM("impressionCount") as "totalSearchImpressions",
                        SUM("clickCount") as "totalSearchClicks",
                        SUM("purchaseCount") as "totalSearchPurchases",
                        AVG("clickThroughRate") as "avgSearchCTR",
                        AVG("conversionRate") as "avgSearchConversionRate"
                    FROM "SearchProductFeatures" 
                    WHERE "shopId" = $1 AND "productId" = ANY($2) AND "lastComputedAt" >= $3::timestamp
                    GROUP BY "productId"
                """
                result = await db.query_raw(
                    query, shop_id, product_ids, last_sync_timestamp
                )
            else:
                query = """
                    SELECT 
                        "productId",
                        COUNT(DISTINCT "searchQuery") as "searchQueriesCount",
                        SUM("impressionCount") as "totalSearchImpressions",
                        SUM("clickCount") as "totalSearchClicks",
                        SUM("purchaseCount") as "totalSearchPurchases",
                        AVG("clickThroughRate") as "avgSearchCTR",
                        AVG("conversionRate") as "avgSearchConversionRate"
                    FROM "SearchProductFeatures" 
                    WHERE "shopId" = $1 AND "productId" = ANY($2)
                    GROUP BY "productId"
                """
                result = await db.query_raw(query, shop_id, product_ids)

            return {row["productId"]: dict(row) for row in result} if result else {}

        except Exception as e:
            logger.warning(f"Failed to fetch search product data: {str(e)}")
            return {}

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
                    "categories": json.dumps(
                        categories
                    ),  # Serialize to JSON string for raw SQL
                    "labels": json.dumps(
                        labels
                    ),  # Serialize to JSON string for raw SQL
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
