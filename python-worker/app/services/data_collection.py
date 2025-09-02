"""
Data collection service for gathering and saving Shopify data
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import (
    get_database,
    get_or_create_shop,
    clear_shop_data,
    update_shop_last_analysis,
    get_latest_timestamps,
)
from app.services.shopify_api import ShopifyAPIClient, calculate_since_date
from app.core.logging import get_logger, log_error, log_data_collection, log_performance
from prisma import Json

logger = get_logger(__name__)


class DataCollectionConfig(BaseModel):
    """Configuration for data collection"""

    shop_id: str
    shop_domain: str
    access_token: str
    days_back: Optional[int] = None
    is_incremental: bool = False


class DataCollectionResult(BaseModel):
    """Result of data collection operation"""

    shop_db_id: str
    orders_count: int
    products_count: int
    customers_count: int
    duration_ms: float
    success: bool
    error: Optional[str] = None


class DataCollectionService:
    """Service for collecting and saving Shopify data"""

    def __init__(self):
        self.db = None

    async def initialize(self):
        """Initialize database connection"""
        self.db = await get_database()

    async def get_shop_config(self, shop_id: str) -> Optional[Dict[str, Any]]:
        """Get shop configuration from database"""
        try:
            # Try to find shop by ID first (in case shop_id is the database ID)
            shop = await self.db.shop.find_first(where={"id": shop_id})

            if not shop:
                # If not found by ID, try by domain (in case shop_id is the domain)
                shop = await self.db.shop.find_first(where={"shopDomain": shop_id})

            if not shop:
                raise Exception(f"Shop not found in database for shop_id: {shop_id}")

            # Return shop configuration
            return {
                "shop_id": shop.id,  # Use the database ID
                "shop_domain": shop.shopDomain,
                "access_token": shop.accessToken,
                "days_back": None,  # Could be configurable in the future
            }

        except Exception as e:
            logger.error(
                f"Failed to get shop config from database: {e}", shop_id=shop_id
            )
            raise Exception(f"Failed to get shop configuration: {str(e)}")

    async def get_or_create_shop_db_id(self, config) -> str:
        """Get or create shop record in database and return the database ID"""
        try:
            # First try to find existing shop by domain
            shop = await self.db.shop.find_first(
                where={"shopDomain": config.shop_domain}
            )

            if shop:
                logger.info(f"Found existing shop by domain: {shop.id}")
                return shop.id

            # Create new shop if it doesn't exist
            logger.info(f"Creating new shop record for domain: {config.shop_domain}")
            new_shop = await self.db.shop.create(
                data={
                    "shopDomain": config.shop_domain,
                    "accessToken": config.access_token,
                    "createdAt": datetime.now(),
                    "updatedAt": datetime.now(),
                }
            )

            logger.info(f"Created shop record with ID: {new_shop.id}")
            return new_shop.id

        except Exception as e:
            logger.error(f"Failed to get or create shop: {e}", config=config)
            raise Exception(f"Failed to get or create shop: {str(e)}")

    async def save_orders(
        self,
        shop_db_id: str,
        orders: List[Dict[str, Any]],
        is_incremental: bool = False,
    ) -> None:
        """Save orders to database"""
        if not orders:
            logger.info("No orders to save")
            return

        start_time = asyncio.get_event_loop().time()

        try:
            logger.info(
                "Processing orders for database",
                orders_count=len(orders),
                is_incremental=is_incremental,
            )

            # Transform orders data
            order_data = []
            for order in orders:
                # Transform lineItems from GraphQL structure to clean array
                line_items = []
                if order.get("lineItems") and "edges" in order["lineItems"]:
                    line_items = [edge["node"] for edge in order["lineItems"]["edges"]]
                elif isinstance(order.get("lineItems"), list):
                    line_items = order["lineItems"]

                order_record = {
                    "shopId": shop_db_id,
                    "orderId": order["orderId"],
                    "customerId": (
                        order.get("customerId", {}).get("id")
                        if order.get("customerId")
                        else None
                    ),
                    "totalAmount": float(
                        ((order.get("totalAmount") or {}).get("shopMoney") or {}).get(
                            "amount", 0
                        )
                    ),
                    "orderDate": datetime.fromisoformat(
                        order["orderDate"].replace("Z", "+00:00")
                    ),
                    # Normalized fields
                    "orderStatus": order.get("displayFinancialStatus"),
                    "lineItems": Json(line_items),
                }
                order_data.append(order_record)

            # Save to database
            if is_incremental:
                # For incremental saves, use upsert for each order
                for order_record in order_data:
                    await self.db.orderdata.upsert(
                        where={
                            "shopId_orderId": {
                                "shopId": order_record["shopId"],
                                "orderId": order_record["orderId"],
                            }
                        },
                        data=order_record,
                        update={
                            key: value
                            for key, value in order_record.items()
                            if key not in ["shopId", "orderId"]
                        },
                    )
            else:
                # For complete saves, use create_many for better performance
                await self.db.orderdata.create_many(
                    data=order_data, skip_duplicates=False
                )

            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_performance(
                "save_orders",
                duration_ms,
                orders_count=len(orders),
                is_incremental=is_incremental,
            )

            log_data_collection(
                shop_id=shop_db_id,
                operation="save_orders",
                items_count=len(orders),
                duration_ms=duration_ms,
            )

        except Exception as e:
            log_error(
                e,
                {
                    "operation": "save_orders",
                    "shop_db_id": shop_db_id,
                    "orders_count": len(orders),
                },
            )
            raise

    async def save_raw_products(
        self,
        shop_db_id: str,
        products: List[Dict[str, Any]],
    ) -> None:
        """Save raw product data to RawProduct table"""
        try:
            logger.info(f"Saving {len(products)} raw products to RawProduct table")

            # Clear existing raw products for this shop
            await self.db.rawproduct.delete_many(where={"shopId": shop_db_id})

            # Save raw products
            raw_products = []
            for product in products:
                raw_products.append(
                    {
                        "shopId": shop_db_id,
                        "payload": Json(product),
                    }
                )

            await self.db.rawproduct.create_many(data=raw_products)
            logger.info(f"Successfully saved {len(products)} raw products")

        except Exception as e:
            logger.error(f"Failed to save raw products: {e}")
            # Don't fail the entire process if raw saving fails

    async def save_products(
        self,
        shop_db_id: str,
        products: List[Dict[str, Any]],
        is_incremental: bool = False,
    ) -> None:
        """Save products to database"""
        if not products:
            logger.info("No products to save")
            return

        start_time = asyncio.get_event_loop().time()

        try:
            logger.info(
                "Processing products for database",
                products_count=len(products),
                is_incremental=is_incremental,
            )

            if is_incremental:
                # For incremental saves, use upsert to update existing or create new
                for product in products:
                    product_record = {
                        "shopId": shop_db_id,
                        "productId": str(product["id"]),
                        "title": product["title"],
                        "handle": product["handle"],
                        "category": product.get("product_type"),
                        "price": float(
                            product.get("variants", [{}])[0].get("price", 0)
                        ),
                        "inventory": product.get("variants", [{}])[0].get(
                            "inventory_quantity", 0
                        ),
                        "tags": Json(product.get("tags", [])),
                        "imageUrl": product.get("image", {}).get("src"),
                        "imageAlt": product.get("image", {}).get("alt"),
                        "isActive": True,
                    }

                    await self.db.productdata.upsert(
                        where={
                            "shopId_productId": {
                                "shopId": shop_db_id,
                                "productId": str(product["id"]),
                            }
                        },
                        data=product_record,
                        update={
                            key: value
                            for key, value in product_record.items()
                            if key not in ["shopId", "productId"]
                        },
                    )
            else:
                # First, save raw data to RawProduct table
                await self.save_raw_products(shop_db_id, products)

                # For complete saves, use create_many for better performance
                product_data = []
                for product in products:
                    product_record = {
                        "shopId": shop_db_id,
                        "productId": str(product["id"]),
                        "title": product["title"],
                        "handle": product["handle"],
                        "description": product.get("description"),
                        "category": product.get("product_type"),
                        "vendor": product.get("vendor"),
                        "price": float(
                            product.get("variants", [{}])[0].get("price", 0)
                        ),
                        "compareAtPrice": (
                            float(product["variants"][0]["compareAtPrice"])
                            if product.get("variants")
                            and product["variants"][0].get("compareAtPrice")
                            else None
                        ),
                        "inventory": product.get("variants", [{}])[0].get(
                            "inventory_quantity", 0
                        ),
                        "tags": Json(product.get("tags", [])),
                        "imageUrl": product.get("image", {}).get("src"),
                        "imageAlt": product.get("image", {}).get("alt"),
                        "productCreatedAt": (
                            datetime.fromisoformat(
                                product["created_at"].replace("Z", "+00:00")
                            )
                            if product.get("created_at")
                            else None
                        ),
                        "variants": Json(product.get("variants")),
                        "metafields": Json(product.get("metafields")),
                        "isActive": True,
                    }
                    product_data.append(product_record)

                await self.db.productdata.create_many(data=product_data)

            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_performance(
                "save_products",
                duration_ms,
                products_count=len(products),
                is_incremental=is_incremental,
            )

            log_data_collection(
                shop_id=shop_db_id,
                operation="save_products",
                items_count=len(products),
                duration_ms=duration_ms,
            )

        except Exception as e:
            log_error(
                e,
                {
                    "operation": "save_products",
                    "shop_db_id": shop_db_id,
                    "products_count": len(products),
                },
            )
            raise

    async def save_customers(
        self,
        shop_db_id: str,
        customers: List[Dict[str, Any]],
        is_incremental: bool = False,
    ) -> None:
        """Save customers to database"""
        if not customers:
            logger.info("No customers to save")
            return

        start_time = asyncio.get_event_loop().time()

        try:
            logger.info(
                "Processing customers for database",
                customers_count=len(customers),
                is_incremental=is_incremental,
            )

            # Always use upsert for customers (they can be updated)
            for customer in customers:
                # Defensive reads for optional/nested fields
                last_order = customer.get("lastOrder") or {}
                tags_val = customer.get("tags") or []
                addresses_val = customer.get("addresses") or []
                metafields_val = customer.get("metafields") or {}

                customer_record = {
                    "shopId": shop_db_id,
                    "customerId": customer["id"],
                    "email": customer.get("email"),
                    "firstName": customer.get("firstName"),
                    "lastName": customer.get("lastName"),
                    "createdAtShopify": (
                        datetime.fromisoformat(
                            customer["createdAt"].replace("Z", "+00:00")
                        )
                        if customer.get("createdAt")
                        else None
                    ),
                    "lastOrderId": last_order.get("id"),
                    "lastOrderDate": (
                        datetime.fromisoformat(
                            last_order["processedAt"].replace("Z", "+00:00")
                        )
                        if last_order.get("processedAt")
                        else None
                    ),
                    "tags": Json(tags_val),
                    "location": Json(addresses_val),
                    "metafields": Json(metafields_val),
                }

                await self.db.customerdata.upsert(
                    where={
                        "shopId_customerId": {
                            "shopId": shop_db_id,
                            "customerId": customer["id"],
                        }
                    },
                    data=customer_record,
                    update={
                        key: value
                        for key, value in customer_record.items()
                        if key not in ["shopId", "customerId"]
                    },
                )

            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_performance(
                "save_customers",
                duration_ms,
                customers_count=len(customers),
                is_incremental=is_incremental,
            )

            log_data_collection(
                shop_id=shop_db_id,
                operation="save_customers",
                items_count=len(customers),
                duration_ms=duration_ms,
            )

        except Exception as e:
            log_error(
                e,
                {
                    "operation": "save_customers",
                    "shop_db_id": shop_db_id,
                    "customers_count": len(customers),
                },
            )
            raise

    async def collect_and_save_complete_data(
        self, config: DataCollectionConfig
    ) -> DataCollectionResult:
        """Collect and save complete shop data"""
        start_time = asyncio.get_event_loop().time()

        logger.info(
            "Starting complete data collection",
            shop_id=config.shop_id,
            shop_domain=config.shop_domain,
            days_back=config.days_back or settings.MAX_INITIAL_DAYS,
        )

        try:
            # Ensure database is initialized
            if not self.db:
                await self.initialize()

            # Get or create shop record
            shop = await get_or_create_shop(
                config.shop_id, config.shop_domain, config.access_token
            )
            shop_db_id = shop.id

            # Calculate since date
            since_date = calculate_since_date(
                config.days_back or settings.MAX_INITIAL_DAYS
            )

            logger.info(
                "Complete data collection - fetching data from configured period",
                shop_domain=config.shop_domain,
                since_date=since_date,
                days_back=config.days_back or settings.MAX_INITIAL_DAYS,
            )

            # Create Shopify API client
            api_client = ShopifyAPIClient(config.shop_domain, config.access_token)

            try:
                # Collect data in parallel for better performance
                logger.info("Fetching orders, products, and customers in parallel")

                parallel_start = asyncio.get_event_loop().time()

                # Collect data in parallel with timeout protection
                try:
                    async with asyncio.timeout(
                        300
                    ):  # 5 minute timeout for entire parallel operation
                        orders, products, customers = await asyncio.gather(
                            api_client.fetch_orders(since_date),
                            api_client.fetch_products(),
                            api_client.fetch_customers(since_date),
                        )
                except asyncio.TimeoutError:
                    logger.error(
                        "Data collection timed out after 5 minutes",
                        shop_domain=config.shop_domain,
                        since_date=since_date,
                    )
                    raise Exception(
                        "Data collection timed out - Shopify API calls took too long"
                    )

                # Log what we collected
                logger.info(
                    "Data collection results",
                    shop_domain=config.shop_domain,
                    orders_count=len(orders),
                    products_count=len(products),
                    customers_count=len(customers),
                    has_customer_access=customers is not None and len(customers) > 0,
                )

                # If no customers, that's okay - we can still do analysis
                if not customers:
                    customers = []
                    logger.info(
                        "No customer data available - continuing with orders and products only",
                        shop_domain=config.shop_domain,
                    )

                parallel_duration_ms = (
                    asyncio.get_event_loop().time() - parallel_start
                ) * 1000

                log_performance(
                    "parallel_data_collection",
                    parallel_duration_ms,
                    shop_domain=config.shop_domain,
                    orders_count=len(orders),
                    products_count=len(products),
                    customers_count=len(customers),
                )

                # Clear existing data
                await clear_shop_data(shop_db_id)

                # Save data to database in parallel
                try:
                    async with asyncio.timeout(120):  # 2 minute timeout for saving data
                        await asyncio.gather(
                            self.save_products(shop_db_id, products, False),
                            self.save_orders(shop_db_id, orders, False),
                            self.save_customers(shop_db_id, customers, False),
                        )
                except asyncio.TimeoutError:
                    logger.error(
                        "Data saving timed out after 2 minutes",
                        shop_domain=config.shop_domain,
                        shop_db_id=shop_db_id,
                    )
                    raise Exception(
                        "Data saving timed out - database operations took too long"
                    )

                # Update shop's last analysis timestamp
                await update_shop_last_analysis(shop_db_id)

                # Notify user about data collection results
                try:
                    from app.core.redis_client import streams_manager

                    if customers:
                        await streams_manager.publish_user_notification_event(
                            shop_id=config.shop_id,
                            notification_type="data_collection_completed",
                            message=f"Data collection completed successfully! Collected {len(orders)} orders, {len(products)} products, and {len(customers)} customers.",
                            data={
                                "orders_count": len(orders),
                                "products_count": len(products),
                                "customers_count": len(customers),
                                "has_full_data": True,
                            },
                        )
                    else:
                        await streams_manager.publish_user_notification_event(
                            shop_id=config.shop_id,
                            notification_type="data_collection_completed_limited",
                            message=f"✅ Data collection completed! Collected {len(orders)} orders and {len(products)} products. We'll analyze product bundles and recommendations using this data.",
                            data={
                                "orders_count": len(orders),
                                "products_count": len(products),
                                "customers_count": 0,
                                "has_full_data": False,
                                "note": "Customer data access not available - using orders and products for analysis",
                            },
                        )
                except Exception as notification_error:
                    logger.warning(
                        "Failed to send data collection notification",
                        error=str(notification_error),
                        shop_id=config.shop_id,
                    )

                total_duration_ms = (
                    asyncio.get_event_loop().time() - start_time
                ) * 1000

                log_data_collection(
                    shop_id=config.shop_id,
                    operation="complete_data_collection",
                    duration_ms=total_duration_ms,
                )

                # Log success with data availability info
                if customers:
                    logger.info(
                        "Data collection and saving completed successfully with full data",
                        shop_id=config.shop_id,
                        shop_domain=config.shop_domain,
                        products_saved=len(products),
                        orders_saved=len(orders),
                        customers_saved=len(customers),
                        total_duration_ms=total_duration_ms,
                    )
                else:
                    logger.info(
                        "Data collection completed with limited data (no customer access)",
                        shop_id=config.shop_id,
                        shop_domain=config.shop_domain,
                        products_saved=len(products),
                        orders_saved=len(orders),
                        customers_saved=0,
                        total_duration_ms=total_duration_ms,
                        note="Customer data access denied by Shopify - analysis will use orders and products only",
                    )

                return DataCollectionResult(
                    shop_db_id=shop_db_id,
                    orders_count=len(orders),
                    products_count=len(products),
                    customers_count=len(customers),
                    duration_ms=total_duration_ms,
                    success=True,
                )

            finally:
                await api_client.close()

        except Exception as e:
            total_duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            log_error(
                e,
                {
                    "operation": "complete_data_collection",
                    "shop_id": config.shop_id,
                    "shop_domain": config.shop_domain,
                    "total_duration_ms": total_duration_ms,
                },
            )

            return DataCollectionResult(
                shop_db_id="",
                orders_count=0,
                products_count=0,
                customers_count=0,
                duration_ms=total_duration_ms,
                success=False,
                error=str(e),
            )

    async def collect_and_save_incremental_data(
        self, config: DataCollectionConfig
    ) -> DataCollectionResult:
        """Collect and save incremental shop data"""
        start_time = asyncio.get_event_loop().time()

        logger.info(
            "Starting incremental data collection",
            shop_id=config.shop_id,
            shop_domain=config.shop_domain,
        )

        try:
            # Ensure database is initialized
            if not self.db:
                await self.initialize()

            # Get or create shop record
            shop = await get_or_create_shop(
                config.shop_id, config.shop_domain, config.access_token
            )
            shop_db_id = shop.id

            # Determine since date for incremental collection
            since_date = None
            collection_type = ""

            # Get the latest timestamps from database
            timestamps = await get_latest_timestamps(shop_db_id)

            if shop.lastAnalysisAt:
                # Use last analysis timestamp as starting point
                since_date = shop.lastAnalysisAt.isoformat()
                collection_type = "incremental_since_last_analysis"
            elif timestamps["latest_order_date"] or timestamps["latest_product_date"]:
                # Use the latest data timestamp as starting point
                latest_timestamp = max(
                    filter(
                        None,
                        [
                            timestamps["latest_order_date"],
                            timestamps["latest_product_date"],
                        ],
                    )
                )
                since_date = latest_timestamp.isoformat()
                collection_type = "incremental_since_latest_data"
            else:
                # Fallback to configured days if no timestamps exist
                since_date = calculate_since_date(settings.FALLBACK_DAYS)
                collection_type = "incremental_fallback"

            logger.info(
                f"Collecting incremental data since {collection_type}",
                since_date=since_date,
                collection_type=collection_type,
            )

            # Create Shopify API client
            api_client = ShopifyAPIClient(config.shop_domain, config.access_token)

            try:
                # Collect incremental data in parallel
                logger.info(
                    "Fetching incremental orders, products, and customers in parallel"
                )

                parallel_start = asyncio.get_event_loop().time()

                orders, products, customers = await asyncio.gather(
                    api_client.fetch_orders(since_date),
                    api_client.fetch_products(since_date),
                    api_client.fetch_customers(since_date),
                )

                parallel_duration_ms = (
                    asyncio.get_event_loop().time() - parallel_start
                ) * 1000

                log_performance(
                    "parallel_incremental_collection",
                    parallel_duration_ms,
                    shop_domain=config.shop_domain,
                    orders_count=len(orders),
                    products_count=len(products),
                    customers_count=len(customers),
                )

                # Save incremental data to database in parallel
                await asyncio.gather(
                    self.save_products(shop_db_id, products, True),
                    self.save_orders(shop_db_id, orders, True),
                    self.save_customers(shop_db_id, customers, True),
                )

                # Update shop's last analysis timestamp
                await update_shop_last_analysis(shop_db_id)

                total_duration_ms = (
                    asyncio.get_event_loop().time() - start_time
                ) * 1000

                log_data_collection(
                    shop_id=config.shop_id,
                    operation="incremental_data_collection",
                    duration_ms=total_duration_ms,
                )

                logger.info(
                    "Incremental data collection and saving completed successfully",
                    shop_id=config.shop_id,
                    shop_domain=config.shop_domain,
                    products_saved=len(products),
                    orders_saved=len(orders),
                    customers_saved=len(customers),
                    total_duration_ms=total_duration_ms,
                )

                return DataCollectionResult(
                    shop_db_id=shop_db_id,
                    orders_count=len(orders),
                    products_count=len(products),
                    customers_count=len(customers),
                    duration_ms=total_duration_ms,
                    success=True,
                )

            finally:
                await api_client.close()

        except Exception as e:
            total_duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000

            log_error(
                e,
                {
                    "operation": "incremental_data_collection",
                    "shop_id": config.shop_id,
                    "shop_domain": config.shop_domain,
                    "total_duration_ms": total_duration_ms,
                },
            )

            return DataCollectionResult(
                shop_db_id="",
                orders_count=0,
                products_count=0,
                customers_count=0,
                duration_ms=total_duration_ms,
                success=False,
                error=str(e),
            )

    async def get_existing_products_count(self, shop_db_id: str) -> int:
        """Get count of existing products for a shop"""
        try:
            count = await self.db.productdata.count(where={"shopId": shop_db_id})
            return count
        except Exception as e:
            logger.error(f"Failed to get existing products count: {e}")
            return 0

    async def get_existing_orders_count(self, shop_db_id: str) -> int:
        """Get count of existing orders for a shop"""
        try:
            count = await self.db.orderdata.count(where={"shopId": shop_db_id})
            return count
        except Exception as e:
            logger.error(f"Failed to get existing orders count: {e}")
            return 0

    async def get_existing_customers_count(self, shop_db_id: str) -> int:
        """Get count of existing customers for a shop"""
        try:
            count = await self.db.customerdata.count(where={"shopId": shop_db_id})
            return count
        except Exception as e:
            logger.error(f"Failed to get existing customers count: {e}")
            return 0

    async def update_shop_last_products_collection(self, shop_db_id: str):
        """Update shop's last products collection timestamp"""
        try:
            await self.db.shop.update(
                where={"id": shop_db_id},
                data={"lastAnalysisAt": datetime.utcnow()},
            )
        except Exception as e:
            logger.error(f"Failed to update last products collection timestamp: {e}")

    async def update_shop_last_orders_collection(self, shop_db_id: str):
        """Update shop's last orders collection timestamp"""
        try:
            await self.db.shop.update(
                where={"id": shop_db_id},
                data={"lastAnalysisAt": datetime.utcnow()},
            )
        except Exception as e:
            logger.error(f"Failed to update last orders collection timestamp: {e}")

    async def update_shop_last_customers_collection(self, shop_db_id: str):
        """Update shop's last customers collection timestamp"""
        try:
            await self.db.shop.update(
                where={"id": shop_db_id},
                data={"lastAnalysisAt": datetime.utcnow()},
            )
        except Exception as e:
            logger.error(f"Failed to update last customers collection timestamp: {e}")

    def calculate_since_date(self, days_back: int) -> str:
        """Calculate the since date for data collection"""
        since_date = datetime.utcnow() - timedelta(days=days_back)
        return since_date.isoformat()

    async def collect_products_only(
        self, shop_id: str, shop_config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Collect only products data - idempotent operation"""
        try:
            logger.info("Starting products-only data collection", shop_id=shop_id)

            # Use provided shop config or get from database
            if shop_config:
                config = shop_config
            else:
                config = await self.get_shop_config(shop_id)
                if not config:
                    raise Exception(
                        f"Shop configuration not found for shop_id: {shop_id}"
                    )

            # Check if we already have recent products data
            shop_db_id = await self.get_or_create_shop_db_id(config)
            existing_products = await self.get_existing_products_count(shop_db_id)

            if existing_products > 0:
                logger.info(
                    "Products data already exists, skipping collection",
                    shop_id=shop_id,
                    existing_count=existing_products,
                )
                return {
                    "success": True,
                    "message": "Products data already exists",
                    "products_count": existing_products,
                    "skipped": True,
                }

            # Create Shopify API client
            api_client = ShopifyAPIClient(config.shop_domain, config.access_token)

            try:
                # Collect only products
                logger.info("Fetching products data")
                products = await api_client.fetch_products()

                logger.info(
                    "Products collection completed",
                    shop_domain=config.shop_domain,
                    products_count=len(products),
                )

                # Save products to database
                await self.save_products(shop_db_id, products, False)

                # Update shop's last products collection timestamp
                await self.update_shop_last_products_collection(shop_db_id)

                return {
                    "success": True,
                    "message": "Products collected successfully",
                    "products_count": len(products),
                    "skipped": False,
                }

            finally:
                await api_client.close()

        except Exception as e:
            logger.error("Products collection failed", shop_id=shop_id, error=str(e))
            return {
                "success": False,
                "message": f"Products collection failed: {str(e)}",
                "products_count": 0,
                "skipped": False,
            }

    async def collect_orders_only(
        self, shop_id: str, shop_config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Collect only orders data - idempotent operation"""
        try:
            logger.info("Starting orders-only data collection", shop_id=shop_id)

            # Use provided shop config or get from database
            if shop_config:
                config = shop_config
            else:
                config = await self.get_shop_config(shop_id)
                if not config:
                    raise Exception(
                        f"Shop configuration not found for shop_id: {shop_id}"
                    )

            # Check if we already have recent orders data
            shop_db_id = await self.get_or_create_shop_db_id(config)
            existing_orders = await self.get_existing_orders_count(shop_db_id)

            if existing_orders > 0:
                logger.info(
                    "Orders data already exists, skipping collection",
                    shop_id=shop_id,
                    existing_count=existing_orders,
                )
                return {
                    "success": True,
                    "message": "Orders data already exists",
                    "orders_count": existing_orders,
                    "skipped": True,
                }

            # Create Shopify API client
            api_client = ShopifyAPIClient(config.shop_domain, config.access_token)

            try:
                # Calculate since date
                since_date = self.calculate_since_date(
                    config.days_back or settings.MAX_INITIAL_DAYS
                )

                # Collect only orders
                logger.info("Fetching orders data", since_date=since_date)
                orders = await api_client.fetch_orders(since_date)

                logger.info(
                    "Orders collection completed",
                    shop_domain=config.shop_domain,
                    orders_count=len(orders),
                )

                # Save orders to database
                await self.save_orders(shop_db_id, orders, False)

                # Update shop's last orders collection timestamp
                await self.update_shop_last_orders_collection(shop_db_id)

                return {
                    "success": True,
                    "message": "Orders collected successfully",
                    "orders_count": len(orders),
                    "skipped": False,
                }

            finally:
                await api_client.close()

        except Exception as e:
            logger.error("Orders collection failed", shop_id=shop_id, error=str(e))
            return {
                "success": False,
                "message": f"Orders collection failed: {str(e)}",
                "orders_count": 0,
                "skipped": False,
            }

    async def collect_customers_only(
        self, shop_id: str, shop_config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Collect only customers data - idempotent operation"""
        try:
            logger.info("Starting customers-only data collection", shop_id=shop_id)

            # Use provided shop config or get from database
            if shop_config:
                config = shop_config
            else:
                config = await self.get_shop_config(shop_id)
                if not config:
                    raise Exception(
                        f"Shop configuration not found for shop_id: {shop_id}"
                    )

            # Check if we already have recent customers data
            shop_db_id = await self.get_or_create_shop_db_id(config)
            existing_customers = await self.get_existing_customers_count(shop_db_id)

            if existing_customers > 0:
                logger.info(
                    "Customers data already exists, skipping collection",
                    shop_id=shop_id,
                    existing_count=existing_customers,
                )
                return {
                    "success": True,
                    "message": "Customers data already exists",
                    "customers_count": existing_customers,
                    "skipped": False,
                }

            # Create Shopify API client
            api_client = ShopifyAPIClient(config.shop_domain, config.access_token)

            try:
                # Calculate since date
                since_date = self.calculate_since_date(
                    config.days_back or settings.MAX_INITIAL_DAYS
                )

                # Collect only customers
                logger.info("Fetching customers data", since_date=since_date)
                customers = await api_client.fetch_customers(since_date)

                logger.info(
                    "Customers collection completed",
                    shop_domain=config.shop_domain,
                    customers_count=len(customers),
                )

                # Save customers to database
                await self.save_customers(shop_db_id, customers, False)

                # Update shop's last customers collection timestamp
                await self.update_shop_last_customers_collection(shop_db_id)

                return {
                    "success": True,
                    "message": "Customers collected successfully",
                    "customers_count": len(customers),
                    "skipped": False,
                }

            finally:
                await api_client.close()

        except Exception as e:
            logger.error("Customers collection failed", shop_id=shop_id, error=str(e))
            return {
                "success": False,
                "message": f"Customers collection failed: {str(e)}",
                "customers_count": 0,
                "skipped": False,
            }
