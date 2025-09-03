"""
Enterprise-grade data storage service for Shopify data with incremental updates and performance optimizations
"""

import asyncio
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import logging

from prisma import Prisma
# Json type is handled directly in Prisma operations

from app.core.logging import get_logger
from app.core.exceptions import DataStorageError, ConfigurationError
from app.shared.decorators import retry, async_timing
from app.shared.helpers import now_utc
from ..models.shop import ShopifyShop
from ..models.product import ShopifyProduct, ShopifyProductVariant
from ..models.order import ShopifyOrder
from ..models.customer import ShopifyCustomer
from ..models.collection import ShopifyCollection
from ..models.customer_event import ShopifyCustomerEvent

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
class IncrementalConfig:
    """Configuration for incremental data processing"""
    batch_size: int = 100
    max_concurrent_batches: int = 5
    retry_attempts: int = 3
    retry_delay: float = 1.0
    use_transactions: bool = True
    enable_parallel_processing: bool = True
    cache_ttl_seconds: int = 300  # 5 minutes


class ShopifyDataStorageService:
    """
    Enterprise-grade data storage service with:
    - Incremental updates (only process new/changed data)
    - Batch processing for performance
    - Parallel processing capabilities
    - Transaction support
    - Comprehensive error handling
    - Performance monitoring
    - Data integrity checks
    """
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url
        self.db: Optional[Prisma] = None
        self.config = IncrementalConfig()
        self.storage_metrics: Dict[str, StorageMetrics] = {}
        self._connection_pool_size = 10
        self._is_initialized = False
        
        # Performance tracking
        self._performance_cache: Dict[str, Any] = {}
        self._last_cleanup = now_utc()
        
    async def initialize(self) -> None:
        """Initialize database connection and verify schema"""
        try:
            if self._is_initialized:
                return
                
            self.db = Prisma()
            await self.db.connect()
            
            # Verify database schema
            await self._verify_schema()
            
            # Initialize performance cache
            await self._initialize_performance_cache()
            
            self._is_initialized = True
            logger.info("Data storage service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize data storage service: {e}")
            raise DataStorageError(f"Initialization failed: {e}")
    
    async def _verify_schema(self) -> None:
        """Verify that required database tables exist"""
        try:
            # Test basic operations on each table
            tables = ['raworder', 'rawproduct', 'rawcustomer', 'rawcollection', 'rawcustomerevent']
            
            for table in tables:
                # Try to count records to verify table exists
                if hasattr(self.db, table):
                    await getattr(self.db, table).count()
                    logger.debug(f"Table {table} verified")
                else:
                    raise DataStorageError(f"Required table {table} not found")
                    
        except Exception as e:
            logger.error(f"Schema verification failed: {e}")
            raise DataStorageError(f"Schema verification failed: {e}")
    
    async def _initialize_performance_cache(self) -> None:
        """Initialize performance optimization cache"""
        try:
            # Cache shop-specific metadata for faster lookups
            shops = await self.db.shop.find_many(
                select={"id": True, "shopDomain": True, "lastAnalysisAt": True}
            )
            
            for shop in shops:
                cache_key = f"shop_metadata_{shop.id}"
                self._performance_cache[cache_key] = {
                    "domain": shop.shopDomain,
                    "last_analysis": shop.lastAnalysisAt,
                    "cached_at": now_utc()
                }
                
            logger.info(f"Performance cache initialized with {len(shops)} shops")
            
        except Exception as e:
            logger.warning(f"Performance cache initialization failed: {e}")
    
    async def store_shop_data(
        self, 
        shop: ShopifyShop, 
        shop_id: str,
        incremental: bool = True
    ) -> StorageMetrics:
        """Store shop data with incremental update support"""
        metrics = StorageMetrics(
            data_type=DataType.SHOP.value,
            shop_id=shop_id,
            start_time=now_utc()
        )
        
        try:
            await self.initialize()
            
            # Check if shop exists and get last update
            existing_shop = await self.db.shop.find_unique(
                where={"shopDomain": shop.domain}
            )
            
            if existing_shop:
                if incremental:
                    # Check if data has changed
                    if self._has_shop_data_changed(shop, existing_shop):
                        # Update existing shop
                        updated_shop = await self.db.shop.update(
                            where={"id": existing_shop.id},
                            data={
                                "accessToken": shop.access_token,
                                "planType": shop.plan_type or "Free",
                                "currencyCode": shop.currency_code,
                                "moneyFormat": shop.money_format,
                                "email": shop.email,
                                "updatedAt": now_utc()
                            }
                        )
                        metrics.updated_items = 1
                        logger.info(f"Shop updated: {shop.domain}")
                    else:
                        logger.info(f"Shop data unchanged: {shop.domain}")
                        metrics.total_items = 1
                else:
                    # Force update
                    updated_shop = await self.db.shop.update(
                        where={"id": existing_shop.id},
                        data={
                            "accessToken": shop.access_token,
                            "planType": shop.plan_type or "Free",
                            "currencyCode": shop.currency_code,
                            "moneyFormat": shop.money_format,
                            "email": shop.email,
                            "updatedAt": now_utc()
                        }
                    )
                    metrics.updated_items = 1
            else:
                # Create new shop
                new_shop = await self.db.shop.create(
                    data={
                        "shopDomain": shop.domain,
                        "accessToken": shop.access_token,
                        "planType": shop.plan_type or "Free",
                        "currencyCode": shop.currency_code,
                        "moneyFormat": shop.money_format,
                        "email": shop.email
                    }
                )
                metrics.new_items = 1
                logger.info(f"New shop created: {shop.domain}")
            
            metrics.total_items = 1
            metrics.end_time = now_utc()
            metrics.processing_time = (metrics.end_time - metrics.start_time).total_seconds()
            
            # Update performance cache
            await self._update_performance_cache(shop_id, shop.domain)
            
            return metrics
            
        except Exception as e:
            metrics.failed_items = 1
            metrics.end_time = now_utc()
            logger.error(f"Failed to store shop data: {e}")
            raise DataStorageError(f"Shop data storage failed: {e}")
    
    async def store_products_data(
        self, 
        products: List[ShopifyProduct], 
        shop_id: str,
        incremental: bool = True
    ) -> StorageMetrics:
        """Store products data with incremental updates and batch processing"""
        metrics = StorageMetrics(
            data_type=DataType.PRODUCTS.value,
            shop_id=shop_id,
            start_time=now_utc(),
            total_items=len(products)
        )
        
        try:
            await self.initialize()
            
            if not products:
                return metrics
            
            # Process in batches for performance
            batches = self._create_batches(products, self.config.batch_size)
            
            if self.config.enable_parallel_processing:
                # Process batches in parallel
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
            else:
                # Process batches sequentially
                for batch in batches:
                    try:
                        result = await self._process_products_batch(batch, shop_id, incremental)
                        metrics.new_items += result.get("new", 0)
                        metrics.updated_items += result.get("updated", 0)
                        metrics.deleted_items += result.get("deleted", 0)
                    except Exception as e:
                        logger.error(f"Batch processing failed: {e}")
                        metrics.failed_items += len(batch)
            
            metrics.end_time = now_utc()
            metrics.processing_time = (metrics.end_time - metrics.start_time).total_seconds()
            metrics.batch_size = self.config.batch_size
            
            # Update metrics
            self.storage_metrics[f"{shop_id}_{DataType.PRODUCTS.value}"] = metrics
            
            logger.info(f"Products storage completed: {metrics.new_items} new, {metrics.updated_items} updated")
            return metrics
            
        except Exception as e:
            metrics.failed_items = len(products)
            metrics.end_time = now_utc()
            logger.error(f"Failed to store products data: {e}")
            raise DataStorageError(f"Products data storage failed: {e}")
    
    async def _process_products_batch(
        self, 
        products: List[ShopifyProduct], 
        shop_id: str, 
        incremental: bool
    ) -> Dict[str, int]:
        """Process a batch of products with transaction support"""
        batch_metrics = {"new": 0, "updated": 0, "deleted": 0}
        
        try:
            if self.config.use_transactions:
                # Use transaction for batch consistency
                async with self.db.tx() as transaction:
                    batch_metrics = await self._process_products_in_transaction(
                        transaction, products, shop_id, incremental
                    )
            else:
                # Process without transaction
                batch_metrics = await self._process_products_in_transaction(
                    self.db, products, shop_id, incremental
                )
                
            return batch_metrics
            
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            raise
    
    async def _process_products_in_transaction(
        self, 
        db_client: Union[Prisma, Any], 
        products: List[ShopifyProduct], 
        shop_id: str, 
        incremental: bool
    ) -> Dict[str, int]:
        """Process products within a transaction context"""
        batch_metrics = {"new": 0, "updated": 0, "deleted": 0}
        
        for product in products:
            try:
                # Generate data hash for change detection
                data_hash = self._generate_data_hash(product)
                
                if incremental:
                    # Check if product exists and has changed
                    existing_product = await db_client.rawproduct.find_first(
                        where={
                            "shopId": shop_id,
                            "payload": {
                                "path": ["id"],
                                "equals": product.id
                            }
                        }
                    )
                    
                    if existing_product:
                        # Check if data has changed
                        if self._has_product_data_changed(product, existing_product):
                            # Update existing product
                            await db_client.rawproduct.update(
                                where={"id": existing_product.id},
                                data={
                                    "payload": self._serialize_product(product),
                                    "extractedAt": now_utc()
                                }
                            )
                            batch_metrics["updated"] += 1
                        # If no change, skip
                    else:
                        # Create new product
                        await db_client.rawproduct.create(
                            data={
                                "shopId": shop_id,
                                "payload": self._serialize_product(product),
                                "extractedAt": now_utc()
                            }
                        )
                        batch_metrics["new"] += 1
                else:
                    # Force update/create
                    existing_product = await db_client.rawproduct.find_first(
                        where={
                            "shopId": shop_id,
                            "payload": {
                                "path": ["id"],
                                "equals": product.id
                            }
                        }
                    )
                    
                    if existing_product:
                        await db_client.rawproduct.update(
                            where={"id": existing_product.id},
                            data={
                                "payload": self._serialize_product(product),
                                "extractedAt": now_utc()
                            }
                        )
                        batch_metrics["updated"] += 1
                    else:
                        await db_client.rawproduct.create(
                            data={
                                "shopId": shop_id,
                                "payload": self._serialize_product(product),
                                "extractedAt": now_utc()
                            }
                        )
                        batch_metrics["new"] += 1
                        
            except Exception as e:
                logger.error(f"Failed to process product {product.id}: {e}")
                continue
        
        return batch_metrics
    
    def _create_batches(self, items: List[Any], batch_size: int) -> List[List[Any]]:
        """Create batches from a list of items"""
        return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
    
    def _generate_data_hash(self, obj: Any) -> str:
        """Generate a hash for data change detection"""
        # Create a serializable representation
        if hasattr(obj, 'dict'):
            data = obj.dict()
        elif hasattr(obj, '__dict__'):
            data = obj.__dict__
        else:
            data = str(obj)
        
        # Convert to JSON string and hash
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.md5(json_str.encode()).hexdigest()
    
    def _has_shop_data_changed(self, new_shop: ShopifyShop, existing_shop: Any) -> bool:
        """Check if shop data has changed"""
        # Compare key fields
        key_fields = ['access_token', 'plan_type', 'currency_code', 'money_format', 'email']
        
        for field in key_fields:
            new_value = getattr(new_shop, field, None)
            existing_value = getattr(existing_shop, field, None)
            
            if new_value != existing_value:
                return True
        
        return False
    
    def _has_product_data_changed(self, new_product: ShopifyProduct, existing_product: Any) -> bool:
        """Check if product data has changed"""
        # Compare key fields that indicate changes
        key_fields = ['title', 'body_html', 'vendor', 'product_type', 'status', 'tags']
        
        for field in key_fields:
            new_value = getattr(new_product, field, None)
            existing_value = existing_product.payload.get(field, None)
            
            if new_value != existing_value:
                return True
        
        return False
    
    def _serialize_product(self, product: ShopifyProduct) -> str:
        """Serialize product to JSON string for storage"""
        return json.dumps(product.dict(), default=str)
    
    async def _update_performance_cache(self, shop_id: str, domain: str) -> None:
        """Update performance cache with latest shop information"""
        cache_key = f"shop_metadata_{shop_id}"
        self._performance_cache[cache_key] = {
            "domain": domain,
            "last_analysis": now_utc(),
            "cached_at": now_utc()
        }
    
    async def get_storage_metrics(self, shop_id: Optional[str] = None) -> Dict[str, StorageMetrics]:
        """Get storage metrics for monitoring"""
        if shop_id:
            return {k: v for k, v in self.storage_metrics.items() if shop_id in k}
        return self.storage_metrics
    
    async def store_orders_data(self, orders: List[Any], shop_id: str) -> StorageMetrics:
        """Store orders data with enterprise-grade performance"""
        metrics = StorageMetrics(
            operation="store_orders",
            data_type=DataType.ORDERS,
            shop_id=shop_id,
            start_time=now_utc()
        )
        
        try:
            await self.initialize()
            
            # Use enterprise-grade storage strategy
            strategy = self._select_storage_strategy(len(orders))
            
            if strategy == StorageStrategy.STREAMING:
                await self._store_orders_streaming(orders, shop_id, metrics)
            elif strategy == StorageStrategy.BATCH_OPTIMIZED:
                await self._store_orders_batch(orders, shop_id, metrics)
            else:  # MAXIMUM_THROUGHPUT
                await self._store_orders_parallel(orders, shop_id, metrics)
            
            metrics.end_time = now_utc()
            metrics.processing_time = (metrics.end_time - metrics.start_time).total_seconds()
            metrics.batch_size = self.config.batch_size
            
            # Update metrics
            self.storage_metrics[f"{shop_id}_{DataType.ORDERS.value}"] = metrics
            
            logger.info(f"Orders storage completed: {metrics.new_items} new, {metrics.updated_items} updated")
            return metrics
            
        except Exception as e:
            metrics.failed_items = len(orders)
            metrics.end_time = now_utc()
            logger.error(f"Failed to store orders data: {e}")
            raise DataStorageError(f"Orders data storage failed: {e}")
    
    async def store_customers_data(self, customers: List[Any], shop_id: str) -> StorageMetrics:
        """Store customers data with enterprise-grade performance"""
        metrics = StorageMetrics(
            operation="store_customers",
            data_type=DataType.CUSTOMERS,
            shop_id=shop_id,
            start_time=now_utc()
        )
        
        try:
            await self.initialize()
            
            # Use enterprise-grade storage strategy
            strategy = self._select_storage_strategy(len(customers))
            
            if strategy == StorageStrategy.STREAMING:
                await self._store_customers_streaming(customers, shop_id, metrics)
            elif strategy == StorageStrategy.BATCH_OPTIMIZED:
                await self._store_customers_batch(customers, shop_id, metrics)
            else:  # MAXIMUM_THROUGHPUT
                await self._store_customers_parallel(customers, shop_id, metrics)
            
            metrics.end_time = now_utc()
            metrics.processing_time = (metrics.end_time - metrics.start_time).total_seconds()
            metrics.batch_size = self.config.batch_size
            
            # Update metrics
            self.storage_metrics[f"{shop_id}_{DataType.CUSTOMERS.value}"] = metrics
            
            logger.info(f"Customers storage completed: {metrics.new_items} new, {metrics.updated_items} updated")
            return metrics
            
        except Exception as e:
            metrics.failed_items = len(customers)
            metrics.end_time = now_utc()
            logger.error(f"Failed to store customers data: {e}")
            raise DataStorageError(f"Customers data storage failed: {e}")
    
    async def store_collections_data(self, collections: List[Any], shop_id: str) -> StorageMetrics:
        """Store collections data with enterprise-grade performance"""
        metrics = StorageMetrics(
            operation="store_collections",
            data_type=DataType.COLLECTIONS,
            shop_id=shop_id,
            start_time=now_utc()
        )
        
        try:
            await self.initialize()
            
            # Use enterprise-grade storage strategy
            strategy = self._select_storage_strategy(len(collections))
            
            if strategy == StorageStrategy.STREAMING:
                await self._store_collections_streaming(collections, shop_id, metrics)
            elif strategy == StorageStrategy.BATCH_OPTIMIZED:
                await self._store_collections_batch(collections, shop_id, metrics)
            else:  # MAXIMUM_THROUGHPUT
                await self._store_collections_parallel(collections, shop_id, metrics)
            
            metrics.end_time = now_utc()
            metrics.processing_time = (metrics.end_time - metrics.start_time).total_seconds()
            metrics.batch_size = self.config.batch_size
            
            # Update metrics
            self.storage_metrics[f"{shop_id}_{DataType.COLLECTIONS.value}"] = metrics
            
            logger.info(f"Collections storage completed: {metrics.new_items} new, {metrics.updated_items} updated")
            return metrics
            
        except Exception as e:
            metrics.failed_items = len(collections)
            metrics.end_time = now_utc()
            logger.error(f"Failed to store collections data: {e}")
            raise DataStorageError(f"Collections data storage failed: {e}")
    
    async def store_customer_events_data(self, events: List[Any], shop_id: str) -> StorageMetrics:
        """Store customer events data with enterprise-grade performance"""
        metrics = StorageMetrics(
            operation="store_customer_events",
            data_type=DataType.CUSTOMER_EVENTS,
            shop_id=shop_id,
            start_time=now_utc()
        )
        
        try:
            await self.initialize()
            
            # Use enterprise-grade storage strategy
            strategy = self._select_storage_strategy(len(events))
            
            if strategy == StorageStrategy.STREAMING:
                await self._store_customer_events_streaming(events, shop_id, metrics)
            elif strategy == StorageStrategy.BATCH_OPTIMIZED:
                await self._store_customer_events_batch(events, shop_id, metrics)
            else:  # MAXIMUM_THROUGHPUT
                await self._store_customer_events_parallel(events, shop_id, metrics)
            
            metrics.end_time = now_utc()
            metrics.processing_time = (metrics.end_time - metrics.start_time).total_seconds()
            metrics.batch_size = self.config.batch_size
            
            # Update metrics
            self.storage_metrics[f"{shop_id}_{DataType.CUSTOMER_EVENTS.value}"] = metrics
            
            logger.info(f"Customer events storage completed: {metrics.new_items} new, {metrics.updated_items} updated")
            return metrics
            
        except Exception as e:
            metrics.failed_items = len(events)
            metrics.end_time = now_utc()
            logger.error(f"Failed to store customer events data: {e}")
            raise DataStorageError(f"Customer events data storage failed: {e}")
    
    # Enterprise-grade storage implementation methods
    async def _store_orders_streaming(self, orders: List[Any], shop_id: str, metrics: StorageMetrics) -> None:
        """Store orders using streaming strategy for real-time processing"""
        for order in orders:
            try:
                # Store order data
                await self.db.raworder.create(
                    data={
                        "shopId": shop_id,
                        "payload": json.dumps(order.dict() if hasattr(order, 'dict') else order, default=str),
                        "extractedAt": now_utc()
                    }
                )
                metrics.new_items += 1
            except Exception as e:
                metrics.failed_items += 1
                logger.error(f"Failed to store order: {e}")
    
    async def _store_orders_batch(self, orders: List[Any], shop_id: str, metrics: StorageMetrics) -> None:
        """Store orders using batch strategy for optimal performance"""
        batch_size = self.config.batch_size
        for i in range(0, len(orders), batch_size):
            batch = orders[i:i + batch_size]
            try:
                # Create batch data
                batch_data = [
                    {
                        "shopId": shop_id,
                        "payload": json.dumps(order.dict() if hasattr(order, 'dict') else order, default=str),
                        "extractedAt": now_utc()
                    }
                    for order in batch
                ]
                
                # Store batch
                await self.db.raworder.create_many(data=batch_data)
                metrics.new_items += len(batch)
            except Exception as e:
                metrics.failed_items += len(batch)
                logger.error(f"Failed to store order batch: {e}")
    
    async def _store_orders_parallel(self, orders: List[Any], shop_id: str, metrics: StorageMetrics) -> None:
        """Store orders using parallel strategy for maximum throughput"""
        # Use asyncio.gather for parallel processing
        tasks = []
        for order in orders:
            task = self._store_single_order(order, shop_id)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                metrics.failed_items += 1
                logger.error(f"Failed to store order: {result}")
            else:
                metrics.new_items += 1
    
    async def _store_single_order(self, order: Any, shop_id: str) -> None:
        """Store a single order"""
        await self.db.raworder.create(
            data={
                "shopId": shop_id,
                "payload": json.dumps(order.dict() if hasattr(order, 'dict') else order, default=str),
                "extractedAt": now_utc()
            }
        )
    
    async def _store_customers_streaming(self, customers: List[Any], shop_id: str, metrics: StorageMetrics) -> None:
        """Store customers using streaming strategy"""
        for customer in customers:
            try:
                await self.db.rawcustomer.create(
                    data={
                        "shopId": shop_id,
                        "payload": json.dumps(customer.dict() if hasattr(customer, 'dict') else customer, default=str),
                        "extractedAt": now_utc()
                    }
                )
                metrics.new_items += 1
            except Exception as e:
                metrics.failed_items += 1
                logger.error(f"Failed to store customer: {e}")
    
    async def _store_customers_batch(self, customers: List[Any], shop_id: str, metrics: StorageMetrics) -> None:
        """Store customers using batch strategy"""
        batch_size = self.config.batch_size
        for i in range(0, len(customers), batch_size):
            batch = customers[i:i + batch_size]
            try:
                batch_data = [
                    {
                        "shopId": shop_id,
                        "payload": json.dumps(customer.dict() if hasattr(customer, 'dict') else customer, default=str),
                        "extractedAt": now_utc()
                    }
                    for customer in batch
                ]
                await self.db.rawcustomer.create_many(data=batch_data)
                metrics.new_items += len(batch)
            except Exception as e:
                metrics.failed_items += len(batch)
                logger.error(f"Failed to store customer batch: {e}")
    
    async def _store_customers_parallel(self, customers: List[Any], shop_id: str, metrics: StorageMetrics) -> None:
        """Store customers using parallel strategy"""
        tasks = [self._store_single_customer(customer, shop_id) for customer in customers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                metrics.failed_items += 1
                logger.error(f"Failed to store customer: {result}")
            else:
                metrics.new_items += 1
    
    async def _store_single_customer(self, customer: Any, shop_id: str) -> None:
        """Store a single customer"""
        await self.db.rawcustomer.create(
            data={
                "shopId": shop_id,
                "payload": json.dumps(customer.dict() if hasattr(customer, 'dict') else customer, default=str),
                "extractedAt": now_utc()
            }
        )
    
    async def _store_collections_streaming(self, collections: List[Any], shop_id: str, metrics: StorageMetrics) -> None:
        """Store collections using streaming strategy"""
        for collection in collections:
            try:
                await self.db.rawcollection.create(
                    data={
                        "shopId": shop_id,
                        "payload": json.dumps(collection.dict() if hasattr(collection, 'dict') else collection, default=str),
                        "extractedAt": now_utc()
                    }
                )
                metrics.new_items += 1
            except Exception as e:
                metrics.failed_items += 1
                logger.error(f"Failed to store collection: {e}")
    
    async def _store_collections_batch(self, collections: List[Any], shop_id: str, metrics: StorageMetrics) -> None:
        """Store collections using batch strategy"""
        batch_size = self.config.batch_size
        for i in range(0, len(collections), batch_size):
            batch = collections[i:i + batch_size]
            try:
                batch_data = [
                    {
                        "shopId": shop_id,
                        "payload": json.dumps(collection.dict() if hasattr(collection, 'dict') else collection, default=str),
                        "extractedAt": now_utc()
                    }
                    for collection in batch
                ]
                await self.db.rawcollection.create_many(data=batch_data)
                metrics.new_items += len(batch)
            except Exception as e:
                metrics.failed_items += len(batch)
                logger.error(f"Failed to store collection batch: {e}")
    
    async def _store_collections_parallel(self, collections: List[Any], shop_id: str, metrics: StorageMetrics) -> None:
        """Store collections using parallel strategy"""
        tasks = [self._store_single_collection(collection, shop_id) for collection in collections]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                metrics.failed_items += 1
                logger.error(f"Failed to store collection: {result}")
            else:
                metrics.new_items += 1
    
    async def _store_single_collection(self, collection: Any, shop_id: str) -> None:
        """Store a single collection"""
        await self.db.rawcollection.create(
            data={
                "shopId": shop_id,
                "payload": json.dumps(collection.dict() if hasattr(collection, 'dict') else collection, default=str),
                "extractedAt": now_utc()
            }
        )
    
    async def _store_customer_events_streaming(self, events: List[Any], shop_id: str, metrics: StorageMetrics) -> None:
        """Store customer events using streaming strategy"""
        for event in events:
            try:
                await self.db.rawcustomerevent.create(
                    data={
                        "shopId": shop_id,
                        "payload": json.dumps(event.dict() if hasattr(event, 'dict') else event, default=str),
                        "extractedAt": now_utc()
                    }
                )
                metrics.new_items += 1
            except Exception as e:
                metrics.failed_items += 1
                logger.error(f"Failed to store customer event: {e}")
    
    async def _store_customer_events_batch(self, events: List[Any], shop_id: str, metrics: StorageMetrics) -> None:
        """Store customer events using batch strategy"""
        batch_size = self.config.batch_size
        for i in range(0, len(events), batch_size):
            batch = events[i:i + batch_size]
            try:
                batch_data = [
                    {
                        "shopId": shop_id,
                        "payload": json.dumps(event.dict() if hasattr(event, 'dict') else event, default=str),
                        "extractedAt": now_utc()
                    }
                    for event in batch
                ]
                await self.db.rawcustomerevent.create_many(data=batch_data)
                metrics.new_items += len(batch)
            except Exception as e:
                metrics.failed_items += len(batch)
                logger.error(f"Failed to store customer event batch: {e}")
    
    async def _store_customer_events_parallel(self, events: List[Any], shop_id: str, metrics: StorageMetrics) -> None:
        """Store customer events using parallel strategy"""
        tasks = [self._store_single_customer_event(event, shop_id) for event in events]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                metrics.failed_items += 1
                logger.error(f"Failed to store customer event: {result}")
            else:
                metrics.new_items += 1
    
    async def _store_single_customer_event(self, event: Any, shop_id: str) -> None:
        """Store a single customer event"""
        await self.db.rawcustomerevent.create(
            data={
                "shopId": shop_id,
                "payload": json.dumps(event.dict() if hasattr(event, 'dict') else event, default=str),
                "extractedAt": now_utc()
            }
        )
    
    async def cleanup_old_data(self, days_to_keep: int = 90) -> int:
        """Clean up old data to maintain performance"""
        try:
            await self.initialize()
            
            cutoff_date = now_utc() - timedelta(days=days_to_keep)
            deleted_count = 0
            
            # Clean up old raw data
            tables = ['raworder', 'rawproduct', 'rawcustomer', 'rawcollection', 'rawcustomerevent']
            
            for table in tables:
                if hasattr(self.db, table):
                    deleted = await getattr(self.db, table).delete_many(
                        where={"extractedAt": {"lt": cutoff_date}}
                    )
                    deleted_count += deleted
                    logger.info(f"Cleaned up {deleted} old records from {table}")
            
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
            if isinstance(value, dict) and 'cached_at' in value:
                cache_age = (current_time - value['cached_at']).total_seconds()
                if cache_age > self.config.cache_ttl_seconds:
                    expired_keys.append(key)
        
        for key in expired_keys:
            del self._performance_cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    async def close(self) -> None:
        """Close database connection and cleanup resources"""
        try:
            if self.db and self._is_initialized:
                await self.db.disconnect()
                self._is_initialized = False
                logger.info("Data storage service closed")
        except Exception as e:
            logger.error(f"Error closing data storage service: {e}")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
