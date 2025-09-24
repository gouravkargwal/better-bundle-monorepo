from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.domains.shopify.normalization.factory import get_adapter
from app.domains.shopify.normalization.canonical_models import NormalizeJob
from app.domains.shopify.services.normalization_data_storage_service import (
    NormalizationDataStorageService,
)
from app.core.messaging.event_publisher import EventPublisher
from app.core.config.kafka_settings import kafka_settings
from app.shared.helpers import now_utc

logger = get_logger(__name__)


class EntityNormalizationService:
    """Handles core entity normalization logic (products, customers, collections)."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.data_storage = NormalizationDataStorageService()

    async def normalize_entity(
        self, raw_record: Any, shop_id: str, data_type: str
    ) -> bool:
        """Normalize a single entity record."""
        try:
            # Parse and validate payload
            payload = self._parse_payload(raw_record)
            if not payload:
                return False

            # Get adapter and convert to canonical
            data_format = self._detect_format(raw_record, payload)
            adapter = get_adapter(data_format, data_type)
            canonical = adapter.to_canonical(payload, shop_id)
            self.logger.info(
                "📦 Canonical entity prepared",
                extra={
                    "data_type": data_type,
                    "id": canonical.get(f"{data_type[:-1]}Id"),
                    "format": data_format,
                },
            )

            # Check for idempotency before storage
            if self._should_skip_update_by_canonical(canonical, data_type):
                self.logger.info(
                    f"Skipping normalization for {data_type} {canonical.get(f'{data_type[:-1]}Id')} - no updates needed"
                )
                return True

            # Use data storage service for upsert
            return await self.data_storage.upsert_entity(data_type, canonical, shop_id)

        except Exception as e:
            self.logger.error(f"Entity normalization failed: {e}")
            # For certain errors, we should not retry
            if self._should_not_retry(e):
                self.logger.warning(f"Skipping retry for non-retryable error: {e}")
            return False

    def _should_not_retry(self, error: Exception) -> bool:
        """Check if error should not be retried (data format issues, etc.)."""
        error_str = str(error).lower()
        # Don't retry for data format/validation errors
        non_retryable_patterns = [
            "unable to match input value",
            "parse errors",
            "a value is required but not set",
            "invalid input",
            "validation error",
        ]
        return any(pattern in error_str for pattern in non_retryable_patterns)

    def _parse_payload(self, raw_record: Any) -> Optional[Dict]:
        """Parse and validate raw record payload."""
        payload = raw_record.payload

        if isinstance(payload, (bytes, bytearray)):
            try:
                payload = payload.decode("utf-8")
            except Exception:
                self.logger.warning("Skipping raw record: invalid bytes payload")
                return None

            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    self.logger.warning(
                        "Skipping raw record: invalid JSON payload string"
                    )
                    return None

        if (
            isinstance(payload, list)
            and len(payload) == 1
            and isinstance(payload[0], dict)
        ):
            payload = payload[0]

        if not isinstance(payload, dict):
            self.logger.warning("Skipping raw record: unexpected payload type")
            return None

        return payload

    def _detect_format(self, raw_record: Any, payload: Dict) -> str:
        """Detect data format (GraphQL vs REST)."""
        data_format = getattr(raw_record, "format", None)
        if not data_format:
            entity_id = payload.get("id", "")
            data_format = "graphql" if str(entity_id).startswith("gid://") else "rest"
        return data_format

    def _should_skip_update_by_canonical(self, canonical: Dict, data_type: str) -> bool:
        """Check if update should be skipped based on canonical data idempotency."""
        # For now, we'll let the data storage service handle idempotency
        # This could be enhanced to check against existing records if needed
        return False

    async def normalize_entities_batch(
        self, raw_records: List[Any], shop_id: str, data_type: str
    ) -> int:
        """Normalize a batch of entities (products, customers, collections) for efficiency.
        Returns number of successfully processed entities.
        """
        if not raw_records:
            return 0

        # Convert raw records to canonical data
        canonical_data_list = []
        for raw_record in raw_records:
            try:
                payload = self._parse_payload(raw_record)
                if not payload:
                    self.logger.warning(f"Skipping {data_type} record: no payload")
                    continue

                data_format = self._detect_format(raw_record, payload)
                adapter = get_adapter(data_format, data_type)
                canonical = adapter.to_canonical(payload, shop_id)
                canonical_data_list.append(canonical)
            except Exception as e:
                # Log the actual error for debugging
                self.logger.error(
                    f"Failed to convert {data_type} record to canonical: {e}"
                )
                continue

        # Use data storage service for batch upsert
        processed_count = await self.data_storage.upsert_entities_batch(
            data_type, canonical_data_list, shop_id
        )

        return processed_count


class OrderNormalizationService:
    """Handles order-specific normalization including line items."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.data_storage = NormalizationDataStorageService()

    async def normalize_order(
        self, raw_record: Any, shop_id: str, is_webhook: bool = True
    ) -> bool:
        """Normalize an order with its line items in a transaction."""
        try:
            # Parse payload and get canonical
            payload = self._parse_payload(raw_record)
            if not payload:
                return False

            data_format = self._detect_format(raw_record, payload)
            adapter = get_adapter(data_format, "orders")
            canonical = adapter.to_canonical(payload, shop_id)

            # Use data storage service for upsert
            success = await self.data_storage.upsert_order_with_line_items(
                canonical, shop_id
            )

            if not success:
                return False

            # Only publish events for webhook processing (not historical batch processing)
            if is_webhook:
                await self._publish_order_events(shop_id, canonical.get("orderId"))

            return True

        except Exception as e:
            self.logger.error(f"Order normalization failed: {e}")
            # For certain errors, we should not retry
            if self._should_not_retry(e):
                self.logger.warning(f"Skipping retry for non-retryable error: {e}")
            return False

    def _should_not_retry(self, error: Exception) -> bool:
        """Check if error should not be retried (data format issues, etc.)."""
        error_str = str(error).lower()
        # Don't retry for data format/validation errors
        non_retryable_patterns = [
            "unable to match input value",
            "parse errors",
            "a value is required but not set",
            "invalid input",
            "validation error",
        ]
        return any(pattern in error_str for pattern in non_retryable_patterns)

    async def normalize_orders_batch(
        self, raw_records: List[Any], shop_id: str, is_webhook: bool = False
    ) -> int:
        """Normalize a batch of orders in a single transaction for efficiency.
        Returns number of successfully processed orders.
        """
        if not raw_records:
            return 0

        self.logger.info(
            f"🔄 Processing {len(raw_records)} order records for shop {shop_id}"
        )

        # Convert raw records to canonical data
        canonical_data_list = []
        conversion_errors = 0

        for i, raw_record in enumerate(raw_records):
            try:
                self.logger.debug(f"Processing order record {i+1}/{len(raw_records)}")

                payload = self._parse_payload(raw_record)
                if not payload:
                    self.logger.warning(f"Skipping order record {i+1}: no payload")
                    conversion_errors += 1
                    continue

                data_format = self._detect_format(raw_record, payload)
                self.logger.debug(
                    f"Detected format: {data_format} for order record {i+1}"
                )

                adapter = get_adapter(data_format, "orders")
                canonical = adapter.to_canonical(payload, shop_id)

                # Validate canonical data
                if not canonical.get("order_id"):
                    self.logger.error(
                        f"Missing order_id in canonical data for record {i+1}: {list(canonical.keys())}"
                    )
                    conversion_errors += 1
                    continue

                canonical_data_list.append(canonical)
                self.logger.debug(
                    f"Successfully converted order record {i+1} to canonical"
                )

            except Exception as e:
                # Log the actual error for debugging
                self.logger.error(
                    f"Failed to convert order record {i+1} to canonical: {e}",
                    exc_info=True,
                )
                conversion_errors += 1
                continue

        self.logger.info(
            f"📊 Order conversion results: {len(canonical_data_list)} successful, {conversion_errors} failed"
        )

        if not canonical_data_list:
            self.logger.warning("No valid canonical order data to process")
            return 0

        # Use data storage service for batch upsert
        try:
            processed_count = await self.data_storage.upsert_orders_batch(
                canonical_data_list, shop_id
            )
            self.logger.info(
                f"✅ Order batch upsert completed: {processed_count} orders saved"
            )
            return processed_count
        except Exception as e:
            self.logger.error(f"Failed to upsert order batch: {e}", exc_info=True)
            return 0

        # Publish events after commit for webhook-only processing
        if is_webhook:
            for canonical in canonical_data_list:
                try:
                    await self._publish_order_events(shop_id, canonical.get("orderId"))
                except Exception:
                    continue

        return processed_count

    def _parse_payload(self, raw_record: Any) -> Optional[Dict]:
        """Parse order payload."""
        payload = raw_record.payload

        if isinstance(payload, (bytes, bytearray)):
            try:
                payload = payload.decode("utf-8")
            except Exception:
                return None

        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                return None

        if (
            isinstance(payload, list)
            and len(payload) == 1
            and isinstance(payload[0], dict)
        ):
            payload = payload[0]

        return payload if isinstance(payload, dict) else None

    def _detect_format(self, raw_record: Any, payload: Dict) -> str:
        """Detect order data format."""
        data_format = getattr(raw_record, "format", None)
        if not data_format:
            entity_id = payload.get("id", "")
            data_format = "graphql" if str(entity_id).startswith("gid://") else "rest"
        return data_format

    async def _publish_order_events(self, shop_id: str, order_id: str):
        """Publish events after successful order processing."""
        try:
            publisher = EventPublisher(kafka_settings.model_dump())
            await publisher.initialize()
            try:
                await publisher.publish_purchase_attribution_event(
                    {
                        "event_type": "purchase_ready_for_attribution",
                        "shop_id": shop_id,
                        "order_id": order_id,
                        "timestamp": now_utc().isoformat(),
                    }
                )
            finally:
                await publisher.close()
        except Exception as e:
            self.logger.error(f"Failed to publish order events: {e}")


