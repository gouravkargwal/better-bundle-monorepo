"""
Shopify data collection service implementation for BetterBundle Python Worker
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from app.core.logging import get_logger
from app.shared.helpers import now_utc

from ..interfaces.data_collector import IShopifyDataCollector
from ..interfaces.api_client import IShopifyAPIClient
from ..interfaces.permission_service import IShopifyPermissionService
from ..models.shop import ShopifyShop
from ..models.product import ShopifyProduct, ShopifyProductVariant
from ..models.order import ShopifyOrder, ShopifyOrderLineItem
from ..models.customer import ShopifyCustomer, ShopifyCustomerAddress
from ..models.collection import ShopifyCollection
from .data_storage import ShopifyDataStorageService
from .main_table_storage import MainTableStorageService

logger = get_logger(__name__)


@dataclass
class CollectionProgress:
    """Track progress of data collection"""

    shop_domain: str
    data_type: str
    total_items: int = 0
    collected_items: int = 0
    items_collected: int = 0
    items_failed: int = 0
    current_cursor: Optional[str] = None
    has_more: bool = True
    start_time: Optional[datetime] = None
    last_update: Optional[datetime] = None

    @property
    def progress_percentage(self) -> float:
        """Get collection progress percentage"""
        if self.total_items == 0:
            return 0.0
        return (self.collected_items / self.total_items) * 100

    @property
    def is_complete(self) -> bool:
        """Check if collection is complete"""
        return not self.has_more or self.collected_items >= self.total_items


class ShopifyDataCollectionService(IShopifyDataCollector):
    """Shopify data collection service with permission checking and adaptive collection"""

    def __init__(
        self,
        api_client: IShopifyAPIClient,
        permission_service: IShopifyPermissionService,
    ):
        self.api_client = api_client
        self.permission_service = permission_service

        # Initialize data storage services
        self.data_storage = ShopifyDataStorageService()
        # Main table storage will use the connection pool directly
        self.main_table_storage = None

        # Collection settings
        self.default_batch_size = 250  # Increased from 50 to 250 for faster API calls
        self.max_batch_size = 250
        self.collection_timeout = 300  # 5 minutes per data type

        # Progress tracking
        self.collection_progress: Dict[str, Dict[str, CollectionProgress]] = {}

        # Collection statistics
        self.collection_stats: Dict[str, Dict[str, Any]] = {}

    async def collect_shop_data(
        self, shop_domain: str, access_token: str = None
    ) -> Optional[ShopifyShop]:
        """Collect shop data from Shopify API"""
        try:

            # Connect API client if not already connected
            await self.api_client.connect()

            # Set access token for API client
            if access_token:
                await self.api_client.set_access_token(shop_domain, access_token)

            # Check permissions first
            permissions = await self.permission_service.check_shop_permissions(
                shop_domain, access_token
            )
            if not permissions.get("has_access", False):
                logger.warning(f"No access to shop data", shop_domain=shop_domain)
                return None

            # Collect shop info
            shop_info = await self.api_client.get_shop_info(shop_domain)

            if not shop_info:
                logger.error(f"Failed to collect shop info", shop_domain=shop_domain)
                return None

            # Create ShopifyShop model
            shop = ShopifyShop(
                id=shop_info.get("id", ""),
                name=shop_info.get("name", ""),
                domain=shop_info.get("myshopifyDomain", shop_domain),
                email=shop_info.get("email"),
                phone=None,  # Not available in current query
                access_token=access_token,
                address1=None,  # Not available in current query
                address2=None,  # Not available in current query
                city=None,  # Not available in current query
                province=None,  # Not available in current query
                country=None,  # Not available in current query
                zip=None,  # Not available in current query
                currency=shop_info.get("currencyCode", "USD"),
                primary_locale="en",  # Default value
                timezone=shop_info.get("ianaTimezone"),
                plan_name=None,  # Not available in current query
                plan_display_name=(
                    shop_info.get("plan", {}).get("displayName")
                    if shop_info.get("plan")
                    else None
                ),
                shop_owner=None,  # Not available in current query
                has_storefront=False,  # Default value
                has_discounts=False,  # Not available in current query
                has_gift_cards=False,  # Not available in current query
                has_marketing=False,  # Not available in current query
                has_multi_location=False,  # Not available in current query
                google_analytics_account=None,  # Not available in current query
                google_analytics_domain=None,  # Not available in current query
                seo_title=None,  # Not available in current query
                seo_description=None,  # Not available in current query
                meta_description=None,  # Not available in current query
                facebook_account=None,  # Not available in current query
                instagram_account=None,  # Not available in current query
                twitter_account=None,  # Not available in current query
                myshopify_domain=shop_info.get("myshopifyDomain", shop_domain),
                primary_location_id=None,  # Not available in current query
                created_at=(
                    datetime.fromisoformat(shop_info.get("createdAt"))
                    if shop_info.get("createdAt")
                    else None
                ),
                updated_at=(
                    datetime.fromisoformat(shop_info.get("updatedAt"))
                    if shop_info.get("updatedAt")
                    else None
                ),
                raw_data={"shop": shop_info},
            )

            return shop

        except Exception as e:
            logger.error(
                f"Failed to collect shop data", shop_domain=shop_domain, error=str(e)
            )
            raise

    async def collect_products(
        self,
        shop_domain: str,
        access_token: str = None,
        limit: Optional[int] = None,
        since_id: Optional[str] = None,
    ) -> List[ShopifyProduct]:
        """Collect products data from Shopify API with smart incremental collection"""
        try:
            # Note: Permissions already checked in collect_all_data method

            # Get the last collection timestamp from database
            last_updated_at = await self._get_last_collection_time(
                shop_domain, "products"
            )

            # Calculate the query date (max 90 days back, or since last collection)
            now = now_utc()
            max_days_back = now - timedelta(days=90)

            if last_updated_at:
                # Use the later of: last collection time or 90 days ago
                query_since = max(last_updated_at, max_days_back)
            else:
                # No previous data, collect last 90 days
                query_since = max_days_back

            products = []
            cursor = since_id
            batch_size = min(limit or self.default_batch_size, self.max_batch_size)

            # Build query for incremental collection (use created_at for products)
            query_filter = f"created_at:>={query_since.strftime('%Y-%m-%dT%H:%M:%S')}"
            logger.info(
                f"Starting incremental products collection since {query_since}",
                shop_domain=shop_domain,
            )

            # Initialize progress tracking
            progress = CollectionProgress(
                shop_domain=shop_domain, data_type="products", start_time=now_utc()
            )
            self._update_progress(shop_domain, "products", progress)

            while True:
                # Check timeout
                if (
                    progress.start_time
                    and (now_utc() - progress.start_time).seconds
                    > self.collection_timeout
                ):
                    logger.warning(
                        f"Products collection timeout", shop_domain=shop_domain
                    )
                    break

                # Get batch of products with incremental filter
                result = await self.api_client.get_products(
                    shop_domain=shop_domain,
                    limit=batch_size,
                    cursor=cursor,
                    query=query_filter,
                )

                if not result or "edges" not in result:
                    break

                edges = result["edges"]
                if not edges:
                    break

                # Process products
                for edge in edges:
                    product_data = edge["node"]
                    product = await self._create_product_from_data(product_data)
                    products.append(product)

                # Update progress
                progress.collected_items += len(edges)
                progress.current_cursor = cursor
                progress.last_update = now_utc()

                # Check pagination
                page_info = result.get("pageInfo", {})
                if not page_info.get("hasNextPage", False):
                    progress.has_more = False
                    break

                cursor = page_info.get("endCursor")
                if not cursor:
                    break

                # Check if we've reached the limit
                if limit and progress.collected_items >= limit:
                    break

                # Small delay to respect rate limits
                await asyncio.sleep(0.1)

            # Finalize progress
            progress.total_items = progress.collected_items
            progress.last_update = now_utc()
            self._update_progress(shop_domain, "products", progress)

            return products

        except Exception as e:
            logger.error(
                f"Failed to collect products", shop_domain=shop_domain, error=str(e)
            )
            raise

    async def collect_orders(
        self,
        shop_domain: str,
        access_token: str = None,
        limit: Optional[int] = None,
        since_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[ShopifyOrder]:
        """Collect orders data from Shopify API with smart incremental collection"""
        try:
            # Note: Permissions already checked in collect_all_data method

            # Get the last collection timestamp from database
            last_updated_at = await self._get_last_collection_time(
                shop_domain, "orders"
            )

            # Calculate the query date (max 90 days back, or since last collection)
            now = now_utc()
            max_days_back = now - timedelta(days=90)

            if last_updated_at:
                # Use the later of: last collection time or 90 days ago
                query_since = max(last_updated_at, max_days_back)
            else:
                # No previous data, collect last 90 days
                query_since = max_days_back

            # Build query filter for orders (use created_at for orders)
            query_filter = f"created_at:>={query_since.strftime('%Y-%m-%dT%H:%M:%S')}"

            return await self._collect_data_generic(
                shop_domain=shop_domain,
                data_type="orders",
                api_method="get_orders",
                create_method="_create_order_from_data",
                query_since=query_since,
                limit=limit,
                since_id=since_id,
                query=query_filter,
            )

        except Exception as e:
            logger.error(
                f"Failed to collect orders", shop_domain=shop_domain, error=str(e)
            )
            raise

    async def collect_customers(
        self,
        shop_domain: str,
        access_token: str = None,
        limit: Optional[int] = None,
        since_id: Optional[str] = None,
    ) -> List[ShopifyCustomer]:
        """Collect customers data from Shopify API with smart incremental collection"""
        try:
            # Note: Permissions already checked in collect_all_data method

            # Get the last collection timestamp from database
            last_updated_at = await self._get_last_collection_time(
                shop_domain, "customers"
            )

            # Calculate the query date (max 90 days back, or since last collection)
            now = now_utc()
            max_days_back = now - timedelta(days=90)

            if last_updated_at:
                # Use the later of: last collection time or 90 days ago
                query_since = max(last_updated_at, max_days_back)
                logger.info(
                    f"Starting incremental customers collection since {query_since}",
                    shop_domain=shop_domain,
                )
            else:
                # No previous data, collect last 90 days
                query_since = max_days_back
                logger.info(
                    f"Starting full customers collection (last 90 days)",
                    shop_domain=shop_domain,
                )

            query_filter = f"updated_at:>={query_since.strftime('%Y-%m-%dT%H:%M:%S')}"
            return await self._collect_data_generic(
                shop_domain=shop_domain,
                data_type="customers",
                api_method="get_customers",
                create_method="_create_customer_from_data",
                query_since=query_since,
                limit=limit,
                since_id=since_id,
                query=query_filter,
            )

        except Exception as e:
            logger.error(
                f"Failed to collect customers", shop_domain=shop_domain, error=str(e)
            )
            raise

    async def collect_collections(
        self,
        shop_domain: str,
        access_token: str = None,
        limit: Optional[int] = None,
        since_id: Optional[str] = None,
    ) -> List[ShopifyCollection]:
        """Collect collections data from Shopify API with smart incremental collection"""
        try:
            # Note: Permissions already checked in collect_all_data method

            # Get the last collection timestamp from database
            last_updated_at = await self._get_last_collection_time(
                shop_domain, "collections"
            )

            # Calculate the query date (max 90 days back, or since last collection)
            now = now_utc()
            max_days_back = now - timedelta(days=90)

            if last_updated_at:
                # Use the later of: last collection time or 90 days ago
                query_since = max(last_updated_at, max_days_back)
                logger.info(
                    f"Starting incremental collections collection since {query_since}",
                    shop_domain=shop_domain,
                )
            else:
                # No previous data, collect last 90 days
                query_since = max_days_back
                logger.info(
                    f"Starting full collections collection (last 90 days)",
                    shop_domain=shop_domain,
                )

            # Build query filter for collections
            query_filter = f"updated_at:>={query_since.strftime('%Y-%m-%dT%H:%M:%S')}"

            return await self._collect_data_generic(
                shop_domain=shop_domain,
                data_type="collections",
                api_method="get_collections",
                create_method="_create_collection_from_data",
                query_since=query_since,
                limit=limit,
                since_id=since_id,
                query=query_filter,
            )

        except Exception as e:
            logger.error(
                f"Failed to collect collections", shop_domain=shop_domain, error=str(e)
            )
            raise

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

            # Connect API client if not already connected
            await self.api_client.connect()

            # Set access token for API client
            if access_token:
                await self.api_client.set_access_token(shop_domain, access_token)

            # Check permissions ONCE at the top level to avoid recursion
            permissions = await self.permission_service.check_shop_permissions(
                shop_domain, access_token
            )

            # Determine what data to collect based on permissions
            collectable_data = []
            if permissions.get("products"):
                collectable_data.append("products")
            if permissions.get("orders"):
                collectable_data.append("orders")
            if permissions.get("customers"):
                collectable_data.append("customers")
            if permissions.get("collections"):
                collectable_data.append("collections")

            if not collectable_data:
                logger.warning(f"No data can be collected", shop_domain=shop_domain)
                return {
                    "shop": None,
                    "message": "No data can be collected due to missing permissions",
                }

            # Create strategy object for compatibility
            strategy = {
                "collectable_data": collectable_data,
                "collection_method": (
                    "full" if len(collectable_data) >= 3 else "partial"
                ),
                "collection_priority": collectable_data,
            }

            # Initialize collection results
            collection_results = {
                "shop": None,
                "products": [],
                "orders": [],
                "customers": [],
                "collections": [],
                "collection_strategy": strategy,
                "collection_stats": {},
                "started_at": now_utc().isoformat(),
            }

            # Use provided shop_id or get it from shop data
            internal_shop_id = shop_id

            if not internal_shop_id:
                # Collect shop data first (fallback for when shop_id is not provided)
                shop = await self.collect_shop_data(shop_domain, access_token)
                collection_results["shop"] = shop

                # Store shop data in database and get the internal shop ID
                if shop:
                    try:
                        # Store shop data - the method will create or update the shop
                        shop_metrics = await self.data_storage.store_shop_data(
                            shop, shop.domain  # Pass domain instead of shop.id
                        )

                        # Get the internal shop ID from the database
                        db_shop = await self.data_storage.get_shop_by_domain(
                            shop.domain
                        )
                        if db_shop:
                            internal_shop_id = db_shop.id
                            logger.info(
                                f"Retrieved internal shop ID: {internal_shop_id} for domain: {shop.domain}"
                            )
                        else:
                            logger.error(
                                f"Failed to retrieve internal shop ID for domain: {shop.domain}"
                            )
                    except Exception as e:
                        logger.error(f"Failed to store shop data: {e}")
            else:
                logger.info(
                    f"Using provided shop_id: {internal_shop_id} for domain: {shop_domain}"
                )

            # Collect data based on permissions and preferences using parallel processing
            collection_tasks = []
            task_data_types = []

            if "products" in collectable_data and include_products:
                collection_tasks.append(
                    asyncio.create_task(
                        self._collect_with_progress(
                            "products", shop_domain, access_token
                        )
                    )
                )
                task_data_types.append("products")

            if "orders" in collectable_data and include_orders:
                collection_tasks.append(
                    asyncio.create_task(
                        self._collect_with_progress("orders", shop_domain, access_token)
                    )
                )
                task_data_types.append("orders")

            if "customers" in collectable_data and include_customers:
                collection_tasks.append(
                    asyncio.create_task(
                        self._collect_with_progress(
                            "customers", shop_domain, access_token
                        )
                    )
                )
                task_data_types.append("customers")

            if "collections" in collectable_data and include_collections:
                collection_tasks.append(
                    asyncio.create_task(
                        self._collect_with_progress(
                            "collections", shop_domain, access_token
                        )
                    )
                )
                task_data_types.append("collections")

            # Execute collection tasks
            if collection_tasks:
                results = await asyncio.gather(
                    *collection_tasks, return_exceptions=True
                )

                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(
                            f"Collection task failed",
                            shop_domain=shop_domain,
                            task_index=i,
                            error=str(result),
                        )
                    else:
                        data_type = task_data_types[i]
                        collection_results[data_type] = result

                        # Store collected data using enterprise-grade storage service
                        if result and len(result) > 0 and internal_shop_id:
                            try:
                                logger.info(
                                    f"Storing {len(result)} {data_type} items for shop {internal_shop_id}"
                                )
                                if data_type == "products":
                                    storage_result = (
                                        await self.data_storage.store_products_data(
                                            result, internal_shop_id
                                        )
                                    )
                                elif data_type == "orders":
                                    storage_result = (
                                        await self.data_storage.store_orders_data(
                                            result, internal_shop_id
                                        )
                                    )
                                elif data_type == "customers":
                                    storage_result = (
                                        await self.data_storage.store_customers_data(
                                            result, internal_shop_id
                                        )
                                    )
                                elif data_type == "collections":
                                    storage_result = (
                                        await self.data_storage.store_collections_data(
                                            result, internal_shop_id
                                        )
                                    )

                                logger.info(
                                    f"Successfully stored {data_type} data: {storage_result.new_items} new, {storage_result.updated_items} updated"
                                )
                            except Exception as storage_error:
                                logger.error(
                                    f"Failed to store {data_type} data",
                                    shop_domain=shop_domain,
                                    data_type=data_type,
                                    error=str(storage_error),
                                )
                        elif not internal_shop_id:
                            logger.error(
                                f"Cannot store {data_type} data: internal shop ID not available",
                                shop_domain=shop_domain,
                                data_type=data_type,
                            )
                        elif not result or len(result) == 0:
                            logger.info(f"No {data_type} data to store (empty result)")

            # Finalize collection
            collection_results["completed_at"] = now_utc().isoformat()
            collection_results["total_items"] = sum(
                len(collection_results.get(data_type, []))
                for data_type in [
                    "products",
                    "orders",
                    "customers",
                    "collections",
                    "customer_events",
                ]
            )

            # Update collection statistics
            self._update_collection_stats(shop_domain, collection_results)

            # Store data in main tables after raw storage is complete
            if internal_shop_id:
                try:
                    logger.info(
                        f"Starting main table storage for shop {internal_shop_id}"
                    )

                    # Initialize main table storage (now uses connection pool internally)
                    main_table_storage = MainTableStorageService()

                    # Pass the collection start time for incremental processing
                    main_storage_result = await main_table_storage.store_all_data(
                        internal_shop_id, incremental=True
                    )
                    logger.info(
                        f"Main table storage completed: {main_storage_result.processed_count} processed, "
                        f"{main_storage_result.error_count} errors, {main_storage_result.duration_ms}ms"
                    )

                    # Add main storage results to collection results
                    collection_results["main_storage"] = {
                        "success": main_storage_result.success,
                        "processed_count": main_storage_result.processed_count,
                        "error_count": main_storage_result.error_count,
                        "duration_ms": main_storage_result.duration_ms,
                        "errors": main_storage_result.errors,
                    }

                    # Fire event to trigger ML feature computation
                    if (
                        main_storage_result.success
                        and main_storage_result.processed_count > 0
                    ):
                        try:
                            from app.core.redis_client import streams_manager

                            # Generate a unique job ID for feature computation
                            feature_job_id = f"feature_compute_{internal_shop_id}_{int(now_utc().timestamp())}"

                            # Publish ML training event to trigger feature computation
                            event_id = await streams_manager.publish_ml_training_event(
                                job_id=feature_job_id,
                                shop_id=internal_shop_id,
                                shop_domain=shop_domain,
                                data_collection_completed=True,
                            )

                            logger.info(
                                f"Published ML training event for feature computation",
                                event_id=event_id,
                                job_id=feature_job_id,
                                shop_id=internal_shop_id,
                                shop_domain=shop_domain,
                            )

                            # Add event info to collection results
                            collection_results["ml_event"] = {
                                "event_id": event_id,
                                "job_id": feature_job_id,
                                "status": "published",
                            }

                        except Exception as e:
                            logger.error(
                                f"Failed to publish ML training event: {str(e)}"
                            )
                            collection_results["ml_event"] = {
                                "success": False,
                                "error": str(e),
                            }
                    else:
                        logger.warning(
                            "Skipping ML event: main table storage failed or no data processed"
                        )
                        collection_results["ml_event"] = {
                            "success": False,
                            "error": "No data processed",
                        }
                except Exception as e:
                    logger.error(f"Failed to store data in main tables: {str(e)}")
                    collection_results["main_storage"] = {
                        "success": False,
                        "error": str(e),
                    }
            else:
                logger.warning(
                    "Skipping main table storage: internal shop ID not available"
                )
                collection_results["main_storage"] = {
                    "success": False,
                    "error": "Internal shop ID not available",
                }

            return collection_results

        except Exception as e:
            logger.error(
                f"Failed to collect all data", shop_domain=shop_domain, error=str(e)
            )
            raise

    async def check_permissions(
        self, shop_domain: str, access_token: str = None
    ) -> Dict[str, bool]:
        """Check what data can be collected based on app permissions"""
        return await self.permission_service.check_shop_permissions(
            shop_domain, access_token
        )

    async def get_collection_status(self, shop_domain: str) -> Dict[str, Any]:
        """Get status of data collection for a shop"""
        progress = self.collection_progress.get(shop_domain, {})
        stats = self.collection_stats.get(shop_domain, {})

        return {
            "shop_domain": shop_domain,
            "progress": {
                data_type: progress_obj.__dict__
                for data_type, progress_obj in progress.items()
            },
            "statistics": stats,
            "last_updated": now_utc().isoformat(),
        }

    async def validate_shop_access(
        self, shop_domain: str, access_token: str = None
    ) -> bool:
        """Validate that the app has access to the shop"""
        try:
            permissions = await self.permission_service.check_shop_permissions(
                shop_domain, access_token
            )
            return permissions.get("has_access", False)
        except Exception as e:
            logger.error(
                f"Failed to validate shop access", shop_domain=shop_domain, error=str(e)
            )
            return False

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
            elif data_type == "customer_events":
                latest_record = (
                    await self.data_storage.get_latest_customer_event_update(shop.id)
                )
            else:
                return None

            if latest_record and hasattr(latest_record, "extractedAt"):
                return latest_record.extractedAt
            return None

        except Exception as e:
            logger.warning(f"Failed to get last collection time for {data_type}: {e}")
            return None

    async def _collect_with_progress(
        self, data_type: str, shop_domain: str, access_token: str = None
    ) -> List[Any]:
        """Collect data with progress tracking"""
        if data_type == "products":
            return await self.collect_products(shop_domain, access_token)
        elif data_type == "orders":
            return await self.collect_orders(shop_domain, access_token)
        elif data_type == "customers":
            return await self.collect_customers(shop_domain, access_token)
        elif data_type == "collections":
            return await self.collect_collections(shop_domain, access_token)
        elif data_type == "customer_events":
            return await self.collect_customer_events(shop_domain, access_token)
        else:
            logger.warning(f"Unknown data type for collection", data_type=data_type)
            return []

    async def _collect_all_data_parallel(
        self,
        shop_domain: str,
        access_token: str,
        collection_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Collect all data types in parallel for better performance"""
        try:
            logger.info(f"Starting parallel data collection for {shop_domain}")

            # Get permissions first
            permissions = await self.permission_service.check_shop_permissions(
                shop_domain, access_token
            )

            if not permissions.get("has_access", False):
                logger.warning(f"No access permissions for {shop_domain}")
                return {"total_items": 0, "collections": {}}

            # Determine which data types to collect based on permissions
            data_types_to_collect = []
            if permissions.get("products", False):
                data_types_to_collect.append("products")
            if permissions.get("orders", False):
                data_types_to_collect.append("orders")
            if permissions.get("customers", False):
                data_types_to_collect.append("customers")
            if permissions.get("collections", False):
                data_types_to_collect.append("collections")
            if permissions.get("customer_events", False):
                data_types_to_collect.append("customer_events")

            if not data_types_to_collect:
                logger.warning(f"No data types can be collected for {shop_domain}")
                return {"total_items": 0, "collections": {}}

            # Collect shop info first (required for all other operations)
            shop_info = await self.api_client.get_shop_info(shop_domain, access_token)
            if not shop_info:
                raise Exception("Failed to get shop information")

            # Set shop plan for rate limiting based on shop info
            plan_name = shop_info.get("plan", {}).get("displayName", "").lower()
            if "plus" in plan_name:
                self.api_client.set_shop_plan(shop_domain, "plus")
            elif "advanced" in plan_name:
                self.api_client.set_shop_plan(shop_domain, "advanced")
            elif "enterprise" in plan_name or "commerce components" in plan_name:
                self.api_client.set_shop_plan(shop_domain, "enterprise")
            else:
                self.api_client.set_shop_plan(shop_domain, "standard")

            # Store shop data
            await self.storage_service.store_shop_data(shop_domain, shop_info)

            # Create parallel collection tasks
            collection_tasks = []
            for data_type in data_types_to_collect:
                task = asyncio.create_task(
                    self._collect_with_progress(data_type, shop_domain, access_token)
                )
                collection_tasks.append((data_type, task))

            # Execute all collections in parallel
            logger.info(f"Executing {len(collection_tasks)} parallel collection tasks")
            results = {}
            total_items = 0

            # Wait for all tasks to complete
            for data_type, task in collection_tasks:
                try:
                    data = await task
                    results[data_type] = data
                    total_items += len(data)
                    logger.info(
                        f"Parallel collection completed for {data_type}: {len(data)} items"
                    )
                except Exception as e:
                    logger.error(f"Parallel collection failed for {data_type}: {e}")
                    results[data_type] = []
                    # Continue with other collections even if one fails

            logger.info(
                f"Parallel data collection completed for {shop_domain}: {total_items} total items"
            )

            return {
                "total_items": total_items,
                "collections": results,
                "shop_domain": shop_domain,
                "permissions": permissions,
            }

        except Exception as e:
            logger.error(f"Parallel data collection failed for {shop_domain}: {e}")
            raise

    async def _create_product_from_data(
        self, product_data: Dict[str, Any]
    ) -> ShopifyProduct:
        """Create ShopifyProduct from API data"""
        # Extract basic product info
        product = ShopifyProduct(
            id=product_data.get("id", ""),
            title=product_data.get("title", ""),
            description=product_data.get("description"),
            body_html=product_data.get("bodyHtml"),  # Keep legacy field
            vendor=product_data.get("vendor", ""),
            product_type=product_data.get("productType", ""),
            handle=product_data.get("handle", ""),
            seo_title=(
                product_data.get("seo", {}).get("title")
                if product_data.get("seo")
                else None
            ),
            seo_description=(
                product_data.get("seo", {}).get("description")
                if product_data.get("seo")
                else None
            ),
            meta_description=(
                product_data.get("seo", {}).get("description")
                if product_data.get("seo")
                else None
            ),
            status=(product_data.get("status", "active") or "active").lower(),
            published_at=(
                datetime.fromisoformat(product_data.get("publishedAt"))
                if product_data.get("publishedAt")
                else None
            ),
            published_scope=product_data.get("publishedScope", "web"),
            tags=product_data.get("tags", []),
            template_suffix=product_data.get("templateSuffix"),
            total_inventory=product_data.get("totalInventory"),
            metafields=(
                product_data.get("metafields", {}).get("edges", [])
                if product_data.get("metafields")
                else []
            ),
            created_at=(
                datetime.fromisoformat(product_data.get("createdAt"))
                if product_data.get("createdAt")
                else now_utc()
            ),
            updated_at=(
                datetime.fromisoformat(product_data.get("updatedAt"))
                if product_data.get("updatedAt")
                else now_utc()
            ),
            raw_data={"product": product_data},
        )

        # Extract image IDs and full image data
        images = product_data.get("images", {}).get("edges", [])
        product.image_ids = [
            edge["node"]["id"] for edge in images if edge.get("node", {}).get("id")
        ]
        product.images = [
            {
                "id": edge["node"]["id"],
                "url": edge["node"].get("url"),
                "altText": edge["node"].get("altText"),
                "width": edge["node"].get("width"),
                "height": edge["node"].get("height"),
            }
            for edge in images
            if edge.get("node", {}).get("id")
        ]

        # Extract variants
        variants = product_data.get("variants", {}).get("edges", [])
        for variant_edge in variants:
            variant_data = variant_edge["node"]
            variant = ShopifyProductVariant(
                id=variant_data.get("id", ""),
                product_id=product.id,
                title=variant_data.get("title", ""),
                sku=variant_data.get("sku"),
                barcode=variant_data.get("barcode"),
                price=float(variant_data.get("price", 0)),
                compare_at_price=(
                    float(variant_data.get("compareAtPrice"))
                    if variant_data.get("compareAtPrice")
                    else None
                ),
                cost_per_item=(
                    float(variant_data.get("costPerItem"))
                    if variant_data.get("costPerItem")
                    else None
                ),
                inventory_quantity=int(variant_data.get("inventoryQuantity", 0)),
                inventory_policy=variant_data.get("inventoryPolicy", "deny"),
                inventory_management=variant_data.get(
                    "inventoryManagement"
                ),  # May be None if field doesn't exist
                weight=(
                    float(variant_data.get("weight"))
                    if variant_data.get("weight")
                    else None
                ),
                weight_unit=variant_data.get(
                    "weightUnit", "g"
                ),  # May be None if field doesn't exist
                requires_shipping=variant_data.get(
                    "requiresShipping", True
                ),  # May be None if field doesn't exist
                taxable=variant_data.get("taxable", True),
                selected_options=variant_data.get("selectedOptions", []),
                # Keep legacy fields for backward compatibility
                option1=variant_data.get("option1"),
                option2=variant_data.get("option2"),
                option3=variant_data.get("option3"),
                created_at=(
                    datetime.fromisoformat(variant_data.get("createdAt"))
                    if variant_data.get("createdAt")
                    else now_utc()
                ),
                updated_at=(
                    datetime.fromisoformat(variant_data.get("updatedAt"))
                    if variant_data.get("updatedAt")
                    else now_utc()
                ),
                raw_data={"variant": variant_data},
            )
            product.add_variant(variant)

        # Extract product options
        options = product_data.get("options", [])
        product.options = [
            {
                "id": option.get("id"),
                "name": option.get("name"),
                "values": option.get("values", []),
            }
            for option in options
        ]

        # Extract collection IDs
        collections = product_data.get("collections", {}).get("edges", [])
        product.collection_ids = [
            edge["node"]["id"] for edge in collections if edge.get("node", {}).get("id")
        ]

        return product

    def _create_order_from_data(self, order_data: Dict[str, Any]) -> ShopifyOrder:
        """Create ShopifyOrder from API data"""
        # Extract basic order info
        order = ShopifyOrder(
            id=order_data.get("id", ""),
            name=order_data.get("name"),
            email=order_data.get("email"),
            phone=order_data.get("phone"),
            created_at=(
                datetime.fromisoformat(order_data.get("createdAt"))
                if order_data.get("createdAt")
                else now_utc()
            ),
            updated_at=(
                datetime.fromisoformat(order_data.get("updatedAt"))
                if order_data.get("updatedAt")
                else now_utc()
            ),
            processed_at=(
                datetime.fromisoformat(order_data.get("processedAt"))
                if order_data.get("processedAt")
                else None
            ),
            cancelled_at=(
                datetime.fromisoformat(order_data.get("cancelledAt"))
                if order_data.get("cancelledAt")
                else None
            ),
            cancel_reason=order_data.get("cancelReason"),
            # Financial information from price sets
            total_price=float(
                order_data.get("totalPriceSet", {})
                .get("shopMoney", {})
                .get("amount", 0)
            ),
            subtotal_price=float(
                order_data.get("subtotalPriceSet", {})
                .get("shopMoney", {})
                .get("amount", 0)
            ),
            total_tax=float(
                order_data.get("totalTaxSet", {}).get("shopMoney", {}).get("amount", 0)
            ),
            total_shipping_price=float(
                order_data.get("totalShippingPriceSet", {})
                .get("shopMoney", {})
                .get("amount", 0)
            ),
            total_refunded=float(
                order_data.get("totalRefundedSet", {})
                .get("shopMoney", {})
                .get("amount", 0)
            ),
            total_outstanding=float(
                order_data.get("totalOutstandingSet", {})
                .get("shopMoney", {})
                .get("amount", 0)
            ),
            currency=order_data.get("currencyCode", "USD"),
            currency_code=order_data.get("currencyCode", "USD"),
            presentment_currency_code=order_data.get("presentmentCurrencyCode"),
            # Customer information
            customer_id=(
                order_data.get("customer", {}).get("id")
                if order_data.get("customer")
                else None
            ),
            customer_first_name=(
                order_data.get("customer", {}).get("firstName")
                if order_data.get("customer")
                else None
            ),
            customer_last_name=(
                order_data.get("customer", {}).get("lastName")
                if order_data.get("customer")
                else None
            ),
            customer_email=(
                order_data.get("customer", {}).get("email")
                if order_data.get("customer")
                else None
            ),
            customer_tags=(
                order_data.get("customer", {}).get("tags", [])
                if order_data.get("customer")
                else []
            ),
            # Addresses
            shipping_address=order_data.get("shippingAddress"),
            billing_address=order_data.get("billingAddress"),
            # Order metadata
            tags=order_data.get("tags", []),
            note=order_data.get("note"),
            confirmed=order_data.get("confirmed", False),
            test=order_data.get("test", False),
            customer_locale=order_data.get("customerLocale"),
            # Discounts and metafields
            discount_applications=(
                order_data.get("discountApplications", {}).get("edges", [])
                if order_data.get("discountApplications")
                else []
            ),
            metafields=(
                order_data.get("metafields", {}).get("edges", [])
                if order_data.get("metafields")
                else []
            ),
            raw_data={"order": order_data},
        )

        # Extract line items
        line_items = order_data.get("lineItems", {}).get("edges", [])
        order.line_items = []
        for item_edge in line_items:
            item_data = item_edge.get("node", {})
            if item_data:
                variant_data = item_data.get("variant", {})
                product_data = variant_data.get("product", {}) if variant_data else {}

                line_item = ShopifyOrderLineItem(
                    id=item_data.get("id", ""),
                    order_id=order.id,
                    quantity=int(item_data.get("quantity", 0)),
                    title=item_data.get("title", ""),
                    variant_id=variant_data.get("id"),
                    variant_title=variant_data.get("title"),
                    sku=variant_data.get("sku"),
                    barcode=variant_data.get("barcode"),
                    product_id=product_data.get("id"),
                    product_title=product_data.get("title"),
                    vendor=product_data.get("vendor"),
                    product_type=product_data.get("productType"),
                    product_tags=product_data.get("tags", []),
                    price=float(variant_data.get("price", 0)),
                    total_discount=0.0,  # Will be calculated from discount applications
                    created_at=now_utc(),
                    updated_at=now_utc(),
                    raw_data={"line_item": item_data},
                )
                order.line_items.append(line_item)

        return order

    def _create_customer_from_data(
        self, customer_data: Dict[str, Any]
    ) -> ShopifyCustomer:
        """Create ShopifyCustomer from API data"""
        # Extract basic customer info
        customer = ShopifyCustomer(
            id=customer_data.get("id", ""),
            email=customer_data.get("email"),
            phone=customer_data.get("phone"),
            first_name=customer_data.get("firstName"),
            last_name=customer_data.get("lastName"),
            accepts_marketing=customer_data.get("acceptsMarketing", False),
            accepts_marketing_updated_at=(
                datetime.fromisoformat(customer_data.get("acceptsMarketingUpdatedAt"))
                if customer_data.get("acceptsMarketingUpdatedAt")
                else None
            ),
            marketing_opt_in_level=customer_data.get("marketingOptInLevel"),
            created_at=(
                datetime.fromisoformat(customer_data.get("createdAt"))
                if customer_data.get("createdAt")
                else None
            ),
            updated_at=(
                datetime.fromisoformat(customer_data.get("updatedAt"))
                if customer_data.get("updatedAt")
                else None
            ),
            state=customer_data.get("state", "disabled"),
            note=customer_data.get("note"),
            verified_email=customer_data.get("verifiedEmail", False),
            multipass_identifier=customer_data.get("multipassIdentifier"),
            tax_exempt=customer_data.get("taxExempt", False),
            tags=customer_data.get("tags", []),
            last_order_id=customer_data.get("lastOrderId"),
            last_order_name=customer_data.get("lastOrderName"),
            currency=customer_data.get("currency", "USD"),
            total_spent=float(customer_data.get("totalSpent", 0)),
            orders_count=int(customer_data.get("ordersCount", 0)),
            raw_data={"customer": customer_data},
        )

        # Extract addresses
        addresses = customer_data.get("addresses", {}).get("edges", [])
        customer.addresses = []
        for addr_edge in addresses:
            addr_data = addr_edge.get("node", {})
            if addr_data:
                address = ShopifyCustomerAddress(
                    id=addr_data.get("id", ""),
                    customer_id=customer.id,
                    address1=addr_data.get("address1"),
                    address2=addr_data.get("address2"),
                    city=addr_data.get("city"),
                    province=addr_data.get("province"),
                    country=addr_data.get("country"),
                    zip=addr_data.get("zip"),
                    phone=addr_data.get("phone"),
                    company=addr_data.get("company"),
                    first_name=addr_data.get("firstName"),
                    last_name=addr_data.get("lastName"),
                    country_code=addr_data.get("countryCode"),
                    province_code=addr_data.get("provinceCode"),
                )
                customer.addresses.append(address)

        return customer

    async def _collect_data_generic(
        self,
        shop_domain: str,
        data_type: str,
        api_method: str,
        create_method: str,
        query_since: datetime,
        limit: Optional[int] = None,
        since_id: Optional[str] = None,
        **kwargs,
    ) -> List[Any]:
        """Generic data collection method to avoid code duplication"""
        items = []
        cursor = since_id
        batch_size = min(limit or self.default_batch_size, self.max_batch_size)

        # Initialize progress tracking
        progress = CollectionProgress(
            shop_domain=shop_domain, data_type=data_type, start_time=now_utc()
        )
        self._update_progress(shop_domain, data_type, progress)

        while True:
            # Check timeout
            if (
                progress.start_time
                and (now_utc() - progress.start_time).seconds > self.collection_timeout
            ):
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

            # Process items in this batch
            for edge in edges:
                item_data = edge.get("node", {})
                if item_data:
                    try:
                        create_method_func = getattr(self, create_method)
                        item = create_method_func(item_data)
                        items.append(item)
                        progress.items_collected += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to process {data_type} {item_data.get('id', 'unknown')}: {e}",
                            shop_domain=shop_domain,
                        )
                        progress.items_failed += 1
                        continue

            # Update progress
            progress.items_processed = len(items)
            self._update_progress(shop_domain, data_type, progress)

            # Check if there are more pages
            page_info = result.get("pageInfo", {})
            if not page_info.get("hasNextPage", False):
                break

            cursor = page_info.get("endCursor")
            if not cursor:
                break

        # Final progress update
        progress.end_time = now_utc()
        progress.status = "completed"
        self._update_progress(shop_domain, data_type, progress)

        logger.info(
            f"{data_type.title()} collection completed | shop_domain={shop_domain} | total_{data_type}={len(items)}"
        )
        return items

    def _create_collection_from_data(
        self, collection_data: Dict[str, Any]
    ) -> ShopifyCollection:
        """Create ShopifyCollection from API data"""
        # Extract image data
        image_data = collection_data.get("image", {})
        image_id = image_data.get("id") if image_data else None
        image_url = image_data.get("url") if image_data else None
        image_alt_text = image_data.get("altText") if image_data else None

        # Extract SEO data
        seo_data = collection_data.get("seo", {})
        seo_title = seo_data.get("title") if seo_data else None
        seo_description = seo_data.get("description") if seo_data else None

        # Extract product IDs from products
        product_ids = []
        products = collection_data.get("products", {}).get("edges", [])
        for product_edge in products:
            product_node = product_edge.get("node", {})
            if product_node.get("id"):
                product_ids.append(product_node["id"])

        return ShopifyCollection(
            id=collection_data.get("id", ""),
            title=collection_data.get("title", ""),
            handle=collection_data.get("handle", ""),
            description=collection_data.get("description"),
            description_html=collection_data.get("descriptionHtml"),
            seo_title=seo_title,
            seo_description=seo_description,
            sort_order=collection_data.get("sortOrder", "manual"),
            template_suffix=collection_data.get("templateSuffix"),
            products_count=len(product_ids),
            image_id=image_id,
            image_url=image_url,
            image_alt_text=image_alt_text,
            product_ids=product_ids,
            created_at=(
                datetime.fromisoformat(collection_data.get("createdAt"))
                if collection_data.get("createdAt")
                else now_utc()
            ),
            updated_at=(
                datetime.fromisoformat(collection_data.get("updatedAt"))
                if collection_data.get("updatedAt")
                else now_utc()
            ),
            raw_data={"collection": collection_data},
        )

    def _update_progress(
        self, shop_domain: str, data_type: str, progress: CollectionProgress
    ):
        """Update collection progress tracking"""
        if shop_domain not in self.collection_progress:
            self.collection_progress[shop_domain] = {}

        self.collection_progress[shop_domain][data_type] = progress

    def _update_collection_stats(
        self, shop_domain: str, collection_results: Dict[str, Any]
    ):
        """Update collection statistics"""
        self.collection_stats[shop_domain] = {
            "last_collection": now_utc().isoformat(),
            "total_items": collection_results.get("total_items", 0),
            "data_types_collected": [
                data_type
                for data_type in [
                    "products",
                    "orders",
                    "customers",
                    "collections",
                    "customer_events",
                ]
                if collection_results.get(data_type)
            ],
            "collection_duration": self._calculate_collection_duration(
                collection_results
            ),
            "success_rate": 1.0,  # Will be enhanced with error tracking
        }

    def _calculate_collection_duration(
        self, collection_results: Dict[str, Any]
    ) -> Optional[float]:
        """Calculate total collection duration in seconds"""
        started_at = collection_results.get("started_at")
        completed_at = collection_results.get("completed_at")

        if started_at and completed_at:
            try:
                start_time = datetime.fromisoformat(started_at)
                end_time = datetime.fromisoformat(completed_at)
                return (end_time - start_time).total_seconds()
            except ValueError:
                return None

        return None
