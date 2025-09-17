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

        # Collection settings
        self.default_batch_size = 250  # Increased from 50 to 250 for faster API calls
        self.max_batch_size = 250
        self.collection_timeout = 300  # 5 minutes per data type

        # Declarative data type configuration
        self.DATA_TYPE_CONFIG = {
            "products": {
                "api_method": "get_products",
                "timestamp_field": "updated_at",  # Fixed: Use updated_at to catch product updates
                "storage_method": "store_products_data",
            },
            "orders": {
                "api_method": "get_orders",
                "timestamp_field": "created_at",
                "storage_method": "store_orders_data",
            },
            "customers": {
                "api_method": "get_customers",
                "timestamp_field": "updated_at",  # Customers can be updated
                "storage_method": "store_customers_data",
            },
            "collections": {
                "api_method": "get_collections",
                "timestamp_field": "updated_at",
                "storage_method": "store_collections_data",
            },
        }

    async def _collect_data_by_type(
        self,
        data_type: str,
        shop_domain: str,
        access_token: str = None,
        limit: Optional[int] = None,
        since_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Internal method to collect any supported data type using declarative configuration."""
        config = self.DATA_TYPE_CONFIG.get(data_type)
        if not config:
            raise ValueError(f"Unsupported data type: {data_type}")

        # 1. Get last collection time
        last_updated_at = await self._get_last_collection_time(shop_domain, data_type)

        # 2. Calculate query_since
        query_since = self._calculate_query_since(last_updated_at)

        # 3. Build query filter
        query_filter = f"{config['timestamp_field']}:>='{query_since.isoformat()}'"

        # 4. Call the generic collector
        return await self._collect_data_generic(
            shop_domain=shop_domain,
            data_type=data_type,
            api_method=config["api_method"],
            query_since=query_since,
            query=query_filter,
            limit=limit,
            since_id=since_id,
        )

    def _calculate_query_since(self, last_updated_at: Optional[datetime]) -> datetime:
        """Calculate the query_since date for incremental collection."""
        now = now_utc()
        max_days_back = now - timedelta(days=90)

        if last_updated_at:
            # Use the later of: last collection time or 90 days ago
            return max(last_updated_at, max_days_back)
        else:
            # No previous data, collect last 90 days
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
        """Collect all available data from Shopify API"""
        try:
            # Step 1: Initialization and Permissions
            permissions = await self._initialize_and_check_permissions(
                shop_domain, access_token
            )

            # Check if we have any collectable data
            collectable_data = []
            if permissions.get("products") and include_products:
                collectable_data.append("products")
            if permissions.get("orders") and include_orders:
                collectable_data.append("orders")
            if permissions.get("customers") and include_customers:
                collectable_data.append("customers")
            if permissions.get("collections") and include_collections:
                collectable_data.append("collections")

            if not collectable_data:
                logger.warning(f"No data can be collected", shop_domain=shop_domain)
                return {
                    "shop": None,
                    "message": "No data can be collected due to missing permissions",
                }

            # Step 2: Get or create internal shop ID
            internal_shop_id = await self._get_or_create_internal_shop(
                shop_domain, access_token, shop_id
            )

            if not internal_shop_id:
                logger.error(
                    f"Failed to get or create internal shop ID", shop_domain=shop_domain
                )
                return {
                    "shop": None,
                    "message": "Failed to get or create internal shop ID",
                }

            # Step 3: Collect raw data in parallel
            raw_data_results = await self._execute_parallel_collection(
                shop_domain, access_token, collectable_data
            )

            # Step 4: Store raw data
            storage_result = await self._store_raw_data(
                raw_data_results, internal_shop_id
            )

            await self._trigger_normalization_scans(
                internal_shop_id,
                storage_result.get("data_types_processed", []),
                collectable_data,
            )

            # Step 6: Return simple success result
            total_items = sum(len(result) for result in raw_data_results.values())

            return {
                "success": True,
                "total_items": total_items,
            }

        except Exception as e:
            logger.error(
                f"Failed to collect all data", shop_domain=shop_domain, error=str(e)
            )
            raise

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

    async def _initialize_and_check_permissions(
        self, shop_domain: str, access_token: str
    ) -> Dict[str, Any]:
        """Initialize API client and check permissions."""
        # Connect API client if not already connected
        await self.api_client.connect()

        # Set access token for API client
        if access_token:
            await self.api_client.set_access_token(shop_domain, access_token)

            # Check permissions ONCE at the top level to avoid recursion
            permissions = await self.permission_service.check_shop_permissions(
                shop_domain, access_token
            )

        return permissions

    async def _get_or_create_internal_shop(
        self, shop_domain: str, access_token: str, shop_id: str = None
    ) -> Optional[str]:
        """Get internal shop ID with lightweight validation."""
        if not shop_id:
            logger.error(f"shop_id is required for domain: {shop_domain}")
            return None

        # Lightweight validation - just check if shop exists
        try:
            db_shop = await self.data_storage.get_shop_by_id(shop_id)
            if not db_shop:
                logger.error(
                    f"Shop {shop_id} not found in database for domain: {shop_domain}"
                )
                return None

            logger.info(f"Validated shop_id: {shop_id} for domain: {shop_domain}")
            return shop_id
        except Exception as e:
            logger.error(f"Failed to validate shop {shop_id}: {e}")
            return None

    async def _execute_parallel_collection(
        self, shop_domain: str, access_token: str, collectable_data: List[str]
    ) -> Dict[str, Any]:
        """Execute parallel data collection for the specified data types."""
        if not collectable_data:
            logger.warning(f"No data can be collected", shop_domain=shop_domain)
            return {}

        # Collect data using parallel processing
        collection_tasks = []
        task_data_types = []

        for data_type in collectable_data:
            collection_tasks.append(
                asyncio.create_task(
                    self._collect_data_by_type(data_type, shop_domain, access_token)
                )
            )
            task_data_types.append(data_type)

        # Execute collection tasks
        results = {}
        if collection_tasks:
            task_results = await asyncio.gather(
                *collection_tasks, return_exceptions=True
            )

            for i, result in enumerate(task_results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Collection task failed",
                        shop_domain=shop_domain,
                        task_index=i,
                        error=str(result),
                    )
                else:
                    data_type = task_data_types[i]
                    results[data_type] = result

        return results

    async def _store_raw_data(
        self, raw_data_results: Dict[str, Any], internal_shop_id: str
    ) -> Dict[str, Any]:
        """Store collected raw data using the storage service."""
        data_types_processed = []

        for data_type, result in raw_data_results.items():
            if result and len(result) > 0 and internal_shop_id:
                try:
                    logger.info(
                        f"Storing {len(result)} {data_type} items for shop {internal_shop_id}"
                    )

                    # Get storage method from config
                    config = self.DATA_TYPE_CONFIG.get(data_type)
                    if config:
                        storage_method = getattr(
                            self.data_storage, config["storage_method"]
                        )
                        storage_result = await storage_method(result, internal_shop_id)

                        logger.info(
                            f"Successfully stored {data_type} data: {storage_result['new']} new, {storage_result['updated']} updated"
                        )

                        # Track data types that were processed for normalization
                        if (
                            storage_result.get("new", 0) > 0
                            or storage_result.get("updated", 0) > 0
                        ):
                            data_types_processed.append(data_type)

                except Exception as storage_error:
                    logger.error(
                        f"Failed to store {data_type} data",
                        shop_domain=internal_shop_id,
                        data_type=data_type,
                        error=str(storage_error),
                    )
            elif not internal_shop_id:
                logger.error(
                    f"Cannot store {data_type} data: internal shop ID not available",
                    data_type=data_type,
                )
            elif not result or len(result) == 0:
                logger.info(f"No {data_type} data to store (empty result)")

        # Return the data types that were processed so caller can trigger normalization
        return {"data_types_processed": data_types_processed}

    async def _trigger_normalization_scans(
        self,
        internal_shop_id: str,
        data_types_processed: List[str],
        fallback_types: List[str] | None = None,
    ) -> None:
        """Trigger normalization scans for processed data types."""
        types_to_scan = data_types_processed or (fallback_types or [])
        if not types_to_scan:
            return

        try:
            from app.core.redis_client import streams_manager

            for data_type in types_to_scan:
                await streams_manager.publish_shopify_event(
                    {
                        "event_type": "normalize_scan",
                        "shop_id": internal_shop_id,
                        "data_type": data_type,
                        "format": "graphql",
                        "page_size": 100,  # Configure as needed
                        "timestamp": now_utc().isoformat(),
                    }
                )
                logger.info(
                    f"Published normalize_scan event for {data_type}",
                    shop_id=internal_shop_id,
                )

        except Exception as scan_error:
            logger.error(
                f"Failed to publish normalization scans",
                shop_id=internal_shop_id,
                data_types=data_types_processed,
                error=str(scan_error),
            )

    async def _collect_data_generic(
        self,
        shop_domain: str,
        data_type: str,
        api_method: str,
        query_since: datetime,
        limit: Optional[int] = None,
        since_id: Optional[str] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Generic data collection method that stores raw Shopify API responses"""
        raw_items = []
        cursor = since_id
        batch_size = min(limit or self.default_batch_size, self.max_batch_size)
        start_time = now_utc()

        while True:
            # Check timeout
            if (now_utc() - start_time).seconds > self.collection_timeout:
                logger.warning(
                    f"{data_type} collection timeout", shop_domain=shop_domain
                )
                break

            # Get batch using the specified API method
            api_client_method = getattr(self.api_client, api_method)
            result = await api_client_method(
                shop_domain=shop_domain, limit=batch_size, cursor=cursor, **kwargs
            )

            if not result or "edges" not in result:
                break

            edges = result["edges"]
            if not edges:
                break

            # Store raw Shopify API responses without transformation
            for edge in edges:
                item_data = edge.get("node", {})
                if item_data:
                    # Store the raw Shopify API response as-is
                    raw_items.append(item_data)

            # Check if there are more pages
            page_info = result.get("pageInfo", {})
            if not page_info.get("hasNextPage", False):
                break

            cursor = page_info.get("endCursor")
            if not cursor:
                break

            # Check if we've reached the limit
            if limit and len(raw_items) >= limit:
                break

            # Small delay to respect rate limits
            await asyncio.sleep(0.1)

            logger.info(
                f"{data_type.title()} collection completed | shop_domain={shop_domain} | total_{data_type}={len(raw_items)}"
            )
        return raw_items