class FeatureComputationService:
    """Handles feature computation triggers after normalization."""

    def __init__(self):
        self.logger = get_logger(__name__)

    async def trigger_feature_computation(self, shop_id: str, data_type: str):
        """Trigger feature computation after successful normalization."""
        try:
            self.logger.info(
                f"🎯 FeatureComputationService.trigger_feature_computation called for {data_type}"
            )

            if data_type in ["products", "orders", "customers", "collections"]:
                job_id = (
                    f"webhook_feature_compute_{shop_id}_{int(now_utc().timestamp())}"
                )

                metadata = {
                    "batch_size": 100,
                    "incremental": False,  # Use full processing for webhook-triggered events
                    "trigger_source": "webhook_normalization",
                    "entity_type": data_type,
                    "timestamp": now_utc().isoformat(),
                }

                self.logger.info(
                    f"📤 Publishing feature computation event via Kafka: job_id={job_id}, shop_id={shop_id}, data_type={data_type}"
                )

                # Use Kafka instead of Redis streams
                from app.core.messaging.event_publisher import EventPublisher
                from app.core.config.kafka_settings import kafka_settings

                publisher = EventPublisher(kafka_settings.model_dump())
                await publisher.initialize()

                try:
                    feature_event = {
                        "job_id": job_id,
                        "shop_id": shop_id,
                        "features_ready": False,
                        "metadata": metadata,
                        "event_type": "feature_computation",
                        "data_type": data_type,
                        "timestamp": now_utc().isoformat(),
                        "source": "normalization_consumer",
                    }

                    message_id = await publisher.publish_feature_computation_event(
                        feature_event
                    )
                    self.logger.info(
                        f"✅ Feature computation event published successfully via Kafka",
                        message_id=message_id,
                    )

                finally:
                    await publisher.close()

        except Exception as e:
            self.logger.error(f"Failed to trigger feature computation: {e}")


