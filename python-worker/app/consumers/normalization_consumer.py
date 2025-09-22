from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.consumers.base_consumer import BaseConsumer
from app.core.logging import get_logger
from app.shared.constants.redis import NORMALIZATION_STREAM, NORMALIZATION_GROUP
from app.domains.shopify.normalization.factory import get_adapter
from app.domains.shopify.normalization.canonical_models import NormalizeJob
from app.core.database.simple_db_client import get_database
from app.core.redis_client import streams_manager
from app.core.stream_manager import stream_manager, StreamType
from app.shared.helpers import now_utc
from prisma import Json

logger = get_logger(__name__)


class PersistenceMapper:
    """Declarative mapper: canonical DTO -> Prisma input data.

    Centralizes DB-specific concerns: relations, JSON fields, timestamps, and field cleanup.
    """

    # Per-entity configuration
    CONFIG = {
        "products": {
            "json_fields": {
                "metafields",
                "tags",
                "variants",
                "images",
                "media",
                "options",
                "noteAttributes",
                "extras",
            },
            "timestamp_map": {
                "shopifyUpdatedAt": "updatedAt",
                "shopifyCreatedAt": "createdAt",
            },
            "remove_fields": {
                "entityId",
                "canonicalVersion",
                "originalGid",
                "customerCreatedAt",
                "customerUpdatedAt",
                "isActive",
                "shopId",
            },
        },
        "customers": {
            "json_fields": {
                "metafields",
                "tags",
                "addresses",
                "defaultAddress",
                "customerDefaultAddress",
                "location",
                "noteAttributes",
                "extras",
            },
            "timestamp_map": {
                "shopifyUpdatedAt": "updatedAt",
                "shopifyCreatedAt": "createdAt",
            },
            "remove_fields": {
                "entityId",
                "canonicalVersion",
                "originalGid",
                "customerCreatedAt",
                "customerUpdatedAt",
                "isActive",
                "shopId",
            },
        },
        "collections": {
            "json_fields": {
                "metafields",
                "tags",
                "images",
                "noteAttributes",
                "extras",
            },
            "timestamp_map": {
                "shopifyUpdatedAt": "updatedAt",
                "shopifyCreatedAt": "createdAt",
            },
            "remove_fields": {
                "entityId",
                "canonicalVersion",
                "originalGid",
                "customerCreatedAt",
                "customerUpdatedAt",
                "isActive",
                "shopId",
            },
        },
        "orders": {
            "json_fields": {
                "metafields",
                "tags",
                "discountApplications",
                "fulfillments",
                "transactions",
                "shippingAddress",
                "billingAddress",
                "defaultAddress",
                "customerDefaultAddress",
                "location",
                "noteAttributes",
                "extras",
            },
            "timestamp_map": {
                "shopifyUpdatedAt": "updatedAt",
                "shopifyCreatedAt": "createdAt",
            },
            "remove_fields": {
                "entityId",
                "canonicalVersion",
                "originalGid",
                "customerCreatedAt",
                "customerUpdatedAt",
                "isActive",
                "refunds",
                "lineItems",
                "shopId",
            },
        },
    }

    @staticmethod
    def apply(entity: str, canonical: Dict[str, Any], shop_id: str) -> Dict[str, Any]:
        cfg = PersistenceMapper.CONFIG.get(entity, {})
        main_data: Dict[str, Any] = canonical.copy()

        # Use relation connect syntax for all entities
        main_data["shop"] = {"connect": {"id": shop_id}}

        # Timestamp mapping
        ts_map: Dict[str, str] = cfg.get("timestamp_map", {})
        for src, dst in ts_map.items():
            if src in main_data:
                main_data[dst] = main_data[src]

        # Ensure required timestamps
        if "createdAt" not in main_data or main_data.get("createdAt") is None:
            main_data["createdAt"] = now_utc()
        if "updatedAt" not in main_data or main_data.get("updatedAt") is None:
            main_data["updatedAt"] = now_utc()

        # Provide safe defaults for known json-ish nullable fields
        json_default_fields = {
            "customerDefaultAddress",
            "defaultAddress",
            "shippingAddress",
            "billingAddress",
            "location",
        }
        for jf in json_default_fields:
            if jf in main_data and (main_data[jf] is None or main_data[jf] == {}):
                main_data[jf] = {}

        # Wrap configured JSON fields using prisma.Json
        json_fields: set = cfg.get("json_fields", set())
        for field in json_fields:
            if field in main_data and main_data[field] is not None:
                try:
                    main_data[field] = Json(main_data[field])
                except (TypeError, ValueError):
                    # Fallback to empty container of appropriate type
                    if isinstance(main_data[field], (list, tuple)):
                        main_data[field] = Json([])
                    elif isinstance(main_data[field], dict):
                        main_data[field] = Json({})
                    else:
                        main_data[field] = None

        # Remove internal/canonical-only fields and scalar shopId
        for rf in cfg.get("remove_fields", set()):
            main_data.pop(rf, None)

        return main_data


