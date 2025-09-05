"""
Feature repository for handling all database operations related to ML features
"""

from typing import Dict, Any, List, Optional, Tuple
from abc import ABC, abstractmethod

from app.core.logging import get_logger
from app.core.database.simple_db_client import get_database
from app.shared.helpers import now_utc

logger = get_logger(__name__)


class IFeatureRepository(ABC):
    """Interface for feature repository operations"""

    @abstractmethod
    async def bulk_upsert_product_features(self, batch_data: List[tuple]) -> int:
        """Bulk upsert product features"""
        pass

    @abstractmethod
    async def bulk_upsert_customer_features(
        self, user_features_batch: List[tuple], behavior_features_batch: List[tuple]
    ) -> int:
        """Bulk upsert customer features"""
        pass

    @abstractmethod
    async def bulk_upsert_collection_features(self, batch_data: List[tuple]) -> int:
        """Bulk upsert collection features"""
        pass

    @abstractmethod
    async def bulk_upsert_interaction_features(self, batch_data: List[tuple]) -> int:
        """Bulk upsert interaction features"""
        pass

    @abstractmethod
    async def get_products_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of products for a shop"""
        pass

    @abstractmethod
    async def get_orders_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of orders for a shop"""
        pass

    @abstractmethod
    async def get_customers_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of customers for a shop"""
        pass

    @abstractmethod
    async def get_collections_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of collections for a shop"""
        pass

    @abstractmethod
    async def get_events_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of events for a shop"""
        pass

    @abstractmethod
    async def get_entity_count(self, shop_id: str, entity_table: str) -> int:
        """Get the total count of an entity for a shop"""
        pass

    @abstractmethod
    async def get_orders_batch_since(
        self, shop_id: str, since_timestamp: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of orders created since timestamp"""
        pass

    @abstractmethod
    async def get_products_batch_since(
        self, shop_id: str, since_timestamp: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of products updated since timestamp"""
        pass

    @abstractmethod
    async def get_customers_batch_since(
        self, shop_id: str, since_timestamp: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of customers updated since timestamp"""
        pass

    @abstractmethod
    async def get_collections_batch_since(
        self, shop_id: str, since_timestamp: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of collections updated since timestamp"""
        pass

    @abstractmethod
    async def get_orders_since(
        self, shop_id: str, since_timestamp: str
    ) -> List[Dict[str, Any]]:
        """Get orders created since timestamp"""
        pass

    @abstractmethod
    async def get_shop_last_computation_time(self, shop_id: str) -> str:
        """Get the last feature computation timestamp for a shop"""
        pass

    @abstractmethod
    async def update_shop_last_computation_time(
        self, shop_id: str, timestamp: str
    ) -> None:
        """Update the last feature computation timestamp for a shop"""
        pass

    @abstractmethod
    async def get_affected_entity_ids_from_orders(
        self, shop_id: str, since_timestamp: str
    ) -> Dict[str, List[str]]:
        """Extract affected product and customer IDs from new orders since timestamp"""
        pass

    @abstractmethod
    async def get_products_by_ids(
        self, shop_id: str, product_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Get products by their IDs for processing"""
        pass

    @abstractmethod
    async def get_customers_by_ids(
        self, shop_id: str, customer_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Get customers by their IDs for processing"""
        pass

    @abstractmethod
    async def get_orders_for_customer_ids(
        self, shop_id: str, customer_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Get all orders for a batch of customer IDs"""
        pass

    @abstractmethod
    async def get_events_for_customer_ids(
        self, shop_id: str, customer_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Get all events for a batch of customer IDs"""
        pass


class FeatureRepository(IFeatureRepository):
    """Repository for handling all feature-related database operations"""

    def __init__(self):
        self._db_client = None

    async def _get_database(self):
        """Get or initialize the database client"""
        if self._db_client is None:
            self._db_client = await get_database()
        return self._db_client

    async def bulk_upsert_product_features(self, batch_data: List[tuple]) -> int:
        """Bulk upsert product features using a single query with multiple VALUES"""
        try:
            if not batch_data:
                return 0

            db = await self._get_database()

            # Build a single query with multiple VALUES clauses
            values_clauses = []
            params = []
            param_index = 1

            for data in batch_data:
                values_clause = f"(${param_index}, ${param_index + 1}, ${param_index + 2}, ${param_index + 3}, ${param_index + 4}, ${param_index + 5}, ${param_index + 6}, ${param_index + 7}, ${param_index + 8}, ${param_index + 9}, ${param_index + 10})"
                values_clauses.append(values_clause)
                params.extend(data)
                param_index += 11

            bulk_upsert_query = f"""
            INSERT INTO "ProductFeatures" (
                "shopId", "productId", "popularity", "priceTier", "category",
                "variantComplexity", "imageRichness", "tagDiversity", 
                "categoryEncoded", "vendorScore", "lastComputedAt"
            ) VALUES {', '.join(values_clauses)}
            ON CONFLICT ("shopId", "productId") 
            DO UPDATE SET
                "popularity" = EXCLUDED."popularity",
                "priceTier" = EXCLUDED."priceTier",
                "category" = EXCLUDED."category",
                "variantComplexity" = EXCLUDED."variantComplexity",
                "imageRichness" = EXCLUDED."imageRichness",
                "tagDiversity" = EXCLUDED."tagDiversity",
                "categoryEncoded" = EXCLUDED."categoryEncoded",
                "vendorScore" = EXCLUDED."vendorScore",
                "lastComputedAt" = EXCLUDED."lastComputedAt"
            """

            # Execute single bulk query
            await db.execute_raw(bulk_upsert_query, *params)

            return len(batch_data)

        except Exception as e:
            logger.error(f"Failed to bulk upsert product features: {str(e)}")
            return 0

    async def bulk_upsert_customer_features(
        self, user_features_batch: List[tuple], behavior_features_batch: List[tuple]
    ) -> int:
        """Bulk upsert customer features using single queries with multiple VALUES"""
        try:
            total_saved = 0
            db = await self._get_database()

            # Bulk upsert user features
            if user_features_batch:
                # Build a single query with multiple VALUES clauses for user features
                values_clauses = []
                params = []
                param_index = 1

                for data in user_features_batch:
                    values_clause = f"(${param_index}, ${param_index + 1}, ${param_index + 2}, ${param_index + 3}, ${param_index + 4}, ${param_index + 5}, ${param_index + 6}, ${param_index + 7})"
                    values_clauses.append(values_clause)
                    params.extend(data)
                    param_index += 8

                user_upsert_query = f"""
                INSERT INTO "UserFeatures" (
                    "shopId", "customerId", "totalPurchases", "totalSpent", "recencyDays",
                    "avgPurchaseIntervalDays", "preferredCategory", "lastComputedAt"
                ) VALUES {', '.join(values_clauses)}
                ON CONFLICT ("shopId", "customerId") 
                DO UPDATE SET
                    "totalPurchases" = EXCLUDED."totalPurchases",
                    "totalSpent" = EXCLUDED."totalSpent",
                    "recencyDays" = EXCLUDED."recencyDays",
                    "avgPurchaseIntervalDays" = EXCLUDED."avgPurchaseIntervalDays",
                    "preferredCategory" = EXCLUDED."preferredCategory",
                    "lastComputedAt" = EXCLUDED."lastComputedAt"
                """

                await db.execute_raw(user_upsert_query, *params)
                total_saved += len(user_features_batch)

            # Bulk upsert behavior features
            if behavior_features_batch:
                # Build a single query with multiple VALUES clauses for behavior features
                values_clauses = []
                params = []
                param_index = 1

                for data in behavior_features_batch:
                    values_clause = f"(${param_index}, ${param_index + 1}, ${param_index + 2}, ${param_index + 3}, ${param_index + 4}, ${param_index + 5}, ${param_index + 6}, ${param_index + 7}, ${param_index + 8}, ${param_index + 9}, ${param_index + 10}, ${param_index + 11})"
                    values_clauses.append(values_clause)
                    params.extend(data)
                    param_index += 12

                behavior_upsert_query = f"""
                INSERT INTO "CustomerBehaviorFeatures" (
                    "shopId", "customerId", "eventDiversity", "eventFrequency", "daysSinceFirstEvent",
                    "daysSinceLastEvent", "purchaseFrequency", "engagementScore", "recencyScore", 
                    "diversityScore", "behavioralScore", "lastComputedAt"
                ) VALUES {', '.join(values_clauses)}
                ON CONFLICT ("shopId", "customerId") 
                DO UPDATE SET
                    "eventDiversity" = EXCLUDED."eventDiversity",
                    "eventFrequency" = EXCLUDED."eventFrequency",
                    "daysSinceFirstEvent" = EXCLUDED."daysSinceFirstEvent",
                    "daysSinceLastEvent" = EXCLUDED."daysSinceLastEvent",
                    "purchaseFrequency" = EXCLUDED."purchaseFrequency",
                    "engagementScore" = EXCLUDED."engagementScore",
                    "recencyScore" = EXCLUDED."recencyScore",
                    "diversityScore" = EXCLUDED."diversityScore",
                    "behavioralScore" = EXCLUDED."behavioralScore",
                    "lastComputedAt" = EXCLUDED."lastComputedAt"
                """

                await db.execute_raw(behavior_upsert_query, *params)
                total_saved += len(behavior_features_batch)

            return total_saved

        except Exception as e:
            logger.error(f"Failed to bulk upsert customer features: {str(e)}")
            return 0

    async def bulk_upsert_collection_features(self, batch_data: List[tuple]) -> int:
        """Bulk upsert collection features using a single query with multiple VALUES"""
        try:
            if not batch_data:
                return 0

            db = await self._get_database()

            # Build a single query with multiple VALUES clauses
            values_clauses = []
            params = []
            param_index = 1

            for data in batch_data:
                values_clause = f"(${param_index}, ${param_index + 1}, ${param_index + 2}, ${param_index + 3}, ${param_index + 4}, ${param_index + 5}, ${param_index + 6}, ${param_index + 7})"
                values_clauses.append(values_clause)
                params.extend(data)
                param_index += 8

            collection_upsert_query = f"""
            INSERT INTO "CollectionFeatures" (
                "shopId", "collectionId", "productCount", "isAutomated", "performanceScore",
                "seoScore", "imageScore", "lastComputedAt"
            ) VALUES {', '.join(values_clauses)}
            ON CONFLICT ("shopId", "collectionId") 
            DO UPDATE SET
                "productCount" = EXCLUDED."productCount",
                "isAutomated" = EXCLUDED."isAutomated",
                "performanceScore" = EXCLUDED."performanceScore",
                "seoScore" = EXCLUDED."seoScore",
                "imageScore" = EXCLUDED."imageScore",
                "lastComputedAt" = EXCLUDED."lastComputedAt"
            """

            # Execute single bulk query
            await db.execute_raw(collection_upsert_query, *params)

            return len(batch_data)

        except Exception as e:
            logger.error(f"Failed to bulk upsert collection features: {str(e)}")
            return 0

    async def bulk_upsert_interaction_features(self, batch_data: List[tuple]) -> int:
        """Bulk upsert interaction features using a single query with multiple VALUES"""
        try:
            if not batch_data:
                return 0

            db = await self._get_database()

            # Build a single query with multiple VALUES clauses
            values_clauses = []
            params = []
            param_index = 1

            for data in batch_data:
                values_clause = f"(${param_index}, ${param_index + 1}, ${param_index + 2}, ${param_index + 3}, ${param_index + 4}, ${param_index + 5}, ${param_index + 6})"
                values_clauses.append(values_clause)
                params.extend(data)
                param_index += 7

            interaction_upsert_query = f"""
            INSERT INTO "InteractionFeatures" (
                "shopId", "customerId", "productId", "purchaseCount",
                "lastPurchaseDate", "timeDecayedWeight", "lastComputedAt"
            ) VALUES {', '.join(values_clauses)}
            ON CONFLICT ("shopId", "customerId", "productId") 
            DO UPDATE SET
                "purchaseCount" = EXCLUDED."purchaseCount",
                "lastPurchaseDate" = EXCLUDED."lastPurchaseDate",
                "timeDecayedWeight" = EXCLUDED."timeDecayedWeight",
                "lastComputedAt" = EXCLUDED."lastComputedAt"
            """

            # Execute single bulk query
            await db.execute_raw(interaction_upsert_query, *params)

            return len(batch_data)

        except Exception as e:
            logger.error(f"Failed to bulk upsert interaction features: {str(e)}")
            return 0

    async def get_products_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of products for a shop"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "ShopifyProduct" WHERE "shopId" = $1 ORDER BY "id" LIMIT $2 OFFSET $3'
            result = await db.query_raw(query, shop_id, limit, offset)
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(f"Failed to get products batch for shop {shop_id}: {str(e)}")
            return []

    async def get_orders_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of orders for a shop"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "ShopifyOrder" WHERE "shopId" = $1 ORDER BY "id" LIMIT $2 OFFSET $3'
            result = await db.query_raw(query, shop_id, limit, offset)
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(f"Failed to get orders batch for shop {shop_id}: {str(e)}")
            return []

    async def get_customers_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of customers for a shop"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "ShopifyCustomer" WHERE "shopId" = $1 ORDER BY "id" LIMIT $2 OFFSET $3'
            result = await db.query_raw(query, shop_id, limit, offset)
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(f"Failed to get customers batch for shop {shop_id}: {str(e)}")
            return []

    async def get_collections_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of collections for a shop"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "ShopifyCollection" WHERE "shopId" = $1 ORDER BY "id" LIMIT $2 OFFSET $3'
            result = await db.query_raw(query, shop_id, limit, offset)
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(
                f"Failed to get collections batch for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_events_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of events for a shop"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "ShopifyEvent" WHERE "shopId" = $1 ORDER BY "id" LIMIT $2 OFFSET $3'
            result = await db.query_raw(query, shop_id, limit, offset)
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(f"Failed to get events batch for shop {shop_id}: {str(e)}")
            return []

    async def get_entity_count(self, shop_id: str, entity_table: str) -> int:
        """Get the total count of an entity for a shop"""
        try:
            db = await self._get_database()
            query = (
                f'SELECT COUNT(*) as count FROM "{entity_table}" WHERE "shopId" = $1'
            )
            result = await db.query_raw(query, shop_id)
            return result[0]["count"] if result else 0
        except Exception as e:
            logger.error(
                f"Failed to get entity count for {entity_table} in shop {shop_id}: {str(e)}"
            )
            return 0

    async def get_orders_batch_since(
        self, shop_id: str, since_timestamp: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of orders created since timestamp"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "ShopifyOrder" WHERE "shopId" = $1 AND "createdAt" > $2 ORDER BY "createdAt" LIMIT $3 OFFSET $4'
            result = await db.query_raw(query, shop_id, since_timestamp, limit, offset)
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(
                f"Failed to get orders batch since {since_timestamp} for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_products_batch_since(
        self, shop_id: str, since_timestamp: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of products updated since timestamp"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "ShopifyProduct" WHERE "shopId" = $1 AND "updatedAt" > $2 ORDER BY "updatedAt" LIMIT $3 OFFSET $4'
            result = await db.query_raw(query, shop_id, since_timestamp, limit, offset)
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(
                f"Failed to get products batch since {since_timestamp} for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_customers_batch_since(
        self, shop_id: str, since_timestamp: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of customers updated since timestamp"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "ShopifyCustomer" WHERE "shopId" = $1 AND "updatedAt" > $2 ORDER BY "updatedAt" LIMIT $3 OFFSET $4'
            result = await db.query_raw(query, shop_id, since_timestamp, limit, offset)
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(
                f"Failed to get customers batch since {since_timestamp} for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_collections_batch_since(
        self, shop_id: str, since_timestamp: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of collections updated since timestamp"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "ShopifyCollection" WHERE "shopId" = $1 AND "updatedAt" > $2 ORDER BY "updatedAt" LIMIT $3 OFFSET $4'
            result = await db.query_raw(query, shop_id, since_timestamp, limit, offset)
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(
                f"Failed to get collections batch since {since_timestamp} for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_orders_since(
        self, shop_id: str, since_timestamp: str
    ) -> List[Dict[str, Any]]:
        """Get orders created since timestamp"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "ShopifyOrder" WHERE "shopId" = $1 AND "createdAt" > $2 ORDER BY "createdAt"'
            result = await db.query_raw(query, shop_id, since_timestamp)
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(
                f"Failed to get orders since {since_timestamp} for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_shop_last_computation_time(self, shop_id: str) -> str:
        """Get the last feature computation timestamp for a shop"""
        try:
            db = await self._get_database()
            query = (
                'SELECT "lastFeatureComputationAt" FROM "ShopifyShop" WHERE "id" = $1'
            )
            result = await db.query_raw(query, shop_id)
            if result and result[0].get("lastFeatureComputationAt"):
                return result[0]["lastFeatureComputationAt"]
            # Return a very old timestamp for first run
            return "1970-01-01T00:00:00Z"
        except Exception as e:
            logger.error(
                f"Failed to get last computation time for shop {shop_id}: {str(e)}"
            )
            return "1970-01-01T00:00:00Z"

    async def update_shop_last_computation_time(
        self, shop_id: str, timestamp: str
    ) -> None:
        """Update the last feature computation timestamp for a shop"""
        try:
            db = await self._get_database()
            query = 'UPDATE "ShopifyShop" SET "lastFeatureComputationAt" = $1 WHERE "id" = $2'
            await db.execute_raw(query, timestamp, shop_id)
        except Exception as e:
            logger.error(
                f"Failed to update last computation time for shop {shop_id}: {str(e)}"
            )

    async def get_affected_entity_ids_from_orders(
        self, shop_id: str, since_timestamp: str
    ) -> Dict[str, List[str]]:
        """Extract affected product and customer IDs from new orders since timestamp"""
        try:
            db = await self._get_database()

            # Query to get all unique product and customer IDs from new orders
            query = """
            SELECT DISTINCT 
                o."customerId",
                li."productId"
            FROM "ShopifyOrder" o
            JOIN "ShopifyLineItem" li ON o."id" = li."orderId"
            WHERE o."shopId" = $1 
            AND o."createdAt" > $2
            AND o."customerId" IS NOT NULL
            AND li."productId" IS NOT NULL
            """

            result = await db.query_raw(query, shop_id, since_timestamp)

            # Extract unique IDs
            customer_ids = set()
            product_ids = set()

            for row in result:
                if row.get("customerId"):
                    customer_ids.add(row["customerId"])
                if row.get("productId"):
                    product_ids.add(row["productId"])

            return {
                "customer_ids": list(customer_ids),
                "product_ids": list(product_ids),
            }

        except Exception as e:
            logger.error(
                f"Failed to get affected entity IDs from orders for shop {shop_id}: {str(e)}"
            )
            return {"customer_ids": [], "product_ids": []}

    async def get_products_by_ids(
        self, shop_id: str, product_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Get products by their IDs for processing"""
        try:
            if not product_ids:
                return []

            db = await self._get_database()

            # Create placeholders for the IN clause
            placeholders = ",".join([f"${i+2}" for i in range(len(product_ids))])
            query = f'SELECT * FROM "ShopifyProduct" WHERE "shopId" = $1 AND "id" IN ({placeholders})'

            result = await db.query_raw(query, shop_id, *product_ids)
            return [dict(row) for row in result] if result else []

        except Exception as e:
            logger.error(f"Failed to get products by IDs for shop {shop_id}: {str(e)}")
            return []

    async def get_customers_by_ids(
        self, shop_id: str, customer_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Get customers by their IDs for processing"""
        try:
            if not customer_ids:
                return []

            db = await self._get_database()

            # Create placeholders for the IN clause
            placeholders = ",".join([f"${i+2}" for i in range(len(customer_ids))])
            query = f'SELECT * FROM "ShopifyCustomer" WHERE "shopId" = $1 AND "id" IN ({placeholders})'

            result = await db.query_raw(query, shop_id, *customer_ids)
            return [dict(row) for row in result] if result else []

        except Exception as e:
            logger.error(f"Failed to get customers by IDs for shop {shop_id}: {str(e)}")
            return []

    async def get_orders_for_customer_ids(
        self, shop_id: str, customer_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Get all orders for a batch of customer IDs"""
        try:
            if not customer_ids:
                return []

            db = await self._get_database()

            # Create placeholders for the IN clause
            placeholders = ",".join([f"${i+2}" for i in range(len(customer_ids))])
            query = f'SELECT * FROM "ShopifyOrder" WHERE "shopId" = $1 AND "customerId" IN ({placeholders})'

            result = await db.query_raw(query, shop_id, *customer_ids)
            return [dict(row) for row in result] if result else []

        except Exception as e:
            logger.error(
                f"Failed to get orders for customer IDs for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_events_for_customer_ids(
        self, shop_id: str, customer_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Get all events for a batch of customer IDs"""
        try:
            if not customer_ids:
                return []

            db = await self._get_database()

            # Create placeholders for the IN clause
            placeholders = ",".join([f"${i+2}" for i in range(len(customer_ids))])
            query = f'SELECT * FROM "ShopifyCustomerEvent" WHERE "shopId" = $1 AND "customerId" IN ({placeholders})'

            result = await db.query_raw(query, shop_id, *customer_ids)
            return [dict(row) for row in result] if result else []

        except Exception as e:
            logger.error(
                f"Failed to get events for customer IDs for shop {shop_id}: {str(e)}"
            )
            return []