class EntityDeletionService:
    """Handles entity deletion (soft delete) logic."""

    def __init__(self):
        self.logger = get_logger(__name__)

    async def handle_entity_deletion(self, job: NormalizeJob, db):
        """Handle entity deletion by marking as inactive."""
        try:
            entity_config = {
                "products": {
                    "table": db.productdata,
                    "id_field": "productId",
                    "entity_name": "Product",
                },
                "collections": {
                    "table": db.collectiondata,
                    "id_field": "collectionId",
                    "entity_name": "Collection",
                },
                "customers": {
                    "table": db.customerdata,
                    "id_field": "customerId",
                    "entity_name": "Customer",
                },
                "orders": {
                    "table": db.orderdata,
                    "id_field": "orderId",
                    "entity_name": "Order",
                },
            }

            config = entity_config.get(job.data_type)
            if not config:
                self.logger.warning(
                    f"Unknown entity type for deletion: {job.data_type}"
                )
                return

            # Check if entity exists
            entity = await config["table"].find_first(
                where={"shopId": job.shop_id, config["id_field"]: str(job.shopify_id)}
            )

            if entity:
                # Mark as inactive
                await config["table"].update_many(
                    where={
                        "shopId": job.shop_id,
                        config["id_field"]: str(job.shopify_id),
                    },
                    data={"isActive": False, "updatedAt": now_utc()},
                )
                self.logger.info(
                    f"{config['entity_name']} {job.shopify_id} marked as inactive"
                )
            else:
                self.logger.warning(
                    f"No normalized {config['entity_name'].lower()} found for deletion"
                )

        except Exception as e:
            self.logger.error(f"Failed to handle entity deletion: {e}")
            raise


