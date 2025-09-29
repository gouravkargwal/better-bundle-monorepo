from __future__ import annotations

import json
from datetime import datetime
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
from app.core.database.session import get_session_context
from app.core.database.models.collection_data import CollectionData
from sqlalchemy import select

logger = get_logger(__name__)


class EntityNormalizationService:
    """
    Handles normalization of individual entities (products, customers, collections).

    This service converts raw Shopify data into canonical models that can be stored
    in our database. It handles both single entities and batch processing.
    """

    def __init__(self):
        self.logger = get_logger(__name__)
        self.data_storage = NormalizationDataStorageService()

    async def _get_existing_collection_products(
        self, shop_id: str, collection_id: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch existing products for a collection to preserve them during updates.

        This is used when updating collections to avoid losing existing product
        relationships that might not be included in the update payload.
        """
        try:
            async with get_session_context() as session:
                result = await session.execute(
                    select(CollectionData).where(
                        CollectionData.shop_id == shop_id,
                        CollectionData.collection_id == collection_id,
                    )
                )
                existing_collection = result.scalar_one_or_none()
                if existing_collection and existing_collection.products:
                    return existing_collection.products
                return []
        except Exception as e:
            self.logger.warning(f"Could not fetch existing collection products: {e}")
            return []

    async def normalize_entity(
        self, raw_record: Any, shop_id: str, data_type: str
    ) -> bool:
        """
        Normalize a single entity record from raw Shopify data.

        This is the main entry point for converting raw Shopify data into our
        canonical format and storing it in the database.

        Args:
            raw_record: Raw data from Shopify (GraphQL or REST format)
            shop_id: ID of the shop this data belongs to
            data_type: Type of entity (products, customers, collections, orders)

        Returns:
            bool: True if normalization succeeded, False otherwise
        """
        try:
            # Step 1: Parse and validate the raw data
            payload = self._parse_and_validate_payload(raw_record)
            if not payload:
                return False

            # Step 2: Convert to canonical format
            canonical_data = self._convert_to_canonical(payload, shop_id, data_type)
            if not canonical_data:
                return False

            # Step 3: Check if we should skip this update
            if self._should_skip_update(canonical_data, data_type):
                return True

            # Step 4: Store the canonical data
            return await self._store_canonical_data(data_type, canonical_data, shop_id)

        except Exception as e:
            self._log_normalization_error(e, raw_record, shop_id, data_type)
            return False

    def _parse_and_validate_payload(self, raw_record: Any) -> Optional[Dict]:
        """Parse and validate the raw record payload."""
        payload = self._parse_payload(raw_record)
        if not payload:
            self.logger.warning("Skipping entity: invalid or empty payload")
            return None
        return payload

    def _convert_to_canonical(
        self, payload: Dict, shop_id: str, data_type: str
    ) -> Optional[Dict]:
        """Convert raw payload to canonical format using the appropriate adapter."""
        try:
            # Detect data format and get the right adapter
            data_format = self._detect_format_from_payload(payload)
            adapter = get_adapter(data_format, data_type)

            # Convert to canonical format
            canonical = adapter.to_canonical(payload, shop_id)

            self.logger.info(
                "📦 Entity converted to canonical format",
                extra={
                    "data_type": data_type,
                    "entity_id": canonical.get(f"{data_type[:-1]}Id"),
                    "format": data_format,
                },
            )
            return canonical

        except Exception as e:
            self.logger.error(f"Failed to convert {data_type} to canonical format: {e}")
            return None

    def _should_skip_update(self, canonical_data: Dict, data_type: str) -> bool:
        """Check if this update should be skipped based on idempotency rules."""
        if self._should_skip_update_by_canonical(canonical_data, data_type):
            entity_id = canonical_data.get(f"{data_type[:-1]}Id")
            self.logger.info(f"Skipping {data_type} {entity_id} - no updates needed")
            return True
        return False

    async def _store_canonical_data(
        self, data_type: str, canonical_data: Dict, shop_id: str
    ) -> bool:
        """Store the canonical data in the database."""
        try:
            return await self.data_storage.upsert_entity(
                data_type, canonical_data, shop_id
            )
        except Exception as e:
            self.logger.error(f"Failed to store {data_type} data: {e}")
            return False

    def _log_normalization_error(
        self, error: Exception, raw_record: Any, shop_id: str, data_type: str
    ):
        """Log detailed error information for debugging."""
        self.logger.error(
            f"Entity normalization failed: {error}",
            extra={
                "data_type": data_type,
                "shop_id": shop_id,
                "error_type": type(error).__name__,
                "error_details": str(error),
                "raw_record_type": type(raw_record).__name__,
                "raw_record_keys": (
                    list(raw_record.keys())
                    if isinstance(raw_record, dict)
                    else "not_dict"
                ),
            },
        )

        # Check if this error should not be retried
        if self._should_not_retry(error):
            self.logger.warning(f"Skipping retry for non-retryable error: {error}")

    def _detect_format_from_payload(self, payload: Dict) -> str:
        """Detect data format from the payload content."""
        # Since we now use unified GraphQL collection, all data should be GraphQL format
        # But we keep this method for backward compatibility
        entity_id = payload.get("id", "")
        return "graphql" if str(entity_id).startswith("gid://") else "graphql"

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
        """
        Normalize a batch of entities for efficiency.

        This method processes multiple entities at once, which is much more efficient
        than processing them individually. It's used for historical data processing
        and bulk operations.

        Args:
            raw_records: List of raw Shopify data records
            shop_id: ID of the shop this data belongs to
            data_type: Type of entities being processed

        Returns:
            int: Number of successfully processed entities
        """
        if not raw_records:
            self.logger.info(f"No {data_type} records to process")
            return 0

        self.logger.info(
            f"🔄 Processing {len(raw_records)} {data_type} records in batch"
        )

        # Step 1: Convert all raw records to canonical format
        canonical_data_list = self._convert_batch_to_canonical(
            raw_records, shop_id, data_type
        )

        # Step 2: Store all canonical data in batch
        processed_count = await self._store_batch_canonical_data(
            data_type, canonical_data_list, shop_id
        )

        # Step 3: Log processing summary
        self._log_batch_summary(
            raw_records, canonical_data_list, processed_count, data_type, shop_id
        )

        return processed_count

    def _convert_batch_to_canonical(
        self, raw_records: List[Any], shop_id: str, data_type: str
    ) -> List[Dict[str, Any]]:
        """Convert a batch of raw records to canonical format."""
        canonical_data_list = []
        conversion_errors = 0

        for i, raw_record in enumerate(raw_records):
            try:
                canonical_data = self._convert_single_record_to_canonical(
                    raw_record, shop_id, data_type, record_index=i
                )
                if canonical_data:
                    canonical_data_list.append(canonical_data)
                else:
                    conversion_errors += 1
            except Exception as e:
                self._log_conversion_error(e, raw_record, data_type, shop_id, i)
                conversion_errors += 1

        self.logger.info(
            f"📊 Batch conversion results: {len(canonical_data_list)} successful, {conversion_errors} failed"
        )
        return canonical_data_list

    def _convert_single_record_to_canonical(
        self, raw_record: Any, shop_id: str, data_type: str, record_index: int
    ) -> Optional[Dict[str, Any]]:
        """Convert a single raw record to canonical format."""
        # Parse the payload
        payload = self._parse_payload(raw_record)
        if not payload:
            self.logger.warning(
                f"Skipping {data_type} record {record_index + 1}: no payload"
            )
            return None

        # Detect format and get adapter
        data_format = self._detect_format(raw_record, payload)
        adapter = get_adapter(data_format, data_type)

        # Convert to canonical
        return adapter.to_canonical(payload, shop_id)

    def _log_conversion_error(
        self,
        error: Exception,
        raw_record: Any,
        data_type: str,
        shop_id: str,
        record_index: int,
    ):
        """Log detailed error information for batch conversion failures."""
        self.logger.error(
            f"Failed to convert {data_type} record {record_index + 1} to canonical: {error}",
            extra={
                "data_type": data_type,
                "shop_id": shop_id,
                "record_index": record_index,
                "error_type": type(error).__name__,
                "error_details": str(error),
                "raw_record_keys": (
                    list(raw_record.keys())
                    if isinstance(raw_record, dict)
                    else "not_dict"
                ),
                "raw_record_sample": (
                    {k: str(v)[:100] for k, v in list(raw_record.items())[:3]}
                    if isinstance(raw_record, dict)
                    else str(raw_record)[:200]
                ),
            },
        )

    async def _store_batch_canonical_data(
        self, data_type: str, canonical_data_list: List[Dict], shop_id: str
    ) -> int:
        """Store a batch of canonical data in the database."""
        if not canonical_data_list:
            self.logger.warning(f"No canonical {data_type} data to store")
            return 0

        try:
            processed_count = await self.data_storage.upsert_entities_batch(
                data_type, canonical_data_list, shop_id
            )
            self.logger.info(
                f"✅ Stored {processed_count} {data_type} entities in batch"
            )
            return processed_count
        except Exception as e:
            self.logger.error(f"Failed to store {data_type} batch: {e}")
            return 0

    def _log_batch_summary(
        self,
        raw_records: List[Any],
        canonical_data_list: List[Dict],
        processed_count: int,
        data_type: str,
        shop_id: str,
    ):
        """Log a summary of the batch processing results."""
        total_records = len(raw_records)
        conversion_failed = total_records - len(canonical_data_list)
        storage_failed = len(canonical_data_list) - processed_count
        success_rate = (
            (processed_count / total_records * 100) if total_records > 0 else 0
        )

        self.logger.info(
            f"📊 Batch normalization summary for {data_type}",
            extra={
                "data_type": data_type,
                "shop_id": shop_id,
                "total_records": total_records,
                "conversion_successful": len(canonical_data_list),
                "conversion_failed": conversion_failed,
                "storage_successful": processed_count,
                "storage_failed": storage_failed,
                "overall_success_rate": f"{success_rate:.1f}%",
            },
        )


class OrderNormalizationService:
    """
    Handles order-specific normalization including line items.

    Orders are more complex than other entities because they contain line items
    that need to be processed and stored separately. This service handles both
    individual order processing and batch processing of orders.
    """

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

            if data_type in ["products", "orders", "customers", "collections", "all"]:
                job_id = (
                    f"webhook_feature_compute_{shop_id}_{int(now_utc().timestamp())}"
                )

                metadata = {
                    "batch_size": 100,
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

    async def handle_entity_deletion(self, job: Dict[str, Any], db=None):
        """Handle entity deletion by marking as inactive using SQLAlchemy."""
        try:
            from app.core.database.session import get_transaction_context
            from app.core.database.models import (
                ProductData,
                CollectionData,
                CustomerData,
                OrderData,
            )
            from sqlalchemy import update

            entity_config = {
                "products": {
                    "model": ProductData,
                    "id_field": "product_id",
                    "entity_name": "Product",
                },
                "collections": {
                    "model": CollectionData,
                    "id_field": "collection_id",
                    "entity_name": "Collection",
                },
                "customers": {
                    "model": CustomerData,
                    "id_field": "customer_id",
                    "entity_name": "Customer",
                },
                "orders": {
                    "model": OrderData,
                    "id_field": "order_id",
                    "entity_name": "Order",
                },
            }

            data_type = job.get("data_type")
            config = entity_config.get(data_type)
            if not config:
                self.logger.warning(f"Unknown entity type for deletion: {data_type}")
                return

            shop_id = job.get("shop_id")
            shopify_id = job.get("shopify_id")

            if not shop_id or not shopify_id:
                self.logger.error("Missing shop_id or shopify_id for deletion")
                return

            # Mark as inactive using SQLAlchemy
            async with get_transaction_context() as session:
                model_class = config["model"]
                id_field = config["id_field"]

                # Update the entity to mark as inactive
                result = await session.execute(
                    update(model_class)
                    .where(
                        (model_class.shop_id == shop_id)
                        & (getattr(model_class, id_field) == str(shopify_id))
                    )
                    .values(is_active=False, updated_at=now_utc())
                )

                if result.rowcount > 0:
                    self.logger.info(
                        f"{config['entity_name']} {shopify_id} marked as inactive"
                    )
                else:
                    self.logger.warning(
                        f"No normalized {config['entity_name'].lower()} found for deletion"
                    )

        except Exception as e:
            self.logger.error(f"Failed to handle entity deletion: {e}")
            raise


class NormalizationService:
    """
    Unified service that handles all normalization logic from the consumer.

    This is the main entry point for all normalization operations. It coordinates
    between different specialized services to handle:
    - Individual entity processing (webhooks)
    - Batch processing (historical data)
    - Feature computation triggers
    - Entity deletion
    """

    def __init__(self):
        self.logger = get_logger(__name__)
        # Initialize specialized services
        self.entity_service = EntityNormalizationService()
        self.order_service = OrderNormalizationService()
        self.feature_service = FeatureComputationService()
        self.deletion_service = EntityDeletionService()
        self.data_storage = NormalizationDataStorageService()

    async def normalize_data(
        self, shop_id: str, data_type: str, normalization_params: Dict[str, Any]
    ) -> bool:
        """
        Unified normalization - no complex mode switching
        Just process data chunks like a proper Kafka system
        """
        try:
            # Check if this is a webhook event with specific IDs
            if normalization_params.get("shopify_id"):
                return await self._execute_webhook_normalization(
                    shop_id, data_type, normalization_params
                )
            else:
                return await self._execute_batch_normalization(
                    shop_id, data_type, normalization_params
                )

        except Exception as e:
            self.logger.error(
                f"❌ Error in unified normalization: {e}",
                shop_id=shop_id,
                data_type=data_type,
                exc_info=True,
            )
            return False

    async def _execute_webhook_normalization(
        self, shop_id: str, data_type: str, params: Dict[str, Any]
    ) -> bool:
        """Execute webhook normalization for specific entity."""
        shopify_id = params["shopify_id"]

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
                self.logger.error(f"❌ Unknown data type for entity: {data_type}")
                return False

            # Extract numeric ID from GraphQL ID for search
            # GraphQL IDs are stored as "gid://shopify/Product/7195111358549"
            # We need to search for the numeric part "7195111358549"
            numeric_id = self._extract_numeric_id_from_graphql(shopify_id)

            async with get_session_context() as session:
                # Search by extracting numeric ID from stored GraphQL IDs
                result = await session.execute(
                    select(model_class).where(
                        (model_class.shop_id == shop_id)
                        & (model_class.shopify_id.like(f"%/{numeric_id}"))
                    )
                )
                raw = result.scalar_one_or_none()

            if not raw:
                self.logger.warning(
                    "Entity not found in RAW",
                    shopify_id=shopify_id,
                    numeric_id=numeric_id,
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
                    f"✅ Entity normalized",
                    extra={
                        "shop_id": shop_id,
                        "data_type": data_type,
                        "shopify_id": shopify_id,
                    },
                )

            return success

        except Exception as e:
            self.logger.error(
                f"Failed entity normalization: {e}",
                shop_id=shop_id,
                data_type=data_type,
                shopify_id=shopify_id,
            )
            return False

    def _extract_numeric_id_from_graphql(self, shopify_id: str) -> str:
        """Extract numeric ID from GraphQL ID or return as-is if already numeric."""
        # If it's already a numeric ID, return as-is
        if shopify_id.isdigit():
            return shopify_id

        # If it's a GraphQL ID like "gid://shopify/Product/7195111358549", extract the numeric part
        if "/" in shopify_id:
            return shopify_id.split("/")[-1]

        # Fallback: return as-is
        return shopify_id

    async def _execute_batch_normalization(
        self, shop_id: str, data_type: str, params: Dict[str, Any]
    ) -> bool:
        """Execute batch normalization for time-based processing."""
        format_type = params.get("format", "graphql")

        self.logger.info(
            f"📚 Starting batch processing for {data_type}",
            extra={"shop_id": shop_id, "data_type": data_type},
        )

        # Process all data for the shop - no complex mode switching
        return await self.process_normalization_window(
            shop_id=shop_id,
            data_type=data_type,
            format_type=format_type,
        )

    async def process_normalization_window(
        self,
        shop_id: str,
        data_type: str,
        format_type: str,
    ) -> bool:
        """
        Unified normalization processing - no complex mode switching
        Just process data chunks like a proper Kafka system
        """
        try:
            self.logger.info(f"🔄 Processing {data_type} for shop {shop_id}")

            # Step 1: Determine what data types to process
            data_types_to_process = self._get_data_types_to_process(data_type)

            # Step 2: Process each data type
            for dt in data_types_to_process:
                await self._process_single_data_type(
                    shop_id, dt, format_type, None, None
                )

            # Step 3: Trigger feature computation
            await self._trigger_feature_computation_for_data_types(shop_id, data_type)

            return True

        except Exception as e:
            self.logger.error(f"Failed to process normalization window: {e}")
            return False

    def _get_data_types_to_process(self, data_type: str) -> List[str]:
        """Determine which data types to process based on the input."""
        if data_type == "all":
            return ["products", "orders", "customers", "collections"]
        return [data_type]

    async def _trigger_feature_computation_for_data_types(
        self, shop_id: str, data_type: str
    ):
        """Trigger feature computation for the processed data types."""
        await self.feature_service.trigger_feature_computation(shop_id, data_type)
        self.logger.info(f"✅ Feature computation triggered for {data_type}")

    async def _process_single_data_type(
        self,
        shop_id: str,
        data_type: str,
        format_type: str,
        start_time: Optional[str],
        end_time: Optional[str],
    ) -> Optional[str]:
        """
        Process a single data type with pagination and batch processing.

        This method handles the core logic of fetching raw data from the database
        and processing it in batches. It's designed to be efficient and handle
        large amounts of data without running out of memory.

        Returns:
            Optional[str]: Last processed timestamp in ISO format
        """
        # Step 1: Get the database model for this data type
        model_class = self._get_model_class_for_data_type(data_type)
        if not model_class:
            return None

        # Step 2: Build a simple query for all data for this shop
        from sqlalchemy import select

        query = select(model_class).where(model_class.shop_id == shop_id)

        # Step 3: Process data in batches
        await self._process_data_in_batches(
            query, model_class, shop_id, data_type, format_type
        )

        self.logger.info(f"✅ Normalization completed for {data_type}")
        return None

    def _get_model_class_for_data_type(self, data_type: str):
        """Get the database model class for the given data type."""
        from app.core.database.models import (
            RawOrder,
            RawProduct,
            RawCustomer,
            RawCollection,
        )

        model_mapping = {
            "orders": RawOrder,
            "products": RawProduct,
            "customers": RawCustomer,
            "collections": RawCollection,
        }

        model_class = model_mapping.get(data_type)
        if not model_class:
            self.logger.error(f"❌ Unknown data type: {data_type}")
            return None

        return model_class

    async def _process_data_in_batches(
        self, query, model_class, shop_id: str, data_type: str, format_type: str
    ) -> None:
        """Process data in batches with pagination."""
        from app.core.database.session import get_session_context

        page_size = 100
        offset = 0
        total_processed = 0

        while True:
            # Fetch batch of records
            raw_records = await self._fetch_batch_of_records(
                query, model_class, offset, page_size
            )

            if not raw_records:
                break

            # Process the batch
            successful = await self._process_batch_of_records(
                raw_records, shop_id, data_type, format_type
            )

            # Update tracking variables
            total_processed += successful

            # Log batch results
            self._log_batch_results(
                data_type, successful, len(raw_records), total_processed, offset
            )

            # Check if we should continue
            if len(raw_records) < page_size:
                break

            offset += page_size

        self._log_processing_complete(data_type, total_processed)

    async def _fetch_batch_of_records(
        self, query, model_class, offset: int, page_size: int
    ):
        """Fetch a batch of records from the database."""
        from app.core.database.session import get_session_context

        self.logger.info(
            "📥 Fetching raw batch",
            extra={
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
            return result.scalars().all()

    async def _process_batch_of_records(
        self, raw_records, shop_id: str, data_type: str, format_type: str
    ) -> int:
        """Process a batch of records using the appropriate service."""
        self.logger.info(
            "📄 Processing batch",
            extra={
                "data_type": data_type,
                "batch_count": len(raw_records),
            },
        )

        if format_type == "graphql":
            # Use batch processing for efficiency
            if data_type == "orders":
                return await self.order_service.normalize_orders_batch(
                    raw_records, shop_id, is_webhook=False
                )
            else:
                return await self.entity_service.normalize_entities_batch(
                    raw_records, shop_id, data_type
                )
        else:
            # Use individual processing for real-time updates
            return await self._process_records_individually(
                raw_records, shop_id, data_type
            )

    async def _process_records_individually(
        self, raw_records, shop_id: str, data_type: str
    ) -> int:
        """Process records individually for real-time updates."""
        import asyncio

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
        for result in results:
            if result is not None and not isinstance(result, Exception):
                successful += 1

        return successful

    def _log_batch_results(
        self,
        data_type: str,
        successful: int,
        batch_size: int,
        total_processed: int,
        offset: int,
    ):
        """Log the results of processing a batch."""
        failures = batch_size - successful
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
                "batch_size": batch_size,
                "cumulative_processed": total_processed,
            },
        )

    def _log_processing_complete(self, data_type: str, total_processed: int):
        """Log the completion of processing."""
        self.logger.info(
            "🎉 Normalization complete",
            extra={
                "data_type": data_type,
                "total_processed": total_processed,
            },
        )
