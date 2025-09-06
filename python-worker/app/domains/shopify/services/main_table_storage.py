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


def _parse_datetime_global(date_value: Any) -> Optional[datetime]:
    """Parse various date formats to datetime object"""
    if date_value is None:
        return None

    if isinstance(date_value, datetime):
        return date_value

    if isinstance(date_value, str):
        try:
            # Handle ISO format with Z suffix
            if date_value.endswith("Z"):
                date_value = date_value.replace("Z", "+00:00")
            return datetime.fromisoformat(date_value)
        except (ValueError, TypeError):
            logger.warning(f"Failed to parse datetime: {date_value}")
            return None

    return None


def _parse_boolean(bool_value: Any) -> bool:
    """Parse various boolean representations to bool"""
    if bool_value is None:
        return False

    if isinstance(bool_value, bool):
        return bool_value

    if isinstance(bool_value, str):
        return bool_value.lower() in ("true", "1", "yes", "on")

    if isinstance(bool_value, (int, float)):
        return bool(bool_value)

    return False


def clean_product_data_for_storage(product_data: Dict[str, Any]) -> Dict[str, Any]:
    """Clean and fix product data before storing in main tables"""
    try:
        # Fix missing product_type
        if not product_data.get("productType"):
            product_data["productType"] = "Unknown"

        # Fix invalid status values - map to ENUM values
        status = product_data.get("status", "").lower()
        if status == "active":
            product_data["status"] = "active"
        elif status == "archived":
            product_data["status"] = "archived"
        elif status == "draft":
            product_data["status"] = "draft"
        else:
            product_data["status"] = "draft"  # Default to draft for unknown status

        # Fix missing images
        if product_data.get("images") is None:
            product_data["images"] = []

        # Fix missing metafields
        if product_data.get("metafields") is None:
            product_data["metafields"] = []

        # Convert numeric fields to proper types (only if not already converted)
        # Convert main product price fields
        if product_data.get("price") is not None and not isinstance(
            product_data["price"], (int, float)
        ):
            try:
                product_data["price"] = float(product_data["price"])
            except (ValueError, TypeError):
                product_data["price"] = 0.0

        if product_data.get("compareAtPrice") is not None and not isinstance(
            product_data["compareAtPrice"], (int, float)
        ):
            try:
                product_data["compareAtPrice"] = float(product_data["compareAtPrice"])
            except (ValueError, TypeError):
                product_data["compareAtPrice"] = None

        if product_data.get("totalInventory") is not None and not isinstance(
            product_data["totalInventory"], int
        ):
            try:
                product_data["totalInventory"] = int(product_data["totalInventory"])
            except (ValueError, TypeError):
                product_data["totalInventory"] = 0

        # Convert date fields to proper types
        if product_data.get("productCreatedAt") is not None:
            product_data["productCreatedAt"] = _parse_datetime_global(
                product_data["productCreatedAt"]
            )

        if product_data.get("productUpdatedAt") is not None:
            product_data["productUpdatedAt"] = _parse_datetime_global(
                product_data["productUpdatedAt"]
            )

        # Convert boolean fields
        if "isActive" in product_data:
            product_data["isActive"] = _parse_boolean(product_data["isActive"])

        # Fix variants - ensure each variant has product_id and convert numeric fields
        variants = product_data.get("variants", [])
        for variant in variants:
            if not variant.get("product_id") and product_data.get("productId"):
                variant["product_id"] = product_data["productId"]

            # Convert variant numeric fields (only if not already converted)
            if variant.get("price") is not None and not isinstance(
                variant["price"], (int, float)
            ):
                try:
                    variant["price"] = float(variant["price"])
                except (ValueError, TypeError):
                    variant["price"] = 0.0

            if variant.get("compareAtPrice") is not None and not isinstance(
                variant["compareAtPrice"], (int, float)
            ):
                try:
                    variant["compareAtPrice"] = float(variant["compareAtPrice"])
                except (ValueError, TypeError):
                    variant["compareAtPrice"] = None

            if variant.get("inventoryQuantity") is not None and not isinstance(
                variant["inventoryQuantity"], int
            ):
                try:
                    variant["inventoryQuantity"] = int(variant["inventoryQuantity"])
                except (ValueError, TypeError):
                    variant["inventoryQuantity"] = 0

            if variant.get("weight") is not None and not isinstance(
                variant["weight"], (int, float)
            ):
                try:
                    variant["weight"] = float(variant["weight"])
                except (ValueError, TypeError):
                    variant["weight"] = None

        return product_data
    except Exception as e:
        logger.warning(f"Failed to clean product data: {str(e)}")
        # Return the original data if cleaning fails to prevent storage failures
        return product_data