class NormalizationService:
    """Unified service that handles all normalization logic from the consumer."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.entity_service = EntityNormalizationService()
        self.order_service = OrderNormalizationService()
        self.feature_service = FeatureComputationService()
        self.deletion_service = EntityDeletionService()
        self.data_storage = NormalizationDataStorageService()

    async def process_rest_entity(
        self, shop_id: str, data_type: str, shopify_id: str
    ) -> bool:
        """Process a single REST entity by shopify_id (real-time)."""
        try:
            from app.core.database.session import get_session_context
            from app.core.database.models import (
                RawOrder,
                RawProduct,
                RawCustomer,
                RawCollection,
            )
            from sqlalchemy import select

            model_class = {
                "orders": RawOrder,
                "products": RawProduct,
                "customers": RawCustomer,
                "collections": RawCollection,
            }.get(data_type)

            if not model_class:
                self.logger.error(f"❌ Unknown data type for REST entity: {data_type}")
                return False

            async with get_session_context() as session:
                result = await session.execute(
                    select(model_class).where(
                        (model_class.shop_id == shop_id)
                        & (model_class.shopify_id == str(shopify_id))
                    )
                )
                raw = result.scalar_one_or_none()

            if not raw:
                self.logger.warning(
                    "REST entity not found in RAW",
                    shopify_id=shopify_id,
                    shop_id=shop_id,
                    data_type=data_type,
                )
                return False

            # Normalize according to data type
            if data_type == "orders":
                success = await self.order_service.normalize_order(
                    raw, shop_id, is_webhook=True
                )
            else:
                success = await self.entity_service.normalize_entity(
                    raw, shop_id, data_type
                )

            if success:
                # Update PipelineWatermark.lastNormalizedAt with raw.extractedAt if available
                if getattr(raw, "extracted_at", None):
                    await self.data_storage.upsert_watermark(
                        shop_id=shop_id,
                        data_type=data_type,
                        iso_time=raw.extracted_at.isoformat(),
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

            return success

        except Exception as e:
            self.logger.error(
                f"Failed REST entity normalization: {e}",
                shop_id=shop_id,
                data_type=data_type,
                shopify_id=shopify_id,
            )
            return False

    async def process_normalization_window(
        self,
        shop_id: str,
        data_type: str,
        format_type: str,
        start_time: Optional[str],
        end_time: Optional[str],
    ) -> bool:
        """Process normalization for a time window."""
        try:
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
                    await self.feature_service.trigger_feature_computation(shop_id, dt)
                    # Upsert watermark to the max of last_extracted and dt_end
                    if dt_end or last_extracted:
                        await self.data_storage.upsert_watermark(
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
                await self.feature_service.trigger_feature_computation(
                    shop_id, data_type
                )
                # Upsert watermark
                if res_end or last_extracted:
                    await self.data_storage.upsert_watermark(
                        shop_id, data_type, last_extracted or res_end, format_type
                    )
                self.logger.info(f"✅ Feature computation triggered for {data_type}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to process normalization window: {e}")
            return False

    async def _resolve_window_from_watermark(
        self,
        shop_id: str,
        data_type: str,
        start_time: Optional[str],
        end_time: Optional[str],
        format_type: Optional[str] = None,
    ) -> (Optional[str], Optional[str]):
        """Resolve normalization window using watermark when event window is missing."""
        if start_time and end_time:
            return start_time, end_time

        try:
            if format_type == "graphql":
                # Get watermark from data storage service
                watermark = await self.data_storage.get_watermark(
                    shop_id, data_type, format_type
                )

                # Start from last normalized, else last window start; end at last collected/window end, else now
                from datetime import datetime, timezone

                # Get all available timestamps
                last_normalized = (
                    watermark.last_normalized_at.isoformat()
                    if watermark and watermark.last_normalized_at
                    else None
                )
                last_window_start = (
                    watermark.last_window_start.isoformat()
                    if watermark and watermark.last_window_start
                    else None
                )
                last_collected = (
                    watermark.last_collected_at.isoformat()
                    if watermark and watermark.last_collected_at
                    else None
                )
                last_window_end = (
                    watermark.last_window_end.isoformat()
                    if watermark and watermark.last_window_end
                    else None
                )
                now_iso = datetime.now(timezone.utc).isoformat()

                # Collect all available timestamps and sort them
                available_timestamps = [
                    ts
                    for ts in [
                        last_normalized,
                        last_window_start,
                        last_collected,
                        last_window_end,
                    ]
                    if ts
                ]

                if available_timestamps:
                    # Use the earliest timestamp as start, latest as end
                    resolved_start = start_time or min(available_timestamps)
                    resolved_end = end_time or max(available_timestamps)
                else:
                    # Fallback to current time
                    resolved_start = start_time or now_iso
                    resolved_end = end_time or now_iso

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
                        if format_type == "graphql"
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

    async def _process_single_data_type(
        self,
        shop_id: str,
        data_type: str,
        format_type: str,
        start_time: Optional[str],
        end_time: Optional[str],
    ) -> Optional[str]:
        """Process a single data type - simple and efficient. Returns last processed extractedAt (ISO) if available."""
        import asyncio
        from app.core.database.session import get_session_context
        from app.core.database.models import (
            RawOrder,
            RawProduct,
            RawCustomer,
            RawCollection,
        )
        from sqlalchemy import select
        from datetime import datetime, timezone

        model_class = {
            "orders": RawOrder,
            "products": RawProduct,
            "customers": RawCustomer,
            "collections": RawCollection,
        }.get(data_type)

        if not model_class:
            self.logger.error(f"❌ Unknown data type: {data_type}")
            return None

        # Build query conditions
        query = select(model_class).where(model_class.shop_id == shop_id)

        # Always add time filters (required for all events)
        if start_time or end_time:
            # Use shopify_updated_at for GraphQL data, extracted_at otherwise
            time_field = (
                model_class.shopify_updated_at
                if format_type == "graphql"
                else model_class.extracted_at
            )

            # Parse ISO strings to timezone-aware UTC datetimes to avoid varchar comparisons
            def _parse_iso_to_aware(dt_str: Optional[str]) -> Optional[datetime]:
                if not dt_str:
                    return None
                try:
                    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                except Exception:
                    return None

            parsed_start = _parse_iso_to_aware(start_time)
            parsed_end = _parse_iso_to_aware(end_time)

            if parsed_start:
                query = query.where(time_field >= parsed_start)
            if parsed_end:
                query = query.where(time_field <= parsed_end)

        self.logger.info(
            f"🔍 Time filter on {'shopify_updated_at' if format_type == 'graphql' else 'extracted_at'}: {start_time} to {end_time}"
        )

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

            async with get_session_context() as session:
                result = await session.execute(
                    query.order_by(model_class.extracted_at.desc())
                    .offset(offset)
                    .limit(page_size)
                )
                raw_records = result.scalars().all()

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

            # Process records: batch for GraphQL, individual for REST
            if format_type == "graphql":
                # GraphQL batch processing for efficiency
                if data_type == "orders":
                    successful = await self.order_service.normalize_orders_batch(
                        raw_records, shop_id, is_webhook=False
                    )
                else:
                    successful = await self.entity_service.normalize_entities_batch(
                        raw_records, shop_id, data_type
                    )
                # Only advance window if something actually succeeded
                if successful > 0:
                    for raw_record in raw_records:
                        if getattr(raw_record, "extracted_at", None):
                            try:
                                last_extracted_iso = (
                                    max(
                                        last_extracted_iso or "",
                                        raw_record.extracted_at.isoformat(),
                                    )
                                    or raw_record.extracted_at.isoformat()
                                )
                            except Exception:
                                last_extracted_iso = raw_record.extracted_at.isoformat()
            else:
                # REST individual processing for real-time updates
                tasks = []
                for raw_record in raw_records:
                    if data_type == "orders":
                        task = self.order_service.normalize_order(
                            raw_record, shop_id, is_webhook=True
                        )
                    else:
                        task = self.entity_service.normalize_entity(
                            raw_record, shop_id, data_type
                        )
                    tasks.append(task)

                results = await asyncio.gather(*tasks, return_exceptions=True)
                successful = 0
                for raw_record, result in zip(raw_records, results):
                    if result is not None and not isinstance(result, Exception):
                        successful += 1
                        if getattr(raw_record, "extracted_at", None):
                            try:
                                last_extracted_iso = (
                                    max(
                                        last_extracted_iso or "",
                                        raw_record.extracted_at.isoformat(),
                                    )
                                    or raw_record.extracted_at.isoformat()
                                )
                            except Exception:
                                last_extracted_iso = raw_record.extracted_at.isoformat()
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
