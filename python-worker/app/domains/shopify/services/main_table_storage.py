"""
Main Table Storage Service for BetterBundle Python Worker

This service efficiently extracts key fields from raw JSON data and stores them
in structured main tables for fast querying and feature computation.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

from prisma import Json
from app.core.database.simple_db_client import get_database
from app.core.logging import get_logger
from app.shared.helpers import now_utc
from app.core.redis_client import streams_manager
from app.core.config.settings import settings

logger = get_logger(__name__)


@dataclass
class StorageResult:
    """Result of main table storage operation"""

    success: bool
    processed_count: int
    error_count: int
    errors: List[str]
    duration_ms: int


class MainTableStorageService:
    """Service for storing structured data in main tables"""

    def __init__(self):
        self.logger = logger
        self._db_client = None

    async def _get_database(self):
        """Get or initialize the database client"""
        if self._db_client is None:
            self._db_client = await get_database()
        return self._db_client

    async def _get_processed_shopify_ids(self, shop_id: str, data_type: str) -> set:
        """Get all Shopify IDs that have already been processed in the main table using efficient raw SQL queries"""
        try:
            db = await self._get_database()

            # Use raw SQL queries to get only the IDs we need - much more memory efficient
            if data_type == "orders":
                result = await db.query_raw(
                    'SELECT "orderId" FROM "OrderData" WHERE "shopId" = $1', shop_id
                )
                return {row["orderId"] for row in result if row["orderId"]}
            elif data_type == "products":
                result = await db.query_raw(
                    'SELECT "productId" FROM "ProductData" WHERE "shopId" = $1', shop_id
                )
                return {row["productId"] for row in result if row["productId"]}
            elif data_type == "customers":
                result = await db.query_raw(
                    'SELECT "customerId" FROM "CustomerData" WHERE "shopId" = $1',
                    shop_id,
                )
                return {row["customerId"] for row in result if row["customerId"]}
            elif data_type == "collections":
                result = await db.query_raw(
                    'SELECT "collectionId" FROM "CollectionData" WHERE "shopId" = $1',
                    shop_id,
                )
                return {row["collectionId"] for row in result if row["collectionId"]}
            elif data_type == "customer_events":
                result = await db.query_raw(
                    'SELECT "eventId" FROM "CustomerEventData" WHERE "shopId" = $1',
                    shop_id,
                )
                return {row["eventId"] for row in result if row["eventId"]}
            else:
                return set()

        except Exception as e:
            self.logger.warning(
                f"Failed to get processed Shopify IDs for {data_type}: {e}"
            )
            return set()

    async def _get_updated_shopify_ids(self, shop_id: str, data_type: str) -> set:
        """Get Shopify IDs that have been updated in raw tables since last main table processing"""
        try:
            db = await self._get_database()

            # Compare raw table extractedAt with main table updatedAt to find updated records
            if data_type == "orders":
                result = await db.query_raw(
                    """
                    SELECT r."shopifyId" 
                    FROM "RawOrder" r
                    LEFT JOIN "OrderData" o ON r."shopifyId" = o."orderId" AND r."shopId" = o."shopId"
                    WHERE r."shopId" = $1 
                    AND r."shopifyId" IS NOT NULL
                    AND (o."orderId" IS NULL OR r."extractedAt" > o."updatedAt")
                    """,
                    shop_id,
                )
                return {row["shopifyId"] for row in result if row["shopifyId"]}
            elif data_type == "products":
                result = await db.query_raw(
                    """
                    SELECT r."shopifyId" 
                    FROM "RawProduct" r
                    LEFT JOIN "ProductData" p ON r."shopifyId" = p."productId" AND r."shopId" = p."shopId"
                    WHERE r."shopId" = $1 
                    AND r."shopifyId" IS NOT NULL
                    AND (p."productId" IS NULL OR r."extractedAt" > p."updatedAt")
                    """,
                    shop_id,
                )
                return {row["shopifyId"] for row in result if row["shopifyId"]}
            elif data_type == "customers":
                result = await db.query_raw(
                    """
                    SELECT r."shopifyId" 
                    FROM "RawCustomer" r
                    LEFT JOIN "CustomerData" c ON r."shopifyId" = c."customerId" AND r."shopId" = c."shopId"
                    WHERE r."shopId" = $1 
                    AND r."shopifyId" IS NOT NULL
                    AND (c."customerId" IS NULL OR r."extractedAt" > c."updatedAt")
                    """,
                    shop_id,
                )
                return {row["shopifyId"] for row in result if row["shopifyId"]}
            elif data_type == "collections":
                result = await db.query_raw(
                    """
                    SELECT r."shopifyId" 
                    FROM "RawCollection" r
                    LEFT JOIN "CollectionData" c ON r."shopifyId" = c."collectionId" AND r."shopId" = c."shopId"
                    WHERE r."shopId" = $1 
                    AND r."shopifyId" IS NOT NULL
                    AND (c."collectionId" IS NULL OR r."extractedAt" > c."updatedAt")
                    """,
                    shop_id,
                )
                return {row["shopifyId"] for row in result if row["shopifyId"]}
            elif data_type == "customer_events":
                result = await db.query_raw(
                    """
                    SELECT r."shopifyId" 
                    FROM "RawCustomerEvent" r
                    LEFT JOIN "CustomerEventData" e ON r."shopifyId" = e."eventId" AND r."shopId" = e."shopId"
                    WHERE r."shopId" = $1 
                    AND r."shopifyId" IS NOT NULL
                    AND (e."eventId" IS NULL OR r."extractedAt" > e."updatedAt")
                    """,
                    shop_id,
                )
                return {row["shopifyId"] for row in result if row["shopifyId"]}
            else:
                return set()

        except Exception as e:
            self.logger.error(f"Error getting updated Shopify IDs for {data_type}: {e}")
            return set()

    def _extract_order_id(self, order_data: Dict[str, Any]) -> Optional[str]:
        """Extract Shopify order ID from order data"""
        try:
            return str(order_data.get("id", ""))
        except Exception:
            return None

    def _extract_product_id(self, product_data: Dict[str, Any]) -> Optional[str]:
        """Extract Shopify product ID from product data"""
        try:
            return str(product_data.get("id", ""))
        except Exception:
            return None

    def _extract_customer_id(self, customer_data: Dict[str, Any]) -> Optional[str]:
        """Extract Shopify customer ID from customer data"""
        try:
            return str(customer_data.get("id", ""))
        except Exception:
            return None

    def _extract_collection_id(self, collection_data: Dict[str, Any]) -> Optional[str]:
        """Extract Shopify collection ID from collection data"""
        try:
            return str(collection_data.get("id", ""))
        except Exception:
            return None

    def _extract_customer_event_id(self, event_data: Dict[str, Any]) -> Optional[str]:
        """Extract Shopify customer event ID from event data"""
        try:
            # Customer events might not have a direct ID, use a combination of fields
            customer_id = event_data.get("customer_id", "")
            event_type = event_data.get("event_type", "")
            timestamp = event_data.get("timestamp", "")
            return f"{customer_id}_{event_type}_{timestamp}"
        except Exception:
            return None

    async def store_all_data(
        self, shop_id: str, incremental: bool = True
    ) -> StorageResult:
        """Store raw data for a shop to main tables with incremental processing"""
        start_time = now_utc()
        total_processed = 0
        total_errors = 0
        all_errors = []

        try:
            # Store all data types concurrently using asyncio.gather
            self.logger.info(
                f"Starting {'incremental' if incremental else 'full'} storage for all data types for shop {shop_id}"
            )

            # Run all storage operations concurrently
            results = await asyncio.gather(
                self.store_orders(shop_id, incremental=incremental),
                self.store_products(shop_id, incremental=incremental),
                self.store_customers(shop_id, incremental=incremental),
                self.store_collections(shop_id, incremental=incremental),
                self.store_customer_events(shop_id, incremental=incremental),
                return_exceptions=True,  # Don't fail if one operation fails
            )

            # Process results from concurrent operations
            data_types = [
                "orders",
                "products",
                "customers",
                "collections",
                "customer_events",
            ]

            for i, result in enumerate(results):
                data_type = data_types[i]

                if isinstance(result, Exception):
                    # Handle exceptions from concurrent operations
                    error_msg = f"Failed to store {data_type}: {str(result)}"
                    self.logger.error(error_msg)
                    all_errors.append(error_msg)
                    total_errors += 1
                else:
                    # Process successful result
                    total_processed += result.processed_count
                    total_errors += result.error_count
                    all_errors.extend(result.errors)
                    self.logger.info(
                        f"Completed {data_type} storage: {result.processed_count} processed, {result.error_count} errors"
                    )

            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            self.logger.info(f"Concurrent storage completed in {duration_ms}ms")

            # Publish event to trigger feature computation if storage was successful
            if total_errors == 0 and total_processed > 0:
                await self._publish_feature_computation_event(
                    shop_id, total_processed, duration_ms
                )

            return StorageResult(
                success=total_errors == 0,
                processed_count=total_processed,
                error_count=total_errors,
                errors=all_errors,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            error_msg = f"Failed to store all data: {str(e)}"
            self.logger.error(error_msg)

            return StorageResult(
                success=False,
                processed_count=total_processed,
                error_count=total_errors + 1,
                errors=all_errors + [error_msg],
                duration_ms=duration_ms,
            )

    async def store_orders(
        self, shop_id: str, incremental: bool = True
    ) -> StorageResult:
        """Store orders from raw table to OrderData table with memory-efficient incremental processing"""
        start_time = now_utc()
        processed_count = 0
        error_count = 0
        errors = []
        batch_size = 1000  # Process 1000 orders at a time to avoid memory issues

        try:
            db = await self._get_database()

            # Step 1: Get all raw order IDs using efficient raw SQL query
            raw_order_result = await db.query_raw(
                'SELECT "shopifyId" FROM "RawOrder" WHERE "shopId" = $1 AND "shopifyId" IS NOT NULL ORDER BY "extractedAt" ASC',
                shop_id,
            )
            raw_order_ids = [row["shopifyId"] for row in raw_order_result]

            total_raw_count = len(raw_order_ids)
            self.logger.info(f"Found {total_raw_count} raw orders for shop {shop_id}")

            if total_raw_count == 0:
                self.logger.info(f"No raw orders found for shop {shop_id}")
                return StorageResult(
                    success=True,
                    processed_count=0,
                    error_count=0,
                    errors=[],
                    duration_ms=int((now_utc() - start_time).total_seconds() * 1000),
                )

            # Step 2: Get records to process (new + updated)
            records_to_process = set()
            if incremental:
                # Get new records (not in main table)
                processed_shopify_ids = await self._get_processed_shopify_ids(
                    shop_id, "orders"
                )
                raw_shopify_ids = set(raw_order_ids)
                new_shopify_ids = raw_shopify_ids - processed_shopify_ids

                # Get updated records (in main table but raw table has newer data)
                updated_shopify_ids = await self._get_updated_shopify_ids(
                    shop_id, "orders"
                )

                # Combine new and updated records
                records_to_process = new_shopify_ids | updated_shopify_ids

                self.logger.info(
                    f"Found {len(processed_shopify_ids)} already processed orders for shop {shop_id}"
                )
                self.logger.info(
                    f"Found {len(new_shopify_ids)} new orders, {len(updated_shopify_ids)} updated orders"
                )
            else:
                # Full refresh: process all records
                records_to_process = set(raw_order_ids)

            total_count = len(records_to_process)
            self.logger.info(
                f"Processing {total_count} orders (new + updated) for shop {shop_id} in batches of {batch_size}"
            )

            if total_count == 0:
                self.logger.info(f"No orders to process for shop {shop_id}")
                return StorageResult(
                    success=True,
                    processed_count=0,
                    error_count=0,
                    errors=[],
                    duration_ms=int((now_utc() - start_time).total_seconds() * 1000),
                )

            # Step 4: Process orders in batches by fetching only needed records
            records_to_process_list = list(records_to_process)
            for i in range(0, total_count, batch_size):
                batch_shopify_ids = records_to_process_list[i : i + batch_size]

                # Fetch only the raw records we need to process (database does the filtering)
                raw_orders = await db.raworder.find_many(
                    where={"shopId": shop_id, "shopifyId": {"in": batch_shopify_ids}}
                )

                # Collect order data for batch processing
                batch_order_data = []

                for raw_order in raw_orders:
                    try:
                        # Parse the JSON payload
                        payload = raw_order.payload
                        if isinstance(payload, str):
                            payload = json.loads(payload)

                        # Extract order data
                        order_data = self._extract_order_fields(payload, shop_id)

                        if order_data:
                            batch_order_data.append(order_data)
                        else:
                            self.logger.warning(
                                f"Could not extract order data from raw order {raw_order.id}"
                            )

                    except Exception as e:
                        error_msg = f"Failed to process order {raw_order.id}: {str(e)}"
                        self.logger.error(error_msg)
                        errors.append(error_msg)
                        error_count += 1

                # Batch upsert all orders in this batch
                if batch_order_data:
                    try:
                        await self._batch_upsert_order_data(batch_order_data, db)
                        processed_count += len(batch_order_data)
                    except Exception as e:
                        error_msg = f"Failed to batch upsert orders: {str(e)}"
                        self.logger.error(error_msg)
                        errors.append(error_msg)
                        error_count += len(batch_order_data)

                # Log progress
                progress_percent = min(100, (processed_count / total_count) * 100)
                self.logger.info(
                    f"Processed {processed_count}/{total_count} orders ({progress_percent:.1f}%)"
                )

            self.logger.info(f"Successfully processed {processed_count} orders")

            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            return StorageResult(
                success=error_count == 0,
                processed_count=processed_count,
                error_count=error_count,
                errors=errors,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            error_msg = f"Failed to store orders: {str(e)}"
            self.logger.error(error_msg)
            return StorageResult(
                success=False,
                processed_count=processed_count,
                error_count=error_count + 1,
                errors=errors + [error_msg],
                duration_ms=duration_ms,
            )

    async def store_products(
        self, shop_id: str, incremental: bool = True
    ) -> StorageResult:
        """Store products from raw table to ProductData table with memory-efficient incremental processing"""
        start_time = now_utc()
        processed_count = 0
        error_count = 0
        errors = []
        batch_size = 1000  # Process 1000 products at a time to avoid memory issues

        try:
            db = await self._get_database()

            # Step 1: Get all raw product IDs using efficient raw SQL query
            raw_product_result = await db.query_raw(
                'SELECT "shopifyId" FROM "RawProduct" WHERE "shopId" = $1 AND "shopifyId" IS NOT NULL ORDER BY "extractedAt" ASC',
                shop_id,
            )
            raw_product_ids = [row["shopifyId"] for row in raw_product_result]

            total_raw_count = len(raw_product_ids)
            self.logger.info(f"Found {total_raw_count} raw products for shop {shop_id}")

            if total_raw_count == 0:
                self.logger.info(f"No raw products found for shop {shop_id}")
                return StorageResult(
                    success=True,
                    processed_count=0,
                    error_count=0,
                    errors=[],
                    duration_ms=int((now_utc() - start_time).total_seconds() * 1000),
                )

            # Step 2: Get records to process (new + updated)
            records_to_process = set()
            if incremental:
                # Get new records (not in main table)
                processed_shopify_ids = await self._get_processed_shopify_ids(
                    shop_id, "products"
                )
                raw_shopify_ids = set(raw_product_ids)
                new_shopify_ids = raw_shopify_ids - processed_shopify_ids

                # Get updated records (in main table but raw table has newer data)
                updated_shopify_ids = await self._get_updated_shopify_ids(
                    shop_id, "products"
                )

                # Combine new and updated records
                records_to_process = new_shopify_ids | updated_shopify_ids

                self.logger.info(
                    f"Found {len(processed_shopify_ids)} already processed products for shop {shop_id}"
                )
                self.logger.info(
                    f"Found {len(new_shopify_ids)} new products, {len(updated_shopify_ids)} updated products"
                )
            else:
                # Full refresh: process all records
                records_to_process = set(raw_product_ids)

            total_count = len(records_to_process)
            self.logger.info(
                f"Processing {total_count} products (new + updated) for shop {shop_id} in batches of {batch_size}"
            )

            if total_count == 0:
                self.logger.info(f"No products to process for shop {shop_id}")
                return StorageResult(
                    success=True,
                    processed_count=0,
                    error_count=0,
                    errors=[],
                    duration_ms=int((now_utc() - start_time).total_seconds() * 1000),
                )

            # Step 4: Process products in batches by fetching only needed records
            records_to_process_list = list(records_to_process)
            for i in range(0, total_count, batch_size):
                batch_shopify_ids = records_to_process_list[i : i + batch_size]

                # Fetch only the raw records we need to process (database does the filtering)
                raw_products = await db.rawproduct.find_many(
                    where={"shopId": shop_id, "shopifyId": {"in": batch_shopify_ids}}
                )

                # Collect product data for batch processing
                batch_product_data = []

                for raw_product in raw_products:
                    try:
                        # Parse the JSON payload
                        payload = raw_product.payload
                        if isinstance(payload, str):
                            payload = json.loads(payload)

                        # Extract product data
                        product_data = self._extract_product_fields(payload, shop_id)

                        if product_data:
                            batch_product_data.append(product_data)
                        else:
                            self.logger.warning(
                                f"Could not extract product data from raw product {raw_product.id}"
                            )

                    except Exception as e:
                        error_msg = (
                            f"Failed to process product {raw_product.id}: {str(e)}"
                        )
                        self.logger.error(error_msg)
                        errors.append(error_msg)
                        error_count += 1

                # Batch upsert all products in this batch
                if batch_product_data:
                    try:
                        await self._batch_upsert_product_data(batch_product_data, db)
                        processed_count += len(batch_product_data)
                    except Exception as e:
                        error_msg = f"Failed to batch upsert products: {str(e)}"
                        self.logger.error(error_msg)
                        errors.append(error_msg)
                        error_count += len(batch_product_data)

                # Log progress
                progress_percent = min(100, (processed_count / total_count) * 100)
                self.logger.info(
                    f"Processed {processed_count}/{total_count} products ({progress_percent:.1f}%)"
                )

            self.logger.info(f"Successfully processed {processed_count} products")

            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            return StorageResult(
                success=error_count == 0,
                processed_count=processed_count,
                error_count=error_count,
                errors=errors,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            error_msg = f"Failed to store products: {str(e)}"
            self.logger.error(error_msg)
            return StorageResult(
                success=False,
                processed_count=processed_count,
                error_count=error_count + 1,
                errors=errors + [error_msg],
                duration_ms=duration_ms,
            )

    async def store_customers(
        self, shop_id: str, incremental: bool = True
    ) -> StorageResult:
        """Store customers from raw table to CustomerData table with memory-efficient incremental processing"""
        start_time = now_utc()
        processed_count = 0
        error_count = 0
        errors = []
        batch_size = 1000  # Process 1000 customers at a time to avoid memory issues

        try:
            db = await self._get_database()

            # Step 1: Get all raw customer IDs using efficient raw SQL query
            raw_customer_result = await db.query_raw(
                'SELECT "shopifyId" FROM "RawCustomer" WHERE "shopId" = $1 AND "shopifyId" IS NOT NULL ORDER BY "extractedAt" ASC',
                shop_id,
            )
            raw_customer_ids = [row["shopifyId"] for row in raw_customer_result]

            total_raw_count = len(raw_customer_ids)
            self.logger.info(
                f"Found {total_raw_count} raw customers for shop {shop_id}"
            )

            if total_raw_count == 0:
                self.logger.info(f"No raw customers found for shop {shop_id}")
                return StorageResult(
                    success=True,
                    processed_count=0,
                    error_count=0,
                    errors=[],
                    duration_ms=int((now_utc() - start_time).total_seconds() * 1000),
                )

            # Step 2: Get records to process (new + updated)
            records_to_process = set()
            if incremental:
                # Get new records (not in main table)
                processed_shopify_ids = await self._get_processed_shopify_ids(
                    shop_id, "customers"
                )
                raw_shopify_ids = set(raw_customer_ids)
                new_shopify_ids = raw_shopify_ids - processed_shopify_ids

                # Get updated records (in main table but raw table has newer data)
                updated_shopify_ids = await self._get_updated_shopify_ids(
                    shop_id, "customers"
                )

                # Combine new and updated records
                records_to_process = new_shopify_ids | updated_shopify_ids

                self.logger.info(
                    f"Found {len(processed_shopify_ids)} already processed customers for shop {shop_id}"
                )
                self.logger.info(
                    f"Found {len(new_shopify_ids)} new customers, {len(updated_shopify_ids)} updated customers"
                )
            else:
                # Full refresh: process all records
                records_to_process = set(raw_customer_ids)

            total_count = len(records_to_process)
            self.logger.info(
                f"Processing {total_count} customers (new + updated) for shop {shop_id} in batches of {batch_size}"
            )

            if total_count == 0:
                self.logger.info(f"No customers to process for shop {shop_id}")
                return StorageResult(
                    success=True,
                    processed_count=0,
                    error_count=0,
                    errors=[],
                    duration_ms=int((now_utc() - start_time).total_seconds() * 1000),
                )

            # Step 4: Process customers in batches by fetching only needed records
            records_to_process_list = list(records_to_process)
            for i in range(0, total_count, batch_size):
                batch_shopify_ids = records_to_process_list[i : i + batch_size]

                # Fetch only the raw records we need to process (database does the filtering)
                raw_customers = await db.rawcustomer.find_many(
                    where={"shopId": shop_id, "shopifyId": {"in": batch_shopify_ids}}
                )

                # Collect customer data for batch processing
                batch_customer_data = []

                for raw_customer in raw_customers:
                    try:
                        # Parse the JSON payload
                        payload = raw_customer.payload
                        if isinstance(payload, str):
                            payload = json.loads(payload)

                        # Extract customer data
                        customer_data = self._extract_customer_fields(payload, shop_id)

                        if customer_data:
                            batch_customer_data.append(customer_data)
                        else:
                            self.logger.warning(
                                f"Could not extract customer data from raw customer {raw_customer.id}"
                            )

                    except Exception as e:
                        error_msg = (
                            f"Failed to process customer {raw_customer.id}: {str(e)}"
                        )
                        self.logger.error(error_msg)
                        errors.append(error_msg)
                        error_count += 1

                # Batch upsert all customers in this batch
                if batch_customer_data:
                    try:
                        await self._batch_upsert_customer_data(batch_customer_data, db)
                        processed_count += len(batch_customer_data)
                    except Exception as e:
                        error_msg = f"Failed to batch upsert customers: {str(e)}"
                        self.logger.error(error_msg)
                        errors.append(error_msg)
                        error_count += len(batch_customer_data)

                # Log progress
                progress_percent = min(100, (processed_count / total_count) * 100)
                self.logger.info(
                    f"Processed {processed_count}/{total_count} customers ({progress_percent:.1f}%)"
                )

            self.logger.info(f"Successfully processed {processed_count} customers")

            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            return StorageResult(
                success=error_count == 0,
                processed_count=processed_count,
                error_count=error_count,
                errors=errors,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            error_msg = f"Failed to store customers: {str(e)}"
            self.logger.error(error_msg)
            return StorageResult(
                success=False,
                processed_count=processed_count,
                error_count=error_count + 1,
                errors=errors + [error_msg],
                duration_ms=duration_ms,
            )

    async def store_collections(
        self, shop_id: str, incremental: bool = True
    ) -> StorageResult:
        """Store collections from raw table to CollectionData table with memory-efficient incremental processing"""
        start_time = now_utc()
        processed_count = 0
        error_count = 0
        errors = []
        batch_size = 1000  # Process 1000 collections at a time to avoid memory issues

        try:
            db = await self._get_database()

            # Step 1: Get all raw collection IDs using efficient raw SQL query
            raw_collection_result = await db.query_raw(
                'SELECT "shopifyId" FROM "RawCollection" WHERE "shopId" = $1 AND "shopifyId" IS NOT NULL ORDER BY "extractedAt" ASC',
                shop_id,
            )
            raw_collection_ids = [row["shopifyId"] for row in raw_collection_result]

            total_raw_count = len(raw_collection_ids)
            self.logger.info(
                f"Found {total_raw_count} raw collections for shop {shop_id}"
            )

            if total_raw_count == 0:
                self.logger.info(f"No raw collections found for shop {shop_id}")
                return StorageResult(
                    success=True,
                    processed_count=0,
                    error_count=0,
                    errors=[],
                    duration_ms=int((now_utc() - start_time).total_seconds() * 1000),
                )

            # Step 2: Get records to process (new + updated)
            records_to_process = set()
            if incremental:
                # Get new records (not in main table)
                processed_shopify_ids = await self._get_processed_shopify_ids(
                    shop_id, "collections"
                )
                raw_shopify_ids = set(raw_collection_ids)
                new_shopify_ids = raw_shopify_ids - processed_shopify_ids

                # Get updated records (in main table but raw table has newer data)
                updated_shopify_ids = await self._get_updated_shopify_ids(
                    shop_id, "collections"
                )

                # Combine new and updated records
                records_to_process = new_shopify_ids | updated_shopify_ids

                self.logger.info(
                    f"Found {len(processed_shopify_ids)} already processed collections for shop {shop_id}"
                )
                self.logger.info(
                    f"Found {len(new_shopify_ids)} new collections, {len(updated_shopify_ids)} updated collections"
                )
            else:
                # Full refresh: process all records
                records_to_process = set(raw_collection_ids)

            total_count = len(records_to_process)
            self.logger.info(
                f"Processing {total_count} collections (new + updated) for shop {shop_id} in batches of {batch_size}"
            )

            if total_count == 0:
                self.logger.info(f"No collections to process for shop {shop_id}")
                return StorageResult(
                    success=True,
                    processed_count=0,
                    error_count=0,
                    errors=[],
                    duration_ms=int((now_utc() - start_time).total_seconds() * 1000),
                )

            # Step 4: Process collections in batches by fetching only needed records
            records_to_process_list = list(records_to_process)
            for i in range(0, total_count, batch_size):
                batch_shopify_ids = records_to_process_list[i : i + batch_size]

                # Fetch only the raw records we need to process (database does the filtering)
                raw_collections = await db.rawcollection.find_many(
                    where={"shopId": shop_id, "shopifyId": {"in": batch_shopify_ids}}
                )

                # Collect collection data for batch processing
                batch_collection_data = []

                for raw_collection in raw_collections:
                    try:
                        # Parse the JSON payload
                        payload = raw_collection.payload
                        if isinstance(payload, str):
                            payload = json.loads(payload)

                        # Extract collection data
                        collection_data = self._extract_collection_fields(
                            payload, shop_id
                        )

                        if collection_data:
                            batch_collection_data.append(collection_data)
                        else:
                            self.logger.warning(
                                f"Could not extract collection data from raw collection {raw_collection.id}"
                            )

                    except Exception as e:
                        error_msg = f"Failed to process collection {raw_collection.id}: {str(e)}"
                        self.logger.error(error_msg)
                        errors.append(error_msg)
                        error_count += 1

                # Batch upsert all collections in this batch
                if batch_collection_data:
                    try:
                        await self._batch_upsert_collection_data(
                            batch_collection_data, db
                        )
                        processed_count += len(batch_collection_data)
                    except Exception as e:
                        error_msg = f"Failed to batch upsert collections: {str(e)}"
                        self.logger.error(error_msg)
                        errors.append(error_msg)
                        error_count += len(batch_collection_data)

                # Log progress
                progress_percent = min(100, (processed_count / total_count) * 100)
                self.logger.info(
                    f"Processed {processed_count}/{total_count} collections ({progress_percent:.1f}%)"
                )

            self.logger.info(f"Successfully processed {processed_count} collections")

            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            return StorageResult(
                success=error_count == 0,
                processed_count=processed_count,
                error_count=error_count,
                errors=errors,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            error_msg = f"Failed to store collections: {str(e)}"
            self.logger.error(error_msg)
            return StorageResult(
                success=False,
                processed_count=processed_count,
                error_count=error_count + 1,
                errors=errors + [error_msg],
                duration_ms=duration_ms,
            )

    async def store_customer_events(
        self, shop_id: str, incremental: bool = True
    ) -> StorageResult:
        """Store customer events from raw table to CustomerEventData table with memory-efficient incremental processing"""
        start_time = now_utc()
        processed_count = 0
        error_count = 0
        errors = []
        batch_size = (
            1000  # Process 1000 customer events at a time to avoid memory issues
        )

        try:
            db = await self._get_database()

            # Step 1: Get all raw customer event IDs using efficient raw SQL query
            raw_event_result = await db.query_raw(
                'SELECT "shopifyId" FROM "RawCustomerEvent" WHERE "shopId" = $1 AND "shopifyId" IS NOT NULL ORDER BY "extractedAt" ASC',
                shop_id,
            )
            raw_event_ids = [row["shopifyId"] for row in raw_event_result]

            total_raw_count = len(raw_event_ids)
            self.logger.info(
                f"Found {total_raw_count} raw customer events for shop {shop_id}"
            )

            if total_raw_count == 0:
                self.logger.info(f"No raw customer events found for shop {shop_id}")
                return StorageResult(
                    success=True,
                    processed_count=0,
                    error_count=0,
                    errors=[],
                    duration_ms=int((now_utc() - start_time).total_seconds() * 1000),
                )

            # Step 2: Get records to process (new + updated)
            records_to_process = set()
            if incremental:
                # Get new records (not in main table)
                processed_shopify_ids = await self._get_processed_shopify_ids(
                    shop_id, "customer_events"
                )
                raw_shopify_ids = set(raw_event_ids)
                new_shopify_ids = raw_shopify_ids - processed_shopify_ids

                # Get updated records (in main table but raw table has newer data)
                updated_shopify_ids = await self._get_updated_shopify_ids(
                    shop_id, "customer_events"
                )

                # Combine new and updated records
                records_to_process = new_shopify_ids | updated_shopify_ids

                self.logger.info(
                    f"Found {len(processed_shopify_ids)} already processed customer events for shop {shop_id}"
                )
                self.logger.info(
                    f"Found {len(new_shopify_ids)} new customer events, {len(updated_shopify_ids)} updated customer events"
                )
            else:
                # Full refresh: process all records
                records_to_process = set(raw_event_ids)

            total_count = len(records_to_process)
            self.logger.info(
                f"Processing {total_count} customer events (new + updated) for shop {shop_id} in batches of {batch_size}"
            )

            if total_count == 0:
                self.logger.info(f"No customer events to process for shop {shop_id}")
                return StorageResult(
                    success=True,
                    processed_count=0,
                    error_count=0,
                    errors=[],
                    duration_ms=int((now_utc() - start_time).total_seconds() * 1000),
                )

            # Step 4: Process customer events in batches by fetching only needed records
            records_to_process_list = list(records_to_process)
            for i in range(0, total_count, batch_size):
                batch_shopify_ids = records_to_process_list[i : i + batch_size]

                # Fetch only the raw records we need to process (database does the filtering)
                raw_events = await db.rawcustomerevent.find_many(
                    where={"shopId": shop_id, "shopifyId": {"in": batch_shopify_ids}}
                )

                # Collect customer event data for batch processing
                batch_event_data = []

                for raw_event in raw_events:
                    try:
                        # Parse the JSON payload
                        payload = raw_event.payload
                        if isinstance(payload, str):
                            payload = json.loads(payload)

                        # Extract customer event data
                        event_data_list = self._extract_customer_event_fields(
                            payload, shop_id
                        )

                        if event_data_list:
                            batch_event_data.extend(event_data_list)
                        else:
                            self.logger.warning(
                                f"Could not extract customer event data from raw event {raw_event.id}"
                            )

                    except Exception as e:
                        error_msg = (
                            f"Failed to process customer event {raw_event.id}: {str(e)}"
                        )
                        self.logger.error(error_msg)
                        errors.append(error_msg)
                        error_count += 1

                # Batch upsert all customer events in this batch
                if batch_event_data:
                    try:
                        await self._batch_upsert_customer_event_data(
                            batch_event_data, db
                        )
                        processed_count += len(batch_event_data)
                    except Exception as e:
                        error_msg = f"Failed to batch upsert customer events: {str(e)}"
                        self.logger.error(error_msg)
                        errors.append(error_msg)
                        error_count += len(batch_event_data)

                # Log progress
                progress_percent = min(100, (processed_count / total_count) * 100)
                self.logger.info(
                    f"Processed {processed_count}/{total_count} customer events ({progress_percent:.1f}%)"
                )

            self.logger.info(
                f"Successfully processed {processed_count} customer events"
            )

            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            return StorageResult(
                success=error_count == 0,
                processed_count=processed_count,
                error_count=error_count,
                errors=errors,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            error_msg = f"Failed to store customer events: {str(e)}"
            self.logger.error(error_msg)
            return StorageResult(
                success=False,
                processed_count=processed_count,
                error_count=error_count + 1,
                errors=errors + [error_msg],
                duration_ms=duration_ms,
            )

    def _extract_order_fields(
        self, payload: Dict[str, Any], shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """Extract key order fields from nested JSON payload"""
        try:
            # Check if payload is None or not a dict
            if payload is None or not isinstance(payload, dict):
                return None

            # Handle nested JSON structure: payload.raw_data.order
            order_data = None

            # Try nested structure first: payload.raw_data.order
            if "raw_data" in payload and isinstance(payload["raw_data"], dict):
                raw_data = payload["raw_data"]
                if raw_data is not None and "order" in raw_data:
                    order_data = raw_data["order"]

            # Fallback to direct order data
            if not order_data:
                order_data = (
                    payload.get("order")
                    or payload.get("data", {}).get("order")
                    or payload
                )

            if (
                not order_data
                or not isinstance(order_data, dict)
                or not order_data.get("id")
            ):
                return None

            # Extract order ID
            order_id = self._extract_shopify_id(order_data.get("id", ""))

            if not order_id:
                return None

            # Extract customer information
            customer = order_data.get("customer", {})

            # Extract line items (keep as JSON for complex data)
            line_items = order_data.get("lineItems", {})
            if isinstance(line_items, dict) and "edges" in line_items:
                line_items = [
                    edge.get("node", {}) for edge in line_items.get("edges", [])
                ]

            # Extract shipping address
            shipping_address = order_data.get("shippingAddress")

            # Extract billing address
            billing_address = order_data.get("billingAddress")

            # Extract discount applications (keep as JSON for complex data)
            discount_applications = order_data.get("discountApplications", {})
            if (
                isinstance(discount_applications, dict)
                and "edges" in discount_applications
            ):
                discount_applications = [
                    edge.get("node", {})
                    for edge in discount_applications.get("edges", [])
                ]

            # Extract metafields (keep as JSON for complex data)
            metafields = order_data.get("metafields", {})
            if isinstance(metafields, dict) and "edges" in metafields:
                metafields = [
                    edge.get("node", {}) for edge in metafields.get("edges", [])
                ]

            # Process tags - ensure it's a proper JSON array
            tags = order_data.get("tags", [])
            if isinstance(tags, str):
                # Split comma-separated tags and clean them
                tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
            elif not isinstance(tags, list):
                tags = []

            return {
                "shopId": shop_id,
                "orderId": order_id,
                "orderName": order_data.get("name"),
                "customerId": (
                    self._extract_shopify_id(customer.get("id", ""))
                    if customer
                    else None
                ),
                "customerEmail": order_data.get("email")
                or (customer.get("email") if customer else None),
                "customerPhone": order_data.get("phone"),
                "totalAmount": float(
                    order_data.get("totalPriceSet", {})
                    .get("shopMoney", {})
                    .get("amount", 0)
                ),
                "subtotalAmount": float(
                    order_data.get("subtotalPriceSet", {})
                    .get("shopMoney", {})
                    .get("amount", 0)
                ),
                "totalTaxAmount": float(
                    order_data.get("totalTaxSet", {})
                    .get("shopMoney", {})
                    .get("amount", 0)
                ),
                "totalShippingAmount": float(
                    order_data.get("totalShippingPriceSet", {})
                    .get("shopMoney", {})
                    .get("amount", 0)
                ),
                "totalRefundedAmount": float(
                    order_data.get("totalRefundedSet", {})
                    .get("shopMoney", {})
                    .get("amount", 0)
                ),
                "totalOutstandingAmount": float(
                    order_data.get("totalOutstandingSet", {})
                    .get("shopMoney", {})
                    .get("amount", 0)
                ),
                "orderDate": self._parse_datetime(order_data.get("createdAt"))
                or now_utc(),
                "processedAt": self._parse_datetime(order_data.get("processedAt")),
                "cancelledAt": self._parse_datetime(order_data.get("cancelledAt")),
                "cancelReason": order_data.get("cancelReason"),
                "orderStatus": (
                    "cancelled" if order_data.get("cancelledAt") else "active"
                ),
                "orderLocale": order_data.get("customerLocale"),
                "currencyCode": order_data.get("currencyCode", "USD"),
                "presentmentCurrencyCode": order_data.get("presentmentCurrencyCode"),
                "confirmed": order_data.get("confirmed", False),
                "test": order_data.get("test", False),
                "tags": tags,
                "note": order_data.get("note"),
                "lineItems": line_items,
                "shippingAddress": shipping_address,
                "billingAddress": billing_address,
                "discountApplications": discount_applications,
                "metafields": metafields,
            }

        except Exception as e:
            import traceback

            self.logger.error(f"Failed to extract order fields: {str(e)}")
            self.logger.error(f"Exception type: {type(e).__name__}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            self.logger.error(f"Payload that caused error: {payload}")
            self.logger.error(f"Shop ID: {shop_id}")
            return None

    def _extract_product_fields(
        self, payload: Dict[str, Any], shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """Extract key product fields from nested JSON payload"""
        try:
            # Handle nested JSON structure: payload.raw_data.product
            product_data = None

            if isinstance(payload, dict):
                # Try nested structure first: payload.raw_data.product
                if "raw_data" in payload and isinstance(payload["raw_data"], dict):
                    raw_data = payload["raw_data"]
                    if raw_data is not None and "product" in raw_data:
                        product_data = raw_data["product"]

                # Fallback to direct product data
                if not product_data:
                    product_data = (
                        payload.get("product")
                        or payload.get("data", {}).get("product")
                        or payload
                    )

            if (
                not product_data
                or not isinstance(product_data, dict)
                or not product_data.get("id")
            ):
                return None

            # Extract product ID
            product_id = self._extract_shopify_id(product_data.get("id", ""))
            if not product_id:
                return None

            # Extract variants (keep as JSON for complex data)
            variants = product_data.get("variants", {})
            if isinstance(variants, dict) and "edges" in variants:
                variants = [edge.get("node", {}) for edge in variants.get("edges", [])]

            # Extract images (keep as JSON for complex data)
            images = product_data.get("images", {})
            if isinstance(images, dict) and "edges" in images:
                images = [edge.get("node", {}) for edge in images.get("edges", [])]

            # Extract options (keep as JSON for complex data)
            options = product_data.get("options", [])

            # Extract collections (keep as JSON for complex data)
            collections = product_data.get("collections", {})
            if isinstance(collections, dict) and "edges" in collections:
                collections = [
                    edge.get("node", {}) for edge in collections.get("edges", [])
                ]

            # Extract metafields (keep as JSON for complex data)
            metafields = product_data.get("metafields", {})
            if isinstance(metafields, dict) and "edges" in metafields:
                metafields = [
                    edge.get("node", {}) for edge in metafields.get("edges", [])
                ]

            # Get main image URL for fast access
            main_image_url = None
            if images:
                main_image = images[0]
                main_image_url = main_image.get("url")

            # Process tags - convert string to array if needed
            tags = product_data.get("tags", [])
            if isinstance(tags, str):
                # Split comma-separated tags and clean them
                tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
            elif not isinstance(tags, list):
                tags = []

            # Ensure required fields have proper values
            title = product_data.get("title", "").strip()
            handle = product_data.get("handle", "").strip()
            price = self._get_product_price(variants)

            # Skip products with missing required fields
            if not title or not handle or price is None:
                self.logger.warning(
                    f"Skipping product {product_id} - missing required fields: title='{title}', handle='{handle}', price={price}"
                )
                return None

            return {
                "shopId": shop_id,
                "productId": product_id,
                "title": title,
                "handle": handle,
                "description": product_data.get("description"),
                "descriptionHtml": product_data.get("bodyHtml"),
                "productType": product_data.get("productType"),
                "vendor": product_data.get("vendor"),
                "tags": tags,
                "status": product_data.get("status", "active"),
                "totalInventory": product_data.get("totalInventory"),
                "price": price,
                "compareAtPrice": self._get_product_compare_price(variants),
                "inventory": self._get_total_inventory(variants),
                "imageUrl": main_image_url,
                "imageAlt": images[0].get("altText") if images else None,
                "productCreatedAt": self._parse_datetime(product_data.get("createdAt")),
                "productUpdatedAt": self._parse_datetime(product_data.get("updatedAt")),
                "variants": variants,
                "images": images,
                "options": options,
                "collections": collections,
                "metafields": metafields,
                "isActive": product_data.get("status", "active") == "active",
            }

        except Exception as e:
            self.logger.error(f"Failed to extract product fields: {str(e)}")
            return None

    def _extract_customer_fields(
        self, payload: Dict[str, Any], shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """Extract key customer fields from nested JSON payload"""
        try:
            # Handle nested JSON structure: payload.raw_data.customer
            customer_data = None

            if isinstance(payload, dict):
                # Try nested structure first: payload.raw_data.customer
                if "raw_data" in payload and isinstance(payload["raw_data"], dict):
                    raw_data = payload["raw_data"]
                    if raw_data is not None and "customer" in raw_data:
                        customer_data = raw_data["customer"]

                # Fallback to direct customer data
                if not customer_data:
                    customer_data = (
                        payload.get("customer")
                        or payload.get("data", {}).get("customer")
                        or payload
                    )

            if (
                not customer_data
                or not isinstance(customer_data, dict)
                or not customer_data.get("id")
            ):
                return None

            # Extract customer ID
            customer_id = self._extract_shopify_id(customer_data.get("id", ""))
            if not customer_id:
                return None

            # Extract default address
            default_address = customer_data.get("defaultAddress", {})

            # Extract addresses (keep as JSON for complex data)
            addresses = customer_data.get("addresses", {})
            if isinstance(addresses, dict) and "edges" in addresses:
                addresses = [
                    edge.get("node", {}) for edge in addresses.get("edges", [])
                ]

            # Extract metafields (keep as JSON for complex data)
            metafields = customer_data.get("metafields", {})
            if isinstance(metafields, dict) and "edges" in metafields:
                metafields = [
                    edge.get("node", {}) for edge in metafields.get("edges", [])
                ]

            # Process tags - convert string to array if needed
            tags = customer_data.get("tags", [])
            if isinstance(tags, str):
                # Split comma-separated tags and clean them
                tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
            elif not isinstance(tags, list):
                tags = []

            return {
                "shopId": shop_id,
                "customerId": customer_id,
                "email": customer_data.get("email") or "",  # Ensure email is never None
                "firstName": customer_data.get("firstName")
                or "",  # Ensure firstName is never None
                "lastName": customer_data.get("lastName")
                or "",  # Ensure lastName is never None
                "totalSpent": float(customer_data.get("totalSpent", 0)),
                "orderCount": int(customer_data.get("ordersCount", 0)),
                "lastOrderDate": self._parse_datetime(
                    customer_data.get("lastOrderDate")
                ),
                "tags": tags,
                "createdAtShopify": self._parse_datetime(
                    customer_data.get("createdAt")
                ),
                "lastOrderId": customer_data.get("lastOrderId"),
                "location": (
                    {
                        "city": default_address.get("city"),
                        "province": default_address.get("province"),
                        "country": default_address.get("country"),
                        "zip": default_address.get("zip"),
                    }
                    if default_address
                    else None
                ),
                "metafields": metafields,
                "state": customer_data.get("state"),
                "verifiedEmail": customer_data.get("verifiedEmail", False),
                "taxExempt": customer_data.get("taxExempt", False),
                "defaultAddress": default_address,
                "addresses": addresses,
                "currencyCode": customer_data.get("currency") or "USD",
                "customerLocale": customer_data.get("locale"),
            }

        except Exception as e:
            self.logger.error(f"Failed to extract customer fields: {str(e)}")
            return None

    def _extract_collection_fields(
        self, payload: Dict[str, Any], shop_id: str
    ) -> Optional[Dict[str, Any]]:
        """Extract key collection fields from nested JSON payload"""
        try:

            if payload is None:
                return None

            # Handle nested JSON structure: payload.raw_data.collection
            collection_data = None

            if isinstance(payload, dict):

                if "raw_data" in payload and isinstance(payload["raw_data"], dict):
                    raw_data = payload["raw_data"]
                    if raw_data is not None and "collection" in raw_data:
                        collection_data = raw_data["collection"]

                    else:
                        pass  # No collection found in raw_data
                else:
                    pass  # No raw_data found or raw_data is not dict

                # Fallback to direct collection data
                if not collection_data:
                    collection_data = (
                        payload.get("collection")
                        or payload.get("data", {}).get("collection")
                        or payload
                    )

            if (
                not collection_data
                or not isinstance(collection_data, dict)
                or not collection_data.get("id")
            ):
                return None

            # Extract collection ID
            collection_id = self._extract_shopify_id(collection_data.get("id", ""))
            if not collection_id:
                return None

            # Extract image information
            image = collection_data.get("image")
            image_url = image.get("url") if image and isinstance(image, dict) else None
            image_alt = (
                image.get("altText") if image and isinstance(image, dict) else None
            )

            # Extract SEO information
            seo = collection_data.get("seo", {})

            # Extract metafields (keep as JSON for complex data)
            metafields = collection_data.get("metafields", {})
            if isinstance(metafields, dict) and "edges" in metafields:
                metafields = [
                    edge.get("node", {}) for edge in metafields.get("edges", [])
                ]

            # Ensure required fields have proper values
            title = collection_data.get("title", "").strip()
            handle = collection_data.get("handle", "").strip()

            # Skip collections with missing required fields
            if not title or not handle:
                return None

            return {
                "shopId": shop_id,
                "collectionId": collection_id,
                "title": title,
                "handle": handle,
                "description": collection_data.get("description"),
                "sortOrder": collection_data.get("sortOrder"),
                "templateSuffix": collection_data.get("templateSuffix"),
                "seoTitle": seo.get("title"),
                "seoDescription": seo.get("description"),
                "imageUrl": image_url,
                "imageAlt": image_alt,
                "productCount": int(collection_data.get("productsCount", 0)),
                "isAutomated": (
                    collection_data.get("ruleSet", {}).get("rules", []) != []
                    if collection_data.get("ruleSet")
                    and isinstance(collection_data.get("ruleSet"), dict)
                    else False
                ),
                "metafields": metafields,
            }

        except Exception as e:
            self.logger.error(f"Failed to extract collection fields: {str(e)}")
            return None

    def _extract_customer_event_fields(
        self, payload: Dict[str, Any], shop_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Extract key customer event fields from nested JSON payload"""
        try:
            # Handle nested JSON structure: payload.raw_data.customer_event
            customer_data = None

            if isinstance(payload, dict):
                # Try nested structure first: payload.raw_data.customer_event
                if "raw_data" in payload and isinstance(payload["raw_data"], dict):
                    raw_data = payload["raw_data"]
                    if raw_data is not None and "customer_event" in raw_data:
                        customer_data = raw_data["customer_event"]

                # Fallback to direct customer data
                if not customer_data:
                    customer_data = (
                        payload.get("customer")
                        or payload.get("data", {}).get("customer")
                        or payload
                    )

            if (
                not customer_data
                or not isinstance(customer_data, dict)
                or not customer_data.get("id")
            ):
                return None

            # Extract customer ID
            customer_id = self._extract_shopify_id(customer_data.get("id", ""))
            if not customer_id:
                return None

            # For customer events, we create a single event record from the customer data
            # since the payload structure shows this is a customer record, not multiple events
            event_data_list = []

            # Create a customer event record from the customer data
            # Extract the event ID the same way it was stored in the raw table
            event_id = self._extract_customer_event_id_from_payload(payload)

            event_data_list.append(
                {
                    "shopId": shop_id,
                    "customerId": customer_id,
                    "eventId": event_id
                    or customer_id,  # Use extracted event ID or fallback to customer ID
                    "eventType": payload.get("event_type", "CustomerEvent"),
                    "customerEmail": customer_data.get("email"),
                    "customerFirstName": customer_data.get("firstName"),
                    "customerLastName": customer_data.get("lastName"),
                    "customerTags": Json(customer_data.get("tags", [])),
                    "customerState": customer_data.get("state"),
                    "customerOrdersCount": int(customer_data.get("numberOfOrders", 0)),
                    "customerAmountSpent": float(
                        customer_data.get("amountSpent", {}).get("amount", 0)
                    ),
                    "customerCurrency": customer_data.get("amountSpent", {}).get(
                        "currencyCode", "USD"
                    ),
                    "eventTimestamp": self._parse_datetime(
                        customer_data.get("createdAt")
                    ),
                    "rawEventData": Json(customer_data),
                }
            )

            return event_data_list

        except Exception as e:
            self.logger.error(f"Failed to extract customer event fields: {str(e)}")
            return None

    def _extract_customer_event_id_from_payload(
        self, payload: Dict[str, Any]
    ) -> Optional[str]:
        """Extract customer event ID from payload - same logic as data_storage.py"""
        try:
            # Try to get the event ID from the payload
            event_id = None

            # Check if payload has an id field
            if "id" in payload:
                event_id = str(payload["id"])

            # If no direct id, check in nested structures
            if not event_id and "raw_data" in payload:
                raw_data = payload["raw_data"]
                if isinstance(raw_data, dict):
                    # Check for customer_event nested structure
                    if "customer_event" in raw_data:
                        customer_event = raw_data["customer_event"]
                        if isinstance(customer_event, dict) and "id" in customer_event:
                            event_id = str(customer_event["id"])
                    # Check for direct id in raw_data
                    elif "id" in raw_data:
                        event_id = str(raw_data["id"])

            if not event_id:
                return None

            # Extract numeric ID from Shopify GraphQL ID format (gid://shopify/MarketingEvent/123456789)
            if event_id.startswith("gid://shopify/MarketingEvent/"):
                return event_id.split("/")[-1]

            return event_id
        except Exception as e:
            self.logger.warning(
                f"Failed to extract customer event ID from payload: {e}"
            )
            return None

    def _extract_shopify_id(self, gid: str) -> Optional[str]:
        """Extract numeric ID from Shopify GraphQL GID"""
        if not gid:
            return None
        try:
            # Handle GID format: gid://shopify/Order/123456789
            if gid.startswith("gid://shopify/"):
                return gid.split("/")[-1]
            return gid
        except Exception:
            return None

    def _parse_datetime(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string to datetime object"""
        if not date_str:
            return None
        try:
            # Handle ISO format with timezone
            if date_str.endswith("Z"):
                date_str = date_str[:-1] + "+00:00"
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return None

    def _get_product_price(self, variants: List[Dict[str, Any]]) -> float:
        """Get the minimum price from product variants"""
        if not variants:
            return 0.0
        prices = [float(v.get("price", 0)) for v in variants if v.get("price")]
        return min(prices) if prices else 0.0

    def _get_product_compare_price(
        self, variants: List[Dict[str, Any]]
    ) -> Optional[float]:
        """Get the minimum compare at price from product variants"""
        if not variants:
            return None
        compare_prices = [
            float(v.get("compareAtPrice", 0))
            for v in variants
            if v.get("compareAtPrice")
        ]
        return min(compare_prices) if compare_prices else None

    def _get_total_inventory(self, variants: List[Dict[str, Any]]) -> int:
        """Get total inventory across all variants"""
        if not variants:
            return 0
        return sum(int(v.get("inventoryQuantity", 0)) for v in variants)

    async def _batch_upsert_product_data(
        self, product_data_list: List[Dict[str, Any]], db=None
    ) -> None:
        """Batch upsert product data to ProductData table using Prisma"""
        if not product_data_list:
            return

        # If no db connection provided, get one
        if db is None:
            db = await self._get_database()
            await self._batch_upsert_product_data(product_data_list, db)
            return

        # Prepare data for both batch insert and individual upserts
        def prepare_product_data(product_data):
            """Prepare product data for database insertion"""
            data = {
                "shopId": product_data["shopId"],
                "productId": product_data["productId"],
                "title": product_data["title"],
                "handle": product_data["handle"],
                "description": product_data["description"],
                "descriptionHtml": product_data["descriptionHtml"],
                "productType": product_data["productType"],
                "vendor": product_data["vendor"],
                "tags": Json(product_data["tags"]),
                "status": product_data["status"],
                "totalInventory": product_data["totalInventory"],
                "price": product_data["price"],
                "compareAtPrice": product_data["compareAtPrice"],
                "inventory": product_data["inventory"],
                "imageUrl": product_data["imageUrl"],
                "imageAlt": product_data["imageAlt"],
                "productCreatedAt": product_data["productCreatedAt"],
                "productUpdatedAt": product_data["productUpdatedAt"],
                "isActive": product_data["isActive"],
            }

            # Only add optional fields if they have values
            if product_data["variants"]:
                data["variants"] = Json(product_data["variants"])
            if product_data["images"]:
                data["images"] = Json(product_data["images"])
            if product_data["options"]:
                data["options"] = Json(product_data["options"])
            if product_data["collections"]:
                data["collections"] = Json(product_data["collections"])
            if product_data["metafields"]:
                data["metafields"] = Json(product_data["metafields"])

            return data

        # Use Prisma's create_many for batch insert (much faster than individual upserts)
        try:
            # Prepare data for create_many
            create_data = [
                prepare_product_data(product_data) for product_data in product_data_list
            ]

            # Use create_many with skipDuplicates for batch insert
            await db.productdata.create_many(data=create_data, skip_duplicates=True)

        except Exception as e:
            # Fallback to individual upserts if batch insert fails
            self.logger.warning(
                f"Batch insert failed, falling back to individual upserts: {str(e)}"
            )
            for product_data in product_data_list:
                prepared_data = prepare_product_data(product_data)
                await db.productdata.upsert(
                    where={
                        "shopId_productId": {
                            "shopId": product_data["shopId"],
                            "productId": product_data["productId"],
                        }
                    },
                    data=prepared_data,
                )

    async def _batch_upsert_order_data(
        self, order_data_list: List[Dict[str, Any]], db=None
    ) -> None:
        """Batch upsert order data to OrderData table using Prisma"""
        if not order_data_list:
            return

        # If no db connection provided, get one
        if db is None:
            db = await self._get_database()
            await self._batch_upsert_order_data(order_data_list, db)
            return

        # Prepare data for both batch insert and individual upserts
        def prepare_order_data(order_data):
            """Prepare order data for database insertion"""
            return {
                "shopId": order_data["shopId"],
                "orderId": order_data["orderId"],
                "orderName": order_data.get("orderName"),
                "customerId": order_data.get("customerId"),
                "customerEmail": order_data.get("customerEmail"),
                "customerPhone": order_data.get("customerPhone"),
                "totalAmount": order_data["totalAmount"],
                "subtotalAmount": order_data.get("subtotalAmount"),
                "totalTaxAmount": order_data.get("totalTaxAmount"),
                "totalShippingAmount": order_data.get("totalShippingAmount"),
                "totalRefundedAmount": order_data.get("totalRefundedAmount"),
                "totalOutstandingAmount": order_data.get("totalOutstandingAmount"),
                "orderDate": order_data["orderDate"],
                "processedAt": order_data.get("processedAt"),
                "cancelledAt": order_data.get("cancelledAt"),
                "cancelReason": order_data.get("cancelReason"),
                "orderStatus": order_data.get("orderStatus"),
                "orderLocale": order_data.get("orderLocale"),
                "currencyCode": order_data.get("currencyCode"),
                "presentmentCurrencyCode": order_data.get("presentmentCurrencyCode"),
                "confirmed": order_data.get("confirmed", False),
                "test": order_data.get("test", False),
                "tags": Json(order_data.get("tags", [])),
                "note": order_data.get("note"),
                "lineItems": Json(order_data.get("lineItems", [])),
                "shippingAddress": (
                    Json(order_data.get("shippingAddress"))
                    if order_data.get("shippingAddress")
                    else Json({})
                ),
                "billingAddress": (
                    Json(order_data.get("billingAddress"))
                    if order_data.get("billingAddress")
                    else Json({})
                ),
                "discountApplications": Json(
                    order_data.get("discountApplications", [])
                ),
                "metafields": Json(order_data.get("metafields", [])),
            }

        # Use Prisma's create_many for batch insert (much faster than individual upserts)
        try:
            # Prepare data for create_many
            create_data = [
                prepare_order_data(order_data) for order_data in order_data_list
            ]

            # Use create_many with skipDuplicates for batch insert
            await db.orderdata.create_many(data=create_data, skip_duplicates=True)

        except Exception as e:
            # Fallback to individual upserts if batch insert fails
            self.logger.warning(
                f"Batch insert failed, falling back to individual upserts: {str(e)}"
            )
            for order_data in order_data_list:
                prepared_data = prepare_order_data(order_data)
                await db.orderdata.upsert(
                    where={
                        "shopId_orderId": {
                            "shopId": order_data["shopId"],
                            "orderId": order_data["orderId"],
                        }
                    },
                    data=prepared_data,
                )

    async def _batch_upsert_customer_data(
        self, customer_data_list: List[Dict[str, Any]], db=None
    ) -> None:
        """Batch upsert customer data to CustomerData table using Prisma"""
        if not customer_data_list:
            return

        # If no db connection provided, get one
        if db is None:
            db = await self._get_database()
            await self._batch_upsert_customer_data(customer_data_list, db)
            return

        # Prepare data for both batch insert and individual upserts
        def prepare_customer_data(customer_data):
            """Prepare customer data for database insertion"""
            data = {
                "shopId": customer_data["shopId"],
                "customerId": customer_data["customerId"],
                "email": customer_data["email"],
                "firstName": customer_data["firstName"],
                "lastName": customer_data["lastName"],
                "totalSpent": customer_data["totalSpent"],
                "orderCount": customer_data["orderCount"],
                "lastOrderDate": customer_data["lastOrderDate"],
                "tags": Json(customer_data["tags"]),
                "createdAtShopify": customer_data["createdAtShopify"],
                "lastOrderId": customer_data["lastOrderId"],
                "state": customer_data["state"],
                "verifiedEmail": customer_data["verifiedEmail"],
                "taxExempt": customer_data["taxExempt"],
                "currencyCode": customer_data["currencyCode"],
                "customerLocale": customer_data["customerLocale"],
            }

            # Only add optional fields if they have values
            if customer_data["location"]:
                data["location"] = Json(customer_data["location"])
            if customer_data["metafields"]:
                data["metafields"] = Json(customer_data["metafields"])
            if customer_data["defaultAddress"]:
                data["defaultAddress"] = Json(customer_data["defaultAddress"])
            if customer_data["addresses"]:
                data["addresses"] = Json(customer_data["addresses"])

            return data

        # Use Prisma's create_many for batch insert (much faster than individual upserts)
        try:
            # Prepare data for create_many
            create_data = [
                prepare_customer_data(customer_data)
                for customer_data in customer_data_list
            ]

            # Use create_many with skipDuplicates for batch insert
            await db.customerdata.create_many(data=create_data, skip_duplicates=True)

        except Exception as e:
            # Fallback to individual upserts if batch insert fails
            self.logger.warning(
                f"Batch insert failed, falling back to individual upserts: {str(e)}"
            )
            for customer_data in customer_data_list:
                prepared_data = prepare_customer_data(customer_data)
                await db.customerdata.upsert(
                    where={
                        "shopId_customerId": {
                            "shopId": customer_data["shopId"],
                            "customerId": customer_data["customerId"],
                        }
                    },
                    data=prepared_data,
                )

    async def _batch_upsert_collection_data(
        self, collection_data_list: List[Dict[str, Any]], db=None
    ) -> None:
        """Batch upsert collection data to CollectionData table using Prisma"""
        if not collection_data_list:
            return

        # If no db connection provided, get one
        if db is None:
            db = await self._get_database()
            await self._batch_upsert_collection_data(collection_data_list, db)
            return

        # Prepare data for both batch insert and individual upserts
        def prepare_collection_data(collection_data):
            """Prepare collection data for database insertion"""
            return {
                "shopId": collection_data["shopId"],
                "collectionId": collection_data["collectionId"],
                "title": collection_data["title"],
                "handle": collection_data["handle"],
                "description": collection_data["description"],
                "sortOrder": collection_data["sortOrder"],
                "templateSuffix": collection_data["templateSuffix"],
                "seoTitle": collection_data["seoTitle"],
                "seoDescription": collection_data["seoDescription"],
                "imageUrl": collection_data["imageUrl"],
                "imageAlt": collection_data["imageAlt"],
                "productCount": collection_data["productCount"],
                "isAutomated": collection_data["isAutomated"],
                "metafields": (
                    Json(collection_data["metafields"])
                    if collection_data["metafields"]
                    else Json({})
                ),
            }

        # Use Prisma's create_many for batch insert (much faster than individual upserts)
        try:
            # Prepare data for create_many
            create_data = [
                prepare_collection_data(collection_data)
                for collection_data in collection_data_list
            ]

            # Use create_many with skipDuplicates for batch insert
            await db.collectiondata.create_many(data=create_data, skip_duplicates=True)

        except Exception as e:
            # Fallback to individual upserts if batch insert fails
            self.logger.warning(
                f"Batch insert failed, falling back to individual upserts: {str(e)}"
            )
            for collection_data in collection_data_list:
                prepared_data = prepare_collection_data(collection_data)
                await db.collectiondata.upsert(
                    where={
                        "shopId_collectionId": {
                            "shopId": collection_data["shopId"],
                            "collectionId": collection_data["collectionId"],
                        }
                    },
                    data=prepared_data,
                )

    async def _batch_upsert_customer_event_data(
        self, event_data_list: List[Dict[str, Any]], db=None
    ) -> None:
        """Batch upsert customer event data to CustomerEventData table using Prisma"""
        if not event_data_list:
            return

        # If no db connection provided, get one
        if db is None:
            db = await self._get_database()
            await self._batch_upsert_customer_event_data(event_data_list, db)
            return

        # Prepare data for both batch insert and individual upserts
        def prepare_customer_event_data(event_data):
            """Prepare customer event data for database insertion"""
            return {
                "shopId": event_data["shopId"],
                "customerId": event_data["customerId"],
                "eventId": event_data["eventId"],
                "eventType": event_data["eventType"],
                "customerEmail": event_data["customerEmail"],
                "customerFirstName": event_data["customerFirstName"],
                "customerLastName": event_data["customerLastName"],
                "customerTags": Json(event_data["customerTags"]),
                "customerState": event_data["customerState"],
                "customerOrdersCount": event_data["customerOrdersCount"],
                "customerAmountSpent": event_data["customerAmountSpent"],
                "customerCurrency": event_data["customerCurrency"],
                "eventTimestamp": event_data["eventTimestamp"],
                "rawEventData": (
                    Json(event_data["rawEventData"])
                    if event_data["rawEventData"]
                    else None
                ),
            }

        # Use Prisma's create_many for batch insert (much faster than individual upserts)
        try:
            # Prepare data for create_many
            create_data = [
                prepare_customer_event_data(event_data)
                for event_data in event_data_list
            ]

            # Use create_many with skipDuplicates for batch insert
            await db.customereventdata.create_many(
                data=create_data, skip_duplicates=True
            )

        except Exception as e:
            # Fallback to individual upserts if batch insert fails
            self.logger.warning(
                f"Batch insert failed, falling back to individual upserts: {str(e)}"
            )
            for event_data in event_data_list:
                prepared_data = prepare_customer_event_data(event_data)
                await db.customereventdata.upsert(
                    where={
                        "shopId_eventId": {
                            "shopId": event_data["shopId"],
                            "eventId": event_data["eventId"],
                        }
                    },
                    data=prepared_data,
                )

    async def _publish_feature_computation_event(
        self, shop_id: str, processed_count: int, duration_ms: int
    ) -> None:
        """Publish event to trigger feature computation after successful main table storage"""
        try:
            # Generate a unique job ID for this feature computation
            job_id = f"feature_compute_{shop_id}_{now_utc().timestamp()}"

            # Prepare event metadata
            metadata = {
                "processed_count": processed_count,
                "storage_duration_ms": duration_ms,
                "trigger_source": "main_table_storage",
                "timestamp": now_utc().isoformat(),
            }

            # Publish the event
            event_id = await streams_manager.publish_features_computed_event(
                job_id=job_id,
                shop_id=shop_id,
                features_ready=False,  # Features need to be computed
                metadata=metadata,
            )

            self.logger.info(
                f"Published feature computation event",
                shop_id=shop_id,
                job_id=job_id,
                event_id=event_id,
                processed_count=processed_count,
            )

        except Exception as e:
            # Don't fail the main storage operation if event publishing fails
            self.logger.error(
                f"Failed to publish feature computation event for shop {shop_id}: {str(e)}"
            )
