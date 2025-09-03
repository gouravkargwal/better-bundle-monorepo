import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

from app.core.config import settings
from app.core.database import (
    get_database,
)
from app.utils.shopify_client import ShopifyEnhancedAPIClient
from app.core.logger import get_logger
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
    collections_count: int
    customer_events_count: int
    duration_ms: float
    success: bool
    error: Optional[str] = None
    permissions_status: Dict[str, bool] = {}


class DataCollectionService:
    """Enhanced service for collecting and saving Shopify data with all 5 APIs"""

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
                return shop.id

            # Create new shop if it doesn't exist
            new_shop = await self.db.shop.create(
                data={
                    "shopDomain": config.shop_domain,
                    "accessToken": config.access_token,
                    "createdAt": datetime.now(),
                    "updatedAt": datetime.now(),
                }
            )

            return new_shop.id

        except Exception as e:
            logger.error(f"Failed to get or create shop: {e}", config=config)
            raise Exception(f"Failed to get or create shop: {str(e)}")

    async def save_raw_orders(
        self,
        shop_db_id: str,
        orders: List[Dict[str, Any]],
    ) -> None:
        """Save raw order data to RawOrder table"""
        try:

            # Clear existing raw orders for this shop
            await self.db.raworder.delete_many(where={"shopId": shop_db_id})

            # Save raw orders
            raw_orders = []
            for order in orders:
                raw_orders.append(
                    {
                        "shopId": shop_db_id,
                        "payload": Json(order),
                    }
                )

            await self.db.raworder.create_many(data=raw_orders)

        except Exception as e:
            logger.error(f"Failed to save raw orders: {e}")
            # Don't fail the entire process if raw saving fails

    async def save_raw_customers(
        self,
        shop_db_id: str,
        customers: List[Dict[str, Any]],
    ) -> None:
        """Save raw customer data to RawCustomer table"""
        try:

            # Clear existing raw customers for this shop
            await self.db.rawcustomer.delete_many(where={"shopId": shop_db_id})

            # Save raw customers
            raw_customers = []
            for customer in customers:
                raw_customers.append(
                    {
                        "shopId": shop_db_id,
                        "payload": Json(customer),
                    }
                )

            await self.db.rawcustomer.create_many(data=raw_customers)

        except Exception as e:
            logger.error(f"Failed to save raw customers: {e}")
            # Don't fail the entire process if raw saving fails

    async def save_raw_products(
        self,
        shop_db_id: str,
        products: List[Dict[str, Any]],
    ) -> None:
        """Save raw product data to RawProduct table"""
        try:

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

        except Exception as e:
            logger.error(f"Failed to save raw products: {e}")
            # Don't fail the entire process if raw saving fails

    async def save_raw_collections(
        self,
        shop_db_id: str,
        collections: List[Dict[str, Any]],
    ) -> None:
        """Save raw collection data to RawCollection table"""
        try:
            # Clear existing raw collections for this shop
            await self.db.rawcollection.delete_many(where={"shopId": shop_db_id})

            # Save raw collections
            raw_collections = []
            for collection in collections:
                raw_collections.append(
                    {
                        "shopId": shop_db_id,
                        "payload": Json(collection),
                    }
                )

            await self.db.rawcollection.create_many(data=raw_collections)

        except Exception as e:
            logger.error(f"Failed to save raw collections: {e}")
            # Don't fail the entire process if raw saving fails

    async def save_raw_customer_events(
        self,
        shop_db_id: str,
        customer_events: List[Dict[str, Any]],
    ) -> None:
        """Save raw customer events data to RawCustomerEvent table"""
        try:
            # Clear existing raw customer events for this shop
            await self.db.rawcustomerevent.delete_many(where={"shopId": shop_db_id})

            # Save raw customer events
            raw_events = []
            for event in customer_events:
                raw_events.append(
                    {
                        "shopId": shop_db_id,
                        "payload": Json(event),
                    }
                )

            await self.db.rawcustomerevent.create_many(data=raw_events)

        except Exception as e:
            logger.error(f"Failed to save raw customer events: {e}")
            # Don't fail the entire process if raw saving fails

    async def save_orders(
        self,
        shop_db_id: str,
        orders: List[Dict[str, Any]],
        is_incremental: bool = False,
    ) -> None:
        """Save orders to database"""
        if not orders:
            return

        start_time = asyncio.get_event_loop().time()

        try:

            # Always use batch operations for better performance
            # First, save raw data to RawOrder table
            await self.save_raw_orders(shop_db_id, orders)

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

            # Save to database - always use batch operations for better performance
            try:
                # Use create_many with skip_duplicates for better performance
                # This handles both new and existing records efficiently
                await self.db.orderdata.create_many(
                    data=order_data, skip_duplicates=True
                )
            except Exception as batch_error:
                logger.warning(
                    f"Batch insert failed, falling back to individual upserts: {batch_error}"
                )
                # Fallback to individual upserts if batch fails
                for order_record in order_data:
                    await self.db.orderdata.upsert(
                        where={
                            "shopId_orderId": {
                                "shopId": order_record["shopId"],
                                "orderId": order_record["orderId"],
                            }
                        },
                        data={
                            "create": order_record,
                            "update": {
                                key: value
                                for key, value in order_record.items()
                                if key not in ["shopId", "orderId"]
                            },
                        },
                    )

        except Exception as e:
            logger.error(
                f"Save orders error | operation=save_orders | shop_db_id={shop_db_id} | orders_count={len(orders)} | error={str(e)}"
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
            return

        start_time = asyncio.get_event_loop().time()

        try:

            # Always use batch operations for better performance
            # First, save raw data to RawProduct table
            await self.save_raw_products(shop_db_id, products)

            # Prepare product data for batch insert
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
                    "price": float(product.get("variants", [{}])[0].get("price", 0)),
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

            # Use create_many with skip_duplicates for better performance
            try:
                await self.db.productdata.create_many(
                    data=product_data, skip_duplicates=True
                )
            except Exception as batch_error:
                logger.warning(
                    f"Batch insert failed, falling back to individual upserts: {batch_error}"
                )
                # Fallback to individual upserts if batch fails
                for product_record in product_data:
                    await self.db.productdata.upsert(
                        where={
                            "shopId_productId": {
                                "shopId": product_record["shopId"],
                                "productId": product_record["productId"],
                            }
                        },
                        data={
                            "create": product_record,
                            "update": {
                                key: value
                                for key, value in product_record.items()
                                if key not in ["shopId", "productId"]
                            },
                        },
                    )

        except Exception as e:
            logger.error(
                f"Save products error | operation=save_products | shop_db_id={shop_db_id} | products_count={len(products)} | error={str(e)}"
            )
            raise

    async def save_customers(
        self,
        shop_db_id: str,
        customers: List[Dict[str, Any]],
        is_incremental: bool = False,
    ) -> None:
        """Save customers to database using batch operations for optimal performance"""
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

            # Always use batch operations for better performance
            # First, save raw data to RawCustomer table
            await self.save_raw_customers(shop_db_id, customers)

            # Prepare customer data for batch operations
            customer_data = []
            for customer in customers:
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
                customer_data.append(customer_record)

            # Use batch upsert operations for optimal performance
            try:
                # First, try to use create_many with skip_duplicates for better performance
                await self.db.customerdata.create_many(
                    data=customer_data, skip_duplicates=True
                )
                logger.info(
                    f"Batch insert completed successfully for {len(customer_data)} customers"
                )
            except Exception as batch_error:
                logger.warning(
                    f"Batch insert failed, falling back to individual upserts: {batch_error}"
                )
                # Fallback to individual upserts if batch fails
                for customer_record in customer_data:
                    await self.db.customerdata.upsert(
                        where={
                            "shopId_customerId": {
                                "shopId": customer_record["shopId"],
                                "customerId": customer_record["customerId"],
                            }
                        },
                        data={
                            "create": customer_record,
                            "update": {
                                key: value
                                for key, value in customer_record.items()
                                if key not in ["shopId", "customerId"]
                            },
                        },
                    )

            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            logger.info(
                f"Performance: save_customers | duration_ms={duration_ms:.2f} | customers_count={len(customers)} | is_incremental={is_incremental}"
            )
            logger.info(
                f"Data collection: save_customers | shop_id={shop_db_id} | operation=save_customers | items_count={len(customers)} | duration_ms={duration_ms:.2f}"
            )

        except Exception as e:
            logger.error(
                f"Save customers error | operation=save_customers | shop_db_id={shop_db_id} | customers_count={len(customers)} | error={str(e)}"
            )
            raise

    async def save_collections(
        self,
        shop_db_id: str,
        collections: List[Dict[str, Any]],
        is_incremental: bool = False,
    ) -> None:
        """Save collections to database"""
        if not collections:
            return

        start_time = asyncio.get_event_loop().time()

        try:
            # Always use batch operations for better performance
            # First, save raw data to RawCollection table
            await self.save_raw_collections(shop_db_id, collections)

            # Transform collections data
            collection_data = []
            for collection in collections:
                collection_record = {
                    "shopId": shop_db_id,
                    "collectionId": str(collection["id"]),
                    "title": collection["title"],
                    "handle": collection["handle"],
                    "description": collection.get("description", ""),
                    "sortOrder": collection.get("sortOrder", ""),
                    "templateSuffix": collection.get("templateSuffix", ""),
                    "seoTitle": collection.get("seo", {}).get("title"),
                    "seoDescription": collection.get("seo", {}).get("description"),
                    "imageUrl": collection.get("image", {}).get("url"),
                    "imageAlt": collection.get("image", {}).get("altText"),
                    "productCount": len(
                        collection.get("products", {}).get("edges", [])
                    ),
                    "isAutomated": bool(collection.get("ruleSet", {}).get("rules")),
                    "metafields": Json(collection.get("metafields", {})),
                    "createdAt": datetime.now(),
                    "updatedAt": datetime.now(),
                }
                collection_data.append(collection_record)

            # Save to database using batch operations
            try:
                await self.db.collectiondata.create_many(
                    data=collection_data, skip_duplicates=True
                )
            except Exception as batch_error:
                logger.warning(
                    f"Batch insert failed for collections, falling back to individual upserts: {batch_error}"
                )
                # Fallback to individual upserts if batch fails
                for collection_record in collection_data:
                    await self.db.collectiondata.upsert(
                        where={
                            "shopId_collectionId": {
                                "shopId": collection_record["shopId"],
                                "collectionId": collection_record["collectionId"],
                            }
                        },
                        data={
                            "create": collection_record,
                            "update": {
                                key: value
                                for key, value in collection_record.items()
                                if key not in ["shopId", "collectionId"]
                            },
                        },
                    )

        except Exception as e:
            logger.error(
                f"Save collections error | operation=save_collections | shop_db_id={shop_db_id} | collections_count={len(collections)} | error={str(e)}"
            )
            raise

    async def save_customer_events(
        self,
        shop_db_id: str,
        customer_events: List[Dict[str, Any]],
        is_incremental: bool = False,
    ) -> None:
        """Save customer events to database"""
        if not customer_events:
            return

        start_time = asyncio.get_event_loop().time()

        try:
            # Always use batch operations for better performance
            # First, save raw data to RawCustomerEvent table
            await self.save_raw_customer_events(shop_db_id, customer_events)

            # Transform customer events data
            event_data = []
            for customer in customer_events:
                # Extract events from customer
                events = customer.get("events", {}).get("edges", [])
                for event_edge in events:
                    event = event_edge["node"]
                    event_record = {
                        "shopId": shop_db_id,
                        "customerId": str(customer["id"]),
                        "eventId": str(event["id"]),
                        "eventType": event.get("__typename", "Unknown"),
                        "customerEmail": customer.get("email"),
                        "customerFirstName": customer.get("firstName"),
                        "customerLastName": customer.get("lastName"),
                        "customerTags": Json(customer.get("tags", [])),
                        "customerState": customer.get("state"),
                        "customerOrdersCount": customer.get("numberOfOrders", 0),
                        "customerAmountSpent": float(
                            customer.get("amountSpent", {}).get("amount", 0)
                        ),
                        "customerCurrency": customer.get("amountSpent", {}).get(
                            "currencyCode", "USD"
                        ),
                        "eventTimestamp": datetime.now(),
                        "rawEventData": Json(event),
                        "createdAt": datetime.now(),
                        "updatedAt": datetime.now(),
                    }
                    event_data.append(event_record)

            # Save to database using batch operations
            try:
                await self.db.customereventdata.create_many(
                    data=event_data, skip_duplicates=True
                )
            except Exception as batch_error:
                logger.warning(
                    f"Batch insert failed for customer events, falling back to individual upserts: {batch_error}"
                )
                # Fallback to individual upserts if batch fails
                for event_record in event_data:
                    await self.db.customereventdata.upsert(
                        where={
                            "shopId_eventId": {
                                "shopId": event_record["shopId"],
                                "eventId": event_record["eventId"],
                            }
                        },
                        data={
                            "create": event_record,
                            "update": {
                                key: value
                                for key, value in event_record.items()
                                if key not in ["shopId", "eventId"]
                            },
                        },
                    )

        except Exception as e:
            logger.error(
                f"Save customer events error | operation=save_customer_events | shop_db_id={shop_db_id} | events_count={len(event_data)} | error={str(e)}"
            )
            raise

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

            # Always compute since_date from database and collect
            shop_db_id = await self.get_or_create_shop_db_id(config)

            # Prefer latest normalized product updatedAt; fallback to configured window
            since_date = None
            try:
                timestamps = await get_latest_timestamps(shop_db_id)
                latest_product = (
                    timestamps.get("latest_product_date") if timestamps else None
                )
                if latest_product:
                    if isinstance(latest_product, str):
                        since_date = latest_product
                    else:
                        since_date = latest_product.isoformat()
            except Exception:
                since_date = None

            if not since_date:
                since_date = self.calculate_since_date(
                    config.days_back or settings.MAX_INITIAL_DAYS
                )

            # Create Shopify API client
            api_client = ShopifyAPIClient(config.shop_domain, config.access_token)

            try:
                # Collect only products
                logger.info("Fetching products data", since_date=since_date)
                products = await api_client.fetch_products(since_date)

                logger.info(
                    "Products collection completed",
                    shop_domain=config.shop_domain,
                    products_count=len(products),
                )

                # Save products to database using upsert (idempotent)
                await self.save_products(shop_db_id, products, True)

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

            # Always compute since_date from database and collect
            shop_db_id = await self.get_or_create_shop_db_id(config)

            # Prefer latest normalized orderDate; fallback to configured window
            since_date = None
            try:
                timestamps = await get_latest_timestamps(shop_db_id)
                latest_order = (
                    timestamps.get("latest_order_date") if timestamps else None
                )
                if latest_order:
                    # latest_order may be datetime already
                    if isinstance(latest_order, str):
                        since_date = latest_order
                    else:
                        since_date = latest_order.isoformat()
            except Exception as _:
                since_date = None

            if not since_date:
                since_date = self.calculate_since_date(
                    config.days_back or settings.MAX_INITIAL_DAYS
                )

            # Create Shopify API client
            api_client = ShopifyAPIClient(config.shop_domain, config.access_token)

            try:
                # Collect only orders
                logger.info("Fetching orders data", since_date=since_date)
                orders = await api_client.fetch_orders(since_date)

                logger.info(
                    "Orders collection completed",
                    shop_domain=config.shop_domain,
                    orders_count=len(orders),
                )

                # Save orders to database using upsert (idempotent, incremental-safe)
                await self.save_orders(shop_db_id, orders, True)

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

            # Always compute since_date and collect
            shop_db_id = await self.get_or_create_shop_db_id(config)

            # For customers, use createdAt-based window
            since_date = self.calculate_since_date(
                config.days_back or settings.MAX_INITIAL_DAYS
            )

            # Create Shopify API client
            api_client = ShopifyEnhancedAPIClient(
                config.shop_domain, config.access_token
            )

            try:
                # Collect only customers
                logger.info("Fetching customers data", since_date=since_date)
                customers = await api_client.fetch_customers(since_date)

                logger.info(
                    "Customers collection completed",
                    shop_domain=config.shop_domain,
                    customers_count=len(customers),
                )

                # Save customers to database using upsert (idempotent)
                await self.save_customers(shop_db_id, customers, True)

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

    async def collect_collections_only(
        self, shop_id: str, shop_config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Collect only collections data - idempotent operation"""
        try:
            logger.info("Starting collections-only data collection", shop_id=shop_id)

            # Use provided shop config or get from database
            if shop_config:
                config = shop_config
            else:
                config = await self.get_shop_config(shop_id)
                if not config:
                    raise Exception(
                        f"Shop configuration not found for shop_id: {shop_id}"
                    )

            shop_db_id = await self.get_or_create_shop_db_id(config)

            # Create enhanced Shopify API client
            api_client = ShopifyEnhancedAPIClient(
                config.shop_domain, config.access_token
            )

            try:
                # Check permissions first
                permissions = await api_client.check_api_permissions()
                if not permissions.get("collections", False):
                    logger.warning("Collections API access denied, skipping")
                    return {
                        "success": False,
                        "message": "Collections API access denied",
                        "collections_count": 0,
                        "skipped": True,
                    }

                # Collect collections
                logger.info("Fetching collections data")
                collections, success = await api_client.fetch_collections()

                if not success:
                    logger.warning("Collections collection failed")
                    return {
                        "success": False,
                        "message": "Collections collection failed",
                        "collections_count": 0,
                        "skipped": False,
                    }

                logger.info(
                    "Collections collection completed",
                    shop_domain=config.shop_domain,
                    collections_count=len(collections),
                )

                # Save collections to database
                await self.save_collections(shop_db_id, collections, True)

                return {
                    "success": True,
                    "message": "Collections collected successfully",
                    "collections_count": len(collections),
                    "skipped": False,
                }

            finally:
                await api_client.close()

        except Exception as e:
            logger.error("Collections collection failed", shop_id=shop_id, error=str(e))
            return {
                "success": False,
                "message": f"Collections collection failed: {str(e)}",
                "collections_count": 0,
                "skipped": False,
            }

    async def collect_customer_events_only(
        self, shop_id: str, shop_config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Collect only customer events data - idempotent operation"""
        try:
            logger.info(
                "Starting customer events-only data collection", shop_id=shop_id
            )

            # Use provided shop config or get from database
            if shop_config:
                config = shop_config
            else:
                config = await self.get_shop_config(shop_id)
                if not config:
                    raise Exception(
                        f"Shop configuration not found for shop_id: {shop_id}"
                    )

            shop_db_id = await self.get_or_create_shop_db_id(config)

            # Create enhanced Shopify API client
            api_client = ShopifyEnhancedAPIClient(
                config.shop_domain, config.access_token
            )

            try:
                # Check permissions first
                permissions = await api_client.check_api_permissions()
                if not permissions.get("customer_events", False):
                    logger.warning("Customer Events API access denied, skipping")
                    return {
                        "success": False,
                        "message": "Customer Events API access denied",
                        "customer_events_count": 0,
                        "skipped": True,
                    }

                # Collect customer events
                logger.info("Fetching customer events data")
                customer_events, success = await api_client.fetch_customer_events()

                if not success:
                    logger.warning("Customer events collection failed")
                    return {
                        "success": False,
                        "message": "Customer events collection failed",
                        "customer_events_count": 0,
                        "skipped": False,
                    }

                logger.info(
                    "Customer events collection completed",
                    shop_domain=config.shop_domain,
                    customer_events_count=len(customer_events),
                )

                # Save customer events to database
                await self.save_customer_events(shop_db_id, customer_events, True)

                return {
                    "success": True,
                    "message": "Customer events collected successfully",
                    "customer_events_count": len(customer_events),
                    "skipped": False,
                }

            finally:
                await api_client.close()

        except Exception as e:
            logger.error(
                "Customer events collection failed", shop_id=shop_id, error=str(e)
            )
            return {
                "success": False,
                "message": f"Customer events collection failed: {str(e)}",
                "customer_events_count": 0,
                "skipped": False,
            }
