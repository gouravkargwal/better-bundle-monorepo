"""
Kafka-based normalization consumer for processing entity normalization jobs
"""

import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.core.messaging.event_subscriber import EventSubscriber
from app.core.messaging.interfaces import EventHandler
from app.core.database.simple_db_client import get_database
from app.core.logging import get_logger
from app.domains.shopify.services.normalisation_service import (
    EntityNormalizationService,
    OrderNormalizationService,
    FeatureComputationService,
    EntityDeletionService,
)

logger = get_logger(__name__)


class NormalizationKafkaConsumer:
    """Kafka consumer for normalization jobs"""

    def __init__(self):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self.event_subscriber = EventSubscriber(kafka_settings.model_dump())
        self._initialized = False

        self.entity_service = EntityNormalizationService()
        self.order_service = OrderNormalizationService()
        self.feature_service = FeatureComputationService()
        self.deletion_service = EntityDeletionService()

    async def initialize(self):
        """Initialize consumer"""
        try:
            # Initialize Kafka consumer
            await self.consumer.initialize(
                topics=["normalization-jobs"], group_id="normalization-processors"
            )

            # Initialize event subscriber
            await self.event_subscriber.initialize(
                topics=["normalization-jobs"], group_id="normalization-processors"
            )

            # Add event handlers
            self.event_subscriber.add_handler(NormalizationJobHandler(self))

            self._initialized = True
            logger.info("Normalization Kafka consumer initialized")

        except Exception as e:
            logger.error(f"Failed to initialize normalization consumer: {e}")
            raise

    async def start_consuming(self):
        """Start consuming messages"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info("Starting normalization consumer...")
            await self.event_subscriber.consume_and_handle(
                topics=["normalization-jobs"], group_id="normalization-processors"
            )
        except Exception as e:
            logger.error(f"Error in normalization consumer: {e}")
            raise

    async def close(self):
        """Close consumer"""
        if self.consumer:
            await self.consumer.close()
        if self.event_subscriber:
            await self.event_subscriber.close()
        logger.info("Normalization consumer closed")

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the normalization consumer"""
        return {
            "status": "running" if self._initialized else "stopped",
            "last_health_check": datetime.utcnow().isoformat(),
        }


