"""
Data collection service for gathering and saving Shopify data
"""

import asyncio
from datetime import datetime
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
from app.core.logging import get_logger, log_error, log_performance, log_data_collection

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
                    "totalAmount": float(order["totalAmount"]["shopMoney"]["amount"]),
                    "orderDate": datetime.fromisoformat(
                        order["orderDate"].replace("Z", "+00:00")
                    ),
                    "orderStatus": (
                        order.get("displayFinancialStatus")
                        or order.get("fulfillmentStatus")
                    ),
                    "currencyCode": (
                        order.get("currencyCode")
                        or order["totalAmount"]["shopMoney"].get("currencyCode")
                    ),
                    "lineItems": line_items,
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
                {"orders_count": len(orders), "is_incremental": is_incremental},
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
                        "tags": product.get("tags", []),
                        "imageUrl": product.get("image", {}).get("src"),
                        "imageAlt": product.get("image", {}).get("alt"),
                        "productCreatedAt": (
                            datetime.fromisoformat(
                                product["created_at"].replace("Z", "+00:00")
                            )
                            if product.get("created_at")
                            else None
                        ),
                        "variants": product.get("variants"),
                        "metafields": product.get("metafields"),
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
                        "tags": product.get("tags", []),
                        "imageUrl": product.get("image", {}).get("src"),
                        "imageAlt": product.get("image", {}).get("alt"),
                        "productCreatedAt": (
                            datetime.fromisoformat(
                                product["created_at"].replace("Z", "+00:00")
                            )
                            if product.get("created_at")
                            else None
                        ),
                        "variants": product.get("variants"),
                        "metafields": product.get("metafields"),
                        "isActive": True,
                    }
                    product_data.append(product_record)

                await self.db.productdata.create_many(data=product_data)

            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_performance(
                "save_products",
                duration_ms,
                {"products_count": len(products), "is_incremental": is_incremental},
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
                    "lastOrderId": customer.get("lastOrder", {}).get("id"),
                    "lastOrderDate": (
                        datetime.fromisoformat(
                            customer["lastOrder"]["processedAt"].replace("Z", "+00:00")
                        )
                        if customer.get("lastOrder", {}).get("processedAt")
                        else None
                    ),
                    "tags": customer.get("tags", []),
                    "location": customer.get("addresses", []),
                    "metafields": customer.get("metafields", []),
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
                {"customers_count": len(customers), "is_incremental": is_incremental},
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

                orders, products, customers = await asyncio.gather(
                    api_client.fetch_orders(since_date),
                    api_client.fetch_products(),
                    api_client.fetch_customers(since_date),
                )

                parallel_duration_ms = (
                    asyncio.get_event_loop().time() - parallel_start
                ) * 1000

                log_performance(
                    "parallel_data_collection",
                    parallel_duration_ms,
                    {
                        "shop_domain": config.shop_domain,
                        "orders_count": len(orders),
                        "products_count": len(products),
                        "customers_count": len(customers),
                    },
                )

                # Clear existing data
                await clear_shop_data(shop_db_id)

                # Save data to database in parallel
                await asyncio.gather(
                    self.save_products(shop_db_id, products, False),
                    self.save_orders(shop_db_id, orders, False),
                    self.save_customers(shop_db_id, customers, False),
                )

                # Update shop's last analysis timestamp
                await update_shop_last_analysis(shop_db_id)

                total_duration_ms = (
                    asyncio.get_event_loop().time() - start_time
                ) * 1000

                log_data_collection(
                    shop_id=config.shop_id,
                    operation="complete_data_collection",
                    duration_ms=total_duration_ms,
                )

                logger.info(
                    "Data collection and saving completed successfully",
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
                    {
                        "shop_domain": config.shop_domain,
                        "orders_count": len(orders),
                        "products_count": len(products),
                        "customers_count": len(customers),
                    },
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
