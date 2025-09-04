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
    async def get_shop_data(self, shop_id: str) -> Dict[str, Any]:
        """Get all shop data for feature computation"""
        pass

    @abstractmethod
    async def get_products_for_shop(self, shop_id: str) -> List[Dict[str, Any]]:
        """Get all products for a shop"""
        pass

    @abstractmethod
    async def get_orders_for_shop(self, shop_id: str) -> List[Dict[str, Any]]:
        """Get all orders for a shop"""
        pass

    @abstractmethod
    async def get_customers_for_shop(self, shop_id: str) -> List[Dict[str, Any]]:
        """Get all customers for a shop"""
        pass

    @abstractmethod
    async def get_collections_for_shop(self, shop_id: str) -> List[Dict[str, Any]]:
        """Get all collections for a shop"""
        pass

    @abstractmethod
    async def get_events_for_shop(self, shop_id: str) -> List[Dict[str, Any]]:
        """Get all customer events for a shop"""
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
        """Bulk upsert product features using parameterized queries to avoid SQL injection"""
        try:
            if not batch_data:
                return 0

            db = await self._get_database()

            # Use parameterized query to prevent SQL injection
            bulk_upsert_query = """
            INSERT INTO "ProductFeatures" (
                "shopId", "productId", "popularity", "priceTier", "category",
                "variantComplexity", "imageRichness", "tagDiversity", 
                "categoryEncoded", "vendorScore", "lastComputedAt"
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
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

            # Execute each row as a separate parameterized query
            for data in batch_data:
                await db.execute_raw(bulk_upsert_query, *data)

            return len(batch_data)

        except Exception as e:
            logger.error(f"Failed to bulk upsert product features: {str(e)}")
            return 0

    async def bulk_upsert_customer_features(
        self, user_features_batch: List[tuple], behavior_features_batch: List[tuple]
    ) -> int:
        """Bulk upsert customer features using parameterized queries to avoid SQL injection"""
        try:
            total_saved = 0
            db = await self._get_database()

            # Bulk upsert user features
            if user_features_batch:
                user_upsert_query = """
                INSERT INTO "UserFeatures" (
                    "shopId", "customerId", "totalPurchases", "totalSpent", "recencyDays",
                    "avgPurchaseIntervalDays", "preferredCategory", "lastComputedAt"
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT ("shopId", "customerId") 
                DO UPDATE SET
                    "totalPurchases" = EXCLUDED."totalPurchases",
                    "totalSpent" = EXCLUDED."totalSpent",
                    "recencyDays" = EXCLUDED."recencyDays",
                    "avgPurchaseIntervalDays" = EXCLUDED."avgPurchaseIntervalDays",
                    "preferredCategory" = EXCLUDED."preferredCategory",
                    "lastComputedAt" = EXCLUDED."lastComputedAt"
                """

                for data in user_features_batch:
                    await db.execute_raw(user_upsert_query, *data)

                total_saved += len(user_features_batch)

            # Bulk upsert behavior features
            if behavior_features_batch:
                behavior_upsert_query = """
                INSERT INTO "CustomerBehaviorFeatures" (
                    "shopId", "customerId", "eventDiversity", "eventFrequency", "daysSinceFirstEvent",
                    "daysSinceLastEvent", "purchaseFrequency", "engagementScore", "recencyScore", 
                    "diversityScore", "behavioralScore", "lastComputedAt"
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
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

                for data in behavior_features_batch:
                    await db.execute_raw(behavior_upsert_query, *data)

                total_saved += len(behavior_features_batch)

            return total_saved

        except Exception as e:
            logger.error(f"Failed to bulk upsert customer features: {str(e)}")
            return 0

    async def bulk_upsert_collection_features(self, batch_data: List[tuple]) -> int:
        """Bulk upsert collection features using parameterized queries to avoid SQL injection"""
        try:
            if not batch_data:
                return 0

            db = await self._get_database()

            collection_upsert_query = """
            INSERT INTO "CollectionFeatures" (
                "shopId", "collectionId", "productCount", "isAutomated", "performanceScore",
                "seoScore", "imageScore", "lastComputedAt"
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT ("shopId", "collectionId") 
            DO UPDATE SET
                "productCount" = EXCLUDED."productCount",
                "isAutomated" = EXCLUDED."isAutomated",
                "performanceScore" = EXCLUDED."performanceScore",
                "seoScore" = EXCLUDED."seoScore",
                "imageScore" = EXCLUDED."imageScore",
                "lastComputedAt" = EXCLUDED."lastComputedAt"
            """

            for data in batch_data:
                await db.execute_raw(collection_upsert_query, *data)

            return len(batch_data)

        except Exception as e:
            logger.error(f"Failed to bulk upsert collection features: {str(e)}")
            return 0

    async def bulk_upsert_interaction_features(self, batch_data: List[tuple]) -> int:
        """Bulk upsert interaction features using parameterized queries to avoid SQL injection"""
        try:
            if not batch_data:
                return 0

            db = await self._get_database()

            interaction_upsert_query = """
            INSERT INTO "InteractionFeatures" (
                "shopId", "customerId", "productId", "purchaseCount",
                "lastPurchaseDate", "timeDecayedWeight", "lastComputedAt"
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT ("shopId", "customerId", "productId") 
            DO UPDATE SET
                "purchaseCount" = EXCLUDED."purchaseCount",
                "lastPurchaseDate" = EXCLUDED."lastPurchaseDate",
                "timeDecayedWeight" = EXCLUDED."timeDecayedWeight",
                "lastComputedAt" = EXCLUDED."lastComputedAt"
            """

            for data in batch_data:
                await db.execute_raw(interaction_upsert_query, *data)

            return len(batch_data)

        except Exception as e:
            logger.error(f"Failed to bulk upsert interaction features: {str(e)}")
            return 0

    async def get_shop_data(self, shop_id: str) -> Dict[str, Any]:
        """Get all shop data for feature computation"""
        try:
            db = await self._get_database()

            # Get shop info
            shop_query = 'SELECT * FROM "ShopifyShop" WHERE "id" = $1'
            shop_result = await db.fetch_one(shop_query, shop_id)

            if not shop_result:
                logger.warning(f"Shop not found: {shop_id}")
                return {}

            return {
                "shop": shop_result,
                "products": await self.get_products_for_shop(shop_id),
                "orders": await self.get_orders_for_shop(shop_id),
                "customers": await self.get_customers_for_shop(shop_id),
                "collections": await self.get_collections_for_shop(shop_id),
                "events": await self.get_events_for_shop(shop_id),
            }

        except Exception as e:
            logger.error(f"Failed to get shop data for {shop_id}: {str(e)}")
            return {}

    async def get_products_for_shop(self, shop_id: str) -> List[Dict[str, Any]]:
        """Get all products for a shop"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "ShopifyProduct" WHERE "shopId" = $1'
            return await db.fetch_all(query, shop_id)
        except Exception as e:
            logger.error(f"Failed to get products for shop {shop_id}: {str(e)}")
            return []

    async def get_orders_for_shop(self, shop_id: str) -> List[Dict[str, Any]]:
        """Get all orders for a shop"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "ShopifyOrder" WHERE "shopId" = $1'
            return await db.fetch_all(query, shop_id)
        except Exception as e:
            logger.error(f"Failed to get orders for shop {shop_id}: {str(e)}")
            return []

    async def get_customers_for_shop(self, shop_id: str) -> List[Dict[str, Any]]:
        """Get all customers for a shop"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "ShopifyCustomer" WHERE "shopId" = $1'
            return await db.fetch_all(query, shop_id)
        except Exception as e:
            logger.error(f"Failed to get customers for shop {shop_id}: {str(e)}")
            return []

    async def get_collections_for_shop(self, shop_id: str) -> List[Dict[str, Any]]:
        """Get all collections for a shop"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "ShopifyCollection" WHERE "shopId" = $1'
            return await db.fetch_all(query, shop_id)
        except Exception as e:
            logger.error(f"Failed to get collections for shop {shop_id}: {str(e)}")
            return []

    async def get_events_for_shop(self, shop_id: str) -> List[Dict[str, Any]]:
        """Get all customer events for a shop"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "ShopifyCustomerEvent" WHERE "shopId" = $1'
            return await db.fetch_all(query, shop_id)
        except Exception as e:
            logger.error(f"Failed to get events for shop {shop_id}: {str(e)}")
            return []
