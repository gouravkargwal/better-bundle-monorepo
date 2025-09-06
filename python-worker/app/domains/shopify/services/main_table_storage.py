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
from app.domains.shopify.services.field_extractor import FieldExtractorService
from app.domains.shopify.services.data_cleaning_service import DataCleaningService

logger = get_logger(__name__)


@dataclass
class StorageResult:
    """Result of main table storage operation"""

    success: bool
    processed_count: int
    error_count: int
    errors: List[str]
    duration_ms: int


# Field mapping configuration for database conversion
FIELD_MAPPINGS = {
    "orders": {
        "required_fields": ["shopId", "orderId", "totalAmount", "orderDate"],
        "json_fields": [
            "tags",
            "lineItems",
            "shippingAddress",
            "billingAddress",
            "discountApplications",
            "metafields",
        ],
        "optional_fields": [
            "orderName",
            "customerId",
            "customerEmail",
            "customerPhone",
            "subtotalAmount",
            "totalTaxAmount",
            "totalShippingAmount",
            "totalRefundedAmount",
            "totalOutstandingAmount",
            "processedAt",
            "cancelledAt",
            "cancelReason",
            "orderStatus",
            "orderLocale",
            "currencyCode",
            "presentmentCurrencyCode",
            "confirmed",
            "test",
            "note",
        ],
        "where_clause": "shopId_orderId",
    },
    "products": {
        "required_fields": ["shopId", "productId", "title", "handle", "price"],
        "json_fields": [
            "tags",
            "variants",
            "images",
            "options",
            "collections",
            "metafields",
        ],
        "optional_fields": [
            "description",
            "descriptionHtml",
            "productType",
            "vendor",
            "status",
            "totalInventory",
            "compareAtPrice",
            "inventory",
            "imageUrl",
            "imageAlt",
            "productCreatedAt",
            "productUpdatedAt",
            "isActive",
        ],
        "where_clause": "shopId_productId",
    },
    "customers": {
        "required_fields": [
            "shopId",
            "customerId",
            "email",
            "firstName",
            "lastName",
            "totalSpent",
            "orderCount",
        ],
        "json_fields": [
            "tags",
            "location",
            "metafields",
            "defaultAddress",
            "addresses",
        ],
        "optional_fields": [
            "lastOrderDate",
            "createdAtShopify",
            "lastOrderId",
            "state",
            "verifiedEmail",
            "taxExempt",
            "currencyCode",
            "customerLocale",
        ],
        "where_clause": "shopId_customerId",
    },
    "collections": {
        "required_fields": ["shopId", "collectionId", "title", "handle"],
        "json_fields": ["metafields"],
        "optional_fields": [
            "description",
            "sortOrder",
            "templateSuffix",
            "seoTitle",
            "seoDescription",
            "imageUrl",
            "imageAlt",
            "productCount",
            "isAutomated",
        ],
        "where_clause": "shopId_collectionId",
    },
}

# Configuration for different data types
DATA_TYPE_CONFIG = {
    "orders": {
        "raw_table": "RawOrder",
        "main_table": "OrderData",
        "id_field": "orderId",
        "raw_id_field": "shopifyId",
        "clean_function": None,  # Now handled by DataCleaningService
        "batch_size": 1000,
        "field_mapping": FIELD_MAPPINGS["orders"],
    },
    "products": {
        "raw_table": "RawProduct",
        "main_table": "ProductData",
        "id_field": "productId",
        "raw_id_field": "shopifyId",
        "clean_function": None,  # Now handled by DataCleaningService
        "batch_size": 1000,
        "field_mapping": FIELD_MAPPINGS["products"],
    },
    "customers": {
        "raw_table": "RawCustomer",
        "main_table": "CustomerData",
        "id_field": "customerId",
        "raw_id_field": "shopifyId",
        "clean_function": None,  # Now handled by DataCleaningService
        "batch_size": 1000,
        "field_mapping": FIELD_MAPPINGS["customers"],
    },
    "collections": {
        "raw_table": "RawCollection",
        "main_table": "CollectionData",
        "id_field": "collectionId",
        "raw_id_field": "shopifyId",
        "clean_function": None,  # Now handled by DataCleaningService
        "batch_size": 1000,
        "field_mapping": FIELD_MAPPINGS["collections"],
    },
}


