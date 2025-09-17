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
            logger.info(f"Normalization message received: {payload}")
            logger.info(f"Normalization message type: {type(payload)}")
            logger.info(f"Normalization message keys: {list(payload.keys())[:5]}")
            logger.info(f"Normalization message values: {list(payload.values())[:5]}")
            logger.info(f"Normalization message length: {len(payload)}")
            logger.info(f"Normalization message is dict: {isinstance(payload, dict)}")
            logger.info(f"Normalization message is list: {isinstance(payload, list)}")
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    pass
            # Trace message payload shape
            try:
                self.logger.info(
                    "Normalization message received",
                    event_type=(
                        payload.get("event_type") if isinstance(payload, dict) else None
                    ),
                    payload_type=type(payload).__name__,
                )
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
        # Normalize since value; Redis may serialize None as "None"
        if isinstance(since, str) and since.lower() in ("none", "null", ""):
            since = None
        # Trace since after sanitation
        try:
            self.logger.info(
                "Normalization batch since",
                since_value=since,
                since_type=type(since).__name__,
                data_type=data_type,
            )
        except Exception:
            pass
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
            self.logger.info(
                f"No more records to normalize for batch",
                shop_id=shop_id,
                data_type=data_type,
            )
            return

        # Process each record concurrently with bounded parallelism
        import asyncio

        semaphore = asyncio.Semaphore(20)

        async def process_record(raw_record):
            async with semaphore:
                await self._normalize_single_raw_record(raw_record, shop_id, data_type)
                return raw_record.shopifyUpdatedAt

        tasks = [process_record(raw_record) for raw_record in raw_records]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        # Track the last updated timestamp from the processed batch
        last_updated_at = max(results) if results else None

        # If we got a full page, publish next batch event
        if len(raw_records) == page_size:
            next_batch_payload = {
                "event_type": "normalize_batch",
                "shop_id": shop_id,
                "data_type": data_type,
                "page_size": page_size,
                "timestamp": datetime.now().isoformat(),
            }
            if last_updated_at:
                next_batch_payload["since"] = last_updated_at.isoformat()
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

        # Update watermark to the last successfully processed updatedAt
        if last_updated_at is not None:
            await db.normalizationwatermark.upsert(
                where={"shopId_dataType": {"shopId": shop_id, "dataType": data_type}},
                data={
                    "shopId": shop_id,
                    "dataType": data_type,
                    "lastNormalizedAt": last_updated_at,
                },
                create={
                    "shopId": shop_id,
                    "dataType": data_type,
                    "lastNormalizedAt": last_updated_at,
                },
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
            "page_size": page_size,
            "timestamp": datetime.now().isoformat(),
        }
        # Only include 'since' when present to avoid sending string "None"
        if since:
            batch_payload["since"] = since
        await streams_manager.publish_shopify_event(batch_payload)

        self.logger.info(
            f"Initiated scan normalization", shop_id=shop_id, data_type=data_type
        )

    async def _normalize_single_raw_record(
        self, raw_record: Any, shop_id: str, data_type: str
    ):
        """Normalize a single raw record and upsert to staging."""
        # Normalize payload to a dict (guards against stringified JSON, bytes, or single-item lists)
        payload = raw_record.payload
        try:
            self.logger.info(
                "Raw payload received",
                payload_type=type(payload).__name__,
                data_type=data_type,
            )
        except Exception:
            pass
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
        try:
            self.logger.info(
                "Raw payload normalized",
                normalized_type=type(payload).__name__,
                has_id=(isinstance(payload, dict) and ("id" in payload)),
                keys=(list(payload.keys())[:5] if isinstance(payload, dict) else None),
            )
        except Exception:
            pass
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
