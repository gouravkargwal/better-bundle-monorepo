"""
Shopify data collection service implementation for BetterBundle Python Worker
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from app.core.logging import get_logger
from app.shared.helpers import now_utc

from ..interfaces.data_collector import IShopifyDataCollector
from ..interfaces.api_client import IShopifyAPIClient
from ..interfaces.permission_service import IShopifyPermissionService
from .data_storage import ShopifyDataStorageService

logger = get_logger(__name__)


class ShopifyDataCollectionService(IShopifyDataCollector):
    """Shopify data collection service with permission checking and adaptive collection"""

    def __init__(
        self,
        api_client: IShopifyAPIClient,
        permission_service: IShopifyPermissionService,
        data_storage: ShopifyDataStorageService = None,
    ):
        self.api_client = api_client
        self.permission_service = permission_service

        # Inject storage service or create default
        self.data_storage = data_storage or ShopifyDataStorageService()

        # Collection settings - Industry standard constants
        self.BATCH_SIZE = 250
        self.TIMEOUT_SECONDS = 300
        self.RATE_LIMIT_DELAY = 0.1
        self.MAX_DAYS_BACK = 90

        # Simplified data type mapping
        self.DATA_TYPES = {
            "products": {
                "api": "get_products",
                "field": "updated_at",
                "store": "store_products_data",
            },
            "orders": {
                "api": "get_orders",
                "field": "created_at",
                "store": "store_orders_data",
            },
            "customers": {
                "api": "get_customers",
                "field": "updated_at",
                "store": "store_customers_data",
            },
            "collections": {
                "api": "get_collections",
                "field": "updated_at",
                "store": "store_collections_data",
            },
        }

    async def _collect_data_by_type(
        self,
        data_type: str,
        shop_domain: str,
        access_token: str = None,
        limit: Optional[int] = None,
        since_id: Optional[str] = None,
        force_full_collection: bool = False,
    ) -> List[Dict[str, Any]]:
        """Collect data by type - Simplified Industry Standard"""
        config = self.DATA_TYPES.get(data_type)
        if not config:
            raise ValueError(f"Unsupported data type: {data_type}")

        # Check if full collection needed
        should_do_full = await self._should_do_full_collection(
            shop_domain, data_type, force_full_collection
        )

        if should_do_full:
            logger.info(f"Full collection for {data_type}")
            return await self._collect_data_generic(
                shop_domain=shop_domain,
                data_type=data_type,
                api_method=config["api"],
                query_since=None,
                query=None,
                limit=limit,
                since_id=since_id,
            )
        else:
            # Incremental collection - Only collect recent data
            logger.info(f"Incremental collection for {data_type}")
            last_updated = await self._get_last_collection_time(shop_domain, data_type)

            if last_updated:
                # Calculate time window for incremental collection (last 7 days)
                from datetime import timedelta

                query_since = max(last_updated, now_utc() - timedelta(days=7))
                query_filter = f"{config['field']}:>='{query_since.isoformat()}'"

                logger.info(f"📅 Incremental query since: {query_since.isoformat()}")

                result = await self._collect_data_generic(
                    shop_domain=shop_domain,
                    data_type=data_type,
                    api_method=config["api"],
                    query_since=query_since,
                    query=query_filter,
                    limit=limit,
                    since_id=since_id,
                )

                # If incremental finds data, return it
                if result and len(result) > 0:
                    logger.info(
                        f"✅ Incremental collection found {len(result)} new/updated {data_type}"
                    )
                    return result
                else:
                    logger.info(
                        f"📭 No new/updated data found for {data_type} in incremental collection"
                    )
                    return (
                        []
                    )  # Return empty list instead of falling back to full collection
            else:
                # No last collection time, do full collection
                logger.info(
                    f"🔄 No last collection time found, doing full collection for {data_type}"
                )
                return await self._collect_data_generic(
                    shop_domain=shop_domain,
                    data_type=data_type,
                    api_method=config["api"],
                    query_since=None,
                    query=None,
                    limit=limit,
                    since_id=since_id,
                )

    async def _should_do_full_collection(
        self, shop_domain: str, data_type: str, force_full_collection: bool
    ) -> bool:
        """Determine if we should do full collection - Fixed Logic"""
        if force_full_collection:
            logger.info(f"🔄 Force full collection requested for {data_type}")
            return True

        # Check if we have any data for this data type
        try:
            shop = await self.data_storage.get_shop_by_domain(shop_domain)
            if not shop:
                logger.info(f"🔄 No shop found, doing full collection for {data_type}")
                return True

            # Check if we have any raw data for this data type
            has_data = await self._has_any_raw_data(shop.id, data_type)
            if not has_data:
                logger.info(
                    f"🔄 No existing data found, doing full collection for {data_type}"
                )
                return True

            # Check if we have recent data (within last 24 hours) - if yes, do incremental
            last_collection_time = await self._get_last_collection_time(
                shop_domain, data_type
            )
            if last_collection_time:
                from datetime import timedelta

                hours_since_last = (
                    now_utc() - last_collection_time
                ).total_seconds() / 3600
                if (
                    hours_since_last < 24
                ):  # If collected within last 24 hours, do incremental
                    logger.info(
                        f"📈 Recent data found ({hours_since_last:.1f}h ago), doing incremental collection for {data_type}"
                    )
                    return False
                else:
                    logger.info(
                        f"🔄 Data is old ({hours_since_last:.1f}h ago), doing full collection for {data_type}"
                    )
                    return True
            else:
                logger.info(
                    f"🔄 No last collection time found, doing full collection for {data_type}"
                )
                return True

        except Exception as e:
            logger.warning(
                f"⚠️ Error checking existing data for {data_type}: {e}, defaulting to full collection"
            )
            return True

    async def _has_any_raw_data(self, shop_id: str, data_type: str) -> bool:
        """Check if we have any raw data for this data type."""
        try:
            from app.core.database.simple_db_client import get_database

            db = await get_database()

            if data_type == "products":
                count = await db.rawproduct.count(where={"shopId": shop_id})
            elif data_type == "orders":
                count = await db.raworder.count(where={"shopId": shop_id})
            elif data_type == "customers":
                count = await db.rawcustomer.count(where={"shopId": shop_id})
            elif data_type == "collections":
                count = await db.rawcollection.count(where={"shopId": shop_id})
            else:
                return False

            logger.info(f"🔍 Raw {data_type} count for shop {shop_id}: {count}")
            return count > 0
        except Exception as e:
            logger.warning(f"⚠️ Error checking raw data count for {data_type}: {e}")
            return False

    def _calculate_query_since(self, last_updated_at: Optional[datetime]) -> datetime:
        """Calculate the query_since date for incremental collection."""
        now = now_utc()
        max_days_back = now - timedelta(days=self.MAX_DAYS_BACK)

        if last_updated_at:
            return max(last_updated_at, max_days_back)
        else:
            return max_days_back

    async def collect_all_data(
        self,
        shop_domain: str,
        access_token: str = None,
        shop_id: str = None,
        include_products: bool = True,
        include_orders: bool = True,
        include_customers: bool = True,
        include_collections: bool = True,
    ) -> Dict[str, Any]:
        """Collect all available data from Shopify API - Simplified Industry Standard"""
        logger.info(f"Starting data collection for {shop_domain}")

        try:
            # 1. Check permissions
            permissions = await self._check_permissions(shop_domain, access_token)
            collectable_data = self._get_collectable_data_types(
                permissions,
                {
                    "products": include_products,
                    "orders": include_orders,
                    "customers": include_customers,
                    "collections": include_collections,
                },
            )

            if not collectable_data:
                return {
                    "success": False,
                    "message": "No permissions for data collection",
                }

            # 2. Validate shop
            if not shop_id:
                return {"success": False, "message": "Shop ID required"}

            # 3. Collect & Store data
            results = await self._collect_and_store_data(
                shop_domain, access_token, shop_id, collectable_data
            )

            # 4. Trigger normalization
            await self._trigger_normalization(
                shop_id, results.get("processed_types", [])
            )

            total_items = sum(
                len(data) for data in results.get("collected_data", {}).values() if data
            )
            logger.info(f"Collection completed: {total_items} items")

            return {"success": True, "total_items": total_items}

        except Exception as e:
            logger.error(f"Collection failed for {shop_domain}: {e}")
            raise

    async def _check_permissions(
        self, shop_domain: str, access_token: str
    ) -> Dict[str, Any]:
        """Check permissions - simplified"""
        await self.api_client.connect()
        if access_token:
            await self.api_client.set_access_token(shop_domain, access_token)
            return await self.permission_service.check_shop_permissions(
                shop_domain, access_token
            )
        return {}

    def _get_collectable_data_types(
        self, permissions: Dict, includes: Dict
    ) -> List[str]:
        """Get list of collectable data types based on permissions and includes"""
        collectable = []
        for data_type, include in includes.items():
            if include and permissions.get(data_type):
                collectable.append(data_type)
        return collectable

    async def _collect_and_store_data(
        self, shop_domain: str, access_token: str, shop_id: str, data_types: List[str]
    ) -> Dict:
        """Collect and store data in parallel - simplified"""
        # Collect data in parallel
        tasks = [
            self._collect_data_by_type(dt, shop_domain, access_token)
            for dt in data_types
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        collected_data = {}
        processed_types = []

        for i, result in enumerate(results):
            data_type = data_types[i]
            if isinstance(result, Exception):
                logger.error(f"Collection failed for {data_type}: {result}")
            else:
                collected_data[data_type] = result
                # Store data
                if result and len(result) > 0:
                    await self._store_data(data_type, result, shop_id)
                    processed_types.append(data_type)

        return {"collected_data": collected_data, "processed_types": processed_types}

    async def _store_data(self, data_type: str, data: List[Dict], shop_id: str):
        """Store data using appropriate storage method"""
        config = self.DATA_TYPES.get(data_type)
        if config:
            storage_method = getattr(self.data_storage, config["store"])
            await storage_method(data, shop_id)

    async def _trigger_normalization(self, shop_id: str, data_types: List[str]):
        """Trigger normalization for processed data types using Kafka"""
        if not data_types:
            return

        try:
            from app.core.messaging.event_publisher import EventPublisher
            from app.core.config.kafka_settings import kafka_settings

            logger.info(
                f"🔄 Triggering normalization via Kafka for shop {shop_id}",
                data_types=data_types,
            )

            # Initialize event publisher
            publisher = EventPublisher(kafka_settings.model_dump())
            await publisher.initialize()

            try:
                # Create normalization event
                normalization_event = {
                    "event_type": "normalize_batch",
                    "shop_id": shop_id,
                    "data_type": "all",  # Process all data types
                    "data_types": data_types,  # Pass all data types for processing
                    "format": "graphql",
                    "page_size": 100,
                    "timestamp": now_utc().isoformat(),
                    "source": "data_collection_service",
                }

                # Publish to normalization-jobs topic
                message_id = await publisher.publish_normalization_event(
                    normalization_event
                )

                logger.info(
                    f"✅ Normalization event published successfully",
                    shop_id=shop_id,
                    data_types=data_types,
                    message_id=message_id,
                )

            finally:
                await publisher.close()

        except Exception as e:
            logger.error(f"❌ Failed to trigger normalization via Kafka: {e}")

    async def _get_last_collection_time(
        self, shop_domain: str, data_type: str
    ) -> Optional[datetime]:
        """Get the last collection timestamp for incremental updates"""
        try:
            # Get the shop ID first
            shop = await self.data_storage.get_shop_by_domain(shop_domain)
            if not shop:
                return None

            # Get the most recent record for this data type from RAW tables (not main tables)
            if data_type == "products":
                latest_record = await self.data_storage.get_latest_product_update(
                    shop.id
                )
            elif data_type == "orders":
                latest_record = await self.data_storage.get_latest_order_update(shop.id)
            elif data_type == "customers":
                latest_record = await self.data_storage.get_latest_customer_update(
                    shop.id
                )
            elif data_type == "collections":
                latest_record = await self.data_storage.get_latest_collection_update(
                    shop.id
                )
            else:
                return None

            if latest_record and hasattr(latest_record, "extractedAt"):
                return latest_record.extractedAt
            return None

        except Exception as e:
            logger.warning(f"Failed to get last collection time for {data_type}: {e}")
            return None

    async def _collect_data_generic(
        self,
        shop_domain: str,
        data_type: str,
        api_method: str,
        query_since: Optional[datetime],
        limit: Optional[int] = None,
        since_id: Optional[str] = None,
        query: Optional[str] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Generic data collection method - Industry Standard Simplified"""
        logger.info(f"Collecting {data_type} for {shop_domain}")

        raw_items = []
        cursor = since_id
        batch_size = min(limit or self.BATCH_SIZE, self.BATCH_SIZE)
        start_time = now_utc()

        while True:
            # Check timeout
            if (now_utc() - start_time).seconds > self.TIMEOUT_SECONDS:
                logger.warning(f"Timeout for {data_type} collection")
                break

            # Get batch from API
            try:
                api_method_func = getattr(self.api_client, api_method)
                result = await api_method_func(
                    shop_domain=shop_domain, limit=batch_size, cursor=cursor, **kwargs
                )
            except Exception as e:
                logger.error(f"API call failed for {data_type}: {e}")
                break

            if not result or "edges" not in result:
                break

            edges = result["edges"]
            if not edges:
                break

            # Extract items from edges
            for edge in edges:
                item_data = edge.get("node", {})
                if item_data:
                    raw_items.append(item_data)

            # Check pagination
            page_info = result.get("pageInfo", {})
            if not page_info.get("hasNextPage", False):
                break

            cursor = page_info.get("endCursor")
            if not cursor:
                break

            # Check limit
            if limit and len(raw_items) >= limit:
                break

            # Rate limiting
            await asyncio.sleep(self.RATE_LIMIT_DELAY)

        logger.info(f"Collected {len(raw_items)} {data_type} items")
        return raw_items
