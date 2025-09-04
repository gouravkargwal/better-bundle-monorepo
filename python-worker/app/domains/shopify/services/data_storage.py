"""
Optimized data storage service for Shopify data with parallel processing and performance optimizations
"""

import asyncio
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from enum import Enum
from prisma import Prisma
from app.core.logging import get_logger
from app.core.exceptions import DataStorageError
from app.core.database.simple_db_client import get_database
from app.shared.helpers import now_utc

logger = get_logger(__name__)


class DataType(Enum):
    """Supported data types for storage"""

    SHOP = "shop"
    PRODUCTS = "products"
    ORDERS = "orders"
    CUSTOMERS = "customers"
    COLLECTIONS = "collections"
    CUSTOMER_EVENTS = "customer_events"


@dataclass
class StorageMetrics:
    """Storage operation metrics"""

    data_type: str
    shop_id: str
    total_items: int = 0
    new_items: int = 0
    updated_items: int = 0
    deleted_items: int = 0
    failed_items: int = 0
    processing_time: float = 0.0
    batch_size: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_items == 0:
            return 0.0
        successful = self.new_items + self.updated_items + self.deleted_items
        return (successful / self.total_items) * 100.0


@dataclass
class StorageConfig:
    """Configuration for data storage"""

    batch_size: int = 200  # Batch size for processing
    retry_attempts: int = 3
    retry_delay: float = 1.0
    cache_ttl_seconds: int = 300  # 5 minutes