def clean_customer_data_for_storage(customer_data: Dict[str, Any]) -> Dict[str, Any]:
    """Clean and fix customer data before storing in main tables"""
    try:
        # Fix missing addresses - ensure it's an empty list if None
        if customer_data.get("addresses") is None:
            customer_data["addresses"] = []

        # Convert numeric fields to proper types (only if not already converted)
        if customer_data.get("totalSpent") is not None and not isinstance(
            customer_data["totalSpent"], (int, float)
        ):
            try:
                customer_data["totalSpent"] = float(customer_data["totalSpent"])
            except (ValueError, TypeError):
                customer_data["totalSpent"] = 0.0

        if customer_data.get("orderCount") is not None and not isinstance(
            customer_data["orderCount"], int
        ):
            try:
                customer_data["orderCount"] = int(customer_data["orderCount"])
            except (ValueError, TypeError):
                customer_data["orderCount"] = 0

        # Convert date fields to proper types
        if customer_data.get("lastOrderDate") is not None:
            customer_data["lastOrderDate"] = _parse_datetime_global(
                customer_data["lastOrderDate"]
            )

        if customer_data.get("createdAt") is not None:
            customer_data["createdAt"] = _parse_datetime_global(
                customer_data["createdAt"]
            )

        # Convert boolean fields
        if "verifiedEmail" in customer_data:
            customer_data["verifiedEmail"] = _parse_boolean(
                customer_data["verifiedEmail"]
            )

        if "taxExempt" in customer_data:
            customer_data["taxExempt"] = _parse_boolean(customer_data["taxExempt"])

        # Process tags - convert string to array if needed
        tags = customer_data.get("tags", [])
        if isinstance(tags, str):
            # Split comma-separated tags and clean them
            tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
        elif not isinstance(tags, list):
            tags = []
        customer_data["tags"] = tags

        return customer_data
    except Exception as e:
        logger.warning(f"Failed to clean customer data: {str(e)}")
        # Return the original data if cleaning fails to prevent storage failures
        return customer_data


