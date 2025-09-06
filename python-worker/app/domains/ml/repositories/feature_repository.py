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
    async def update_shop_last_computation_time(self, shop_id: str, timestamp) -> None:
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
        """Bulk upsert product features using Prisma native methods"""
        try:
            if not batch_data:
                return 0

            db = await self._get_database()

            # Convert tuple data to Prisma format
            create_data = []
            for data in batch_data:
                if len(data) != 11:
                    logger.error(
                        f"Invalid batch data length: {len(data)}, expected 11. Data: {data}"
                    )
                    continue

                # Convert tuple to dict format expected by Prisma
                feature_data = {
                    "shopId": data[0],
                    "productId": data[1],
                    "popularity": data[2],
                    "priceTier": data[3],
                    "category": data[4],
                    "variantComplexity": data[5],
                    "imageRichness": data[6],
                    "tagDiversity": data[7],
                    "categoryEncoded": data[8],
                    "vendorScore": data[9],
                    # lastComputedAt will be set automatically by the database
                }
                create_data.append(feature_data)

            if not create_data:
                return 0

            # Use Prisma's create_many with skip_duplicates for bulk insert
            try:
                await db.productfeatures.create_many(
                    data=create_data, skip_duplicates=True
                )
                return len(create_data)
            except Exception as create_error:
                # Fallback to individual upserts if batch insert fails
                logger.warning(
                    f"Batch insert failed, falling back to individual upserts: {str(create_error)}"
                )

                success_count = 0
                for feature_data in create_data:
                    try:
                        await db.productfeatures.upsert(
                            where={
                                "shopId_productId": {
                                    "shopId": feature_data["shopId"],
                                    "productId": feature_data["productId"],
                                }
                            },
                            data=feature_data,
                            update=feature_data,
                        )
                        success_count += 1
                    except Exception as upsert_error:
                        logger.error(
                            f"Failed to upsert product feature {feature_data.get('productId')}: {str(upsert_error)}"
                        )
                        continue

                return success_count

        except Exception as e:
            logger.error(f"Failed to bulk upsert product features: {str(e)}")
            return 0

    async def bulk_upsert_customer_features(
        self, user_features_batch: List[tuple], behavior_features_batch: List[tuple]
    ) -> int:
        """Bulk upsert customer features using Prisma native methods"""
        try:
            total_saved = 0
            db = await self._get_database()

            # Bulk upsert user features
            if user_features_batch:
                user_create_data = []
                for data in user_features_batch:
                    if len(data) != 8:  # 7 fields + timestamp
                        logger.error(
                            f"Invalid user features batch data length: {len(data)}, expected 8"
                        )
                        continue

                    user_data = {
                        "shopId": data[0],
                        "customerId": data[1],
                        "totalPurchases": data[2],
                        "totalSpent": data[3],
                        "recencyDays": data[4],
                        "avgPurchaseIntervalDays": data[5],
                        "preferredCategory": data[6],
                    }
                    user_create_data.append(user_data)

                if user_create_data:
                    try:
                        await db.userfeatures.create_many(
                            data=user_create_data, skip_duplicates=True
                        )
                        total_saved += len(user_create_data)
                    except Exception as create_error:
                        logger.warning(
                            f"User features batch insert failed, falling back to individual upserts: {str(create_error)}"
                        )

                        for user_data in user_create_data:
                            try:
                                await db.userfeatures.upsert(
                                    where={
                                        "shopId_customerId": {
                                            "shopId": user_data["shopId"],
                                            "customerId": user_data["customerId"],
                                        }
                                    },
                                    data=user_data,
                                    update=user_data,
                                )
                                total_saved += 1
                            except Exception as upsert_error:
                                logger.error(
                                    f"Failed to upsert user feature {user_data.get('customerId')}: {str(upsert_error)}"
                                )
                                continue

            # Bulk upsert behavior features
            if behavior_features_batch:
                behavior_create_data = []
                for data in behavior_features_batch:
                    if len(data) != 12:  # 11 fields + timestamp
                        logger.error(
                            f"Invalid behavior features batch data length: {len(data)}, expected 12"
                        )
                        continue

                    behavior_data = {
                        "shopId": data[0],
                        "customerId": data[1],
                        "eventDiversity": data[2],
                        "eventFrequency": data[3],
                        "daysSinceFirstEvent": data[4],
                        "daysSinceLastEvent": data[5],
                        "purchaseFrequency": data[6],
                        "engagementScore": data[7],
                        "recencyScore": data[8],
                        "diversityScore": data[9],
                        "behavioralScore": data[10],
                    }
                    behavior_create_data.append(behavior_data)

                if behavior_create_data:
                    try:
                        await db.customerbehaviorfeatures.create_many(
                            data=behavior_create_data, skip_duplicates=True
                        )
                        total_saved += len(behavior_create_data)
                    except Exception as create_error:
                        logger.warning(
                            f"Behavior features batch insert failed, falling back to individual upserts: {str(create_error)}"
                        )

                        for behavior_data in behavior_create_data:
                            try:
                                await db.customerbehaviorfeatures.upsert(
                                    where={
                                        "shopId_customerId": {
                                            "shopId": behavior_data["shopId"],
                                            "customerId": behavior_data["customerId"],
                                        }
                                    },
                                    data=behavior_data,
                                    update=behavior_data,
                                )
                                total_saved += 1
                            except Exception as upsert_error:
                                logger.error(
                                    f"Failed to upsert behavior feature {behavior_data.get('customerId')}: {str(upsert_error)}"
                                )
                                continue

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
                values_clause = f"(${param_index}, ${param_index + 1}, ${param_index + 2}, ${param_index + 3}, ${param_index + 4}, ${param_index + 5}, ${param_index + 6}, NOW())"
                values_clauses.append(values_clause)
                params.extend(data[:-1])  # Remove the last element (timestamp)
                param_index += 7

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
                "lastComputedAt" = NOW()
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
                values_clause = f"(${param_index}, ${param_index + 1}, ${param_index + 2}, ${param_index + 3}, ${param_index + 4}, ${param_index + 5}, NOW())"
                values_clauses.append(values_clause)
                params.extend(data[:-1])  # Remove the last element (timestamp)
                param_index += 6

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
                "lastComputedAt" = NOW()
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
        """Get a batch of products for a shop from main table"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "ProductData" WHERE "shopId" = $1 ORDER BY "id" LIMIT $2 OFFSET $3'
            result = await db.query_raw(query, shop_id, limit, offset)
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(f"Failed to get products batch for shop {shop_id}: {str(e)}")
            return []

    async def get_orders_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of orders for a shop from main table"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "OrderData" WHERE "shopId" = $1 ORDER BY "id" LIMIT $2 OFFSET $3'
            result = await db.query_raw(query, shop_id, limit, offset)
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(f"Failed to get orders batch for shop {shop_id}: {str(e)}")
            return []

    async def get_customers_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of customers for a shop from main table"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "CustomerData" WHERE "shopId" = $1 ORDER BY "id" LIMIT $2 OFFSET $3'
            result = await db.query_raw(query, shop_id, limit, offset)
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(f"Failed to get customers batch for shop {shop_id}: {str(e)}")
            return []

    async def get_collections_batch(
        self, shop_id: str, limit: int, offset: int
    ) -> List[Dict[str, Any]]:
        """Get a batch of collections for a shop from main table"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "CollectionData" WHERE "shopId" = $1 ORDER BY "id" LIMIT $2 OFFSET $3'
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
            query = 'SELECT * FROM "ShopifyE" WHERE "shopId" = $1 ORDER BY "id" LIMIT $2 OFFSET $3'
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
            query = 'SELECT * FROM "OrderData" WHERE "shopId" = $1 AND "createdAt" > $2::timestamp ORDER BY "createdAt" LIMIT $3 OFFSET $4'
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
        """Get a batch of products updated since timestamp from main table"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "ProductData" WHERE "shopId" = $1 AND "updatedAt" > $2::timestamp ORDER BY "updatedAt" LIMIT $3 OFFSET $4'
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
        """Get a batch of customers updated since timestamp from main table"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "CustomerData" WHERE "shopId" = $1 AND "updatedAt" > $2::timestamp ORDER BY "updatedAt" LIMIT $3 OFFSET $4'
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
        """Get a batch of collections updated since timestamp from main table"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "CollectionData" WHERE "shopId" = $1 AND "updatedAt" > $2::timestamp ORDER BY "updatedAt" LIMIT $3 OFFSET $4'
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
        """Get orders created since timestamp from main table"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "OrderData" WHERE "shopId" = $1 AND "createdAt" > $2::timestamp ORDER BY "createdAt"'
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
            query = 'SELECT "lastAnalysisAt" FROM "Shop" WHERE "id" = $1'
            result = await db.query_raw(query, shop_id)
            if result and result[0].get("lastAnalysisAt"):
                return result[0]["lastAnalysisAt"]
            # Return a very old timestamp for first run
            return "1970-01-01T00:00:00Z"
        except Exception as e:
            logger.error(
                f"Failed to get last computation time for shop {shop_id}: {str(e)}"
            )
            return "1970-01-01T00:00:00Z"

    async def update_shop_last_computation_time(self, shop_id: str, timestamp) -> None:
        """Update the last feature computation timestamp for a shop"""
        try:
            db = await self._get_database()
            # Convert timestamp to ISO format string if it's a datetime object
            if hasattr(timestamp, "isoformat"):
                timestamp_str = timestamp.isoformat()
            else:
                timestamp_str = str(timestamp)

            query = 'UPDATE "Shop" SET "lastAnalysisAt" = $1 WHERE "id" = $2'
            await db.execute_raw(query, timestamp_str, shop_id)
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
            # Note: lineItems are stored as JSON in OrderData table
            query = """
            SELECT DISTINCT 
                o."customerId",
                jsonb_array_elements(o."lineItems")->>'productId' as "productId"
            FROM "OrderData" o
            WHERE o."shopId" = $1 
            AND o."createdAt" > $2::timestamp
            AND o."customerId" IS NOT NULL
            AND o."lineItems" IS NOT NULL
            AND jsonb_array_length(o."lineItems") > 0
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
            query = f'SELECT * FROM "ProductData" WHERE "shopId" = $1 AND "id" IN ({placeholders})'

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
            query = f'SELECT * FROM "CustomerData" WHERE "shopId" = $1 AND "id" IN ({placeholders})'

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
            query = f'SELECT * FROM "OrderData" WHERE "shopId" = $1 AND "customerId" IN ({placeholders})'

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
        """Get all behavioral events for a batch of customer IDs"""
        try:
            if not customer_ids:
                return []

            db = await self._get_database()

            # Create placeholders for the IN clause
            placeholders = ",".join([f"${i+2}" for i in range(len(customer_ids))])
            query = f'SELECT * FROM "BehavioralEvents" WHERE "shopId" = $1 AND "customerId" IN ({placeholders}) ORDER BY "occurredAt" DESC'

            result = await db.query_raw(query, shop_id, *customer_ids)
            return [dict(row) for row in result] if result else []

        except Exception as e:
            logger.error(
                f"Failed to get behavioral events for customer IDs for shop {shop_id}: {str(e)}"
            )
            return []
