"""
Feature repository for handling all database operations related to ML features
"""

from typing import Dict, Any, List
from abc import ABC, abstractmethod

from app.core.logging import get_logger
from app.core.database.simple_db_client import get_database

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
        """Generic bulk upsert method using Prisma's native methods"""
        try:
            if not batch_data:
                return 0

            db = await self._get_database()

            # Map table names to actual Prisma model names
            model_mapping = {
                "ProductFeatures": "productfeatures",
                "UserFeatures": "userfeatures",
                "CollectionFeatures": "collectionfeatures",
                "CustomerBehaviorFeatures": "customerbehaviorfeatures",
                "InteractionFeatures": "interactionfeatures",
                "SessionFeatures": "sessionfeatures",
                "ProductPairFeatures": "productpairfeatures",
                "SearchProductFeatures": "searchproductfeatures",
            }

            model_name = model_mapping.get(table_name)
            if not model_name:
                raise ValueError(f"No model mapping found for table: {table_name}")

            model = getattr(db, model_name, None)
            if not model:
                raise ValueError(
                    f"No model found for table: {table_name} (mapped to: {model_name})"
                )

            # Use Prisma's createMany with skipDuplicates for bulk operations
            # This is more efficient than individual upserts
            try:
                await model.create_many(data=batch_data, skip_duplicates=True)
                logger.info(f"Bulk upserted {len(batch_data)} records to {table_name}")
                return len(batch_data)
            except Exception as create_error:
                logger.error(f"{table_name} batch insert failed: {str(create_error)}")
                # For now, we'll just log the error and return 0
                # In the future, we could implement a proper upsert fallback
                return 0

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
        """Get the last feature computation timestamp for a shop by checking feature tables"""
        try:
            db = await self._get_database()

            # Get the most recent feature computation time from all feature tables
            feature_tables = [
                db.productfeatures,
                db.customerbehaviorfeatures,
                db.collectionfeatures,
                db.userfeatures,
                db.interactionfeatures,
                db.sessionfeatures,
                db.productpairfeatures,
                db.searchproductfeatures,
            ]

            latest_timestamp = None
            for table in feature_tables:
                try:
                    # Get the most recent record for this shop
                    latest_record = await table.find_first(
                        where={"shopId": shop_id}, order={"createdAt": "desc"}
                    )
                    if latest_record and latest_record.createdAt:
                        if (
                            latest_timestamp is None
                            or latest_record.createdAt > latest_timestamp
                        ):
                            latest_timestamp = latest_record.createdAt
                except Exception as e:
                    logger.warning(f"Could not check feature table {table}: {str(e)}")
                    continue

            if latest_timestamp:
                return latest_timestamp.isoformat()
            else:
                # Return a very old timestamp for first run
                return "1970-01-01T00:00:00Z"

        except Exception as e:
            logger.error(
                f"Failed to get last computation time for shop {shop_id}: {str(e)}"
            )
            return "1970-01-01T00:00:00Z"

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

    # Incremental data loading methods
    async def get_products_batch_since(
        self, shop_id: str, since_timestamp: str, limit: int, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get products modified since a specific timestamp for incremental processing"""
        try:
            db = await self._get_database()
            logger.info(f"Querying products since {since_timestamp} for shop {shop_id}")

            # Use Prisma's native find_many with where conditions
            result = await db.productdata.find_many(
                where={"shopId": shop_id, "updatedAt": {"gt": since_timestamp}},
                order={"updatedAt": "asc"},
                take=limit,
                skip=offset,
            )

            logger.info(
                f"Found {len(result)} products modified since {since_timestamp}"
            )
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(
                f"Failed to get products batch since {since_timestamp} for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_customers_batch_since(
        self, shop_id: str, since_timestamp: str, limit: int, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get customers modified since a specific timestamp for incremental processing"""
        try:
            db = await self._get_database()
            # Use Prisma's native find_many with where conditions
            result = await db.customerdata.find_many(
                where={"shopId": shop_id, "updatedAt": {"gt": since_timestamp}},
                order={"updatedAt": "asc"},
                take=limit,
                skip=offset,
            )
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(
                f"Failed to get customers batch since {since_timestamp} for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_orders_batch_since(
        self, shop_id: str, since_timestamp: str, limit: int, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get orders modified since a specific timestamp for incremental processing"""
        try:
            db = await self._get_database()
            # Use Prisma's native find_many with where conditions
            result = await db.orderdata.find_many(
                where={"shopId": shop_id, "updatedAt": {"gt": since_timestamp}},
                order={"updatedAt": "asc"},
                take=limit,
                skip=offset,
            )
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(
                f"Failed to get orders batch since {since_timestamp} for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_collections_batch_since(
        self, shop_id: str, since_timestamp: str, limit: int, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get collections modified since a specific timestamp for incremental processing"""
        try:
            db = await self._get_database()
            # Use Prisma's native find_many with where conditions
            result = await db.collectiondata.find_many(
                where={"shopId": shop_id, "updatedAt": {"gt": since_timestamp}},
                order={"updatedAt": "asc"},
                take=limit,
                skip=offset,
            )
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(
                f"Failed to get collections batch since {since_timestamp} for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_behavioral_events_batch_since(
        self, shop_id: str, since_timestamp: str, limit: int, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get behavioral events since a specific timestamp for incremental processing"""
        try:
            db = await self._get_database()
            # Use Prisma's native find_many with where conditions
            result = await db.behavioralevents.find_many(
                where={"shopId": shop_id, "occurredAt": {"gt": since_timestamp}},
                order={"occurredAt": "asc"},
                take=limit,
                skip=offset,
            )
            return [dict(row) for row in result] if result else []
        except Exception as e:
            logger.error(
                f"Failed to get behavioral events batch since {since_timestamp} for shop {shop_id}: {str(e)}"
            )
            return []

    async def get_feature_counts_for_shop(self, shop_id: str) -> Dict[str, int]:
        """Get counts of existing features for a shop to determine if incremental processing is needed"""
        try:
            db = await self._get_database()

            # Count features across all feature tables using Prisma
            counts = {}
            total_count = 0

            # Use Prisma's count method for each feature table
            feature_models = [
                ("productfeatures", db.productfeatures),
                ("userfeatures", db.userfeatures),
                ("collectionfeatures", db.collectionfeatures),
                ("customerbehaviorfeatures", db.customerbehaviorfeatures),
                ("sessionfeatures", db.sessionfeatures),
                ("interactionfeatures", db.interactionfeatures),
                ("productpairfeatures", db.productpairfeatures),
                ("searchproductfeatures", db.searchproductfeatures),
            ]

            for table_name, model in feature_models:
                try:
                    count = await model.count(where={"shopId": shop_id})
                    counts[table_name] = count
                    total_count += count
                except Exception as e:
                    logger.warning(
                        f"Failed to count features in {table_name}: {str(e)}"
                    )
                    counts[table_name] = 0

            counts["total"] = total_count
            return counts

        except Exception as e:
            logger.error(f"Failed to get feature counts for shop {shop_id}: {str(e)}")
            return {"total": 0}