class MainTableStorageService:
    """Service for storing structured data in main tables"""

    def __init__(self):
        self.logger = logger
        self._db_client = None
        self.field_extractor = FieldExtractorService()
        self.data_cleaner = DataCleaningService()

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

    async def _store_data_generic(
        self, data_type: str, shop_id: str, incremental: bool = True
    ) -> StorageResult:
        """Generic method to store any data type from raw to main tables"""
        start_time = now_utc()
        processed_count = 0
        error_count = 0
        errors = []

        try:
            config = DATA_TYPE_CONFIG[data_type]
            db = await self._get_database()

            # Get all raw IDs using efficient raw SQL query
            raw_result = await db.query_raw(
                f'SELECT "{config["raw_id_field"]}" FROM "{config["raw_table"]}" WHERE "shopId" = $1 AND "{config["raw_id_field"]}" IS NOT NULL ORDER BY "extractedAt" ASC',
                shop_id,
            )
            raw_ids = [row[config["raw_id_field"]] for row in raw_result]

            total_raw_count = len(raw_ids)
            self.logger.info(
                f"Found {total_raw_count} raw {data_type} for shop {shop_id}"
            )

            if total_raw_count == 0:
                self.logger.info(f"No raw {data_type} found for shop {shop_id}")
                return StorageResult(
                    success=True,
                    processed_count=0,
                    error_count=0,
                    errors=[],
                    duration_ms=int((now_utc() - start_time).total_seconds() * 1000),
                )

            # Get already processed IDs if incremental
            processed_ids = set()
            if incremental:
                processed_ids = await self._get_processed_shopify_ids(
                    shop_id, data_type
                )
                self.logger.info(
                    f"Found {len(processed_ids)} already processed {data_type}"
                )

            # Filter to only new/updated items
            new_ids = [id for id in raw_ids if id not in processed_ids]
            self.logger.info(f"Processing {len(new_ids)} new/updated {data_type}")

            if not new_ids:
                self.logger.info(f"No new {data_type} to process")
                return StorageResult(
                    success=True,
                    processed_count=0,
                    error_count=0,
                    errors=[],
                    duration_ms=int((now_utc() - start_time).total_seconds() * 1000),
                )

            # Process in batches
            batch_size = config["batch_size"]
            for i in range(0, len(new_ids), batch_size):
                batch_ids = new_ids[i : i + batch_size]
                batch_processed, batch_errors = await self._process_batch_generic(
                    data_type, batch_ids, shop_id, db
                )
                processed_count += batch_processed
                error_count += len(batch_errors)
                errors.extend(batch_errors)

            duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
            self.logger.info(
                f"Completed {data_type} storage: {processed_count} processed, {error_count} errors in {duration_ms}ms"
            )

            return StorageResult(
                success=error_count == 0,
                processed_count=processed_count,
                error_count=error_count,
                errors=errors,
                duration_ms=duration_ms,
            )

        except Exception as e:
            error_msg = f"Failed to store {data_type}: {str(e)}"
            self.logger.error(error_msg)
            return StorageResult(
                success=False,
                processed_count=processed_count,
                error_count=error_count + 1,
                errors=errors + [error_msg],
                duration_ms=int((now_utc() - start_time).total_seconds() * 1000),
            )

    async def _process_batch_generic(
        self, data_type: str, batch_ids: List[str], shop_id: str, db
    ) -> Tuple[int, List[str]]:
        """Generic batch processing for any data type"""
        processed_count = 0
        errors = []

        try:
            config = DATA_TYPE_CONFIG[data_type]

            # Get raw data for this batch
            raw_data_result = await db.query_raw(
                f'SELECT "payload" FROM "{config["raw_table"]}" WHERE "shopId" = $1 AND "{config["raw_id_field"]}" = ANY($2)',
                shop_id,
                batch_ids,
            )

            # Process each item
            items_to_upsert = []
            for row in raw_data_result:
                try:
                    payload = row["payload"]
                    if isinstance(payload, str):
                        payload = json.loads(payload)

                    # Extract fields from raw payload first
                    extracted_data = self.field_extractor.extract_fields_generic(
                        data_type, payload, shop_id
                    )
                    if not extracted_data:
                        error_msg = f"Failed to extract {data_type} fields from payload"
                        errors.append(error_msg)
                        self.logger.warning(
                            f"{error_msg} - Payload keys: {list(payload.keys()) if isinstance(payload, dict) else 'Not a dict'}"
                        )
                        continue

                    # Clean the extracted data using the data cleaning service
                    try:
                        cleaned_data = self.data_cleaner.clean_data_generic(
                            extracted_data, data_type
                        )
                    except Exception as clean_error:
                        error_msg = (
                            f"Failed to clean {data_type} data: {str(clean_error)}"
                        )
                        errors.append(error_msg)
                        self.logger.warning(
                            f"{error_msg} - Extracted data keys: {list(extracted_data.keys()) if isinstance(extracted_data, dict) else 'Not a dict'}"
                        )
                        continue

                    # Extract the ID field
                    id_value = cleaned_data.get(config["id_field"])
                    if not id_value:
                        error_msg = f"Missing {config['id_field']} in {data_type} data"
                        errors.append(error_msg)
                        self.logger.warning(
                            f"{error_msg} - Available fields: {list(cleaned_data.keys()) if isinstance(cleaned_data, dict) else 'Not a dict'}"
                        )
                        continue

                    items_to_upsert.append(cleaned_data)
                    processed_count += 1

                except Exception as e:
                    import traceback

                    error_msg = f"Failed to process {data_type} item: {str(e)}"
                    errors.append(error_msg)
                    self.logger.error(
                        f"{error_msg} - Traceback: {traceback.format_exc()}"
                    )
                    continue

            # Batch upsert the processed items
            if items_to_upsert:
                await self._batch_upsert_generic(data_type, items_to_upsert, db)

        except Exception as e:
            errors.append(f"Batch processing failed for {data_type}: {str(e)}")

        return processed_count, errors

    def _convert_to_db_format(
        self, data_type: str, cleaned_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert cleaned data to database format using field mappings"""
        try:
            field_mapping = DATA_TYPE_CONFIG[data_type]["field_mapping"]
            db_data = {}

            # Add required fields
            for field in field_mapping["required_fields"]:
                if field in cleaned_data:
                    db_data[field] = cleaned_data[field]
                else:
                    error_msg = f"Missing required field '{field}' for {data_type} data"
                    self.logger.error(error_msg)
                    raise ValueError(error_msg)

            # Add optional fields
            for field in field_mapping["optional_fields"]:
                if field in cleaned_data and cleaned_data[field] is not None:
                    db_data[field] = cleaned_data[field]

            # Add JSON fields with proper Json wrapping
            for field in field_mapping["json_fields"]:
                if field in cleaned_data and cleaned_data[field] is not None:
                    try:
                        db_data[field] = Json(cleaned_data[field])
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to convert {data_type} field '{field}' to JSON: {str(e)}"
                        )
                        db_data[field] = Json({})  # Fallback to empty JSON

            return db_data

        except Exception as e:
            self.logger.error(
                f"Failed to convert {data_type} data to database format: {str(e)}"
            )
            raise

    async def _batch_upsert_generic(
        self, data_type: str, items: List[Dict[str, Any]], db
    ) -> None:
        """Generic batch upsert for any data type with proper database format conversion"""
        if not items:
            return

        config = DATA_TYPE_CONFIG[data_type]
        table_name = config["main_table"]
        id_field = config["id_field"]

        try:
            # Use Prisma's create_many for batch insert (much faster than individual upserts)
            create_data = [
                self._convert_to_db_format(data_type, item) for item in items
            ]
            await getattr(db, table_name.lower()).create_many(
                data=create_data, skip_duplicates=True
            )

        except Exception as e:
            # Fallback to individual upserts if batch insert fails
            import traceback

            self.logger.warning(
                f"{data_type} batch insert failed, falling back to individual upserts: {str(e)}"
            )
            self.logger.warning(
                f"{data_type} batch insert error details: {type(e).__name__}"
            )
            self.logger.warning(
                f"{data_type} batch insert traceback: {traceback.format_exc()}"
            )

            for item in items:
                try:
                    db_data = self._convert_to_db_format(data_type, item)
                    await getattr(db, table_name.lower()).upsert(
                        where={
                            f"shopId_{id_field}": {
                                "shopId": item["shopId"],
                                id_field: item[id_field],
                            }
                        },
                        data=db_data,
                    )
                except Exception as item_error:
                    import traceback

                    self.logger.error(
                        f"Failed to upsert {data_type} item {item.get(id_field)}: {str(item_error)} - Traceback: {traceback.format_exc()}"
                    )
                    continue

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

            # Run all storage operations concurrently using generic method
            results = await asyncio.gather(
                self._store_data_generic("orders", shop_id, incremental),
                self._store_data_generic("products", shop_id, incremental),
                self._store_data_generic("customers", shop_id, incremental),
                self._store_data_generic("collections", shop_id, incremental),
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
            # if total_errors == 0 and total_processed > 0:
            #     await self._publish_feature_computation_event(
            #         shop_id, total_processed, duration_ms
            #     )

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

    async def store_data_type(
        self, data_type: str, shop_id: str, incremental: bool = True
    ) -> StorageResult:
        """Generic method to store any data type from raw to main tables"""
        if data_type not in DATA_TYPE_CONFIG:
            return StorageResult(
                success=False,
                processed_count=0,
                error_count=1,
                errors=[f"Unknown data type: {data_type}"],
                duration_ms=0,
            )
        return await self._store_data_generic(data_type, shop_id, incremental)

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
