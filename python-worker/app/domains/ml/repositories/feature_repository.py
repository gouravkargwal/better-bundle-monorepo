"""
Feature repository for handling all database operations related to ML features
"""

from typing import Dict, Any, List
from abc import ABC, abstractmethod

from app.core.logging import get_logger
from app.core.database.simple_db_client import get_database
from app.shared.helpers import now_utc

logger = get_logger(__name__)


class IFeatureRepository(ABC):
    """Interface for feature repository operations"""

    @abstractmethod
    async def bulk_upsert_product_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert product features"""
        pass

    @abstractmethod
    async def bulk_upsert_user_features(self, batch_data: List[Dict[str, Any]]) -> int:
        """Bulk upsert user features"""
        pass

    @abstractmethod
    async def bulk_upsert_collection_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert collection features"""
        pass

    @abstractmethod
    async def bulk_upsert_interaction_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert interaction features"""
        pass

    @abstractmethod
    async def bulk_upsert_session_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert session features"""
        pass

    @abstractmethod
    async def bulk_upsert_customer_behavior_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert customer behavior features"""
        pass

    @abstractmethod
    async def bulk_upsert_product_pair_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert product pair features"""
        pass

    @abstractmethod
    async def bulk_upsert_search_product_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert search product features"""
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
    async def get_last_feature_computation_time(self, shop_id: str) -> str:
        """Get the last feature computation timestamp for a shop"""
        pass

    @abstractmethod
    async def update_last_feature_computation_time(
        self, shop_id: str, timestamp
    ) -> None:
        """Update the last feature computation timestamp for a shop"""
        pass

    @abstractmethod
    async def get_shop_data(self, shop_id: str) -> Dict[str, Any]:
        """Get shop data for processing"""
        pass

    @abstractmethod
    async def get_behavioral_events_batch(
        self, shop_id: str, limit: int, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get a batch of behavioral events for a shop"""
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

    async def _bulk_upsert_dict_generic(
        self,
        table_name: str,
        batch_data: List[Dict[str, Any]],
        unique_key_fields: List[str],
    ) -> int:
        """Generic bulk upsert method that accepts dictionary data directly"""
        try:
            if not batch_data:
                return 0

            db = await self._get_database()

            # Prepare data for Prisma - dictionaries are already in the right format
            create_data = []
            for feature_data in batch_data:
                create_data.append(feature_data)

            # Use Prisma's upsert_many for efficient bulk operations
            if create_data:
                # Convert data types for PostgreSQL compatibility
                processed_data = []
                for data in create_data:
                    processed_item = {}
                    for key, value in data.items():
                        if value is None:
                            # Handle None values explicitly
                            processed_item[key] = None
                        elif key in [
                            "lastComputedAt",
                            "lastViewedAt",
                            "lastPurchasedAt",
                            "firstPurchasedAt",
                        ]:
                            # Convert datetime to ISO string for PostgreSQL
                            if hasattr(value, "isoformat"):
                                processed_item[key] = value.isoformat()
                            else:
                                processed_item[key] = value
                        elif key in ["topProducts", "topVendors"] and value is not None:
                            # Ensure JSON fields are properly formatted
                            import json

                            processed_item[key] = json.dumps(value)
                        else:
                            processed_item[key] = value
                    processed_data.append(processed_item)

                # Build the SQL with proper type casting
                columns = list(processed_data[0].keys())
                timestamp_columns = [
                    "lastComputedAt",
                    "lastViewedAt",
                    "lastPurchasedAt",
                    "firstPurchasedAt",
                ]
                json_columns = ["topProducts", "topVendors"]
                float_columns = [
                    "viewToCartRate",
                    "cartToPurchaseRate",
                    "overallConversionRate",
                    "avgSellingPrice",
                    "priceVariance",
                    "inventoryTurnover",
                    "stockVelocity",
                    "variantComplexity",
                    "imageRichness",
                    "tagDiversity",
                    "metafieldUtilization",
                    "popularityScore",
                    "trendingScore",
                    "avgOrderValue",
                    "lifetimeValue",
                    "orderFrequencyPerMonth",
                    "discountSensitivity",
                    "avgDiscountAmount",
                    "clickThroughRate",
                    "bounceRate",
                    "conversionRate",
                    "revenueContribution",
                    "avgSessionDuration",
                    "avgEventsPerSession",
                    "engagementScore",
                    "behavioralScore",
                ]
                int_columns = [
                    "viewCount30d",
                    "uniqueViewers30d",
                    "cartAddCount30d",
                    "purchaseCount30d",
                    "uniquePurchasers30d",
                    "daysSinceFirstPurchase",
                    "daysSinceLastPurchase",
                    "priceTier",
                    "totalPurchases",
                    "totalSpent",
                    "daysSinceFirstOrder",
                    "daysSinceLastOrder",
                    "avgDaysBetweenOrders",
                    "distinctProductsPurchased",
                    "distinctCategoriesPurchased",
                    "ordersWithDiscountCount",
                    "productCount",
                    "uniqueViewers30d",
                    "sessionCount",
                    "viewCount",
                    "cartAddCount",
                    "purchaseCount",
                ]

                # Create type-cast expressions for each column
                value_expressions = []
                for col in columns:
                    if col in timestamp_columns:
                        value_expressions.append(
                            f"${len(value_expressions)+1}::timestamp"
                        )
                    elif col in json_columns:
                        value_expressions.append(f"${len(value_expressions)+1}::jsonb")
                    elif col in float_columns:
                        value_expressions.append(f"${len(value_expressions)+1}::float")
                    elif col in int_columns:
                        value_expressions.append(f"${len(value_expressions)+1}::int")
                    else:
                        value_expressions.append(f"${len(value_expressions)+1}::text")

                await db.execute_raw(
                    f"""
                    INSERT INTO "{table_name}" ({', '.join(f'"{k}"' for k in columns)})
                    VALUES {', '.join([f"({', '.join(value_expressions)})" for _ in processed_data])}
                    ON CONFLICT ({', '.join(f'"{k}"' for k in unique_key_fields)})
                    DO UPDATE SET
                        {', '.join([f'"{k}" = EXCLUDED."{k}"' for k in columns if k not in unique_key_fields])}
                    """,
                    *[item for data in processed_data for item in data.values()],
                )

            logger.info(f"Bulk upserted {len(create_data)} records to {table_name}")
            return len(create_data)

        except Exception as e:
            logger.error(f"Failed to bulk upsert {table_name}: {str(e)}")
            raise

    async def _bulk_upsert_generic(
        self,
        table_name: str,
        batch_data: List[tuple],
        expected_length: int,
        field_names: List[str],
        unique_key_fields: List[str],
    ) -> int:
        """Generic bulk upsert method to eliminate duplication across feature types"""
        try:
            if not batch_data:
                return 0

            db = await self._get_database()

            # Prepare data for Prisma
            create_data = []
            for data in batch_data:
                if len(data) != expected_length:
                    logger.error(
                        f"Invalid batch data length for {table_name}: {len(data)}, expected {expected_length}. Data: {data}"
                    )
                    continue

                # Map tuple to dict using field_names
                feature_data = {
                    field_names[i]: data[i] for i in range(len(field_names))
                }

                create_data.append(feature_data)

            if not create_data:
                return 0

            # Get the Prisma model for the table
            model = getattr(db, table_name.lower() + "features", None)
            if not model:
                raise ValueError(f"No model found for table: {table_name}")

            # Use Prisma's create_many with skip_duplicates for bulk insert
            try:
                await model.create_many(data=create_data, skip_duplicates=True)
                return len(create_data)
            except Exception as create_error:
                # Fallback to individual upserts if batch insert fails
                logger.warning(
                    f"{table_name} batch insert failed, falling back to individual upserts: {str(create_error)}"
                )

                success_count = 0
                for feature_data in create_data:
                    try:
                        # Build unique key dynamically
                        unique_key = {
                            "_".join(unique_key_fields): {
                                field: feature_data[field]
                                for field in unique_key_fields
                            }
                        }
                        await model.upsert(
                            where=unique_key,
                            data=feature_data,
                            update=feature_data,
                        )
                        success_count += 1
                    except Exception as upsert_error:
                        logger.error(
                            f"Failed to upsert {table_name} feature: {str(upsert_error)}"
                        )
                        continue

                return success_count

        except Exception as e:
            logger.error(f"Failed to bulk upsert {table_name} features: {str(e)}")
            return 0

    async def bulk_upsert_product_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert product features using dictionary data structure"""
        return await self._bulk_upsert_dict_generic(
            table_name="ProductFeatures",
            batch_data=batch_data,
            unique_key_fields=["shopId", "productId"],
        )

    async def bulk_upsert_user_features(self, batch_data: List[Dict[str, Any]]) -> int:
        """Bulk upsert user features using dictionary data structure"""
        return await self._bulk_upsert_dict_generic(
            table_name="UserFeatures",
            batch_data=batch_data,
            unique_key_fields=["shopId", "customerId"],
        )

    async def bulk_upsert_collection_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert collection features using dictionary data structure"""
        return await self._bulk_upsert_dict_generic(
            table_name="CollectionFeatures",
            batch_data=batch_data,
            unique_key_fields=["shopId", "collectionId"],
        )

    async def bulk_upsert_interaction_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert interaction features using dictionary data structure"""
        return await self._bulk_upsert_dict_generic(
            table_name="InteractionFeatures",
            batch_data=batch_data,
            unique_key_fields=["shopId", "customerId", "productId"],
        )

    async def bulk_upsert_session_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert session features using dictionary data structure"""
        return await self._bulk_upsert_dict_generic(
            table_name="SessionFeatures",
            batch_data=batch_data,
            unique_key_fields=["shopId", "sessionId"],
        )

    async def bulk_upsert_customer_behavior_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert customer behavior features using dictionary data structure"""
        return await self._bulk_upsert_dict_generic(
            table_name="CustomerBehaviorFeatures",
            batch_data=batch_data,
            unique_key_fields=["shopId", "customerId"],
        )

    async def bulk_upsert_product_pair_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert product pair features using dictionary data structure"""
        return await self._bulk_upsert_dict_generic(
            table_name="ProductPairFeatures",
            batch_data=batch_data,
            unique_key_fields=["shopId", "productId1", "productId2"],
        )

    async def bulk_upsert_search_product_features(
        self, batch_data: List[Dict[str, Any]]
    ) -> int:
        """Bulk upsert search product features using dictionary data structure"""
        return await self._bulk_upsert_dict_generic(
            table_name="SearchProductFeatures",
            batch_data=batch_data,
            unique_key_fields=["shopId", "searchQuery", "productId"],
        )

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

    async def get_last_feature_computation_time(self, shop_id: str) -> str:
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

    async def update_last_feature_computation_time(
        self, shop_id: str, timestamp
    ) -> None:
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

    async def get_shop_data(self, shop_id: str) -> Dict[str, Any]:
        """Get shop data for processing"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "Shop" WHERE "id" = $1'
            result = await db.query_raw(query, shop_id)
            return dict(result[0]) if result else None
        except Exception as e:
            logger.error(f"Failed to get shop data for shop {shop_id}: {str(e)}")
            return None

    async def get_behavioral_events_batch(
        self, shop_id: str, limit: int, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get a batch of behavioral events for a shop"""
        try:
            db = await self._get_database()
            query = 'SELECT * FROM "BehavioralEvents" WHERE "shopId" = $1 ORDER BY "occurredAt" DESC LIMIT $2 OFFSET $3'
            result = await db.query_raw(query, shop_id, limit, offset)
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(
                f"Failed to get behavioral events batch for shop {shop_id}: {str(e)}"
            )
            return []
