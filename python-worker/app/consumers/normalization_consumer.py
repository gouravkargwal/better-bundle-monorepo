from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.consumers.base_consumer import BaseConsumer
from app.core.logging import get_logger
from app.shared.constants.redis import DATA_JOB_STREAM
from app.domains.shopify.normalization.factory import get_adapter
from app.domains.shopify.normalization.canonical_models import NormalizeJob
from app.core.database.simple_db_client import get_database
from app.core.redis_client import streams_manager

logger = get_logger(__name__)


class NormalizationConsumer(BaseConsumer):
    """Consumes normalize_entity, normalize_batch, and normalize_scan jobs and upserts into Staging* tables."""

    def __init__(self) -> None:
        super().__init__(
            stream_name=DATA_JOB_STREAM,
            consumer_group="normalization-consumer-group",
            consumer_name="normalization-consumer",
            batch_size=50,
            poll_timeout=1000,
            max_retries=3,
            retry_delay=0.5,
        )
        self.logger = get_logger(__name__)

    async def _process_single_message(self, message: Dict[str, Any]):
        try:
            payload = message.get("data") or message
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    pass
            event_type = payload.get("event_type")

            if event_type == "normalize_entity":
                await self._handle_normalize_entity(payload)
            elif event_type == "normalize_batch":
                await self._handle_normalize_batch(payload)
            elif event_type == "normalize_scan":
                await self._handle_normalize_scan(payload)
            else:
                # Ignore non-normalization messages
                return

        except Exception as e:
            self.logger.error(f"Normalization failed: {e}")
            raise

    async def _handle_normalize_entity(self, payload: Dict[str, Any]):
        """Handle single entity normalization (webhooks)."""
        # NormalizeJob validation; be lenient about timestamp as string
        if isinstance(payload.get("timestamp"), str):
            # Pydantic will parse ISO strings automatically
            pass

        job = NormalizeJob(**payload)
        db = await get_database()

        # Load raw record
        raw_table = {
            "orders": db.raworder,
            "products": db.rawproduct,
            "customers": db.rawcustomer,
            "collections": db.rawcollection,
        }[job.data_type]

        raw = await raw_table.find_unique(where={"id": job.raw_id})
        if not raw:
            self.logger.warning("Raw record not found", raw_id=job.raw_id)
            return

        await self._normalize_single_raw_record(raw, job.shop_id, job.data_type)

    async def _handle_normalize_batch(self, payload: Dict[str, Any]):
        """Handle batch normalization with pagination."""
        shop_id = payload.get("shop_id")
        data_type = payload.get("data_type")
        fmt = payload.get("format")
        since = payload.get("since")  # ISO string or None
        page_size = payload.get("page_size", 100)

        if not all([shop_id, data_type]):
            self.logger.error(
                "Invalid normalize_batch job: missing required fields", payload=payload
            )
            return

        db = await get_database()
        raw_table = {
            "orders": db.raworder,
            "products": db.rawproduct,
            "customers": db.rawcustomer,
            "collections": db.rawcollection,
        }[data_type]

        # Build query conditions
        where_conditions = {"shopId": shop_id}
        # Normalize since value; Redis may serialize None as "None"
        if isinstance(since, str) and since.lower() in ("none", "null", ""):
            since = None

        if since:
            # Parse since timestamp
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            where_conditions["shopifyUpdatedAt"] = {"gt": since_dt}

        # Fetch page of raw records, ordered by updatedAt, id for consistency
        raw_records = await raw_table.find_many(
            where=where_conditions,
            order=[{"shopifyUpdatedAt": "asc"}, {"id": "asc"}],
            take=page_size,
        )

        if not raw_records:
            return

        # Process each record concurrently with bounded parallelism
        import asyncio

        semaphore = asyncio.Semaphore(20)

        async def process_record(raw_record):
            async with semaphore:
                try:
                    # Force GraphQL adapter when event format says so or payload looks GraphQL
                    if fmt == "graphql":
                        setattr(raw_record, "format", "graphql")
                    await self._normalize_single_raw_record(
                        raw_record, shop_id, data_type
                    )
                    return raw_record.shopifyUpdatedAt
                except Exception as e:
                    self.logger.error(
                        f"Failed to normalize record",
                        error=str(e),
                        shop_id=shop_id,
                        data_type=data_type,
                        record_id=getattr(raw_record, "id", "unknown"),
                    )
                    # Return None to indicate failure, but don't stop the batch
                    return None

        tasks = [process_record(raw_record) for raw_record in raw_records]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out failed results and exceptions
        successful_results = [
            r for r in results if r is not None and not isinstance(r, Exception)
        ]

        # Track the last updated timestamp from the processed batch
        last_updated_at = max(successful_results) if successful_results else None

        # Log batch processing results
        failed_count = len(results) - len(successful_results)
        if failed_count > 0:
            self.logger.warning(
                f"Batch processing completed with failures",
                shop_id=shop_id,
                data_type=data_type,
                total_records=len(raw_records),
                successful=len(successful_results),
                failed=failed_count,
            )

        # If we got a full page, publish next batch event
        if len(raw_records) == page_size:
            next_batch_payload = {
                "event_type": "normalize_batch",
                "shop_id": shop_id,
                "data_type": data_type,
                "format": fmt,
                "page_size": page_size,
                "timestamp": datetime.now().isoformat(),
            }
            if last_updated_at:
                next_batch_payload["since"] = last_updated_at.isoformat()
            await streams_manager.publish_shopify_event(next_batch_payload)

        # Update watermark to the last successfully processed updatedAt
        if last_updated_at is not None:
            await db.normalizationwatermark.upsert(
                where={"shopId_dataType": {"shopId": shop_id, "dataType": data_type}},
                data={
                    "update": {
                        "lastNormalizedAt": last_updated_at,
                    },
                    "create": {
                        "shopId": shop_id,
                        "dataType": data_type,
                        "lastNormalizedAt": last_updated_at,
                    },
                },
            )

    async def _handle_normalize_scan(self, payload: Dict[str, Any]):
        """Handle full scan normalization with watermark tracking."""
        shop_id = payload.get("shop_id")
        data_type = payload.get("data_type")
        fmt = payload.get("format")
        since = payload.get("since")  # Optional watermark
        page_size = payload.get("page_size", 100)

        if not all([shop_id, data_type]):
            self.logger.error(
                "Invalid normalize_scan job: missing required fields", payload=payload
            )
            return

        db = await get_database()

        # Get current watermark if since not provided
        if not since:
            watermark = await db.normalizationwatermark.find_unique(
                where={"shopId_dataType": {"shopId": shop_id, "dataType": data_type}}
            )
            since = watermark.lastNormalizedAt.isoformat() if watermark else None

        # Trigger first batch
        batch_payload = {
            "event_type": "normalize_batch",
            "shop_id": shop_id,
            "data_type": data_type,
            "format": fmt,
            "page_size": page_size,
            "timestamp": datetime.now().isoformat(),
        }
        # Only include 'since' when present to avoid sending string "None"
        if since:
            batch_payload["since"] = since
        await streams_manager.publish_shopify_event(batch_payload)

    async def _normalize_single_raw_record(
        self, raw_record: Any, shop_id: str, data_type: str
    ):
        """Normalize a single raw record and upsert to staging."""
        start_time = time.time()
        # Normalize payload to a dict (guards against stringified JSON, bytes, or single-item lists)
        payload = raw_record.payload
        if isinstance(payload, (bytes, bytearray)):
            try:
                payload = payload.decode("utf-8")
            except Exception:
                self.logger.warning(
                    "Skipping raw record: invalid bytes payload", shop_id=shop_id
                )
                return
        if isinstance(payload, str):
            try:
                import json as _json

                payload = _json.loads(payload)
            except Exception:
                self.logger.warning(
                    "Skipping raw record: invalid JSON payload string", shop_id=shop_id
                )
                return
        # Some sources may wrap node in a single-element list
        if (
            isinstance(payload, list)
            and len(payload) == 1
            and isinstance(payload[0], dict)
        ):
            payload = payload[0]
        if not isinstance(payload, dict):
            self.logger.warning(
                "Skipping raw record: unexpected payload type",
                type=type(payload).__name__,
            )
            return

        # Detect format from normalized payload or use heuristic
        data_format = getattr(raw_record, "format", None)
        if not data_format:
            # GraphQL has 'gid://' in IDs, REST uses numeric IDs
            entity_id = payload.get("id", "")
            data_format = "graphql" if str(entity_id).startswith("gid://") else "rest"

        adapter = get_adapter(data_format, data_type)
        try:
            canonical = adapter.to_canonical(payload, shop_id)
        except Exception as e:
            self.logger.error(
                "Adapter to_canonical failed",
                error=str(e),
                data_format=data_format,
                data_type=data_type,
                payload_keys=(
                    list(payload.keys())[:8] if isinstance(payload, dict) else None
                ),
            )
            raise

        db = await get_database()
        main_table = {
            "orders": db.orderdata,
            "products": db.productdata,
            "customers": db.customerdata,
            "collections": db.collectiondata,
        }[data_type]

        # Prepare main table data (canonical structure + base fields)
        main_data = canonical.copy()
        main_data["shopId"] = shop_id
        # Resolve the primary identifier: now using table-specific id fields directly
        id_field = f"{data_type[:-1]}Id"
        id_value = canonical.get(id_field)
        if not id_value:
            # If still missing, abort this record gracefully
            self.logger.error(
                "Missing primary id for canonical record",
                data_type=data_type,
                id_field=id_field,
            )
            return
        # The id is already in the correct field, no need to reassign

        # Map internal timestamp fields (handle both old and new field names)
        if "shopifyUpdatedAt" in main_data:
            main_data["updatedAt"] = main_data["shopifyUpdatedAt"]
        if "shopifyCreatedAt" in main_data:
            main_data["createdAt"] = main_data["shopifyCreatedAt"]
        if "customerUpdatedAt" in main_data:
            main_data["updatedAt"] = main_data["customerUpdatedAt"]
        if "customerCreatedAt" in main_data:
            main_data["createdAt"] = main_data["customerCreatedAt"]

        # Ensure shopId is always present
        main_data["shopId"] = shop_id

        # Ensure required timestamps are present
        from datetime import datetime

        if "createdAt" not in main_data or main_data["createdAt"] is None:
            main_data["createdAt"] = datetime.utcnow()
        if "updatedAt" not in main_data or main_data["updatedAt"] is None:
            main_data["updatedAt"] = datetime.utcnow()

        # Convert JSON fields to proper format for Prisma
        self._serialize_json_fields(main_data)

        # Guard by shopifyUpdatedAt for idempotency
        incoming_updated_at = canonical.get("shopifyUpdatedAt")
        id_field = f"{data_type[:-1]}Id"

        existing = await main_table.find_first(
            where={"shopId": shop_id, id_field: id_value}
        )

        if (
            existing
            and hasattr(existing, "shopifyUpdatedAt")
            and existing.shopifyUpdatedAt
            and incoming_updated_at
        ):
            if incoming_updated_at <= existing.shopifyUpdatedAt:
                # Older or equal, skip
                return

        # Upsert directly into main table
        unique_where = {"shopId_" + id_field: {"shopId": shop_id, id_field: id_value}}

        # Handle line items separately for orders
        line_items = main_data.pop("lineItems", [])

        # Clean payload to match Prisma inputs - remove internal/canonical fields
        main_data.pop("entityId", None)  # Legacy field
        main_data.pop("canonicalVersion", None)  # Removed field
        main_data.pop("originalGid", None)  # Internal tracking field
        main_data.pop("customerCreatedAt", None)  # Internal timestamp
        main_data.pop("customerUpdatedAt", None)  # Internal timestamp
        main_data.pop("isActive", None)  # Internal field not in DB schema

        # Handle None values for required JSON fields - convert to empty defaults
        if (
            "customerDefaultAddress" in main_data
            and main_data["customerDefaultAddress"] is None
        ):
            main_data["customerDefaultAddress"] = "{}"
        if "location" in main_data and main_data["location"] is None:
            main_data["location"] = "{}"
        if "defaultAddress" in main_data and main_data["defaultAddress"] is None:
            main_data["defaultAddress"] = "{}"
        if "shippingAddress" in main_data and main_data["shippingAddress"] is None:
            main_data["shippingAddress"] = "{}"
        if "billingAddress" in main_data and main_data["billingAddress"] is None:
            main_data["billingAddress"] = "{}"

        # Upsert main record - keep shopId as scalar since all models have it
        if existing:
            await main_table.update(
                where={"id": existing.id},
                data=main_data,
            )
            order_record_id = existing.id
        else:
            created_record = await main_table.create(data=main_data)
            order_record_id = created_record.id

        # Create line items separately for orders
        if data_type == "orders" and line_items:
            await self._create_line_items(order_record_id, line_items)

        # Log performance metrics (production monitoring)
        processing_time = time.time() - start_time
        if processing_time > 1.0:  # Only log slow operations
            self.logger.warning(
                f"Slow normalization detected",
                data_type=data_type,
                processing_time_seconds=round(processing_time, 3),
                shop_id=shop_id,
            )

    def _serialize_json_fields(self, main_data: Dict[str, Any]):
        """Convert JSON fields to proper JSON strings for Prisma."""
        import json

        json_fields = [
            "metafields",
            "tags",
            "addresses",
            "defaultAddress",
            "location",
            "shippingAddress",
            "billingAddress",
            "discountApplications",
            "fulfillments",
            "transactions",
            "variants",
            "images",
            "media",
            "options",
            "noteAttributes",
            "extras",
        ]

        for field in json_fields:
            if field in main_data and main_data[field] is not None:
                # Convert Python objects to JSON strings
                try:
                    main_data[field] = json.dumps(main_data[field])
                except (TypeError, ValueError):
                    # If serialization fails, set to appropriate default
                    if isinstance(main_data[field], (list, tuple)):
                        main_data[field] = "[]"
                    elif isinstance(main_data[field], dict):
                        main_data[field] = "{}"
                    else:
                        main_data[field] = None

    async def _create_line_items(self, order_record_id: str, line_items: List[Any]):
        """Create separate LineItemData records for an order using bulk operations."""
        if not line_items:
            return

        db = await get_database()

        try:
            # Clear existing line items for this order (for updates)
            await db.lineitemdata.delete_many(where={"orderId": order_record_id})

            # Prepare bulk data
            bulk_data = []
            for item in line_items:
                try:
                    if isinstance(item, dict):
                        line_item_data = {
                            "orderId": order_record_id,
                            "productId": item.get("productId"),
                            "variantId": item.get("variantId"),
                            "title": item.get("title"),
                            "quantity": int(item.get("quantity", 0)),
                            "price": float(item.get("price", 0.0)),
                        }
                    else:
                        line_item_data = {
                            "orderId": order_record_id,
                            "productId": getattr(item, "productId", None),
                            "variantId": getattr(item, "variantId", None),
                            "title": getattr(item, "title", None),
                            "quantity": int(getattr(item, "quantity", 0)),
                            "price": float(getattr(item, "price", 0.0)),
                        }
                    bulk_data.append(line_item_data)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Skipping invalid line item: {e}", item=item)
                    continue

            # Bulk create all line items in one operation
            if bulk_data:
                await db.lineitemdata.create_many(data=bulk_data)
                self.logger.debug(
                    f"Created {len(bulk_data)} line items for order {order_record_id}"
                )

        except Exception as e:
            self.logger.error(
                f"Failed to create line items for order {order_record_id}: {e}"
            )
            # Don't raise - let the order still be processed even if line items fail