class NormalizationJobHandler(EventHandler):
    """Handler for normalization jobs"""

    def __init__(self, consumer: NormalizationKafkaConsumer):
        self.consumer = consumer
        self.logger = get_logger(__name__)

    def can_handle(self, event_type: str) -> bool:
        return event_type == "normalize_data"  # Only unified event type

    async def handle(self, event: Dict[str, Any]) -> bool:
        try:
            self.logger.info(f"🔄 Processing normalization message: {event}")

            payload = event.get("data") or event
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    pass
            event_type = payload.get("event_type")

            self.logger.info(f"📋 Extracted event_type: {event_type}")

            if event_type == "normalize_data":
                self.logger.info("📥 Processing normalize_data event")
                await self._handle_unified_normalization(payload)
            else:
                # Ignore non-normalization messages
                self.logger.info(f"⏭️ Ignoring non-normalization message: {event_type}")
                return True

            return True

        except Exception as e:
            self.logger.error(f"Normalization failed: {e}")
            return False

    async def _handle_unified_normalization(self, payload: Dict[str, Any]):
        """Simple, unified normalization handler"""
        self.logger.info(f"🔄 Starting unified normalization: {payload}")

        shop_id = payload.get("shop_id")
        data_type = payload.get("data_type")
        format_type = payload.get("format", "graphql")
        start_time = payload.get("start_time")
        end_time = payload.get("end_time")
        shopify_id = payload.get("shopify_id")

        if not shop_id or not data_type:
            self.logger.error(
                "❌ Invalid normalization event: missing shop_id or data_type"
            )
            return

        # If REST single-entity event with explicit shopify_id, process only that entity
        if (format_type or "").lower() == "rest" and shopify_id:
            await self._process_rest_entity(shop_id, data_type, shopify_id)
            # Feature computation for this type
            await self.consumer.feature_service.trigger_feature_computation(
                shop_id, data_type
            )
            self.logger.info(
                f"✅ Feature computation triggered for {data_type} (REST single entity)"
            )
            return

        # Process data with time range filtering (GraphQL or REST without id falls back to window)
        await self._process_normalization_simple(
            shop_id, data_type, format_type, start_time, end_time
        )

    async def _process_rest_entity(self, shop_id: str, data_type: str, shopify_id: str):
        """Process a single REST entity by shopify_id (real-time)."""
        try:
            db = await get_database()
            raw_table = {
                "orders": db.raworder,
                "products": db.rawproduct,
                "customers": db.rawcustomer,
                "collections": db.rawcollection,
            }.get(data_type)

            if not raw_table:
                self.logger.error(f"❌ Unknown data type for REST entity: {data_type}")
                return

            raw = await raw_table.find_first(
                where={"shopId": shop_id, "shopifyId": str(shopify_id)}
            )
            if not raw:
                self.logger.warning(
                    "REST entity not found in RAW",
                    shopify_id=shopify_id,
                    shop_id=shop_id,
                    data_type=data_type,
                )
                return

            # Normalize according to data type
            if data_type == "orders":
                await self.consumer.order_service.normalize_order(
                    raw, shop_id, is_webhook=True
                )
            else:
                await self.consumer.entity_service.normalize_entity(
                    raw, shop_id, data_type
                )

            # Update PipelineWatermark.lastNormalizedAt with raw.extractedAt if available
            if getattr(raw, "extractedAt", None):
                await self._upsert_watermark(
                    shop_id=shop_id,
                    data_type=data_type,
                    iso_time=raw.extractedAt.isoformat(),
                    format_type="graphql",  # we store in PipelineWatermark to unify tracking
                )

            self.logger.info(
                f"✅ REST entity normalized",
                extra={
                    "shop_id": shop_id,
                    "data_type": data_type,
                    "shopify_id": shopify_id,
                },
            )
        except Exception as e:
            self.logger.error(
                f"Failed REST entity normalization: {e}",
                shop_id=shop_id,
                data_type=data_type,
                shopify_id=shopify_id,
            )
            raise

    async def _resolve_window_from_watermark(
        self,
        shop_id: str,
        data_type: str,
        start_time: Optional[str],
        end_time: Optional[str],
        format_type: Optional[str] = None,
    ) -> (Optional[str], Optional[str]):
        """Resolve normalization window using watermark when event window is missing.
        For GraphQL format, use PipelineWatermark; otherwise, fall back to NormalizationWatermark.
        """
        if start_time and end_time:
            return start_time, end_time
        try:
            db = await get_database()

            if (format_type or "").lower() == "graphql":
                # Prefer the unified PipelineWatermark
                pw = await db.pipelinewatermark.find_unique(
                    where={
                        "shopId_dataType": {"shopId": shop_id, "dataType": data_type}
                    }
                )
                # Start from last normalized, else last window start; end at last collected/window end, else now
                from datetime import datetime, timezone

                resolved_start = start_time or (
                    (
                        pw.lastNormalizedAt.isoformat()
                        if pw and pw.lastNormalizedAt
                        else None
                    )
                    or (
                        pw.lastWindowStart.isoformat()
                        if pw and pw.lastWindowStart
                        else None
                    )
                )
                resolved_end = end_time or (
                    (
                        pw.lastCollectedAt.isoformat()
                        if pw and pw.lastCollectedAt
                        else None
                    )
                    or (
                        pw.lastWindowEnd.isoformat()
                        if pw and pw.lastWindowEnd
                        else None
                    )
                    or datetime.now(timezone.utc).isoformat()
                )
            else:
                # Legacy path: NormalizationWatermark table
                watermark = await db.normalizationwatermark.find_unique(
                    where={
                        "shopId_dataType": {"shopId": shop_id, "dataType": data_type}
                    }
                )
                from datetime import datetime, timezone

                resolved_start = start_time or (
                    watermark.lastNormalizedAt.isoformat() if watermark else None
                )
                resolved_end = end_time or datetime.now(timezone.utc).isoformat()

            # Guard against inverted windows (can occur if lastNormalizedAt > lastCollectedAt)
            if resolved_start and resolved_end and resolved_start > resolved_end:
                self.logger.warning(
                    "⚠️ Inverted normalization window detected; adjusting",
                    extra={
                        "shop_id": shop_id,
                        "data_type": data_type,
                        "original_start": resolved_start,
                        "original_end": resolved_end,
                    },
                )
                # Swap to ensure start <= end
                resolved_start, resolved_end = resolved_end, resolved_start

            self.logger.info(
                "🕒 Normalization window resolved",
                extra={
                    "shop_id": shop_id,
                    "data_type": data_type,
                    "start_time": resolved_start,
                    "end_time": resolved_end,
                    "source": (
                        "PipelineWatermark"
                        if (format_type or "").lower() == "graphql"
                        else "NormalizationWatermark"
                    ),
                },
            )
            return resolved_start, resolved_end
        except Exception as e:
            self.logger.warning(
                f"Failed to resolve watermark for {shop_id}/{data_type}: {e}"
            )
            return start_time, end_time

    async def _process_normalization_simple(
        self,
        shop_id: str,
        data_type: str,
        format_type: str,
        start_time: Optional[str],
        end_time: Optional[str],
    ):
        """Simple, industry-standard normalization processing"""
        self.logger.info(f"🔄 Processing {data_type} for shop {shop_id}")

        # Handle "all" data types
        if data_type == "all":
            data_types = ["products", "orders", "customers", "collections"]
            self.logger.info(f"🔄 Processing all data types: {data_types}")

            for dt in data_types:
                # Resolve window per data type (watermark-aware)
                dt_start, dt_end = await self._resolve_window_from_watermark(
                    shop_id, dt, start_time, end_time, format_type
                )
                last_extracted = await self._process_single_data_type(
                    shop_id, dt, format_type, dt_start, dt_end
                )
                # Trigger feature computation after each data type (independent processing)
                await self.consumer.feature_service.trigger_feature_computation(
                    shop_id, dt
                )
                # Upsert watermark to the max of last_extracted and dt_end
                if dt_end or last_extracted:
                    await self._upsert_watermark(
                        shop_id, dt, last_extracted or dt_end, format_type
                    )
                self.logger.info(f"✅ Feature computation triggered for {dt}")
        else:
            # Resolve window for single data type
            res_start, res_end = await self._resolve_window_from_watermark(
                shop_id, data_type, start_time, end_time, format_type
            )
            last_extracted = await self._process_single_data_type(
                shop_id, data_type, format_type, res_start, res_end
            )
            # Trigger feature computation after this data type
            await self.consumer.feature_service.trigger_feature_computation(
                shop_id, data_type
            )
            # Upsert watermark
            if res_end or last_extracted:
                await self._upsert_watermark(
                    shop_id, data_type, last_extracted or res_end, format_type
                )
            self.logger.info(f"✅ Feature computation triggered for {data_type}")

    async def _upsert_watermark(
        self,
        shop_id: str,
        data_type: str,
        iso_time: str,
        format_type: Optional[str] = None,
    ):
        """Persist last normalized time for incremental normalization.
        Writes to PipelineWatermark for GraphQL; else NormalizationWatermark.
        """
        try:
            db = await get_database()
            from datetime import datetime

            last_dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
            if (format_type or "").lower() == "graphql":
                await db.pipelinewatermark.upsert(
                    where={
                        "shopId_dataType": {"shopId": shop_id, "dataType": data_type}
                    },
                    data={
                        "update": {
                            "lastNormalizedAt": last_dt,
                            "lastWindowEnd": last_dt,
                        },
                        "create": {
                            "shopId": shop_id,
                            "dataType": data_type,
                            "lastNormalizedAt": last_dt,
                            "lastWindowEnd": last_dt,
                        },
                    },
                )
            else:
                await db.normalizationwatermark.upsert(
                    where={
                        "shopId_dataType": {"shopId": shop_id, "dataType": data_type}
                    },
                    data={
                        "update": {"lastNormalizedAt": last_dt},
                        "create": {
                            "shopId": shop_id,
                            "dataType": data_type,
                            "lastNormalizedAt": last_dt,
                        },
                    },
                )
            self.logger.info(
                "💾 Watermark updated",
                extra={
                    "shop_id": shop_id,
                    "data_type": data_type,
                    "lastNormalizedAt": iso_time,
                    "table": (
                        "PipelineWatermark"
                        if (format_type or "").lower() == "graphql"
                        else "NormalizationWatermark"
                    ),
                },
            )
        except Exception as e:
            self.logger.error(
                f"Failed to upsert normalization watermark: {e}",
                shop_id=shop_id,
                data_type=data_type,
            )

    async def _process_single_data_type(
        self,
        shop_id: str,
        data_type: str,
        format_type: str,
        start_time: Optional[str],
        end_time: Optional[str],
    ) -> Optional[str]:
        """Process a single data type - simple and efficient. Returns last processed extractedAt (ISO) if available."""
        db = await get_database()
        raw_table = {
            "orders": db.raworder,
            "products": db.rawproduct,
            "customers": db.rawcustomer,
            "collections": db.rawcollection,
        }.get(data_type)

        if not raw_table:
            self.logger.error(f"❌ Unknown data type: {data_type}")
            return None

        # Simple query - get data for this shop and data type
        where_conditions = {"shopId": shop_id}

        # Always add time filters (required for all events)
        time_filter = {}
        if start_time:
            time_filter["gte"] = start_time
        if end_time:
            time_filter["lte"] = end_time
        if time_filter:
            # Use shopifyUpdatedAt for GraphQL data, extractedAt otherwise
            time_field = (
                "shopifyUpdatedAt"
                if (format_type or "").lower() == "graphql"
                else "extractedAt"
            )
            where_conditions[time_field] = time_filter
        self.logger.info(
            f"🔍 Time filter on {'shopifyUpdatedAt' if (format_type or '').lower() == 'graphql' else 'extractedAt'}: {start_time} to {end_time}"
        )

        self.logger.info(f"🔍 Querying {data_type} with conditions: {where_conditions}")

        # Process data in batches
        page_size = 100
        offset = 0
        total_processed = 0
        last_extracted_iso: Optional[str] = None

        while True:
            self.logger.info(
                "📥 Fetching raw batch",
                extra={
                    "data_type": data_type,
                    "offset": offset,
                    "page_size": page_size,
                },
            )

            raw_records = await raw_table.find_many(
                where=where_conditions,
                skip=offset,
                take=page_size,
                order={"extractedAt": "desc"},  # Most recent first
            )

            if not raw_records:
                break

            self.logger.info(
                "📄 Processing batch",
                extra={
                    "data_type": data_type,
                    "batch_count": len(raw_records),
                    "offset": offset,
                },
            )

            # Process records in parallel
            tasks = []
            for raw_record in raw_records:
                # track max extractedAt seen
                if getattr(raw_record, "extractedAt", None):
                    try:
                        last_extracted_iso = (
                            max(
                                last_extracted_iso or "",
                                raw_record.extractedAt.isoformat(),
                            )
                            or raw_record.extractedAt.isoformat()
                        )
                    except Exception:
                        last_extracted_iso = raw_record.extractedAt.isoformat()

                if format_type == "graphql":
                    raw_record.format = "graphql"

                if data_type == "orders":
                    task = self.consumer.order_service.normalize_order(
                        raw_record, shop_id, is_webhook=False
                    )
                else:
                    task = self.consumer.entity_service.normalize_entity(
                        raw_record, shop_id, data_type
                    )
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)
            successful = len(
                [r for r in results if r is not None and not isinstance(r, Exception)]
            )
            total_processed += successful

            failures = len(raw_records) - successful
            if failures:
                self.logger.warning(
                    "⚠️ Some records failed during normalization",
                    extra={
                        "data_type": data_type,
                        "successful": successful,
                        "failed": failures,
                        "offset": offset,
                    },
                )
            self.logger.info(
                "✅ Batch processed",
                extra={
                    "data_type": data_type,
                    "successful": successful,
                    "batch_size": len(raw_records),
                    "cumulative_processed": total_processed,
                },
            )

            # Check if we need to continue pagination
            if len(raw_records) < page_size:
                break

            offset += page_size

        self.logger.info(
            "🎉 Normalization complete",
            extra={
                "data_type": data_type,
                "total_processed": total_processed,
                "last_extracted_iso": last_extracted_iso,
            },
        )
        return last_extracted_iso