def clean_collection_data_for_storage(
    collection_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Clean and fix collection data before storing in main tables"""
    try:
        # Fix missing body_html
        if not collection_data.get("bodyHtml"):
            collection_data["bodyHtml"] = ""

        # Fix isAutomated boolean type
        if "isAutomated" in collection_data:
            collection_data["isAutomated"] = _parse_boolean(
                collection_data["isAutomated"]
            )

        # Fix sortOrder - map to ENUM values
        sort_order = collection_data.get("sortOrder", "").lower()
        if sort_order == "manual":
            collection_data["sortOrder"] = "manual"
        elif sort_order == "best_selling":
            collection_data["sortOrder"] = "best_selling"
        elif sort_order == "created":
            collection_data["sortOrder"] = "created"
        elif sort_order == "created_desc":
            collection_data["sortOrder"] = "created_desc"
        elif sort_order == "id":
            collection_data["sortOrder"] = "id"
        elif sort_order == "id_desc":
            collection_data["sortOrder"] = "id_desc"
        elif sort_order == "price":
            collection_data["sortOrder"] = "price"
        elif sort_order == "price_desc":
            collection_data["sortOrder"] = "price_desc"
        elif sort_order == "title":
            collection_data["sortOrder"] = "title"
        elif sort_order == "title_desc":
            collection_data["sortOrder"] = "title_desc"
        elif sort_order == "updated_at":
            collection_data["sortOrder"] = "updated_at"
        elif sort_order == "updated_at_desc":
            collection_data["sortOrder"] = "updated_at_desc"
        else:
            collection_data["sortOrder"] = "manual"  # Default to manual

        # Convert date fields to proper types
        if collection_data.get("createdAt") is not None:
            collection_data["createdAt"] = _parse_datetime_global(
                collection_data["createdAt"]
            )

        if collection_data.get("updatedAt") is not None:
            collection_data["updatedAt"] = _parse_datetime_global(
                collection_data["updatedAt"]
            )

        # Process tags - convert string to array if needed
        tags = collection_data.get("tags", [])
        if isinstance(tags, str):
            # Split comma-separated tags and clean them
            tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
        elif not isinstance(tags, list):
            tags = []
        collection_data["tags"] = tags

        return collection_data
    except Exception as e:
        logger.warning(f"Failed to clean collection data: {str(e)}")
        # Return the original data if cleaning fails to prevent storage failures
        return collection_data


def clean_order_data_for_storage(order_data: Dict[str, Any]) -> Dict[str, Any]:
    """Clean and fix order data before storing in main tables"""
    try:
        # Fix orderStatus - map to ENUM values
        order_status = order_data.get("orderStatus", "").lower()
        if order_status == "pending":
            order_data["orderStatus"] = "pending"
        elif order_status == "confirmed":
            order_data["orderStatus"] = "confirmed"
        elif order_status == "paid":
            order_data["orderStatus"] = "paid"
        elif order_status == "partially_paid":
            order_data["orderStatus"] = "partially_paid"
        elif order_status == "partially_refunded":
            order_data["orderStatus"] = "partially_refunded"
        elif order_status == "refunded":
            order_data["orderStatus"] = "refunded"
        elif order_status == "voided":
            order_data["orderStatus"] = "voided"
        elif order_status == "cancelled":
            order_data["orderStatus"] = "cancelled"
        else:
            order_data["orderStatus"] = "pending"  # Default to pending

        # Convert numeric fields to proper types
        numeric_fields = [
            "totalAmount",
            "subtotalAmount",
            "totalTaxAmount",
            "totalShippingAmount",
            "totalRefundedAmount",
            "totalOutstandingAmount",
        ]

        for field in numeric_fields:
            if order_data.get(field) is not None and not isinstance(
                order_data[field], (int, float)
            ):
                try:
                    order_data[field] = float(order_data[field])
                except (ValueError, TypeError):
                    order_data[field] = 0.0

        # Convert date fields to proper types
        if order_data.get("orderDate") is not None:
            order_data["orderDate"] = _parse_datetime_global(order_data["orderDate"])

        if order_data.get("processedAt") is not None:
            order_data["processedAt"] = _parse_datetime_global(
                order_data["processedAt"]
            )

        if order_data.get("cancelledAt") is not None:
            order_data["cancelledAt"] = _parse_datetime_global(
                order_data["cancelledAt"]
            )

        # Convert boolean fields
        if "confirmed" in order_data:
            order_data["confirmed"] = _parse_boolean(order_data["confirmed"])

        if "test" in order_data:
            order_data["test"] = _parse_boolean(order_data["test"])

        # Clean line items if they exist
        if order_data.get("lineItems"):
            for line_item in order_data["lineItems"]:
                if line_item.get("quantity") is not None and not isinstance(
                    line_item["quantity"], int
                ):
                    try:
                        line_item["quantity"] = int(line_item["quantity"])
                    except (ValueError, TypeError):
                        line_item["quantity"] = 0

                if line_item.get("price") is not None and not isinstance(
                    line_item["price"], (int, float)
                ):
                    try:
                        line_item["price"] = float(line_item["price"])
                    except (ValueError, TypeError):
                        line_item["price"] = 0.0

        return order_data
    except Exception as e:
        logger.warning(f"Failed to clean order data: {str(e)}")
        # Return the original data if cleaning fails to prevent storage failures
        return order_data


@dataclass
class StorageResult:
    """Result of main table storage operation"""

    success: bool
    processed_count: int
    error_count: int
    errors: List[str]
    duration_ms: int


# Configuration for different data types
DATA_TYPE_CONFIG = {
    "orders": {
        "raw_table": "RawOrder",
        "main_table": "OrderData",
        "id_field": "orderId",
        "raw_id_field": "shopifyId",
        "clean_function": clean_order_data_for_storage,
        "batch_size": 1000,
    },
    "products": {
        "raw_table": "RawProduct",
        "main_table": "ProductData",
        "id_field": "productId",
        "raw_id_field": "shopifyId",
        "clean_function": clean_product_data_for_storage,
        "batch_size": 1000,
    },
    "customers": {
        "raw_table": "RawCustomer",
        "main_table": "CustomerData",
        "id_field": "customerId",
        "raw_id_field": "shopifyId",
        "clean_function": clean_customer_data_for_storage,
        "batch_size": 1000,
    },
    "collections": {
        "raw_table": "RawCollection",
        "main_table": "CollectionData",
        "id_field": "collectionId",
        "raw_id_field": "shopifyId",
        "clean_function": clean_collection_data_for_storage,
        "batch_size": 1000,
    },
}


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
                return_exceptions=True,  # Don't fail if one operation fails
            )

            # Process results from concurrent operations
            data_types = [
                "orders",
                "products",
                "customers",
                "collections",
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
            import traceback

            error_msg = f"Failed to store orders: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(f"Orders storage error details: {type(e).__name__}")
            self.logger.error(f"Orders storage traceback: {traceback.format_exc()}")
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
            import traceback

            error_msg = f"Failed to store products: {str(e)}"
            self.logger.error(error_msg)
            self.logger.error(f"Products storage error details: {type(e).__name__}")
            self.logger.error(f"Products storage traceback: {traceback.format_exc()}")
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
                "createdAt": self._parse_datetime(customer_data.get("createdAt")),
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
                "createdAt": collection_data.get("createdAt"),
                "updatedAt": collection_data.get("updatedAt"),
                "metafields": metafields,
            }

        except Exception as e:
            self.logger.error(f"Failed to extract collection fields: {str(e)}")
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
            # Clean the data before processing
            cleaned_data = clean_product_data_for_storage(product_data)

            # Validate required fields
            if not cleaned_data.get("shopId") or not cleaned_data.get("productId"):
                raise ValueError(
                    f"Missing required fields: shopId={cleaned_data.get('shopId')}, productId={cleaned_data.get('productId')}"
                )
            data = {
                "shopId": cleaned_data["shopId"],
                "productId": cleaned_data["productId"],
                "title": cleaned_data["title"],
                "handle": cleaned_data["handle"],
                "description": cleaned_data["description"],
                "descriptionHtml": cleaned_data["descriptionHtml"],
                "productType": cleaned_data["productType"],
                "vendor": cleaned_data["vendor"],
                "tags": Json(cleaned_data["tags"]),
                "status": cleaned_data["status"],
                "totalInventory": cleaned_data["totalInventory"],
                "price": cleaned_data["price"],
                "compareAtPrice": cleaned_data["compareAtPrice"],
                "inventory": cleaned_data["inventory"],
                "imageUrl": cleaned_data["imageUrl"],
                "imageAlt": cleaned_data["imageAlt"],
                "productCreatedAt": cleaned_data["productCreatedAt"],
                "productUpdatedAt": cleaned_data["productUpdatedAt"],
                "isActive": cleaned_data["isActive"],
            }

            # Only add optional fields if they have values
            if cleaned_data["variants"]:
                data["variants"] = Json(cleaned_data["variants"])
            if cleaned_data["images"]:
                data["images"] = Json(cleaned_data["images"])
            if cleaned_data["options"]:
                data["options"] = Json(cleaned_data["options"])
            if cleaned_data["collections"]:
                data["collections"] = Json(cleaned_data["collections"])
            if cleaned_data["metafields"]:
                data["metafields"] = Json(cleaned_data["metafields"])

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
            import traceback

            self.logger.warning(
                f"Product batch insert failed, falling back to individual upserts: {str(e)}"
            )
            self.logger.warning(
                f"Product batch insert error details: {type(e).__name__}"
            )
            self.logger.warning(
                f"Product batch insert traceback: {traceback.format_exc()}"
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
            # Clean the data first
            cleaned_data = clean_order_data_for_storage(order_data)

            # Validate required fields
            if not cleaned_data.get("shopId") or not cleaned_data.get("orderId"):
                raise ValueError(
                    f"Missing required fields: shopId={cleaned_data.get('shopId')}, orderId={cleaned_data.get('orderId')}"
                )
            return {
                "shopId": cleaned_data["shopId"],
                "orderId": cleaned_data["orderId"],
                "orderName": cleaned_data.get("orderName"),
                "customerId": cleaned_data.get("customerId"),
                "customerEmail": cleaned_data.get("customerEmail"),
                "customerPhone": cleaned_data.get("customerPhone"),
                "totalAmount": cleaned_data["totalAmount"],
                "subtotalAmount": cleaned_data.get("subtotalAmount"),
                "totalTaxAmount": cleaned_data.get("totalTaxAmount"),
                "totalShippingAmount": cleaned_data.get("totalShippingAmount"),
                "totalRefundedAmount": cleaned_data.get("totalRefundedAmount"),
                "totalOutstandingAmount": cleaned_data.get("totalOutstandingAmount"),
                "orderDate": cleaned_data["orderDate"],
                "processedAt": cleaned_data.get("processedAt"),
                "cancelledAt": cleaned_data.get("cancelledAt"),
                "cancelReason": cleaned_data.get("cancelReason"),
                "orderStatus": cleaned_data.get("orderStatus"),
                "orderLocale": cleaned_data.get("orderLocale"),
                "currencyCode": cleaned_data.get("currencyCode"),
                "presentmentCurrencyCode": cleaned_data.get("presentmentCurrencyCode"),
                "confirmed": cleaned_data.get("confirmed", False),
                "test": cleaned_data.get("test", False),
                "tags": Json(cleaned_data.get("tags", [])),
                "note": cleaned_data.get("note"),
                "lineItems": Json(cleaned_data.get("lineItems", [])),
                "shippingAddress": (
                    Json(cleaned_data.get("shippingAddress"))
                    if cleaned_data.get("shippingAddress")
                    else Json({})
                ),
                "billingAddress": (
                    Json(cleaned_data.get("billingAddress"))
                    if cleaned_data.get("billingAddress")
                    else Json({})
                ),
                "discountApplications": Json(
                    cleaned_data.get("discountApplications", [])
                ),
                "metafields": Json(cleaned_data.get("metafields", [])),
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
            import traceback

            self.logger.warning(
                f"Order batch insert failed, falling back to individual upserts: {str(e)}"
            )
            self.logger.warning(f"Order batch insert error details: {type(e).__name__}")
            self.logger.warning(
                f"Order batch insert traceback: {traceback.format_exc()}"
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
            # Clean the data before processing
            cleaned_data = clean_customer_data_for_storage(customer_data)
            data = {
                "shopId": cleaned_data["shopId"],
                "customerId": cleaned_data["customerId"],
                "email": cleaned_data["email"],
                "firstName": cleaned_data["firstName"],
                "lastName": cleaned_data["lastName"],
                "totalSpent": cleaned_data["totalSpent"],
                "orderCount": cleaned_data["orderCount"],
                "lastOrderDate": cleaned_data["lastOrderDate"],
                "tags": Json(cleaned_data["tags"]),
                "createdAtShopify": cleaned_data["createdAt"],
                "lastOrderId": cleaned_data["lastOrderId"],
                "state": cleaned_data["state"],
                "verifiedEmail": cleaned_data["verifiedEmail"],
                "taxExempt": cleaned_data["taxExempt"],
                "currencyCode": cleaned_data["currencyCode"],
                "customerLocale": cleaned_data["customerLocale"],
            }

            # Only add optional fields if they have values
            if cleaned_data["location"]:
                data["location"] = Json(cleaned_data["location"])
            if cleaned_data["metafields"]:
                data["metafields"] = Json(cleaned_data["metafields"])
            if cleaned_data["defaultAddress"]:
                data["defaultAddress"] = Json(cleaned_data["defaultAddress"])
            if cleaned_data["addresses"]:
                data["addresses"] = Json(cleaned_data["addresses"])

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
            # Clean the data before processing
            cleaned_data = clean_collection_data_for_storage(collection_data)
            return {
                "shopId": cleaned_data["shopId"],
                "collectionId": cleaned_data["collectionId"],
                "title": cleaned_data["title"],
                "handle": cleaned_data["handle"],
                "description": cleaned_data["description"],
                "sortOrder": cleaned_data["sortOrder"],
                "templateSuffix": cleaned_data["templateSuffix"],
                "seoTitle": cleaned_data["seoTitle"],
                "seoDescription": cleaned_data["seoDescription"],
                "imageUrl": cleaned_data["imageUrl"],
                "imageAlt": cleaned_data["imageAlt"],
                "productCount": cleaned_data["productCount"],
                "isAutomated": cleaned_data["isAutomated"],
                "metafields": (
                    Json(cleaned_data["metafields"])
                    if cleaned_data["metafields"]
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
                cleaned_data = clean_collection_data_for_storage(collection_data)
                await db.collectiondata.upsert(
                    where={
                        "shopId_collectionId": {
                            "shopId": cleaned_data["shopId"],
                            "collectionId": cleaned_data["collectionId"],
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
