from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional
from datetime import datetime

from app.core.logging import get_logger
from app.domains.shopify.normalization.factory import get_adapter
from app.domains.shopify.normalization.canonical_models import NormalizeJob
from app.core.database.session import get_session_context, get_transaction_context
from app.core.database.models import (
    Shop,
    OrderData,
    LineItemData,
    ProductData,
    CustomerData,
    CollectionData,
)

# Removed enum imports - using string values directly
from sqlalchemy import select, update, delete, insert
from app.core.messaging.event_publisher import EventPublisher
from app.core.config.kafka_settings import kafka_settings
from app.shared.helpers import now_utc

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

        # Set shop_id directly for SQLAlchemy
        main_data["shop_id"] = shop_id

        # Timestamp mapping
        ts_map: Dict[str, str] = cfg.get("timestamp_map", {})
        for src, dst in ts_map.items():
            if src in main_data:
                main_data[dst] = main_data[src]

        # Ensure required timestamps
        if "created_at" not in main_data or main_data.get("created_at") is None:
            main_data["created_at"] = now_utc()
        if "updated_at" not in main_data or main_data.get("updated_at") is None:
            main_data["updated_at"] = now_utc()

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

        # JSON fields are handled directly by SQLAlchemy with JSONB columns
        # No need for special wrapping like Prisma

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
            self.logger.info(
                "📦 Canonical entity prepared",
                extra={
                    "data_type": data_type,
                    "id": canonical.get(f"{data_type[:-1]}Id"),
                    "format": data_format,
                },
            )

            # Prepare main data
            main_data = self._prepare_main_data(canonical, shop_id, data_type)
            if not main_data:
                return False

            # Get model class
            model_class = self._get_model_class(data_type)

            # Check for existing record and idempotency
            id_field = f"{data_type[:-1]}_id"
            id_value = canonical.get(f"{data_type[:-1]}Id")

            async with get_session_context() as session:
                result = await session.execute(
                    select(model_class).where(
                        (model_class.shop_id == shop_id)
                        & (getattr(model_class, id_field) == id_value)
                    )
                )
                existing = result.scalar_one_or_none()

            if self._should_skip_update(existing, canonical):
                # Even if we skip normalization, we should still trigger feature computation
                # because new behavioral data might have been collected
                self.logger.info(
                    f"Skipping normalization for {data_type} {canonical.get(f'{data_type[:-1]}Id')} - no updates needed, but triggering feature computation"
                )
                return True

            # Upsert main record
            if existing:
                self.logger.info(
                    "✏️ Updating existing entity",
                    extra={
                        "data_type": data_type,
                        "id": id_value,
                        "shop_id": shop_id,
                    },
                )
                async with get_transaction_context() as session:
                    await session.execute(
                        update(model_class)
                        .where(model_class.id == existing.id)
                        .values(**main_data)
                    )
                    await session.commit()
            else:
                self.logger.info(
                    "🆕 Creating new entity",
                    extra={
                        "data_type": data_type,
                        "id": id_value,
                        "shop_id": shop_id,
                    },
                )
                async with get_transaction_context() as session:
                    model_instance = model_class(**main_data)
                    session.add(model_instance)
                    await session.commit()

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

    def _get_model_class(self, data_type: str):
        """Get the appropriate model class for data type."""
        model_map = {
            "orders": OrderData,
            "products": ProductData,
            "customers": CustomerData,
            "collections": CollectionData,
        }
        return model_map[data_type]

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

        # Ensure both are datetime objects for comparison
        if isinstance(incoming_updated_at, str):
            try:
                from datetime import datetime

                # Parse string timestamp to datetime
                if incoming_updated_at.endswith("Z"):
                    incoming_updated_at = datetime.fromisoformat(
                        incoming_updated_at.replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                else:
                    incoming_updated_at = datetime.fromisoformat(incoming_updated_at)
            except Exception as e:
                self.logger.warning(f"Failed to parse incoming timestamp: {e}")
                return False

        return incoming_updated_at <= existing.shopifyUpdatedAt

    def _serialize_json_fields(self, main_data: Dict[str, Any]):
        """No-op for SQLAlchemy: JSON fields are stored as native JSON/JSONB."""
        return

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
            order_record_id = None

            async with get_transaction_context() as session:
                self.logger.info(
                    "🔐 Order normalization transaction started",
                    extra={"orderId": canonical.get("orderId"), "shop_id": shop_id},
                )

                # Check for existing order
                result = await session.execute(
                    select(OrderData).where(
                        (OrderData.shop_id == shop_id)
                        & (OrderData.order_id == canonical.get("orderId"))
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    self.logger.info(
                        "✏️ Updating existing order",
                        extra={
                            "orderId": canonical.get("orderId"),
                            "record_id": existing.id,
                            "shop_id": shop_id,
                        },
                    )
                    await session.execute(
                        update(OrderData)
                        .where(OrderData.id == existing.id)
                        .values(**main_data)
                    )
                    order_record_id = existing.id
                else:
                    self.logger.info(
                        "🆕 Creating new order",
                        extra={
                            "orderId": canonical.get("orderId"),
                            "shop_id": shop_id,
                        },
                    )
                    order_instance = OrderData(**main_data)
                    session.add(order_instance)
                    await session.flush()  # Get the ID without committing
                    order_record_id = order_instance.id

                # Create line items
                if line_items:
                    self.logger.info(
                        "🧾 Replacing line items",
                        extra={
                            "orderId": canonical.get("orderId"),
                            "line_items_count": len(line_items),
                        },
                    )
                    await self._create_line_items(session, order_record_id, line_items)

                await session.commit()

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

        processed_count = 0

        async with get_transaction_context() as session:
            for raw_record in raw_records:
                try:
                    payload = self._parse_payload(raw_record)
                    if not payload:
                        continue

                    data_format = self._detect_format(raw_record, payload)
                    adapter = get_adapter(data_format, "orders")
                    canonical = adapter.to_canonical(payload, shop_id)

                    line_items = canonical.get("lineItems", [])
                    main_data = await self._prepare_order_data(canonical, shop_id)
                    if not main_data:
                        continue

                    # Upsert order
                    result = await session.execute(
                        select(OrderData).where(
                            (OrderData.shop_id == shop_id)
                            & (OrderData.order_id == canonical.get("orderId"))
                        )
                    )
                    existing = result.scalar_one_or_none()

                    if existing:
                        await session.execute(
                            update(OrderData)
                            .where(OrderData.id == existing.id)
                            .values(**main_data)
                        )
                        order_record_id = existing.id
                    else:
                        order_instance = OrderData(**main_data)
                        session.add(order_instance)
                        await session.flush()
                        order_record_id = order_instance.id

                    # Replace line items
                    if line_items:
                        await self._create_line_items(
                            session, order_record_id, line_items
                        )

                    processed_count += 1
                except Exception:
                    # Skip this order, continue with others
                    continue

            await session.commit()

        # Publish events after commit for webhook-only processing
        if is_webhook:
            for raw_record in raw_records:
                try:
                    payload = self._parse_payload(raw_record)
                    if not payload:
                        continue
                    data_format = self._detect_format(raw_record, payload)
                    adapter = get_adapter(data_format, "orders")
                    canonical = adapter.to_canonical(payload, shop_id)
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

    async def _prepare_order_data(
        self, canonical: Dict, shop_id: str
    ) -> Optional[Dict]:
        """Prepare order data for database using declarative mapper (SQLAlchemy)."""
        # Ensure shop exists
        async with get_session_context() as session:
            result = await session.execute(select(Shop).where(Shop.id == shop_id))
            shop_exists = result.scalar_one_or_none()
        if not shop_exists:
            self.logger.error(f"Shop {shop_id} not found")
            return None

        if not canonical.get("orderId"):
            self.logger.error("Missing orderId in canonical data")
            return None

        main_data = PersistenceMapper.apply("orders", canonical, shop_id)
        return main_data

    async def _create_line_items(
        self, session: Any, order_record_id: str, line_items: List[Any]
    ):
        """Replace line items for an order using one delete + bulk insert."""
        if not line_items:
            return

        try:
            # Clear existing line items for the order
            await session.execute(
                delete(LineItemData).where(LineItemData.order_id == order_record_id)
            )

            # Prepare bulk data (snake_case fields)
            bulk_rows: List[Dict[str, Any]] = []
            for item in line_items:
                try:
                    bulk_rows.append(
                        {
                            "order_id": order_record_id,
                            "product_id": item.get("productId"),
                            "variant_id": item.get("variantId"),
                            "title": item.get("title"),
                            "quantity": int(item.get("quantity", 0)),
                            "price": float(item.get("price", 0.0)),
                            "properties": item.get("properties", {}),
                        }
                    )
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Skipping invalid line item: {e}")
                    continue

            if bulk_rows:
                # Use bulk insert for efficiency
                await session.execute(insert(LineItemData).values(bulk_rows))

        except Exception as e:
            self.logger.error(f"Failed to create line items: {e}")

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

    def _serialize_json_fields(self, main_data: Dict[str, Any]):
        """No-op for SQLAlchemy: JSON fields are stored as native JSON/JSONB."""
        return

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
