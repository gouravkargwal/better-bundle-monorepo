from __future__ import annotations

import json
from typing import Any, Dict, Optional
from datetime import datetime

from app.consumers.base_consumer import BaseConsumer
from app.core.logging import get_logger
from app.shared.constants.redis import DATA_JOB_STREAM
from app.domains.shopify.normalization.factory import get_adapter
from app.domains.shopify.normalization.canonical_models import NormalizeJob
from app.core.database.simple_db_client import get_database
from app.core.redis_client import streams_manager


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
        since = payload.get("since")  # ISO string or None
        page_size = payload.get("page_size", 100)

        if not all([shop_id, data_type]):
            self.logger.error(
                "Invalid normalize_batch job: missing required fields", payload=payload
            )
            return

        self.logger.info(
            f"Processing batch normalization",
            shop_id=shop_id,
            data_type=data_type,
            since=since,
        )

        db = await get_database()
        raw_table = {
            "orders": db.raworder,
            "products": db.rawproduct,
            "customers": db.rawcustomer,
            "collections": db.rawcollection,
        }[data_type]

        # Build query conditions
        where_conditions = {"shopId": shop_id}
        if since:
            # Parse since timestamp
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            where_conditions["shopifyUpdatedAt"] = {"gt": since_dt}

        # Fetch page of raw records, ordered by updatedAt, id for consistency
        raw_records = await raw_table.find_many(
            where=where_conditions,
            order_by=[{"shopifyUpdatedAt": "asc"}, {"id": "asc"}],
            take=page_size,
        )

        if not raw_records:
            self.logger.info(
                f"No more records to normalize for batch",
                shop_id=shop_id,
                data_type=data_type,
            )
            return

        # Process each record
        last_updated_at = None
        for raw_record in raw_records:
            await self._normalize_single_raw_record(raw_record, shop_id, data_type)
            last_updated_at = raw_record.shopifyUpdatedAt

        # If we got a full page, publish next batch event
        if len(raw_records) == page_size:
            next_batch_payload = {
                "event_type": "normalize_batch",
                "shop_id": shop_id,
                "data_type": data_type,
                "since": last_updated_at.isoformat() if last_updated_at else None,
                "page_size": page_size,
                "timestamp": datetime.now().isoformat(),
            }
            await streams_manager.publish_shopify_event(next_batch_payload)
            self.logger.info(
                f"Published next batch event",
                shop_id=shop_id,
                data_type=data_type,
                since=last_updated_at,
            )
        else:
            self.logger.info(
                f"Batch normalization completed",
                shop_id=shop_id,
                data_type=data_type,
                processed=len(raw_records),
            )

    async def _handle_normalize_scan(self, payload: Dict[str, Any]):
        """Handle full scan normalization with watermark tracking."""
        shop_id = payload.get("shop_id")
        data_type = payload.get("data_type")
        since = payload.get("since")  # Optional watermark
        page_size = payload.get("page_size", 100)

        if not all([shop_id, data_type]):
            self.logger.error(
                "Invalid normalize_scan job: missing required fields", payload=payload
            )
            return

        self.logger.info(
            f"Processing scan normalization",
            shop_id=shop_id,
            data_type=data_type,
            since=since,
        )

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
            "since": since,
            "page_size": page_size,
            "timestamp": datetime.now().isoformat(),
        }
        await streams_manager.publish_shopify_event(batch_payload)

        # Update watermark to current time (scan initiated)
        # Note: Now tracking main table normalization instead of staging
        await db.normalizationwatermark.upsert(
            where={"shopId_dataType": {"shopId": shop_id, "dataType": data_type}},
            data={
                "shopId": shop_id,
                "dataType": data_type,
                "lastNormalizedAt": datetime.now(),
            },
            create={
                "shopId": shop_id,
                "dataType": data_type,
                "lastNormalizedAt": datetime.now(),
            },
        )

        self.logger.info(
            f"Initiated scan normalization", shop_id=shop_id, data_type=data_type
        )

    async def _normalize_single_raw_record(
        self, raw_record: Any, shop_id: str, data_type: str
    ):
        """Normalize a single raw record and upsert to staging."""
        # Detect format from raw record or use heuristic
        data_format = getattr(raw_record, "format", None)
        if not data_format:
            # Fallback heuristic: GraphQL has 'gid://' in IDs, REST uses numeric IDs
            payload = raw_record.payload
            if isinstance(payload, dict):
                entity_id = payload.get("id", "")
                data_format = (
                    "graphql" if str(entity_id).startswith("gid://") else "rest"
                )
            else:
                data_format = "rest"  # Default fallback

        adapter = get_adapter(data_format, data_type)
        canonical = adapter.to_canonical(raw_record.payload, shop_id)

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
        main_data[f"{data_type[:-1]}Id"] = canonical[
            "entityId"
        ]  # orderId, productId, etc.

        # Map internal timestamp fields
        if "shopifyUpdatedAt" in main_data:
            main_data["updatedAt"] = main_data["shopifyUpdatedAt"]
        if "shopifyCreatedAt" in main_data:
            main_data["createdAt"] = main_data["shopifyCreatedAt"]

        # Guard by shopifyUpdatedAt for idempotency
        incoming_updated_at = canonical.get("shopifyUpdatedAt")
        id_field = f"{data_type[:-1]}Id"

        existing = await main_table.find_first(
            where={"shopId": shop_id, id_field: canonical["entityId"]}
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
        unique_where = {
            "shopId_" + id_field: {"shopId": shop_id, id_field: canonical["entityId"]}
        }

        if existing:
            await main_table.update(
                where={"id": existing.id},
                data=main_data,
            )
        else:
            await main_table.create(data=main_data)