class EntityNormalizationService:
    """Handles core entity normalization logic (products, customers, collections)."""

    def __init__(self):
        self.logger = get_logger(__name__)

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

            # Prepare main data
            main_data = self._prepare_main_data(canonical, shop_id, data_type)
            if not main_data:
                return False

            # Get database and table
            db = await get_database()
            main_table = self._get_main_table(db, data_type)

            # Check for existing record and idempotency
            id_field = f"{data_type[:-1]}Id"
            id_value = canonical.get(id_field)
            existing = await main_table.find_first(
                where={"shopId": shop_id, id_field: id_value}
            )

            if self._should_skip_update(existing, canonical):
                # Even if we skip normalization, we should still trigger feature computation
                # because new behavioral data might have been collected
                self.logger.info(
                    f"Skipping normalization for {data_type} {canonical.get(f'{data_type[:-1]}Id')} - no updates needed, but triggering feature computation"
                )
                return True

            # Upsert main record
            if existing:
                await main_table.update(
                    where={"id": existing.id},
                    data=main_data,
                )
            else:
                await main_table.create(data=main_data)

            return True

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

    def _prepare_main_data(
        self, canonical: Dict, shop_id: str, data_type: str
    ) -> Optional[Dict]:
        """Prepare main table data from canonical structure using declarative mapper."""
        # Validate presence of primary id
        id_field = f"{data_type[:-1]}Id"
        if not canonical.get(id_field):
            self.logger.error(f"Missing primary id for canonical record: {id_field}")
            return None

        # Apply declarative mapping
        main_data = PersistenceMapper.apply(data_type, canonical, shop_id)
        return main_data

    def _get_main_table(self, db, data_type: str):
        """Get the appropriate main table for data type."""
        table_map = {
            "orders": db.orderdata,
            "products": db.productdata,
            "customers": db.customerdata,
            "collections": db.collectiondata,
        }
        return table_map[data_type]

    def _should_skip_update(self, existing, canonical: Dict) -> bool:
        """Check if update should be skipped based on idempotency."""
        if (
            not existing
            or not hasattr(existing, "shopifyUpdatedAt")
            or not existing.shopifyUpdatedAt
        ):
            return False

        incoming_updated_at = canonical.get("shopifyUpdatedAt")
        if not incoming_updated_at:
            return False

        return incoming_updated_at <= existing.shopifyUpdatedAt

    def _serialize_json_fields(self, main_data: Dict[str, Any]):
        """Convert JSON fields to prisma.Json() for proper Prisma handling."""
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
                try:
                    # Use prisma.Json() to properly handle JSON fields
                    main_data[field] = Json(main_data[field])
                except (TypeError, ValueError):
                    if isinstance(main_data[field], (list, tuple)):
                        main_data[field] = Json([])
                    elif isinstance(main_data[field], dict):
                        main_data[field] = Json({})
            else:
                main_data[field] = None

    def _clean_internal_fields(self, main_data: Dict):
        """Remove internal/canonical fields not in DB schema."""
        fields_to_remove = [
            "entityId",
            "canonicalVersion",
            "originalGid",
            "customerCreatedAt",
            "customerUpdatedAt",
            "isActive",
        ]
        for field in fields_to_remove:
            main_data.pop(field, None)


