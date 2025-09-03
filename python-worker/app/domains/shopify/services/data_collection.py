"""
Shopify data collection service implementation for BetterBundle Python Worker
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from app.core.logging import get_logger
from app.core.exceptions import ConfigurationError
from app.shared.decorators import retry, async_timing
from app.shared.helpers import now_utc

from ..interfaces.data_collector import IShopifyDataCollector
from ..interfaces.api_client import IShopifyAPIClient
from ..interfaces.permission_service import IShopifyPermissionService
from ..models.shop import ShopifyShop
from ..models.product import ShopifyProduct, ShopifyProductVariant
from ..models.order import ShopifyOrder
from ..models.customer import ShopifyCustomer
from ..models.collection import ShopifyCollection
from ..models.customer_event import ShopifyCustomerEvent
from .data_storage import ShopifyDataStorageService

logger = get_logger(__name__)


@dataclass
class CollectionProgress:
    """Track progress of data collection"""

    shop_domain: str
    data_type: str
    total_items: int = 0
    collected_items: int = 0
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

        # Initialize data storage service
        self.data_storage = ShopifyDataStorageService()

        # Collection settings
        self.default_batch_size = 50
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
            logger.info(f"Starting shop data collection", shop_domain=shop_domain)

            # Check permissions first
            permissions = await self.permission_service.check_shop_permissions(
                shop_domain, access_token
            )
            if not permissions.get("has_access", False):
                logger.warning(f"No access to shop data", shop_domain=shop_domain)
                return None

            # Collect shop info
            shop_info = await self.api_client.get_shop_info(shop_domain, access_token)

            if not shop_info:
                logger.error(f"Failed to collect shop info", shop_domain=shop_domain)
                return None

            # Create ShopifyShop model
            shop = ShopifyShop(
                id=shop_info.get("id", ""),
                name=shop_info.get("name", ""),
                domain=shop_info.get("domain", shop_domain),
                email=shop_info.get("email"),
                phone=shop_info.get("phone"),
                address1=shop_info.get("address1"),
                address2=shop_info.get("address2"),
                city=shop_info.get("city"),
                province=shop_info.get("province"),
                country=shop_info.get("country"),
                zip=shop_info.get("zip"),
                currency=shop_info.get("currency", "USD"),
                primary_locale=shop_info.get("primaryLocale", "en"),
                timezone=shop_info.get("timezone"),
                plan_name=shop_info.get("planName"),
                plan_display_name=shop_info.get("planDisplayName"),
                shop_owner=shop_info.get("shopOwner"),
                has_storefront=shop_info.get("hasStorefront", False),
                has_discounts=shop_info.get("hasDiscounts", False),
                has_gift_cards=shop_info.get("hasGiftCards", False),
                has_marketing=shop_info.get("hasMarketing", False),
                has_multi_location=shop_info.get("hasMultiLocation", False),
                google_analytics_account=shop_info.get("googleAnalyticsAccount"),
                google_analytics_domain=shop_info.get("googleAnalyticsDomain"),
                seo_title=shop_info.get("seoTitle"),
                seo_description=shop_info.get("seoDescription"),
                meta_description=shop_info.get("metaDescription"),
                facebook_account=shop_info.get("facebookAccount"),
                instagram_account=shop_info.get("instagramAccount"),
                twitter_account=shop_info.get("twitterAccount"),
                myshopify_domain=shop_info.get("myshopifyDomain", shop_domain),
                primary_location_id=shop_info.get("primaryLocationId"),
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

            logger.info(
                f"Shop data collected successfully",
                shop_domain=shop_domain,
                shop_name=shop.name,
                plan=shop.plan_name,
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
        """Collect products data from Shopify API"""
        try:
            # Check permissions
            if not await self.permission_service.can_collect_products(shop_domain):
                logger.warning(
                    f"No permission to collect products", shop_domain=shop_domain
                )
                return []

            logger.info(
                f"Starting products collection",
                shop_domain=shop_domain,
                limit=limit,
                since_id=since_id,
            )

            products = []
            cursor = since_id
            batch_size = min(limit or self.default_batch_size, self.max_batch_size)

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

                # Get batch of products
                result = await self.api_client.get_products(
                    shop_domain=shop_domain,
                    access_token=access_token,
                    limit=batch_size,
                    cursor=cursor,
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

            logger.info(
                f"Products collection completed",
                shop_domain=shop_domain,
                total_products=len(products),
            )

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
        """Collect orders data from Shopify API"""
        try:
            # Check permissions
            if not await self.permission_service.can_collect_orders(shop_domain):
                logger.warning(
                    f"No permission to collect orders", shop_domain=shop_domain
                )
                return []

            logger.info(
                f"Starting orders collection",
                shop_domain=shop_domain,
                limit=limit,
                since_id=since_id,
                status=status,
            )

            # For now, return empty list as we haven't implemented the Order model yet
            # This will be implemented when we create the Order model
            logger.info(
                f"Orders collection not yet implemented", shop_domain=shop_domain
            )
            return []

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
        """Collect customers data from Shopify API"""
        try:
            # Check permissions
            if not await self.permission_service.can_collect_customers(shop_domain):
                logger.warning(
                    f"No permission to collect customers", shop_domain=shop_domain
                )
                return []

            logger.info(
                f"Starting customers collection",
                shop_domain=shop_domain,
                limit=limit,
                since_id=since_id,
            )

            # For now, return empty list as we haven't implemented the Customer model yet
            # This will be implemented when we create the Customer model
            logger.info(
                f"Customers collection not yet implemented", shop_domain=shop_domain
            )
            return []

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
        """Collect collections data from Shopify API"""
        try:
            # Check permissions
            if not await self.permission_service.can_collect_collections(shop_domain):
                logger.warning(
                    f"No permission to collect collections", shop_domain=shop_domain
                )
                return []

            logger.info(
                f"Starting collections collection",
                shop_domain=shop_domain,
                limit=limit,
                since_id=since_id,
            )

            # For now, return empty list as we haven't implemented the Collection model yet
            # This will be implemented when we create the Collection model
            logger.info(
                f"Collections collection not yet implemented", shop_domain=shop_domain
            )
            return []

        except Exception as e:
            logger.error(
                f"Failed to collect collections", shop_domain=shop_domain, error=str(e)
            )
            raise

    async def collect_customer_events(
        self,
        shop_domain: str,
        access_token: str = None,
        limit: Optional[int] = None,
        since_id: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> List[ShopifyCustomerEvent]:
        """Collect customer events data from Shopify API"""
        try:
            # Check permissions
            if not await self.permission_service.can_collect_customer_events(
                shop_domain
            ):
                logger.warning(
                    f"No permission to collect customer events", shop_domain=shop_domain
                )
                return []

            logger.info(
                f"Starting customer events collection",
                shop_domain=shop_domain,
                limit=limit,
                since_id=since_id,
                event_type=event_type,
            )

            # For now, return empty list as we haven't implemented the CustomerEvent model yet
            # This will be implemented when we create the CustomerEvent model
            logger.info(
                f"Customer events collection not yet implemented",
                shop_domain=shop_domain,
            )
            return []

        except Exception as e:
            logger.error(
                f"Failed to collect customer events",
                shop_domain=shop_domain,
                error=str(e),
            )
            raise

    async def collect_all_data(
        self,
        shop_domain: str,
        access_token: str = None,
        include_products: bool = True,
        include_orders: bool = True,
        include_customers: bool = True,
        include_collections: bool = True,
        include_customer_events: bool = True,
    ) -> Dict[str, Any]:
        """Collect all available data from Shopify API"""
        try:
            logger.info(
                f"Starting comprehensive data collection", shop_domain=shop_domain
            )

            # Get collection strategy based on permissions
            strategy = await self.permission_service.get_collection_strategy(
                shop_domain, access_token
            )
            collectable_data = strategy.get("collectable_data", [])

            if not collectable_data:
                logger.warning(f"No data can be collected", shop_domain=shop_domain)
                return {
                    "shop": None,
                    "message": "No data can be collected due to missing permissions",
                }

            # Initialize collection results
            collection_results = {
                "shop": None,
                "products": [],
                "orders": [],
                "customers": [],
                "collections": [],
                "customer_events": [],
                "collection_strategy": strategy,
                "collection_stats": {},
                "started_at": now_utc().isoformat(),
            }

            # Collect shop data first
            shop = await self.collect_shop_data(shop_domain, access_token)
            collection_results["shop"] = shop

            # Store shop data in database
            if shop:
                try:
                    shop_metrics = await self.data_storage.store_shop_data(
                        shop, shop.id
                    )
                    logger.info(
                        f"Shop data stored: {shop_metrics.new_items} new, {shop_metrics.updated_items} updated"
                    )
                except Exception as e:
                    logger.error(f"Failed to store shop data: {e}")

            # Collect data based on permissions and preferences
            collection_tasks = []

            if "products" in collectable_data and include_products:
                collection_tasks.append(
                    self._collect_with_progress("products", shop_domain, access_token)
                )

            if "orders" in collectable_data and include_orders:
                collection_tasks.append(
                    self._collect_with_progress("orders", shop_domain, access_token)
                )

            if "customers" in collectable_data and include_customers:
                collection_tasks.append(
                    self._collect_with_progress("customers", shop_domain, access_token)
                )

            if "collections" in collectable_data and include_collections:
                collection_tasks.append(
                    self._collect_with_progress(
                        "collections", shop_domain, access_token
                    )
                )

            if "customer_events" in collectable_data and include_customer_events:
                collection_tasks.append(
                    self._collect_with_progress(
                        "customer_events", shop_domain, access_token
                    )
                )

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
                        data_type = collection_tasks[i].__name__.split("_")[-1]
                        collection_results[data_type] = result

                        # Store collected data using enterprise-grade storage service
                        if result and len(result) > 0:
                            try:
                                if data_type == "products":
                                    storage_result = (
                                        await self.data_storage.store_products_data(
                                            result, shop.id
                                        )
                                    )
                                    logger.info(
                                        f"Products data stored: {storage_result.new_items} new, {storage_result.updated_items} updated"
                                    )
                                elif data_type == "orders":
                                    storage_result = (
                                        await self.data_storage.store_orders_data(
                                            result, shop.id
                                        )
                                    )
                                    logger.info(
                                        f"Orders data stored: {storage_result.new_items} new, {storage_result.updated_items} updated"
                                    )
                                elif data_type == "customers":
                                    storage_result = (
                                        await self.data_storage.store_customers_data(
                                            result, shop.id
                                        )
                                    )
                                    logger.info(
                                        f"Customers data stored: {storage_result.new_items} new, {storage_result.updated_items} updated"
                                    )
                                elif data_type == "collections":
                                    storage_result = (
                                        await self.data_storage.store_collections_data(
                                            result, shop.id
                                        )
                                    )
                                    logger.info(
                                        f"Collections data stored: {storage_result.new_items} new, {storage_result.updated_items} updated"
                                    )
                                elif data_type == "customer_events":
                                    storage_result = await self.data_storage.store_customer_events_data(
                                        result, shop.id
                                    )
                                    logger.info(
                                        f"Customer events data stored: {storage_result.new_items} new, {storage_result.updated_items} updated"
                                    )
                            except Exception as storage_error:
                                logger.error(
                                    f"Failed to store {data_type} data",
                                    shop_domain=shop_domain,
                                    data_type=data_type,
                                    error=str(storage_error),
                                )

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

            logger.info(
                f"Comprehensive data collection completed",
                shop_domain=shop_domain,
                total_items=collection_results["total_items"],
            )

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

    async def _create_product_from_data(
        self, product_data: Dict[str, Any]
    ) -> ShopifyProduct:
        """Create ShopifyProduct from API data"""
        # Extract basic product info
        product = ShopifyProduct(
            id=product_data.get("id", ""),
            title=product_data.get("title", ""),
            body_html=product_data.get("bodyHtml"),
            vendor=product_data.get("vendor", ""),
            product_type=product_data.get("productType", ""),
            handle=product_data.get("handle", ""),
            seo_title=product_data.get("seoTitle"),
            seo_description=product_data.get("seoDescription"),
            meta_description=product_data.get("metaDescription"),
            status=product_data.get("status", "active"),
            published_at=(
                datetime.fromisoformat(product_data.get("publishedAt"))
                if product_data.get("publishedAt")
                else None
            ),
            published_scope=product_data.get("publishedScope", "web"),
            tags=product_data.get("tags", []),
            template_suffix=product_data.get("templateSuffix"),
            created_at=(
                datetime.fromisoformat(product_data.get("createdAt"))
                if product_data.get("createdAt")
                else None
            ),
            updated_at=(
                datetime.fromisoformat(product_data.get("updatedAt"))
                if product_data.get("updatedAt")
                else None
            ),
            raw_data={"product": product_data},
        )

        # Extract image IDs
        images = product_data.get("images", {}).get("edges", [])
        product.image_ids = [
            edge["node"]["id"] for edge in images if edge.get("node", {}).get("id")
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
                inventory_management=variant_data.get("inventoryManagement"),
                weight=(
                    float(variant_data.get("weight"))
                    if variant_data.get("weight")
                    else None
                ),
                weight_unit=variant_data.get("weightUnit", "g"),
                requires_shipping=variant_data.get("requiresShipping", True),
                taxable=variant_data.get("taxable", True),
                option1=variant_data.get("option1"),
                option2=variant_data.get("option2"),
                option3=variant_data.get("option3"),
                created_at=(
                    datetime.fromisoformat(variant_data.get("createdAt"))
                    if variant_data.get("createdAt")
                    else None
                ),
                updated_at=(
                    datetime.fromisoformat(variant_data.get("updatedAt"))
                    if variant_data.get("updatedAt")
                    else None
                ),
                raw_data={"variant": variant_data},
            )
            product.add_variant(variant)

        # Extract collection IDs
        collections = product_data.get("collections", {}).get("edges", [])
        product.collection_ids = [
            edge["node"]["id"] for edge in collections if edge.get("node", {}).get("id")
        ]

        return product

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
