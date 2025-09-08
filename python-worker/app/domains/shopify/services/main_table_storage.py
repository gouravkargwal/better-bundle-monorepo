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

    def __init__(self, debug_mode=False):
        self.logger = logger
        self._db_client = None
        self.field_extractor = FieldExtractorService()
        self.data_cleaner = DataCleaningService()
        self.debug_mode = debug_mode  # Enable detailed per-item logging for debugging

    async def _get_database(self):
        """Get or initialize the database client"""
        if self._db_client is None:
            self._db_client = await get_database()
        return self._db_client

    def _extract_shopify_id(self, gid: str) -> Optional[str]:
        """
        Extract numeric ID from Shopify GraphQL GID

        🚀 FUTURE OPTIMIZATION: This method should eventually be eliminated by standardizing
        on storing full GIDs in both raw and main tables. Consider migrating to:
        1. Store full GID as primary 'shopifyId' in all tables
        2. Add separate 'numericId' BigInt column if needed elsewhere
        3. Remove all GID conversion logic from processing pipeline

        This would eliminate performance overhead and potential bugs from ID format mismatches.
        """
        if not gid:
            return None
        try:
            # Handle GID format: gid://shopify/Order/123456789
            if gid.startswith("gid://shopify/"):
                return gid.split("/")[-1]
            return gid
        except Exception:
            return None

    async def _store_data_generic(
        self, data_type: str, shop_id: str, incremental: bool = True
    ) -> StorageResult:
        """
        🚀 SCALABLE method to store any data type from raw to main tables.
        Uses database-based filtering and pagination to handle millions of records efficiently.
        Memory usage: O(batch_size) instead of O(total_records)
        """
        start_time = now_utc()
        processed_count = 0
        error_count = 0
        errors = []

        # Ensure counters are defined even if an early exception occurs
        total_batches_processed = 0

        try:
            config = DATA_TYPE_CONFIG[data_type]
            db = await self._get_database()

            # Configuration for pagination
            batch_size = config.get("batch_size", 1000)
            offset = 0

            self.logger.info(
                f"Starting scalable processing of {data_type} for shop {shop_id} (batch_size: {batch_size})"
            )

            while True:
                # 🔥 CRITICAL OPTIMIZATION: Database-optimized query
                # Fetches ONLY new/updated records directly, eliminating memory issues
                if incremental:
                    # Query for records that are NEW or UPDATED since last processing
                    # 🔧 FIX: Handle GID to numeric ID conversion in JOIN
                    if data_type == "products":
                        id_conversion = (
                            "REPLACE(r.\"shopifyId\", 'gid://shopify/Product/', '')"
                        )
                    elif data_type == "orders":
                        id_conversion = (
                            "REPLACE(r.\"shopifyId\", 'gid://shopify/Order/', '')"
                        )
                    elif data_type == "customers":
                        id_conversion = (
                            "REPLACE(r.\"shopifyId\", 'gid://shopify/Customer/', '')"
                        )
                    elif data_type == "collections":
                        id_conversion = (
                            "REPLACE(r.\"shopifyId\", 'gid://shopify/Collection/', '')"
                        )
                    else:
                        id_conversion = f"r.\"{config['raw_id_field']}\""

                    query = f"""
                    SELECT r."payload", r."{config["raw_id_field"]}"
                    FROM "{config["raw_table"]}" r
                    LEFT JOIN "{config["main_table"]}" m 
                        ON {id_conversion} = m."{config["id_field"]}" 
                        AND r."shopId" = m."shopId"
                    WHERE r."shopId" = $1 
                        AND r."{config["raw_id_field"]}" IS NOT NULL
                        AND (m."{config["id_field"]}" IS NULL OR r."extractedAt" > m."updatedAt")
                    ORDER BY r."extractedAt" ASC
                    LIMIT $2 OFFSET $3
                    """
                    params = [shop_id, batch_size, offset]
                else:
                    # Non-incremental: process all records
                    query = f"""
                    SELECT r."payload", r."{config["raw_id_field"]}"
                    FROM "{config["raw_table"]}" r
                    WHERE r."shopId" = $1 
                        AND r."{config["raw_id_field"]}" IS NOT NULL
                    ORDER BY r."extractedAt" ASC
                    LIMIT $2 OFFSET $3
                    """
                    params = [shop_id, batch_size, offset]

                # Execute the optimized query
                batch_result = await db.query_raw(query, *params)

                # No more records to process
                if not batch_result:
                    if total_batches_processed == 0:
                        self.logger.info(
                            f"No new/updated {data_type} records found for shop {shop_id}"
                        )
                    break

                total_batches_processed += 1
                batch_records = len(batch_result)

                self.logger.info(
                    f"Processing batch {total_batches_processed}: {batch_records} {data_type} records (offset: {offset})"
                )

                # Process this batch of records directly (no more ID conversion needed)
                try:
                    batch_processed, batch_errors = await self._process_batch_records(
                        data_type, batch_result, shop_id, db, config
                    )

                    processed_count += batch_processed
                    error_count += len(batch_errors)
                    errors.extend(batch_errors)

                    if self.debug_mode:
                        self.logger.info(
                            f"Batch {total_batches_processed} details: {batch_processed} processed, {len(batch_errors)} errors"
                        )

                except Exception as batch_error:
                    import traceback

                    error_msg = (
                        f"Batch {total_batches_processed} failed: {str(batch_error)}"
                    )
                    self.logger.error(
                        f"{error_msg} - Traceback: {traceback.format_exc()}"
                    )
                    errors.append(error_msg)
                    error_count += batch_records

                # Move to next batch
                offset += batch_size

                # Safety check to prevent infinite loops on massive datasets
                if offset > 10_000_000:  # 10M record safety limit
                    self.logger.warning(
                        f"Safety limit reached processing {data_type}. Stopping at offset {offset}"
                    )
                    break

        except Exception as e:
            import traceback

            error_msg = f"Fatal error in _store_data_generic for {data_type}: {str(e)}"
            self.logger.error(f"{error_msg} - Traceback: {traceback.format_exc()}")
            errors.append(error_msg)
            error_count += 1

        duration_ms = int((now_utc() - start_time).total_seconds() * 1000)
        success = error_count == 0

        self.logger.info(
            f"Completed scalable {data_type} storage: {processed_count} processed, {error_count} errors in {duration_ms}ms ({total_batches_processed} batches)"
        )

        return StorageResult(
            success=success,
            processed_count=processed_count,
            error_count=error_count,
            errors=errors,
            duration_ms=duration_ms,
        )

    async def _process_batch_records(
        self, data_type: str, batch_records: List[dict], shop_id: str, db, config: dict
    ) -> Tuple[int, List[str]]:
        """
        🚀 SCALABLE batch processing that works directly with payload data.
        Eliminates the need for GID conversion and additional database queries.
        """
        processed_count = 0
        errors = []

        try:
            items_to_upsert = []

            # Process each record directly (no more ID lookups needed!)
            for record in batch_records:
                try:
                    # Parse payload
                    payload = record["payload"]
                    if isinstance(payload, str):
                        payload = json.loads(payload)

                    # Extract fields from raw payload
                    extracted_data = self.field_extractor.extract_fields_generic(
                        data_type, payload, shop_id
                    )
                    if not extracted_data:
                        error_msg = f"Failed to extract {data_type} fields from payload"
                        errors.append(error_msg)
                        if self.debug_mode:
                            self.logger.warning(
                                f"{error_msg} - Payload keys: {list(payload.keys()) if isinstance(payload, dict) else 'Not a dict'}"
                            )
                        continue

                    # Clean the extracted data
                    try:
                        cleaned_data = self.data_cleaner.clean_data_generic(
                            extracted_data, data_type
                        )
                    except Exception as clean_error:
                        error_msg = (
                            f"Failed to clean {data_type} data: {str(clean_error)}"
                        )
                        errors.append(error_msg)
                        if self.debug_mode:
                            self.logger.warning(
                                f"{error_msg} - Extracted data keys: {list(extracted_data.keys()) if isinstance(extracted_data, dict) else 'Not a dict'}"
                            )
                        continue

                    # Validate required ID field
                    id_value = cleaned_data.get(config["id_field"])
                    if not id_value:
                        error_msg = f"Missing {config['id_field']} in {data_type} data"
                        errors.append(error_msg)
                        if self.debug_mode:
                            self.logger.warning(
                                f"{error_msg} - Available fields: {list(cleaned_data.keys()) if isinstance(cleaned_data, dict) else 'Not a dict'}"
                            )
                        continue

                    items_to_upsert.append(cleaned_data)

                except Exception as e:
                    import traceback

                    error_msg = f"Failed to process {data_type} item: {str(e)}"
                    errors.append(error_msg)
                    if self.debug_mode:
                        self.logger.error(
                            f"{error_msg} - Traceback: {traceback.format_exc()}"
                        )
                    continue

            # Batch upsert the processed items
            if items_to_upsert:
                try:
                    await self._batch_upsert_generic(data_type, items_to_upsert, db)
                    # Only count as processed after successful upsert
                    processed_count += len(items_to_upsert)
                    if self.debug_mode:
                        self.logger.info(
                            f"Successfully upserted {len(items_to_upsert)} {data_type} items to main table"
                        )
                except Exception as upsert_error:
                    import traceback

                    error_msg = f"Failed to upsert {len(items_to_upsert)} {data_type} items: {str(upsert_error)}"
                    errors.append(error_msg)
                    self.logger.error(
                        f"{error_msg} - Traceback: {traceback.format_exc()}"
                    )
            else:
                if self.debug_mode:
                    self.logger.warning(
                        f"No items to upsert for {data_type} - all items failed processing"
                    )

        except Exception as e:
            import traceback

            error_msg = f"Batch processing failed for {data_type}: {str(e)}"
            errors.append(error_msg)
            self.logger.error(f"{error_msg} - Traceback: {traceback.format_exc()}")

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
            # Try batch create first for new records (without skip_duplicates for proper error handling)
            create_data = [
                self._convert_to_db_format(data_type, item) for item in items
            ]

            # Don't use skip_duplicates - we want to know about conflicts and handle them with upsert
            await getattr(db, table_name.lower()).create_many(data=create_data)

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

            # 🚀 OPTIMIZATION: Parallel individual upserts for better performance
            import asyncio

            async def upsert_single_item(item):
                try:
                    db_data = self._convert_to_db_format(data_type, item)

                    # Manual upsert logic - try update first, then create if not exists
                    table_accessor = getattr(db, table_name.lower())
                    where_clause = {
                        "shopId_"
                        + id_field: {
                            "shopId": item["shopId"],
                            id_field: item[id_field],
                        }
                    }

                    try:
                        # Try update first (more common case for incremental processing)
                        await table_accessor.update(where=where_clause, data=db_data)
                        return {"success": True, "item_id": item.get(id_field)}
                    except Exception as update_error:
                        # Only create if update failed due to record not existing
                        try:
                            await table_accessor.create(data=db_data)
                            return {"success": True, "item_id": item.get(id_field)}
                        except Exception:
                            # Race condition: record was created by another process
                            # Try update one more time
                            try:
                                await table_accessor.update(
                                    where=where_clause, data=db_data
                                )
                                return {"success": True, "item_id": item.get(id_field)}
                            except Exception as final_error:
                                # Log the actual error for debugging
                                raise final_error
                except Exception as item_error:
                    return {
                        "success": False,
                        "item_id": item.get(id_field),
                        "error": str(item_error),
                    }

            # Execute all upserts in parallel
            upsert_tasks = [upsert_single_item(item) for item in items]
            results = await asyncio.gather(*upsert_tasks, return_exceptions=True)

            # Log any individual failures
            failed_count = 0
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    failed_count += 1
                    item_id = items[i].get(id_field, "unknown")
                    self.logger.error(
                        f"Failed to upsert {data_type} item {item_id}: {str(result)}"
                    )
                elif not result.get("success"):
                    failed_count += 1
                    self.logger.error(
                        f"Failed to upsert {data_type} item {result.get('item_id', 'unknown')}: {result.get('error', 'Unknown error')}"
                    )

            if failed_count > 0:
                self.logger.warning(
                    f"Parallel fallback upsert completed with {failed_count}/{len(items)} failures"
                )
            else:
                self.logger.info(
                    f"Parallel fallback upsert successful for all {len(items)} {data_type} items"
                )

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