class OrderNormalizationService:
    """Handles order-specific normalization including line items."""

    def __init__(self):
        self.logger = get_logger(__name__)

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

            # Extract line items BEFORE applying PersistenceMapper
            line_items = canonical.get("lineItems", [])

            # Prepare main data
            main_data = await self._prepare_order_data(canonical, shop_id)
            if not main_data:
                return False

            # Process in transaction
            db = await get_database()
            order_record_id = None

            async with db.tx() as transaction:
                # Upsert main order record
                order_table = transaction.orderdata
                existing = await order_table.find_first(
                    where={"shopId": shop_id, "orderId": canonical.get("orderId")}
                )

                if existing:
                    await order_table.update(
                        where={"id": existing.id},
                        data=main_data,
                    )
                    order_record_id = existing.id
                else:
                    created_record = await order_table.create(data=main_data)
                    order_record_id = created_record.id

                # Create line items
                if line_items:
                    await self._create_line_items(
                        transaction, order_record_id, line_items
                    )

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

    async def _prepare_order_data(
        self, canonical: Dict, shop_id: str
    ) -> Optional[Dict]:
        """Prepare order data for database using declarative mapper."""
        # Ensure shop exists (connect will fail otherwise)
        db = await get_database()
        shop_exists = await db.shop.find_first(where={"id": shop_id})
        if not shop_exists:
            self.logger.error(f"Shop {shop_id} not found")
            return None

        if not canonical.get("orderId"):
            self.logger.error("Missing orderId in canonical data")
            return None

        main_data = PersistenceMapper.apply("orders", canonical, shop_id)
        return main_data

    async def _create_line_items(
        self, db_client: Any, order_record_id: str, line_items: List[Any]
    ):
        """Create line items for an order."""
        if not line_items:
            return

        try:
            # Clear existing line items
            await db_client.lineitemdata.delete_many(where={"orderId": order_record_id})

            # Prepare bulk data
            bulk_data = []
            for item in line_items:
                try:
                    line_item_data = {
                        "orderId": order_record_id,
                        "productId": item.get("productId"),
                        "variantId": item.get("variantId"),
                        "title": item.get("title"),
                        "quantity": int(item.get("quantity", 0)),
                        "price": float(item.get("price", 0.0)),
                        "properties": Json(item.get("properties", {})),
                    }
                    bulk_data.append(line_item_data)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Skipping invalid line item: {e}")
                    continue

            # Bulk create
            if bulk_data:
                await db_client.lineitemdata.create_many(data=bulk_data)

        except Exception as e:
            self.logger.error(f"Failed to create line items: {e}")

    async def _publish_order_events(self, shop_id: str, order_id: str):
        """Publish events after successful order processing."""
        try:
            await stream_manager.publish_to_domain(
                StreamType.PURCHASE_ATTRIBUTION,
                {
                    "event_type": "purchase_ready_for_attribution",
                    "shop_id": shop_id,
                    "order_id": order_id,
                    "timestamp": now_utc().isoformat(),
                },
            )
        except Exception as e:
            self.logger.error(f"Failed to publish order events: {e}")

    def _serialize_json_fields(self, main_data: Dict[str, Any]):
        """Serialize JSON fields using prisma.Json() for proper Prisma handling."""
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
                try:
                    # Use prisma.Json() to properly handle JSON fields
                    main_data[field] = Json(main_data[field])
                except (TypeError, ValueError):
                    if isinstance(main_data[field], (list, tuple)):
                        main_data[field] = Json([])
                    elif isinstance(main_data[field], dict):
                        main_data[field] = Json({})
                    else:
                        main_data[field] = None

    def _clean_internal_fields(self, main_data: Dict):
        """Remove internal fields."""
        fields_to_remove = [
            "entityId",
            "canonicalVersion",
            "originalGid",
            "customerCreatedAt",
            "customerUpdatedAt",
            "isActive",
        ]
        for field in fields_to_remove:
            main_data.pop(field, None)


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