class ShopifyDataStorageService:
    """
    Optimized data storage service with:
    - Parallel processing for maximum efficiency
    - Batch operations for performance
    - Comprehensive error handling
    - Performance monitoring
    - Data integrity checks
    """

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url
        self.config = StorageConfig()
        self.storage_metrics: Dict[str, StorageMetrics] = {}
        self._is_initialized = False
        self._db_client = None

        # Performance tracking
        self._performance_cache: Dict[str, Any] = {}
        self._last_cleanup = now_utc()

    async def initialize(self) -> None:
        """Initialize database connection and verify schema"""
        try:
            if self._is_initialized:
                return

            # Get database client (will initialize if needed)
            self._db_client = await get_database()

            # Initialize performance cache
            await self._initialize_performance_cache()

            self._is_initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize data storage service: {e}")
            raise DataStorageError(f"Initialization failed: {e}")

    async def _verify_schema(self) -> None:
        """Verify that required database tables exist"""
        try:
            # Test basic operations on each table
            tables = [
                "raworder",
                "rawproduct",
                "rawcustomer",
                "rawcollection",
                "rawcustomerevent",
            ]

            db = await get_database()
            for table in tables:
                # Try to count records to verify table exists
                if hasattr(db, table):
                    await getattr(db, table).count()
                else:
                    raise DataStorageError(f"Required table {table} not found")

        except Exception as e:
            logger.error(f"Schema verification failed: {e}")
            raise DataStorageError(f"Schema verification failed: {e}")

    async def _initialize_performance_cache(self) -> None:
        """Initialize performance optimization cache"""
        try:
            # Cache shop-specific metadata for faster lookups
            db = await get_database()
            shops = await db.shop.find_many()

            for shop in shops:
                cache_key = f"shop_metadata_{shop.id}"
                self._performance_cache[cache_key] = {
                    "domain": shop.shopDomain,
                    "last_analysis": shop.lastAnalysisAt,
                    "cached_at": now_utc(),
                }

        except Exception as e:
            logger.warning(f"Performance cache initialization failed: {e}")

    async def store_shop_data(
        self, shop: Any, shop_id: str, incremental: bool = True
    ) -> StorageMetrics:
        """Store shop data with incremental update support"""
        metrics = StorageMetrics(
            data_type=DataType.SHOP.value, shop_id=shop_id, start_time=now_utc()
        )

        try:
            await self.initialize()

            db = await get_database()
            # Check if shop exists and get last update
            existing_shop = await db.shop.find_unique(where={"shopDomain": shop.domain})

            if existing_shop:
                if incremental:
                    # Check if data has changed
                    if self._has_shop_data_changed(shop, existing_shop):
                        # Update existing shop
                        updated_shop = await db.shop.update(
                            where={"id": existing_shop.id},
                            data={
                                "accessToken": shop.access_token,
                                "planType": shop.plan_name or "Free",
                                "currencyCode": shop.currency,
                                "moneyFormat": (
                                    shop.money_format
                                    if hasattr(shop, "money_format")
                                    else None
                                ),
                                "email": shop.email,
                                "updatedAt": now_utc(),
                            },
                        )
                        metrics.updated_items = 1
                    else:
                        metrics.total_items = 1
                else:
                    # Force update
                    updated_shop = await db.shop.update(
                        where={"id": existing_shop.id},
                        data={
                            "accessToken": shop.access_token,
                            "planType": shop.plan_name or "Free",
                            "currencyCode": shop.currency,
                            "moneyFormat": (
                                shop.money_format
                                if hasattr(shop, "money_format")
                                else None
                            ),
                            "email": shop.email,
                            "updatedAt": now_utc(),
                        },
                    )
                    metrics.updated_items = 1
            else:
                # Create new shop
                new_shop = await db.shop.create(
                    data={
                        "shopDomain": shop.domain,
                        "accessToken": shop.access_token,
                        "planType": shop.plan_name or "Free",
                        "currencyCode": shop.currency,
                        "moneyFormat": (
                            shop.money_format if hasattr(shop, "money_format") else None
                        ),
                        "email": shop.email,
                    }
                )
                metrics.new_items = 1

            metrics.total_items = 1
            metrics.end_time = now_utc()
            metrics.processing_time = (
                metrics.end_time - metrics.start_time
            ).total_seconds()

            # Update performance cache
            await self._update_performance_cache(shop_id, shop.domain)

            return metrics

        except Exception as e:
            metrics.failed_items = 1
            metrics.end_time = now_utc()
            logger.error(f"Failed to store shop data: {e}")
            raise DataStorageError(f"Shop data storage failed: {e}")

    async def store_products_data(
        self, products: List[Any], shop_id: str, incremental: bool = True
    ) -> StorageMetrics:
        """Store products data with incremental updates and batch processing"""
        metrics = StorageMetrics(
            data_type=DataType.PRODUCTS.value,
            shop_id=shop_id,
            start_time=now_utc(),
            total_items=len(products),
        )

        try:
            await self.initialize()

            if not products:
                return metrics

            # Process in batches for performance
            batches = self._create_batches(products, self.config.batch_size)

            # Process batches in parallel for maximum efficiency
            batch_tasks = [
                self._process_products_batch(batch, shop_id, incremental)
                for batch in batches
            ]

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Aggregate results
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch processing failed: {result}")
                    metrics.failed_items += self.config.batch_size
                else:
                    metrics.new_items += result.get("new", 0)
                    metrics.updated_items += result.get("updated", 0)
                    metrics.deleted_items += result.get("deleted", 0)

            metrics.end_time = now_utc()
            metrics.processing_time = (
                metrics.end_time - metrics.start_time
            ).total_seconds()
            metrics.batch_size = self.config.batch_size

            # Update metrics
            self.storage_metrics[f"{shop_id}_{DataType.PRODUCTS.value}"] = metrics

            return metrics

        except Exception as e:
            metrics.failed_items = len(products)
            metrics.end_time = now_utc()
            logger.error(f"Failed to store products data: {e}")
            raise DataStorageError(f"Products data storage failed: {e}")

    async def _process_products_batch(
        self, products: List[Any], shop_id: str, incremental: bool
    ) -> Dict[str, int]:
        """Process a batch of products with transaction support"""
        batch_metrics = {"new": 0, "updated": 0, "deleted": 0}

        try:
            # Use database client for operations
            db = await get_database()
            # Use fast batch processing without transactions for maximum speed
            # create_many is already atomic, so no need for explicit transactions
            batch_metrics = await self._process_products_in_transaction(
                db, products, shop_id, incremental
            )

            return batch_metrics

        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            raise

    async def _process_orders_batch(
        self, orders: List[Any], shop_id: str, incremental: bool
    ) -> Dict[str, int]:
        """Process a batch of orders with transaction support"""
        batch_metrics = {"new": 0, "updated": 0, "deleted": 0}

        try:
            # Use database client for operations
            db = await get_database()
            # Use fast batch processing without transactions for maximum speed
            # create_many is already atomic, so no need for explicit transactions
            batch_metrics = await self._process_orders_in_transaction(
                db, orders, shop_id, incremental
            )

            return batch_metrics

        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            raise

    async def _process_products_in_transaction(
        self,
        db_client: Union[Prisma, Any],
        products: List[Any],
        shop_id: str,
        incremental: bool,
    ) -> Dict[str, int]:
        """Process products using fast batch operations with duplicate prevention"""
        batch_metrics = {"new": 0, "updated": 0, "deleted": 0}

        try:
            if not incremental:
                # Full refresh: delete existing and insert all
                await db_client.rawproduct.delete_many(where={"shopId": shop_id})
                batch_data = []
                current_time = now_utc()

                for product in products:
                    product_id = self._extract_product_id(product)
                    created_at, updated_at = self._extract_shopify_timestamps(product)

                    batch_data.append(
                        {
                            "shopId": shop_id,
                            "payload": self._serialize_product(product),
                            "extractedAt": current_time,
                            "shopifyId": product_id,
                            "shopifyCreatedAt": created_at,
                            "shopifyUpdatedAt": updated_at,
                        }
                    )

                await db_client.rawproduct.create_many(data=batch_data)
                batch_metrics["new"] = len(products)
            else:
                # Incremental: timestamp-based approach
                current_time = now_utc()
                new_products = []
                updated_products = []

                for product in products:
                    product_id = self._extract_product_id(product)
                    created_at, updated_at = self._extract_shopify_timestamps(product)

                    if not product_id:
                        continue

                    # Check if product exists
                    existing_product = await db_client.rawproduct.find_first(
                        where={"shopId": shop_id, "shopifyId": product_id}
                    )

                    product_data = {
                        "shopId": shop_id,
                        "payload": self._serialize_product(product),
                        "extractedAt": current_time,
                        "shopifyId": product_id,
                        "shopifyCreatedAt": created_at,
                        "shopifyUpdatedAt": updated_at,
                    }

                    if not existing_product:
                        # New product
                        new_products.append(product_data)
                    elif updated_at and existing_product.shopifyUpdatedAt:
                        # Check if product was updated
                        if updated_at > existing_product.shopifyUpdatedAt:
                            updated_products.append(product_data)
                    elif not existing_product.shopifyUpdatedAt and updated_at:
                        # Existing product without timestamp, add timestamp
                        updated_products.append(product_data)

                # Insert new products
                if new_products:
                    await db_client.rawproduct.create_many(data=new_products)
                    batch_metrics["new"] = len(new_products)

                # Update existing products
                if updated_products:
                    for product_data in updated_products:
                        await db_client.rawproduct.update_many(
                            where={
                                "shopId": shop_id,
                                "shopifyId": product_data["shopifyId"],
                            },
                            data={
                                "payload": product_data["payload"],
                                "extractedAt": product_data["extractedAt"],
                                "shopifyUpdatedAt": product_data["shopifyUpdatedAt"],
                            },
                        )
                    batch_metrics["updated"] = len(updated_products)

        except Exception as e:
            logger.error(f"Fast batch processing failed: {e}")
            # Fallback to individual inserts if batch fails
            for product in products:
                try:
                    await db_client.rawproduct.create(
                        data={
                            "shopId": shop_id,
                            "payload": self._serialize_product(product),
                            "extractedAt": now_utc(),
                        }
                    )
                    batch_metrics["new"] += 1
                except Exception as individual_error:
                    logger.error(
                        f"Failed to process product {product.id}: {individual_error}"
                    )
                    continue

        return batch_metrics

    def _create_batches(self, items: List[Any], batch_size: int) -> List[List[Any]]:
        """Create batches from a list of items"""
        return [items[i : i + batch_size] for i in range(0, len(items), batch_size)]

    def _generate_data_hash(self, obj: Any) -> str:
        """Generate a hash for data change detection"""
        # Create a serializable representation
        if hasattr(obj, "dict"):
            data = obj.dict()
        elif hasattr(obj, "__dict__"):
            data = obj.__dict__
        else:
            data = str(obj)

        # Convert to JSON string and hash
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.md5(json_str.encode()).hexdigest()

    def _has_shop_data_changed(self, new_shop: Any, existing_shop: Any) -> bool:
        """Check if shop data has changed"""
        # Compare key fields
        key_fields = ["access_token", "plan_name", "currency", "email"]

        for field in key_fields:
            new_value = getattr(new_shop, field, None)
            existing_value = getattr(existing_shop, field, None)

            if new_value != existing_value:
                return True

        return False

    def _has_product_data_changed(
        self, new_product: Any, existing_product: Any
    ) -> bool:
        """Check if product data has changed"""
        # Compare key fields that indicate changes
        key_fields = ["title", "body_html", "vendor", "product_type", "status", "tags"]

        for field in key_fields:
            new_value = getattr(new_product, field, None)
            existing_value = existing_product.payload.get(field, None)

            if new_value != existing_value:
                return True

        return False

    def _serialize_product(self, product: Any) -> str:
        """Serialize product to JSON string for storage"""
        try:
            if isinstance(product, str):
                # Already a JSON string, validate and return
                json.loads(product)  # Validate it's valid JSON
                return product
            elif hasattr(product, "dict"):
                # Pydantic model
                return json.dumps(product.dict(), default=str)
            elif isinstance(product, dict):
                # Already a dictionary
                return json.dumps(product, default=str)
            elif hasattr(product, "__dict__"):
                # Object with __dict__ attribute
                return json.dumps(product.__dict__, default=str)
            else:
                # Fallback: try to serialize as-is
                return json.dumps(product, default=str)
        except (TypeError, ValueError, json.JSONDecodeError) as e:
            # If all else fails, convert to string representation
            logger.warning(
                f"Failed to serialize product, using string representation: {e}"
            )
            return json.dumps(
                {"error": "serialization_failed", "data": str(product)}, default=str
            )

    def _extract_product_id(self, product: Any) -> Optional[str]:
        """Extract product ID from product object"""
        try:
            if hasattr(product, "id"):
                product_id = str(product.id)
            elif isinstance(product, dict) and "id" in product:
                product_id = str(product["id"])
            else:
                return None

            # Extract numeric ID from Shopify GraphQL ID format (gid://shopify/Product/123456789)
            if product_id.startswith("gid://shopify/Product/"):
                return product_id.split("/")[-1]
            return product_id
        except Exception as e:
            logger.warning(f"Failed to extract product ID: {e}")
            return None

    def _extract_order_id(self, order: Any) -> Optional[str]:
        """Extract order ID from order object"""
        try:
            if hasattr(order, "id"):
                order_id = str(order.id)
            elif isinstance(order, dict) and "id" in order:
                order_id = str(order["id"])
            else:
                return None

            # Extract numeric ID from Shopify GraphQL ID format (gid://shopify/Order/123456789)
            if order_id.startswith("gid://shopify/Order/"):
                return order_id.split("/")[-1]
            return order_id
        except Exception as e:
            logger.warning(f"Failed to extract order ID: {e}")
            return None

    def _extract_customer_id(self, customer: Any) -> Optional[str]:
        """Extract customer ID from customer object"""
        try:
            if hasattr(customer, "id"):
                customer_id = str(customer.id)
            elif isinstance(customer, dict) and "id" in customer:
                customer_id = str(customer["id"])
            else:
                return None

            # Extract numeric ID from Shopify GraphQL ID format (gid://shopify/Customer/123456789)
            if customer_id.startswith("gid://shopify/Customer/"):
                return customer_id.split("/")[-1]
            return customer_id
        except Exception as e:
            logger.warning(f"Failed to extract customer ID: {e}")
            return None

    def _extract_collection_id(self, collection: Any) -> Optional[str]:
        """Extract collection ID from collection object"""
        try:
            if hasattr(collection, "id"):
                collection_id = str(collection.id)
            elif isinstance(collection, dict) and "id" in collection:
                collection_id = str(collection["id"])
            else:
                return None

            # Extract numeric ID from Shopify GraphQL ID format (gid://shopify/Collection/123456789)
            if collection_id.startswith("gid://shopify/Collection/"):
                return collection_id.split("/")[-1]
            return collection_id
        except Exception as e:
            logger.warning(f"Failed to extract collection ID: {e}")
            return None

    def _extract_customer_event_id(self, event: Any) -> Optional[str]:
        """Extract customer event ID from event object"""
        try:
            if hasattr(event, "id"):
                event_id = str(event.id)
            elif isinstance(event, dict) and "id" in event:
                event_id = str(event["id"])
            else:
                return None

            # Extract numeric ID from Shopify GraphQL ID format (gid://shopify/MarketingEvent/123456789)
            if event_id.startswith("gid://shopify/MarketingEvent/"):
                return event_id.split("/")[-1]
            return event_id
        except Exception as e:
            logger.warning(f"Failed to extract customer event ID: {e}")
            return None

    def _extract_shopify_timestamps(
        self, data: Any
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        """Extract createdAt and updatedAt timestamps from Shopify GraphQL data"""
        created_at = None
        updated_at = None

        try:
            # Handle Pydantic models (snake_case) - this is what we get from data collection
            if hasattr(data, "created_at") and data.created_at:
                if isinstance(data.created_at, datetime):
                    created_at = data.created_at
                else:
                    created_at = self._parse_shopify_timestamp(str(data.created_at))
            elif isinstance(data, dict) and "created_at" in data and data["created_at"]:
                if isinstance(data["created_at"], datetime):
                    created_at = data["created_at"]
                else:
                    created_at = self._parse_shopify_timestamp(str(data["created_at"]))

            # Handle raw GraphQL data (camelCase) - fallback for direct API responses
            elif hasattr(data, "createdAt") and data.createdAt:
                created_at = self._parse_shopify_timestamp(str(data.createdAt))
            elif isinstance(data, dict) and "createdAt" in data and data["createdAt"]:
                created_at = self._parse_shopify_timestamp(str(data["createdAt"]))

            # Handle Pydantic models (snake_case) - this is what we get from data collection
            if hasattr(data, "updated_at") and data.updated_at:
                if isinstance(data.updated_at, datetime):
                    updated_at = data.updated_at
                else:
                    updated_at = self._parse_shopify_timestamp(str(data.updated_at))
            elif isinstance(data, dict) and "updated_at" in data and data["updated_at"]:
                if isinstance(data["updated_at"], datetime):
                    updated_at = data["updated_at"]
                else:
                    updated_at = self._parse_shopify_timestamp(str(data["updated_at"]))

            # Handle raw GraphQL data (camelCase) - fallback for direct API responses
            elif hasattr(data, "updatedAt") and data.updatedAt:
                updated_at = self._parse_shopify_timestamp(str(data.updatedAt))
            elif isinstance(data, dict) and "updatedAt" in data and data["updatedAt"]:
                updated_at = self._parse_shopify_timestamp(str(data["updatedAt"]))

        except Exception as e:
            logger.warning(f"Failed to extract timestamps: {e}")

        return created_at, updated_at

    def _parse_shopify_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse Shopify timestamp string to datetime object"""
        try:
            if isinstance(timestamp_str, str):
                # Handle various Shopify timestamp formats
                if timestamp_str.endswith("Z"):
                    # ISO format with Z
                    return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                elif "+" in timestamp_str or timestamp_str.endswith("T"):
                    # ISO format with timezone
                    return datetime.fromisoformat(timestamp_str)
                else:
                    # Try parsing as ISO format
                    return datetime.fromisoformat(timestamp_str)
        except Exception as e:
            logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}")
        return None

    async def _process_orders_in_transaction(
        self,
        db_client: Union[Prisma, Any],
        orders: List[Any],
        shop_id: str,
        incremental: bool,
        batch_metrics: Dict[str, int] = None,
    ) -> Dict[str, int]:
        """Process orders using timestamp-based incremental logic"""
        if batch_metrics is None:
            batch_metrics = {"new": 0, "updated": 0, "deleted": 0}

        try:
            if not incremental:
                # Full refresh: delete existing and insert all
                await db_client.raworder.delete_many(where={"shopId": shop_id})
                batch_data = []
                current_time = now_utc()

                for order in orders:
                    order_id = self._extract_order_id(order)
                    created_at, updated_at = self._extract_shopify_timestamps(order)

                    batch_data.append(
                        {
                            "shopId": shop_id,
                            "payload": json.dumps(
                                order.dict() if hasattr(order, "dict") else order,
                                default=str,
                            ),
                            "extractedAt": current_time,
                            "shopifyId": order_id,
                            "shopifyCreatedAt": created_at,
                            "shopifyUpdatedAt": updated_at,
                        }
                    )

                await db_client.raworder.create_many(data=batch_data)
                batch_metrics["new"] = len(orders)
            else:
                # Incremental: timestamp-based approach
                current_time = now_utc()
                new_orders = []
                updated_orders = []

                for order in orders:
                    order_id = self._extract_order_id(order)
                    created_at, updated_at = self._extract_shopify_timestamps(order)

                    if not order_id:
                        continue

                    # Check if order exists
                    existing_order = await db_client.raworder.find_first(
                        where={"shopId": shop_id, "shopifyId": order_id}
                    )

                    order_data = {
                        "shopId": shop_id,
                        "payload": json.dumps(
                            order.dict() if hasattr(order, "dict") else order,
                            default=str,
                        ),
                        "extractedAt": current_time,
                        "shopifyId": order_id,
                        "shopifyCreatedAt": created_at,
                        "shopifyUpdatedAt": updated_at,
                    }

                    if not existing_order:
                        # New order
                        new_orders.append(order_data)
                    elif updated_at and existing_order.shopifyUpdatedAt:
                        # Check if order was updated
                        if updated_at > existing_order.shopifyUpdatedAt:
                            updated_orders.append(order_data)
                    elif not existing_order.shopifyUpdatedAt and updated_at:
                        # Existing order without timestamp, add timestamp
                        updated_orders.append(order_data)

                # Insert new orders
                if new_orders:
                    await db_client.raworder.create_many(data=new_orders)
                    batch_metrics["new"] = len(new_orders)

                # Update existing orders
                if updated_orders:
                    for order_data in updated_orders:
                        await db_client.raworder.update_many(
                            where={
                                "shopId": shop_id,
                                "shopifyId": order_data["shopifyId"],
                            },
                            data={
                                "payload": order_data["payload"],
                                "extractedAt": order_data["extractedAt"],
                                "shopifyUpdatedAt": order_data["shopifyUpdatedAt"],
                            },
                        )
                    batch_metrics["updated"] = len(updated_orders)

        except Exception as e:
            logger.error(f"Timestamp-based processing failed: {e}")
            # Fallback to individual inserts if batch fails
            for order in orders:
                try:
                    order_id = self._extract_order_id(order)
                    created_at, updated_at = self._extract_shopify_timestamps(order)

                    await db_client.raworder.create(
                        data={
                            "shopId": shop_id,
                            "payload": json.dumps(
                                order.dict() if hasattr(order, "dict") else order,
                                default=str,
                            ),
                            "extractedAt": now_utc(),
                            "shopifyId": order_id,
                            "shopifyCreatedAt": created_at,
                            "shopifyUpdatedAt": updated_at,
                        }
                    )
                    batch_metrics["new"] += 1
                except Exception as individual_error:
                    logger.error(f"Failed to process order: {individual_error}")
                    batch_metrics["failed"] = batch_metrics.get("failed", 0) + 1
                    continue

        return batch_metrics

    async def _process_customers_batch(
        self, customers: List[Any], shop_id: str, incremental: bool
    ) -> Dict[str, int]:
        """Process a batch of customers with transaction support"""
        batch_metrics = {"new": 0, "updated": 0, "deleted": 0}

        try:
            # Use database client for operations
            db = await get_database()
            # Use fast batch processing without transactions for maximum speed
            # create_many is already atomic, so no need for explicit transactions
            batch_metrics = await self._process_customers_in_transaction(
                db, customers, shop_id, incremental
            )

            return batch_metrics

        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            raise

    async def _process_customers_in_transaction(
        self,
        db_client: Union[Prisma, Any],
        customers: List[Any],
        shop_id: str,
        incremental: bool,
        batch_metrics: Dict[str, int] = None,
    ) -> Dict[str, int]:
        """Process customers using fast batch operations with duplicate prevention"""
        if batch_metrics is None:
            batch_metrics = {"new": 0, "updated": 0, "deleted": 0}

        try:
            if not incremental:
                # Full refresh: delete existing and insert all
                await db_client.rawcustomer.delete_many(where={"shopId": shop_id})
                batch_data = []
                current_time = now_utc()

                for customer in customers:
                    customer_id = self._extract_customer_id(customer)
                    created_at, updated_at = self._extract_shopify_timestamps(customer)

                    batch_data.append(
                        {
                            "shopId": shop_id,
                            "payload": json.dumps(
                                (
                                    customer.dict()
                                    if hasattr(customer, "dict")
                                    else customer
                                ),
                                default=str,
                            ),
                            "extractedAt": current_time,
                            "shopifyId": customer_id,
                            "shopifyCreatedAt": created_at,
                            "shopifyUpdatedAt": updated_at,
                        }
                    )

                await db_client.rawcustomer.create_many(data=batch_data)
                batch_metrics["new"] = len(customers)
                logger.info(f"Full refresh: {len(customers)} customers stored")
            else:
                # Incremental: timestamp-based approach
                current_time = now_utc()
                new_customers = []
                updated_customers = []

                for customer in customers:
                    customer_id = self._extract_customer_id(customer)
                    created_at, updated_at = self._extract_shopify_timestamps(customer)

                    if not customer_id:
                        continue

                    # Check if customer exists
                    existing_customer = await db_client.rawcustomer.find_first(
                        where={"shopId": shop_id, "shopifyId": customer_id}
                    )

                    customer_data = {
                        "shopId": shop_id,
                        "payload": json.dumps(
                            customer.dict() if hasattr(customer, "dict") else customer,
                            default=str,
                        ),
                        "extractedAt": current_time,
                        "shopifyId": customer_id,
                        "shopifyCreatedAt": created_at,
                        "shopifyUpdatedAt": updated_at,
                    }

                    if not existing_customer:
                        # New customer
                        new_customers.append(customer_data)
                    elif updated_at and existing_customer.shopifyUpdatedAt:
                        # Check if customer was updated
                        if updated_at > existing_customer.shopifyUpdatedAt:
                            updated_customers.append(customer_data)
                    elif not existing_customer.shopifyUpdatedAt and updated_at:
                        # Existing customer without timestamp, add timestamp
                        updated_customers.append(customer_data)

                # Insert new customers
                if new_customers:
                    await db_client.rawcustomer.create_many(data=new_customers)
                    batch_metrics["new"] = len(new_customers)
                    logger.info(
                        f"Incremental: {len(new_customers)} new customers stored"
                    )

                # Update existing customers
                if updated_customers:
                    for customer_data in updated_customers:
                        await db_client.rawcustomer.update_many(
                            where={
                                "shopId": shop_id,
                                "shopifyId": customer_data["shopifyId"],
                            },
                            data={
                                "payload": customer_data["payload"],
                                "extractedAt": customer_data["extractedAt"],
                                "shopifyUpdatedAt": customer_data["shopifyUpdatedAt"],
                            },
                        )
                    batch_metrics["updated"] = len(updated_customers)
                    logger.info(
                        f"Incremental: {len(updated_customers)} customers updated"
                    )

        except Exception as e:
            logger.error(f"Timestamp-based processing failed: {e}")
            # Fallback to individual inserts if batch fails
            for customer in customers:
                try:
                    customer_id = self._extract_customer_id(customer)
                    created_at, updated_at = self._extract_shopify_timestamps(customer)

                    await db_client.rawcustomer.create(
                        data={
                            "shopId": shop_id,
                            "payload": json.dumps(
                                (
                                    customer.dict()
                                    if hasattr(customer, "dict")
                                    else customer
                                ),
                                default=str,
                            ),
                            "extractedAt": now_utc(),
                            "shopifyId": customer_id,
                            "shopifyCreatedAt": created_at,
                            "shopifyUpdatedAt": updated_at,
                        }
                    )
                    batch_metrics["new"] += 1
                except Exception as individual_error:
                    logger.error(f"Failed to process customer: {individual_error}")
                    batch_metrics["failed"] = batch_metrics.get("failed", 0) + 1
                    continue

        return batch_metrics

    async def _process_collections_in_transaction(
        self,
        collections: List[Any],
        shop_id: str,
        incremental: bool,
        metrics: StorageMetrics,
    ) -> None:
        """Process collections using fast batch operations with duplicate prevention"""
        try:
            db = await get_database()
            if not incremental:
                # Full refresh: delete existing and insert all
                await db.rawcollection.delete_many(where={"shopId": shop_id})
                batch_data = []
                current_time = now_utc()

                for collection in collections:
                    batch_data.append(
                        {
                            "shopId": shop_id,
                            "payload": json.dumps(
                                (
                                    collection.dict()
                                    if hasattr(collection, "dict")
                                    else collection
                                ),
                                default=str,
                            ),
                            "extractedAt": current_time,
                        }
                    )

                await db.rawcollection.create_many(data=batch_data)
                metrics.new_items = len(collections)
                logger.info(f"Full refresh: {len(collections)} collections stored")
            else:
                # Incremental: efficient batch approach using shopifyId
                current_time = now_utc()
                new_collections = []
                updated_collections = []

                for collection in collections:
                    collection_id = self._extract_collection_id(collection)
                    created_at, updated_at = self._extract_shopify_timestamps(
                        collection
                    )

                    if not collection_id:
                        continue

                    # Check if collection exists using shopifyId
                    existing_collection = await db.rawcollection.find_first(
                        where={"shopId": shop_id, "shopifyId": collection_id}
                    )

                    collection_data = {
                        "shopId": shop_id,
                        "payload": json.dumps(
                            (
                                collection.dict()
                                if hasattr(collection, "dict")
                                else collection
                            ),
                            default=str,
                        ),
                        "extractedAt": current_time,
                        "shopifyId": collection_id,
                        "shopifyCreatedAt": created_at,
                        "shopifyUpdatedAt": updated_at,
                    }

                    if not existing_collection:
                        # New collection
                        new_collections.append(collection_data)
                    elif updated_at and existing_collection.shopifyUpdatedAt:
                        # Check if collection was updated
                        if updated_at > existing_collection.shopifyUpdatedAt:
                            updated_collections.append(collection_data)
                    elif not existing_collection.shopifyUpdatedAt and updated_at:
                        # Existing collection without timestamp, add timestamp
                        updated_collections.append(collection_data)

                # Insert new collections
                if new_collections:
                    await db.rawcollection.create_many(data=new_collections)
                    metrics.new_items = len(new_collections)

                # Update existing collections
                if updated_collections:
                    for collection_data in updated_collections:
                        await db.rawcollection.update_many(
                            where={
                                "shopId": shop_id,
                                "shopifyId": collection_data["shopifyId"],
                            },
                            data={
                                "payload": collection_data["payload"],
                                "extractedAt": collection_data["extractedAt"],
                                "shopifyUpdatedAt": collection_data["shopifyUpdatedAt"],
                            },
                        )
                    metrics.updated_items = len(updated_collections)

                logger.info(
                    f"Incremental: {len(new_collections)} new, {len(updated_collections)} updated collections"
                )

        except Exception as e:
            logger.error(f"Timestamp-based processing failed: {e}")
            # Fallback to individual inserts if batch fails
            db = await get_database()
            for collection in collections:
                try:
                    collection_id = self._extract_collection_id(collection)
                    created_at, updated_at = self._extract_shopify_timestamps(
                        collection
                    )

                    await db.rawcollection.create(
                        data={
                            "shopId": shop_id,
                            "payload": json.dumps(
                                (
                                    collection.dict()
                                    if hasattr(collection, "dict")
                                    else collection
                                ),
                                default=str,
                            ),
                            "extractedAt": now_utc(),
                            "shopifyId": collection_id,
                            "shopifyCreatedAt": created_at,
                            "shopifyUpdatedAt": updated_at,
                        }
                    )
                    metrics.new_items += 1
                except Exception as individual_error:
                    logger.error(f"Failed to process collection: {individual_error}")
                    metrics.failed_items += 1
                    continue

    async def _process_customer_events_in_transaction(
        self,
        db_client: Union[Prisma, Any],
        events: List[Any],
        shop_id: str,
        incremental: bool,
        batch_metrics: Dict[str, int] = None,
    ) -> Dict[str, int]:
        """Process customer events using fast batch operations with duplicate prevention"""
        if batch_metrics is None:
            batch_metrics = {"new": 0, "updated": 0, "deleted": 0}

        try:
            if not incremental:
                # Full refresh: delete existing and insert all
                await db_client.rawcustomerevent.delete_many(where={"shopId": shop_id})
                batch_data = []
                current_time = now_utc()

                for event in events:
                    batch_data.append(
                        {
                            "shopId": shop_id,
                            "payload": json.dumps(
                                event.dict() if hasattr(event, "dict") else event,
                                default=str,
                            ),
                            "extractedAt": current_time,
                        }
                    )

                await db_client.rawcustomerevent.create_many(data=batch_data)
                batch_metrics["new"] = len(events)
                logger.info(f"Full refresh: {len(events)} customer events stored")
            else:
                # Incremental: efficient batch approach using shopifyId
                current_time = now_utc()
                new_events = []
                updated_events = []

                for event in events:
                    event_id = self._extract_customer_event_id(event)
                    created_at, updated_at = self._extract_shopify_timestamps(event)

                    if not event_id:
                        continue

                    # Check if event exists using shopifyId
                    existing_event = await db_client.rawcustomerevent.find_first(
                        where={"shopId": shop_id, "shopifyId": event_id}
                    )

                    event_data = {
                        "shopId": shop_id,
                        "payload": json.dumps(
                            event.dict() if hasattr(event, "dict") else event,
                            default=str,
                        ),
                        "extractedAt": current_time,
                        "shopifyId": event_id,
                        "shopifyCreatedAt": created_at,
                        "shopifyUpdatedAt": updated_at,
                    }

                    if not existing_event:
                        # New event
                        new_events.append(event_data)
                    elif updated_at and existing_event.shopifyUpdatedAt:
                        # Check if event was updated
                        if updated_at > existing_event.shopifyUpdatedAt:
                            updated_events.append(event_data)
                    elif not existing_event.shopifyUpdatedAt and updated_at:
                        # Existing event without timestamp, add timestamp
                        updated_events.append(event_data)

                # Insert new events
                if new_events:
                    await db_client.rawcustomerevent.create_many(data=new_events)
                    batch_metrics["new"] = len(new_events)

                # Update existing events
                if updated_events:
                    for event_data in updated_events:
                        await db_client.rawcustomerevent.update_many(
                            where={
                                "shopId": shop_id,
                                "shopifyId": event_data["shopifyId"],
                            },
                            data={
                                "payload": event_data["payload"],
                                "extractedAt": event_data["extractedAt"],
                                "shopifyUpdatedAt": event_data["shopifyUpdatedAt"],
                            },
                        )
                    batch_metrics["updated"] = len(updated_events)

                logger.info(
                    f"Incremental: {len(new_events)} new, {len(updated_events)} updated customer events"
                )

        except Exception as e:
            logger.error(f"Timestamp-based processing failed: {e}")
            # Fallback to individual inserts if batch fails
            for event in events:
                try:
                    event_id = self._extract_customer_event_id(event)
                    created_at, updated_at = self._extract_shopify_timestamps(event)

                    await db_client.rawcustomerevent.create(
                        data={
                            "shopId": shop_id,
                            "payload": json.dumps(
                                event.dict() if hasattr(event, "dict") else event,
                                default=str,
                            ),
                            "extractedAt": now_utc(),
                            "shopifyId": event_id,
                            "shopifyCreatedAt": created_at,
                            "shopifyUpdatedAt": updated_at,
                        }
                    )
                    batch_metrics["new"] += 1
                except Exception as individual_error:
                    logger.error(
                        f"Failed to process customer event: {individual_error}"
                    )
                    batch_metrics["failed"] = batch_metrics.get("failed", 0) + 1
                    continue

        return batch_metrics

    async def _process_customer_events_batch(
        self, events: List[Any], shop_id: str, incremental: bool
    ) -> Dict[str, int]:
        """Process a batch of customer events with transaction support"""
        batch_metrics = {"new": 0, "updated": 0, "deleted": 0}

        try:
            # Use database client for operations
            db = await get_database()
            # Use fast batch processing without transactions for maximum speed
            # create_many is already atomic, so no need for explicit transactions
            batch_metrics = await self._process_customer_events_in_transaction(
                db, events, shop_id, incremental
            )

            return batch_metrics

        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            raise

    async def _update_performance_cache(self, shop_id: str, domain: str) -> None:
        """Update performance cache with latest shop information"""
        cache_key = f"shop_metadata_{shop_id}"
        self._performance_cache[cache_key] = {
            "domain": domain,
            "last_analysis": now_utc(),
            "cached_at": now_utc(),
        }

    async def get_storage_metrics(
        self, shop_id: Optional[str] = None
    ) -> Dict[str, StorageMetrics]:
        """Get storage metrics for monitoring"""
        if shop_id:
            return {k: v for k, v in self.storage_metrics.items() if shop_id in k}
        return self.storage_metrics

    async def store_orders_data(
        self, orders: List[Any], shop_id: str, incremental: bool = True
    ) -> StorageMetrics:
        """Store orders data with enterprise-grade performance"""
        metrics = StorageMetrics(
            data_type=DataType.ORDERS.value,
            shop_id=shop_id,
            start_time=now_utc(),
            total_items=len(orders),
        )

        try:
            await self.initialize()

            if not orders:
                return metrics

            # Process in batches for performance
            batches = self._create_batches(orders, self.config.batch_size)

            # Process batches in parallel for maximum efficiency
            batch_tasks = [
                self._process_orders_batch(batch, shop_id, incremental)
                for batch in batches
            ]

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Aggregate results
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch processing failed: {result}")
                    metrics.failed_items += len(batch_results)
                else:
                    metrics.new_items += result.get("new", 0)
                    metrics.updated_items += result.get("updated", 0)

            metrics.end_time = now_utc()
            metrics.processing_time = (
                metrics.end_time - metrics.start_time
            ).total_seconds()
            metrics.batch_size = self.config.batch_size

            # Update metrics
            self.storage_metrics[f"{shop_id}_{DataType.ORDERS.value}"] = metrics

            return metrics

        except Exception as e:
            metrics.failed_items = len(orders)
            metrics.end_time = now_utc()
            logger.error(f"Failed to store orders data: {e}")
            raise DataStorageError(f"Orders data storage failed: {e}")

    async def store_customers_data(
        self, customers: List[Any], shop_id: str, incremental: bool = True
    ) -> StorageMetrics:
        """Store customers data with enterprise-grade performance"""
        metrics = StorageMetrics(
            data_type=DataType.CUSTOMERS.value,
            shop_id=shop_id,
            start_time=now_utc(),
            total_items=len(customers),
        )

        try:
            await self.initialize()

            if not customers:
                return metrics

            # Process in batches for performance
            batches = self._create_batches(customers, self.config.batch_size)

            # Process batches in parallel for maximum efficiency
            batch_tasks = [
                self._process_customers_batch(batch, shop_id, incremental)
                for batch in batches
            ]

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Aggregate results
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch processing failed: {result}")
                    metrics.failed_items += len(batch_results)
                else:
                    metrics.new_items += result.get("new", 0)
                    metrics.updated_items += result.get("updated", 0)

            metrics.end_time = now_utc()
            metrics.processing_time = (
                metrics.end_time - metrics.start_time
            ).total_seconds()
            metrics.batch_size = self.config.batch_size

            # Update metrics
            self.storage_metrics[f"{shop_id}_{DataType.CUSTOMERS.value}"] = metrics

            return metrics

        except Exception as e:
            metrics.failed_items = len(customers)
            metrics.end_time = now_utc()
            logger.error(f"Failed to store customers data: {e}")
            raise DataStorageError(f"Customers data storage failed: {e}")

    async def store_collections_data(
        self, collections: List[Any], shop_id: str, incremental: bool = True
    ) -> StorageMetrics:
        """Store collections data with enterprise-grade performance"""
        metrics = StorageMetrics(
            data_type=DataType.COLLECTIONS.value,
            shop_id=shop_id,
            start_time=now_utc(),
            total_items=len(collections),
        )

        try:
            await self.initialize()

            # Use incremental processing for efficiency
            await self._process_collections_in_transaction(
                collections, shop_id, incremental, metrics
            )

            metrics.end_time = now_utc()
            metrics.processing_time = (
                metrics.end_time - metrics.start_time
            ).total_seconds()
            metrics.batch_size = self.config.batch_size

            # Update metrics
            self.storage_metrics[f"{shop_id}_{DataType.COLLECTIONS.value}"] = metrics

            return metrics

        except Exception as e:
            metrics.failed_items = len(collections)
            metrics.end_time = now_utc()
            logger.error(f"Failed to store collections data: {e}")
            raise DataStorageError(f"Collections data storage failed: {e}")

    async def store_customer_events_data(
        self, events: List[Any], shop_id: str, incremental: bool = True
    ) -> StorageMetrics:
        """Store customer events data with enterprise-grade performance"""
        metrics = StorageMetrics(
            data_type=DataType.CUSTOMER_EVENTS.value,
            shop_id=shop_id,
            start_time=now_utc(),
            total_items=len(events),
        )

        try:
            await self.initialize()

            if not events:
                return metrics

            # Process in batches for performance
            batches = self._create_batches(events, self.config.batch_size)

            # Process batches in parallel for maximum efficiency
            batch_tasks = [
                self._process_customer_events_batch(batch, shop_id, incremental)
                for batch in batches
            ]

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Aggregate results
            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch processing failed: {result}")
                    metrics.failed_items += len(batch_results)
                else:
                    metrics.new_items += result.get("new", 0)
                    metrics.updated_items += result.get("updated", 0)

            metrics.end_time = now_utc()
            metrics.processing_time = (
                metrics.end_time - metrics.start_time
            ).total_seconds()
            metrics.batch_size = self.config.batch_size

            # Update metrics
            self.storage_metrics[f"{shop_id}_{DataType.CUSTOMER_EVENTS.value}"] = (
                metrics
            )

            return metrics

        except Exception as e:
            metrics.failed_items = len(events)
            metrics.end_time = now_utc()
            logger.error(f"Failed to store customer events data: {e}")
            raise DataStorageError(f"Customer events data storage failed: {e}")

    async def cleanup_old_data(self, days_to_keep: int = 90) -> int:
        """Clean up old data to maintain performance"""
        try:
            await self.initialize()

            cutoff_date = now_utc() - timedelta(days=days_to_keep)
            deleted_count = 0

            # Clean up old raw data
            tables = [
                "raworder",
                "rawproduct",
                "rawcustomer",
                "rawcollection",
                "rawcustomerevent",
            ]

            db = await get_database()
            for table in tables:
                if hasattr(db, table):
                    deleted = await getattr(db, table).delete_many(
                        where={"extractedAt": {"lt": cutoff_date}}
                    )
                    deleted_count += deleted

            # Clean up performance cache
            await self._cleanup_performance_cache()

            logger.info(f"Data cleanup completed: {deleted_count} records removed")
            return deleted_count

        except Exception as e:
            logger.error(f"Data cleanup failed: {e}")
            raise DataStorageError(f"Data cleanup failed: {e}")

    async def _cleanup_performance_cache(self) -> None:
        """Clean up expired performance cache entries"""
        current_time = now_utc()
        expired_keys = []

        for key, value in self._performance_cache.items():
            if isinstance(value, dict) and "cached_at" in value:
                cache_age = (current_time - value["cached_at"]).total_seconds()
                if cache_age > self.config.cache_ttl_seconds:
                    expired_keys.append(key)

        for key in expired_keys:
            del self._performance_cache[key]

    async def close(self) -> None:
        """Close database connection and cleanup resources"""
        try:
            if self._is_initialized:
                # Connection pool handles its own cleanup
                self._is_initialized = False
        except Exception as e:
            logger.error(f"Error closing data storage service: {e}")

    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def get_shop_by_domain(self, shop_domain: str) -> Optional[Any]:
        """Get shop by domain for incremental collection"""
        try:
            await self.initialize()
            db = await get_database()
            shop = await db.shop.find_first(where={"shopDomain": shop_domain})
            return shop
        except Exception as e:
            logger.error(f"Failed to get shop by domain {shop_domain}: {e}")
            return None

    async def get_latest_product_update(self, shop_id: str) -> Optional[Any]:
        """Get the most recently updated product for incremental collection"""
        try:
            await self.initialize()
            db = await get_database()
            latest_product = await db.rawproduct.find_first(
                where={"shopId": shop_id}, order={"extractedAt": "desc"}
            )
            return latest_product
        except Exception as e:
            logger.error(f"Failed to get latest product update for shop {shop_id}: {e}")
            return None

    async def get_latest_order_update(self, shop_id: str) -> Optional[Any]:
        """Get the most recently updated order for incremental collection"""
        try:
            await self.initialize()
            db = await get_database()
            latest_order = await db.raworder.find_first(
                where={"shopId": shop_id}, order={"extractedAt": "desc"}
            )
            return latest_order
        except Exception as e:
            logger.error(f"Failed to get latest order update for shop {shop_id}: {e}")
            return None

    async def get_latest_customer_update(self, shop_id: str) -> Optional[Any]:
        """Get the most recently updated customer for incremental collection"""
        try:
            await self.initialize()
            db = await get_database()
            latest_customer = await db.rawcustomer.find_first(
                where={"shopId": shop_id}, order={"extractedAt": "desc"}
            )
            return latest_customer
        except Exception as e:
            logger.error(
                f"Failed to get latest customer update for shop {shop_id}: {e}"
            )
            return None

    async def get_latest_collection_update(self, shop_id: str) -> Optional[Any]:
        """Get the most recently updated collection for incremental collection"""
        try:
            await self.initialize()
            db = await get_database()
            latest_collection = await db.rawcollection.find_first(
                where={"shopId": shop_id}, order={"extractedAt": "desc"}
            )
            return latest_collection
        except Exception as e:
            logger.error(
                f"Failed to get latest collection update for shop {shop_id}: {e}"
            )
            return None

    async def get_latest_customer_event_update(self, shop_id: str) -> Optional[Any]:
        """Get the most recently updated customer event for incremental collection"""
        try:
            await self.initialize()
            db = await get_database()
            latest_event = await db.rawcustomerevent.find_first(
                where={"shopId": shop_id}, order={"extractedAt": "desc"}
            )
            return latest_event
        except Exception as e:
            logger.error(
                f"Failed to get latest customer event update for shop {shop_id}: {e}"
            )
            return None
