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
        force_full_collection: bool = False,
    ) -> List[Dict[str, Any]]:
        """Internal method to collect any supported data type using declarative configuration."""
        config = self.DATA_TYPE_CONFIG.get(data_type)
        if not config:
            raise ValueError(f"Unsupported data type: {data_type}")

        # Industry Best Practice: Check if we should do full collection
        should_do_full_collection = await self._should_do_full_collection(
            shop_domain, data_type, force_full_collection
        )

        if should_do_full_collection:
            logger.info(
                f"🔄 Performing FULL collection for {data_type} (no existing data or force flag)"
            )
            # Full collection - no timestamp filter
            return await self._collect_data_generic(
                shop_domain=shop_domain,
                data_type=data_type,
                api_method=config["api_method"],
                query_since=None,  # No timestamp filter
                query=None,  # No query filter
                limit=limit,
                since_id=since_id,
            )
        else:
            # Incremental collection - use timestamp filter
            logger.info(f"📈 Performing INCREMENTAL collection for {data_type}")

            # 1. Get last collection time
            last_updated_at = await self._get_last_collection_time(
                shop_domain, data_type
            )

            # 2. Calculate query_since
            query_since = self._calculate_query_since(last_updated_at)

            # 3. Build query filter
            query_filter = f"{config['timestamp_field']}:>='{query_since.isoformat()}'"

            # 4. Call the generic collector
            result = await self._collect_data_generic(
                shop_domain=shop_domain,
                data_type=data_type,
                api_method=config["api_method"],
                query_since=query_since,
                query=query_filter,
                limit=limit,
                since_id=since_id,
            )

            # Industry Best Practice: Fallback to full collection if incremental finds nothing
            if not result or len(result) == 0:
                logger.warning(
                    f"⚠️ Incremental collection found no data for {data_type}, falling back to FULL collection"
                )
                return await self._collect_data_generic(
                    shop_domain=shop_domain,
                    data_type=data_type,
                    api_method=config["api_method"],
                    query_since=None,  # No timestamp filter
                    query=None,  # No query filter
                    limit=limit,
                    since_id=since_id,
                )

            return result

    async def _should_do_full_collection(
        self, shop_domain: str, data_type: str, force_full_collection: bool
    ) -> bool:
        """Industry Best Practice: Determine if we should do full collection."""
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

            logger.info(
                f"📈 Existing data found, doing incremental collection for {data_type}"
            )
            return False

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
        logger.info(f"🚀 Starting comprehensive data collection for {shop_domain}")
        logger.info(
            f"📋 Collection parameters: products={include_products}, orders={include_orders}, customers={include_customers}, collections={include_collections}"
        )

        try:
            # Step 1: Initialization and Permissions
            logger.info(
                f"🔐 Step 1: Initializing API client and checking permissions for {shop_domain}"
            )
            permissions = await self._initialize_and_check_permissions(
                shop_domain, access_token
            )
            logger.info(f"✅ Permissions checked: {permissions}")

            # Check if we have any collectable data
            collectable_data = []
            if permissions.get("products") and include_products:
                collectable_data.append("products")
                logger.info("✅ Products collection enabled")
            if permissions.get("orders") and include_orders:
                collectable_data.append("orders")
                logger.info("✅ Orders collection enabled")
            if permissions.get("customers") and include_customers:
                collectable_data.append("customers")
                logger.info("✅ Customers collection enabled")
            if permissions.get("collections") and include_collections:
                collectable_data.append("collections")
                logger.info("✅ Collections collection enabled")

            logger.info(f"📊 Collectable data types: {collectable_data}")

            if not collectable_data:
                logger.warning(
                    f"⚠️ No data can be collected for {shop_domain} - missing permissions"
                )
                return {
                    "shop": None,
                    "message": "No data can be collected due to missing permissions",
                }

            # Step 2: Get or create internal shop ID
            logger.info(f"🏪 Step 2: Validating shop ID for {shop_domain}")
            internal_shop_id = await self._get_or_create_internal_shop(
                shop_domain, access_token, shop_id
            )

            if not internal_shop_id:
                logger.error(
                    f"❌ Failed to get or create internal shop ID for {shop_domain}"
                )
                return {
                    "shop": None,
                    "message": "Failed to get or create internal shop ID",
                }
            logger.info(f"✅ Shop ID validated: {internal_shop_id}")

            # Step 3: Collect raw data in parallel
            logger.info(
                f"📥 Step 3: Starting parallel data collection for {len(collectable_data)} data types"
            )
            raw_data_results = await self._execute_parallel_collection(
                shop_domain, access_token, collectable_data
            )

            # Log collection results
            for data_type, result in raw_data_results.items():
                if isinstance(result, Exception):
                    logger.error(f"❌ Collection failed for {data_type}: {str(result)}")
                else:
                    logger.info(
                        f"📊 {data_type.title()} collection result: {len(result) if result else 0} items"
                    )

            # Step 4: Store raw data
            logger.info(f"💾 Step 4: Storing collected data to database")
            storage_result = await self._store_raw_data(
                raw_data_results, internal_shop_id
            )
            logger.info(f"✅ Storage result: {storage_result}")

            # Step 5: Trigger normalization
            logger.info(f"🔄 Step 5: Triggering normalization for processed data types")
            await self._trigger_normalization_scans(
                internal_shop_id,
                storage_result.get("data_types_processed", []),
                collectable_data,
            )

            # Step 6: Return simple success result
            total_items = sum(
                len(result)
                for result in raw_data_results.values()
                if not isinstance(result, Exception)
            )
            logger.info(
                f"🎉 Data collection completed successfully! Total items: {total_items}"
            )

            return {
                "success": True,
                "total_items": total_items,
            }

        except Exception as e:
            logger.error(f"❌ Failed to collect all data for {shop_domain}: {str(e)}")
            logger.error(f"📋 Error details: {type(e).__name__}: {str(e)}")
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
            logger.warning(f"⚠️ No data can be collected for {shop_domain}")
            return {}

        logger.info(
            f"🚀 Starting parallel collection for {len(collectable_data)} data types: {collectable_data}"
        )

        # Collect data using parallel processing
        collection_tasks = []
        task_data_types = []

        for data_type in collectable_data:
            logger.info(f"📋 Creating collection task for {data_type}")
            collection_tasks.append(
                asyncio.create_task(
                    self._collect_data_by_type(data_type, shop_domain, access_token)
                )
            )
            task_data_types.append(data_type)

        logger.info(
            f"⏳ Executing {len(collection_tasks)} collection tasks in parallel..."
        )

        # Execute collection tasks
        results = {}
        if collection_tasks:
            try:
                task_results = await asyncio.gather(
                    *collection_tasks, return_exceptions=True
                )
                logger.info(f"✅ All collection tasks completed")

                for i, result in enumerate(task_results):
                    data_type = task_data_types[i]
                    if isinstance(result, Exception):
                        logger.error(
                            f"❌ Collection task failed for {data_type}: {str(result)}"
                        )
                        logger.error(
                            f"📋 Task error details: {type(result).__name__}: {str(result)}"
                        )
                        import traceback

                        logger.error(f"📋 Task stack trace: {traceback.format_exc()}")
                    else:
                        logger.info(
                            f"✅ Collection task completed for {data_type}: {len(result) if result else 0} items"
                        )
                        results[data_type] = result
            except Exception as gather_error:
                logger.error(f"❌ Parallel collection failed: {str(gather_error)}")
                logger.error(
                    f"📋 Gather error details: {type(gather_error).__name__}: {str(gather_error)}"
                )
                import traceback

                logger.error(f"📋 Gather stack trace: {traceback.format_exc()}")

        logger.info(
            f"🎯 Parallel collection completed. Results: {[(k, len(v) if v else 0) for k, v in results.items()]}"
        )
        return results

    async def _store_raw_data(
        self, raw_data_results: Dict[str, Any], internal_shop_id: str
    ) -> Dict[str, Any]:
        """Store collected raw data using the storage service."""
        logger.info(f"💾 Starting storage process for shop {internal_shop_id}")
        logger.info(
            f"📊 Raw data results summary: {[(k, len(v) if v else 0) for k, v in raw_data_results.items()]}"
        )

        data_types_processed = []

        for data_type, result in raw_data_results.items():
            logger.info(f"🔄 Processing {data_type} for storage...")

            if result and len(result) > 0 and internal_shop_id:
                try:
                    logger.info(
                        f"📦 Storing {len(result)} {data_type} items for shop {internal_shop_id}"
                    )

                    # Log sample data structure for debugging
                    if result and len(result) > 0:
                        sample_item = result[0]
                        logger.info(
                            f"🔍 Sample {data_type} item keys: {list(sample_item.keys()) if isinstance(sample_item, dict) else 'Not a dict'}"
                        )
                        logger.info(
                            f"🔍 Sample {data_type} item ID: {sample_item.get('id', 'No ID') if isinstance(sample_item, dict) else 'Not a dict'}"
                        )

                    # Get storage method from config
                    config = self.DATA_TYPE_CONFIG.get(data_type)
                    if not config:
                        logger.error(f"❌ No storage config found for {data_type}")
                        continue

                    logger.info(f"🔧 Using storage method: {config['storage_method']}")
                    storage_method = getattr(
                        self.data_storage, config["storage_method"]
                    )

                    logger.info(f"🚀 Calling storage method for {data_type}...")
                    storage_result = await storage_method(result, internal_shop_id)
                    logger.info(f"✅ Storage method completed for {data_type}")

                    logger.info(f"📊 Storage result for {data_type}: {storage_result}")
                    logger.info(
                        f"✅ Successfully stored {data_type} data: {storage_result.get('new', 0)} new, {storage_result.get('updated', 0)} updated"
                    )

                    # Track data types that were processed for normalization
                    if (
                        storage_result.get("new", 0) > 0
                        or storage_result.get("updated", 0) > 0
                    ):
                        data_types_processed.append(data_type)
                        logger.info(f"✅ {data_type} added to normalization queue")
                    else:
                        logger.warning(
                            f"⚠️ No new or updated records for {data_type} - skipping normalization"
                        )

                except Exception as storage_error:
                    logger.error(
                        f"❌ Failed to store {data_type} data: {str(storage_error)}"
                    )
                    logger.error(
                        f"📋 Storage error details: {type(storage_error).__name__}: {str(storage_error)}"
                    )
                    import traceback

                    logger.error(f"📋 Stack trace: {traceback.format_exc()}")
            elif not internal_shop_id:
                logger.error(
                    f"❌ Cannot store {data_type} data: internal shop ID not available"
                )
            elif not result or len(result) == 0:
                logger.info(f"📭 No {data_type} data to store (empty result)")
            else:
                logger.warning(
                    f"⚠️ Unexpected condition for {data_type}: result={type(result)}, length={len(result) if result else 'N/A'}"
                )

        logger.info(
            f"🎯 Storage process completed. Data types processed: {data_types_processed}"
        )
        return {"data_types_processed": data_types_processed}

    async def _trigger_normalization_scans(
        self,
        internal_shop_id: str,
        data_types_processed: List[str],
        fallback_types: List[str] | None = None,
    ) -> None:
        """Trigger normalization batch processing for processed data types."""
        types_to_scan = data_types_processed or (fallback_types or [])
        if not types_to_scan:
            return

        try:
            from app.core.redis_client import streams_manager

            for data_type in types_to_scan:
                # Publish normalize_batch events to process all data in batches
                await streams_manager.publish_shopify_event(
                    {
                        "event_type": "normalize_batch",
                        "shop_id": internal_shop_id,
                        "data_type": data_type,
                        "format": "graphql",
                        "page_size": 100,  # Process 100 records at a time
                        "timestamp": now_utc().isoformat(),
                    }
                )
                logger.info(
                    f"Published normalize_batch event for {data_type}",
                    shop_id=internal_shop_id,
                )

        except Exception as scan_error:
            logger.error(
                f"Failed to publish normalization batches",
                shop_id=internal_shop_id,
                data_types=data_types_processed,
                error=str(scan_error),
            )

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
        """Generic data collection method that stores raw Shopify API responses"""
        logger.info(f"🔍 Starting {data_type} collection for {shop_domain}")
        if query_since:
            logger.info(f"📅 Query since: {query_since.isoformat()}")
        else:
            logger.info(f"🔄 FULL collection (no timestamp filter)")
        logger.info(
            f"📊 Batch size: {min(limit or self.default_batch_size, self.max_batch_size)}"
        )
        logger.info(f"🔧 API method: {api_method}")
        if query:
            logger.info(f"🔍 Query filter: {query}")

        raw_items = []
        cursor = since_id
        batch_size = min(limit or self.default_batch_size, self.max_batch_size)
        start_time = now_utc()
        page_count = 0

        while True:
            page_count += 1
            logger.info(
                f"📄 Fetching page {page_count} for {data_type} (cursor: {cursor})"
            )

            # Check timeout
            if (now_utc() - start_time).seconds > self.collection_timeout:
                logger.warning(
                    f"⏰ {data_type} collection timeout after {self.collection_timeout}s for {shop_domain}"
                )
                break

            # Get batch using the specified API method
            try:
                api_client_method = getattr(self.api_client, api_method)
                logger.info(f"🌐 Calling API method: {api_method}")
                result = await api_client_method(
                    shop_domain=shop_domain, limit=batch_size, cursor=cursor, **kwargs
                )
                logger.info(f"📥 API response received for {data_type}")
            except Exception as api_error:
                logger.error(f"❌ API call failed for {data_type}: {str(api_error)}")
                break

            if not result:
                logger.warning(f"⚠️ Empty result from API for {data_type}")
                break

            if "edges" not in result:
                logger.warning(
                    f"⚠️ No 'edges' in API response for {data_type}: {list(result.keys())}"
                )
                break

            edges = result["edges"]
            if not edges:
                logger.info(f"📭 No more items in {data_type} collection")
                break

            logger.info(f"📦 Processing {len(edges)} items from page {page_count}")

            # Store raw Shopify API responses without transformation
            items_added = 0
            for edge in edges:
                item_data = edge.get("node", {})
                if item_data:
                    # Store the raw Shopify API response as-is
                    raw_items.append(item_data)
                    items_added += 1
                else:
                    logger.warning(f"⚠️ Empty node in {data_type} edge")

            logger.info(
                f"✅ Added {items_added} items from page {page_count} (total: {len(raw_items)})"
            )

            # Check if there are more pages
            page_info = result.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            logger.info(f"📄 Page info: hasNextPage={has_next_page}")

            if not has_next_page:
                logger.info(f"🏁 No more pages for {data_type}")
                break

            cursor = page_info.get("endCursor")
            if not cursor:
                logger.warning(f"⚠️ No endCursor in pageInfo for {data_type}")
                break

            # Check if we've reached the limit
            if limit and len(raw_items) >= limit:
                logger.info(f"🎯 Reached limit of {limit} items for {data_type}")
                break

            # Small delay to respect rate limits
            await asyncio.sleep(0.1)

        logger.info(
            f"🎉 {data_type.title()} collection completed | shop_domain={shop_domain} | total_{data_type}={len(raw_items)} | pages={page_count}"
        )
        return raw_items