class NormalizationConsumer(BaseConsumer):
    """Orchestrates normalization using specialized services."""

    def __init__(self) -> None:
        super().__init__(
            stream_name=NORMALIZATION_STREAM,
            consumer_group=NORMALIZATION_GROUP,
            consumer_name="normalization-consumer",
            batch_size=50,
            poll_timeout=1000,
            max_retries=3,
            retry_delay=0.5,
            circuit_breaker_failures=3,  # Open circuit after 3 consecutive failures
            circuit_breaker_timeout=300,  # Wait 5 minutes before attempting reset
        )
        self.logger = get_logger(__name__)

        # Initialize services
        self.entity_service = EntityNormalizationService()
        self.order_service = OrderNormalizationService()
        self.feature_service = FeatureComputationService()
        self.deletion_service = EntityDeletionService()

    async def _process_single_message(self, message: Dict[str, Any]):
        try:
            self.logger.info(f"🔄 Processing normalization message: {message}")

            payload = message.get("data") or message
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    pass
            event_type = payload.get("event_type")

            self.logger.info(f"📋 Extracted event_type: {event_type}")

            if event_type == "normalize_entity":
                self.logger.info("📥 Processing normalize_entity event")
                await self._handle_normalize_entity(payload)
            elif event_type == "normalize_batch":
                self.logger.info("📥 Processing normalize_batch event")
                await self._handle_normalize_batch(payload)
            else:
                # Ignore non-normalization messages
                self.logger.info(f"⏭️ Ignoring non-normalization message: {event_type}")
                return

        except Exception as e:
            self.logger.error(f"Normalization failed: {e}")
            raise

    async def _handle_normalize_entity(self, payload: Dict[str, Any]):
        """Handle single entity normalization (webhooks)."""
        job = NormalizeJob(**payload)
        db = await get_database()

        # Check if this is a deletion event
        original_event_type = payload.get("original_event_type")
        is_deletion_event = original_event_type in [
            "product_deleted",
            "collection_deleted",
            "customer_redacted",
        ]

        if is_deletion_event:
            await self.deletion_service.handle_entity_deletion(job, db)
            await self.feature_service.trigger_feature_computation(
                job.shop_id, job.data_type
            )
            return

        # Find raw record
        raw_table = {
            "orders": db.raworder,
            "products": db.rawproduct,
            "customers": db.rawcustomer,
            "collections": db.rawcollection,
        }[job.data_type]

        raw = await raw_table.find_first(
            where={"shopifyId": str(job.shopify_id), "shopId": job.shop_id}
        )

        if not raw:
            self.logger.warning(
                "Raw record not found for non-deletion event",
                shopify_id=job.shopify_id,
                shop_id=job.shop_id,
                event_type=original_event_type,
            )
            return

        try:
            # Use appropriate service based on data type
            if job.data_type == "orders":
                success = await self.order_service.normalize_order(raw, job.shop_id)
            else:
                success = await self.entity_service.normalize_entity(
                    raw, job.shop_id, job.data_type
                )

            # Always trigger feature computation, even if normalization was skipped
            # This ensures features are updated when new behavioral data is collected
            await self.feature_service.trigger_feature_computation(
                job.shop_id, job.data_type
            )

        except Exception as e:
            self.logger.error(f"Normalization failed: {e}")
            # Log circuit breaker status for monitoring
            self._log_circuit_breaker_status()
            raise

    def _log_circuit_breaker_status(self):
        """Log current circuit breaker status for monitoring."""
        status = self.get_circuit_breaker_status()
        self.logger.warning(
            f"Circuit breaker status: {status['state']}, "
            f"failures: {status['failure_count']}, "
            f"last failure: {status.get('last_failure_time', 'None')}"
        )

    def reset_circuit_breaker_manually(self):
        """Manually reset circuit breaker (for admin use)."""
        self.reset_circuit_breaker()
        self.logger.info("Circuit breaker manually reset")

    async def _handle_normalize_batch(self, payload: Dict[str, Any]):
        """Handle batch normalization with pagination."""
        self.logger.info(f"🔄 Starting batch normalization: {payload}")

        shop_id = payload.get("shop_id")
        data_type = payload.get("data_type")
        fmt = payload.get("format")
        since = payload.get("since")
        page_size = payload.get("page_size", 100)

        self.logger.info(
            f"📋 Batch params: shop_id={shop_id}, data_type={data_type}, format={fmt}, since={since}, page_size={page_size}"
        )

        if not all([shop_id, data_type]):
            self.logger.error(
                "Invalid normalize_batch job: missing required fields", payload=payload
            )
            return

        # Check if we need to process all data types
        if data_type == "all":
            # Process all data types from the payload
            data_types = payload.get(
                "data_types", ["products", "orders", "customers", "collections"]
            )
            self.logger.info(f"🔄 Processing all data types: {data_types}")

            # Process each data type
            for dt in data_types:
                self.logger.info(f"🔄 Processing {dt} data type")
                await self._process_normalize_batch_recursive(
                    shop_id, dt, fmt, since, page_size
                )

            # Trigger feature computation only once after all data types are complete
            self.logger.info(
                f"🚀 All data types complete, triggering feature computation"
            )
            # Trigger feature computation for products (primary data type) which will process all data
            await self.feature_service.trigger_feature_computation(shop_id, "products")
        else:
            # Process single data type
            await self._process_normalize_batch_recursive(
                shop_id, data_type, fmt, since, page_size
            )

            # After all batches are complete, trigger feature computation
            self.logger.info(
                f"🚀 All batches complete for {data_type}, triggering feature computation"
            )
            await self.feature_service.trigger_feature_computation(shop_id, data_type)

    async def _process_normalize_batch_recursive(
        self, shop_id: str, data_type: str, fmt: str, since: str, page_size: int
    ):
        """Recursively process all batches for a data type without firing events"""

        db = await get_database()
        raw_table = {
            "orders": db.raworder,
            "products": db.rawproduct,
            "customers": db.rawcustomer,
            "collections": db.rawcollection,
        }[data_type]

        # Build query conditions
        where_conditions = {"shopId": shop_id}
        if isinstance(since, str) and since.lower() in ("none", "null", ""):
            since = None

        if since:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
            where_conditions["shopifyUpdatedAt"] = {"gt": since_dt}

        # Fetch page of raw records
        raw_records = await raw_table.find_many(
            where=where_conditions,
            order=[{"shopifyUpdatedAt": "asc"}, {"id": "asc"}],
            take=page_size,
        )

        if not raw_records:
            return

        # Process each record concurrently
        import asyncio

        semaphore = asyncio.Semaphore(20)

        async def process_record(raw_record):
            async with semaphore:
                try:
                    if fmt == "graphql":
                        setattr(raw_record, "format", "graphql")

                    # Use appropriate service
                    if data_type == "orders":
                        success = await self.order_service.normalize_order(
                            raw_record, shop_id, is_webhook=False
                        )
                    else:
                        success = await self.entity_service.normalize_entity(
                            raw_record, shop_id, data_type
                        )

                    return raw_record.shopifyUpdatedAt if success else None
                except Exception as e:
                    self.logger.error(f"Failed to normalize record: {e}")
                    return None

        tasks = [process_record(raw_record) for raw_record in raw_records]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter successful results
        successful_results = [
            r for r in results if r is not None and not isinstance(r, Exception)
        ]
        last_updated_at = max(successful_results) if successful_results else None

        # Log batch results
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

        # Don't trigger feature computation after each batch - only at the end

        # Continue pagination if needed - handle directly without events
        if len(raw_records) == page_size:
            self.logger.info(
                f"📄 More records available, continuing pagination for {data_type}"
            )
            # Recursively call the same method for next batch
            await self._process_normalize_batch_recursive(
                shop_id,
                data_type,
                fmt,
                last_updated_at.isoformat() if last_updated_at else None,
                page_size,
            )
        else:
            # Entire normalization process is complete for this data type
            self.logger.info(f"✅ {data_type} normalization process complete")

        # Update watermark
        if last_updated_at is not None:
            await db.normalizationwatermark.upsert(
                where={"shopId_dataType": {"shopId": shop_id, "dataType": data_type}},
                data={
                    "update": {"lastNormalizedAt": last_updated_at},
                    "create": {
                        "shopId": shop_id,
                        "dataType": data_type,
                        "lastNormalizedAt": last_updated_at,
                    },
                },
            )
