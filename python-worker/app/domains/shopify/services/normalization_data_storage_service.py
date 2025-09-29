from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from app.core.logging import get_logger
from app.core.database.session import get_session_context, get_transaction_context
from app.core.database.models import (
    OrderData,
    LineItemData,
    ProductData,
    CustomerData,
    CollectionData,
    PipelineWatermark,
)
from sqlalchemy import select, update, delete, insert
from app.shared.helpers import now_utc

logger = get_logger(__name__)


class NormalizationDataStorageService:
    """Centralized service for all normalization data storage operations."""

    def __init__(self):
        self.logger = get_logger(__name__)

    async def upsert_entity(
        self, data_type: str, canonical_data: Dict[str, Any], shop_id: str
    ) -> bool:
        """Upsert a single entity (product, customer, collection)."""
        try:
            # Get model class and id field
            model_class = self._get_model_class(data_type)
            id_field = f"{data_type[:-1]}_id"
            id_value = canonical_data.get(id_field)

            if not id_value:
                self.logger.error(f"Missing primary id: {id_field}")
                return False

            # Use canonical data directly - it's already aligned with DB schema
            main_data = canonical_data.copy()

            # Remove fields that shouldn't be in the main table
            main_data.pop("lineItems", None)  # For orders
            main_data.pop("line_items", None)  # Alternative name

            # Clean internal fields
            self._clean_internal_fields(main_data)

            # Check for existing record
            async with get_session_context() as session:
                result = await session.execute(
                    select(model_class).where(
                        (model_class.shop_id == shop_id)
                        & (getattr(model_class, id_field) == id_value)
                    )
                )
                existing = result.scalar_one_or_none()

            # Upsert the record
            if existing:
                self.logger.info(
                    "✏️ Updating existing entity",
                    extra={
                        "data_type": data_type,
                        "id": id_value,
                        "shop_id": shop_id,
                    },
                )
                # For updates, preserve created_at and set updated_at to current time
                update_data = main_data.copy()
                update_data.pop("created_at", None)  # Preserve existing created_at
                update_data["updated_at"] = now_utc()  # Set current timestamp

                async with get_transaction_context() as session:
                    await session.execute(
                        update(model_class)
                        .where(model_class.id == existing.id)
                        .values(**update_data)
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
            self.logger.error(f"Entity upsert failed: {e}")
            return False

    async def upsert_order_with_line_items(
        self, canonical_data: Dict[str, Any], shop_id: str
    ) -> bool:
        """Upsert an order with its line items in a transaction."""
        try:
            order_id = canonical_data.get("order_id")
            if not order_id:
                self.logger.error("Missing order_id in canonical data")
                return False

            # Extract line items BEFORE preparing order data
            line_items = canonical_data.get("line_items", [])
            self.logger.info(
                f"🔍 STORAGE SERVICE: Extracted {len(line_items)} line items from canonical data"
            )
            if line_items:
                self.logger.info(
                    f"🔍 STORAGE SERVICE: First line item: {line_items[0]}"
                )
            else:
                self.logger.warning(
                    f"🔍 STORAGE SERVICE: No line items found in canonical data. Keys: {list(canonical_data.keys())}"
                )

            # Use canonical data directly - it's already aligned with DB schema
            order_data = canonical_data.copy()

            # Remove line items since they're handled separately
            # Note: We keep line_items in order_data for processing, but remove lineItems (camelCase)
            order_data.pop("lineItems", None)
            # Don't remove line_items - we need them for processing

            # Clean internal fields
            self._clean_internal_fields(order_data)

            # Process in transaction
            order_record_id = None

            async with get_transaction_context() as session:
                self.logger.info(
                    "🔐 Order normalization transaction started",
                    extra={"orderId": order_id, "shop_id": shop_id},
                )

                # Check for existing order
                result = await session.execute(
                    select(OrderData).where(
                        (OrderData.shop_id == shop_id)
                        & (OrderData.order_id == order_id)
                    )
                )
                existing = result.scalar_one_or_none()

                if existing:
                    self.logger.info(
                        "✏️ Updating existing order",
                        extra={
                            "orderId": order_id,
                            "record_id": existing.id,
                            "shop_id": shop_id,
                        },
                    )
                    await session.execute(
                        update(OrderData)
                        .where(OrderData.id == existing.id)
                        .values(**order_data)
                    )
                    order_record_id = existing.id
                else:
                    self.logger.info(
                        "🆕 Creating new order",
                        extra={
                            "orderId": order_id,
                            "shop_id": shop_id,
                        },
                    )
                    order_instance = OrderData(**order_data)
                    session.add(order_instance)
                    await session.flush()  # Get the ID without committing
                    order_record_id = order_instance.id

                # Create line items
                if line_items:
                    self.logger.info(
                        "🧾 Replacing line items",
                        extra={
                            "orderId": order_id,
                            "line_items_count": len(line_items),
                        },
                    )
                    await self._create_line_items(session, order_record_id, line_items)

                await session.commit()

            return True

        except Exception as e:
            self.logger.error(f"Order upsert failed: {e}")
            return False

    async def upsert_orders_batch(
        self, canonical_data_list: List[Dict[str, Any]], shop_id: str
    ) -> int:
        """Upsert a batch of orders with line items in a single transaction."""
        if not canonical_data_list:
            return 0

        self.logger.info(
            f"🔄 Upserting {len(canonical_data_list)} orders for shop {shop_id}"
        )
        processed_count = 0
        upsert_errors = 0

        async with get_transaction_context() as session:
            for i, canonical_data in enumerate(canonical_data_list):
                try:
                    order_id = canonical_data.get("order_id")
                    if not order_id:
                        self.logger.warning(
                            f"Missing order_id in canonical data {i+1}: {list(canonical_data.keys())}"
                        )
                        upsert_errors += 1
                        continue

                    self.logger.debug(
                        f"Processing order {i+1}/{len(canonical_data_list)}: {order_id}"
                    )

                    line_items = canonical_data.get("line_items", [])
                    self.logger.info(
                        f"🔍 STORAGE SERVICE: Extracted {len(line_items)} line items from canonical data"
                    )
                    if line_items:
                        self.logger.info(
                            f"🔍 STORAGE SERVICE: First line item: {line_items[0]}"
                        )
                    else:
                        self.logger.warning(
                            f"🔍 STORAGE SERVICE: No line items found in canonical data. Keys: {list(canonical_data.keys())}"
                        )

                    # Use canonical data directly - it's already aligned with DB schema
                    order_data = canonical_data.copy()

                    # Remove line items since they're handled separately
                    order_data.pop("lineItems", None)
                    order_data.pop("line_items", None)

                    # Remove fields that don't exist in OrderData model
                    order_data.pop("refunds", None)

                    # Clean internal fields
                    self._clean_internal_fields(order_data)

                    # Upsert order
                    result = await session.execute(
                        select(OrderData).where(
                            (OrderData.shop_id == shop_id)
                            & (OrderData.order_id == order_id)
                        )
                    )
                    existing = result.scalar_one_or_none()

                    if existing:
                        self.logger.debug(f"Updating existing order {order_id}")
                        await session.execute(
                            update(OrderData)
                            .where(OrderData.id == existing.id)
                            .values(**order_data)
                        )
                        order_record_id = existing.id
                    else:
                        self.logger.debug(f"Creating new order {order_id}")
                        order_instance = OrderData(**order_data)
                        session.add(order_instance)
                        await session.flush()
                        order_record_id = order_instance.id

                    # Replace line items
                    if line_items:
                        self.logger.debug(
                            f"Creating {len(line_items)} line items for order {order_id}"
                        )
                        await self._create_line_items(
                            session, order_record_id, line_items
                        )
                    else:
                        self.logger.warning(f"No line items found for order {order_id}")

                    processed_count += 1
                    self.logger.debug(f"Successfully processed order {order_id}")

                except Exception as e:
                    self.logger.error(
                        f"Failed to upsert order {i+1}: {e}", exc_info=True
                    )
                    upsert_errors += 1
                    continue

            await session.commit()

        self.logger.info(
            f"✅ Order batch upsert completed: {processed_count} orders, {upsert_errors} errors"
        )
        return processed_count

    async def upsert_entities_batch(
        self, data_type: str, canonical_data_list: List[Dict[str, Any]], shop_id: str
    ) -> int:
        """Upsert a batch of entities (products, customers, collections) in a single transaction."""
        if not canonical_data_list:
            return 0

        model_class = self._get_model_class(data_type)
        id_field = f"{data_type[:-1]}_id"
        processed_count = 0
        error_count = 0

        self.logger.info(
            f"🔄 Starting batch upsert for {data_type}",
            extra={
                "data_type": data_type,
                "shop_id": shop_id,
                "record_count": len(canonical_data_list),
                "model_class": model_class.__name__,
                "id_field": id_field,
            },
        )

        async with get_transaction_context() as session:
            for canonical_data in canonical_data_list:
                try:
                    # Use canonical data directly - it's already aligned with DB schema
                    id_value = canonical_data.get(id_field)
                    if not id_value:
                        self.logger.warning(
                            f"Missing {id_field} in canonical data: {list(canonical_data.keys())}",
                            extra={
                                "data_type": data_type,
                                "shop_id": shop_id,
                                "id_field": id_field,
                                "canonical_data_keys": list(canonical_data.keys()),
                                "canonical_data_sample": {
                                    k: str(v)[:100]
                                    for k, v in list(canonical_data.items())[:5]
                                },
                            },
                        )
                        continue

                    # Use canonical data directly
                    entity_data = canonical_data.copy()

                    # Remove fields that shouldn't be in the main table
                    entity_data.pop("lineItems", None)  # For orders
                    entity_data.pop("line_items", None)  # Alternative name

                    # Clean internal fields
                    self._clean_internal_fields(entity_data)

                    # Remove id field - database will generate it automatically
                    entity_data.pop("id", None)

                    # Validate fields against model schema
                    self._validate_entity_fields(
                        model_class, entity_data, data_type, id_value
                    )

                    # Check for existing record
                    result = await session.execute(
                        select(model_class).where(
                            (model_class.shop_id == shop_id)
                            & (getattr(model_class, id_field) == id_value)
                        )
                    )
                    existing = result.scalar_one_or_none()

                    # Upsert the record
                    if existing:
                        await session.execute(
                            update(model_class)
                            .where(model_class.id == existing.id)
                            .values(**entity_data)
                        )
                    else:
                        model_instance = model_class(**entity_data)
                        session.add(model_instance)

                    processed_count += 1
                except Exception as e:
                    # Log detailed error for debugging
                    self.logger.error(
                        f"Failed to upsert {data_type} entity: {e}",
                        extra={
                            "data_type": data_type,
                            "shop_id": shop_id,
                            "id_field": id_field,
                            "id_value": id_value,
                            "entity_data_keys": (
                                list(entity_data.keys()) if entity_data else []
                            ),
                            "error_type": type(e).__name__,
                            "error_details": str(e),
                        },
                    )
                    error_count += 1
                    continue

            await session.commit()

        self.logger.info(
            f"✅ Batch upsert completed for {data_type}",
            extra={
                "data_type": data_type,
                "shop_id": shop_id,
                "total_records": len(canonical_data_list),
                "successful": processed_count,
                "errors": error_count,
                "success_rate": (
                    f"{(processed_count/len(canonical_data_list)*100):.1f}%"
                    if canonical_data_list
                    else "0%"
                ),
            },
        )

        return processed_count

    async def upsert_watermark(
        self,
        shop_id: str,
        data_type: str,
        iso_time: str,
        format_type: Optional[str] = None,
    ):
        """Persist last normalized time for incremental normalization."""
        try:
            last_dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))

            if format_type == "graphql":
                async with get_transaction_context() as session:
                    # Try to find existing watermark
                    result = await session.execute(
                        select(PipelineWatermark).where(
                            (PipelineWatermark.shop_id == shop_id)
                            & (PipelineWatermark.data_type == data_type)
                        )
                    )
                    existing = result.scalar_one_or_none()

                    if existing:
                        existing.last_normalized_at = last_dt
                        existing.last_window_end = last_dt
                    else:
                        wm = PipelineWatermark(
                            shop_id=shop_id,
                            data_type=data_type,
                            last_normalized_at=last_dt,
                            last_window_end=last_dt,
                        )
                        session.add(wm)
                    await session.commit()

            self.logger.info(
                "💾 Watermark updated",
                extra={
                    "shop_id": shop_id,
                    "data_type": data_type,
                    "last_normalized_at": iso_time,
                    "table": (
                        "PipelineWatermark"
                        if format_type == "graphql"
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

    async def get_watermark(
        self, shop_id: str, data_type: str, format_type: str = "graphql"
    ) -> Optional[PipelineWatermark]:
        """Get the watermark for a shop and data type."""
        try:
            if format_type == "graphql":
                async with get_session_context() as session:
                    result = await session.execute(
                        select(PipelineWatermark).where(
                            (PipelineWatermark.shop_id == shop_id)
                            & (PipelineWatermark.data_type == data_type)
                        )
                    )
                    return result.scalar_one_or_none()
        except Exception as e:
            self.logger.error(f"Failed to get watermark: {e}")
            return None

    def _get_model_class(self, data_type: str):
        """Get the appropriate model class for data type."""
        model_map = {
            "orders": OrderData,
            "products": ProductData,
            "customers": CustomerData,
            "collections": CollectionData,
        }
        return model_map[data_type]

    async def _create_line_items(
        self, session: Any, order_record_id: str, line_items: List[Any]
    ):
        """Replace line items for an order using one delete + bulk insert."""
        if not line_items:
            return

        self.logger.debug(
            f"Creating {len(line_items)} line items for order {order_record_id}"
        )

        try:
            # Clear existing line items for the order
            await session.execute(
                delete(LineItemData).where(LineItemData.order_id == order_record_id)
            )
            self.logger.debug(
                f"Cleared existing line items for order {order_record_id}"
            )

            # Prepare bulk data (snake_case fields)
            bulk_rows: List[Dict[str, Any]] = []
            line_item_errors = 0

            for i, item in enumerate(line_items):
                try:
                    # Canonical uses snake_case; allow camelCase fallback just in case
                    product_id_value = item.get("product_id") or item.get("productId")
                    variant_id_value = item.get("variant_id") or item.get("variantId")

                    line_item_data = {
                        "order_id": order_record_id,
                        "product_id": product_id_value,
                        "variant_id": variant_id_value,
                        "title": item.get("title"),
                        "quantity": int(item.get("quantity", 0)),
                        "price": float(item.get("price", 0.0)),
                        "properties": item.get("properties", {}),
                    }

                    # Validate required fields - allow line items without product_id
                    # Some line items (like gift cards, custom items) don't have product IDs
                    if (
                        not line_item_data["product_id"]
                        and not line_item_data["variant_id"]
                    ):
                        self.logger.warning(
                            f"Missing both product_id and variant_id in line item {i+1}: {item}"
                        )
                        line_item_errors += 1
                        continue

                    bulk_rows.append(line_item_data)
                    identifier = (
                        line_item_data["product_id"]
                        or line_item_data["variant_id"]
                        or "no-id"
                    )
                    self.logger.debug(f"Prepared line item {i+1}: {identifier}")

                except (ValueError, TypeError) as e:
                    self.logger.warning(
                        f"Skipping invalid line item {i+1}: {e} - {item}"
                    )
                    line_item_errors += 1
                    continue

            self.logger.debug(
                f"Prepared {len(bulk_rows)} line items, {line_item_errors} errors"
            )

            if bulk_rows:
                # Use bulk insert for efficiency
                await session.execute(insert(LineItemData).values(bulk_rows))
                self.logger.debug(f"Successfully inserted {len(bulk_rows)} line items")
            else:
                self.logger.warning(
                    f"No valid line items to insert for order {order_record_id}"
                )

        except Exception as e:
            self.logger.error(
                f"Failed to create line items for order {order_record_id}: {e}",
                exc_info=True,
            )

    def _clean_internal_fields(self, main_data: Dict):
        """Remove internal/canonical fields not in DB schema."""
        fields_to_remove = [
            "entityId",
            "canonicalVersion",
            "originalGid",
            "customerCreatedAt",
            "customerUpdatedAt",
            "isActive",
            "refunds",  # Not in OrderData model
        ]
        for field in fields_to_remove:
            main_data.pop(field, None)

    def _validate_entity_fields(
        self, model_class, entity_data: Dict, data_type: str, id_value: str
    ):
        """Validate entity fields against model schema and log any issues."""
        try:
            # Get model column names
            model_columns = {col.name for col in model_class.__table__.columns}
            entity_fields = set(entity_data.keys())

            # Exclude auto-generated fields from validation
            auto_generated_fields = {
                "id"
            }  # Fields that are auto-generated by the database
            model_columns = model_columns - auto_generated_fields

            # Check for missing required fields
            missing_fields = model_columns - entity_fields
            extra_fields = entity_fields - model_columns

            if missing_fields:
                self.logger.warning(
                    f"Missing fields in {data_type} entity {id_value}",
                    extra={
                        "data_type": data_type,
                        "id_value": id_value,
                        "missing_fields": list(missing_fields),
                        "entity_fields": list(entity_fields),
                        "model_columns": list(model_columns),
                    },
                )

            if extra_fields:
                self.logger.debug(
                    f"Extra fields in {data_type} entity {id_value} (will be ignored)",
                    extra={
                        "data_type": data_type,
                        "id_value": id_value,
                        "extra_fields": list(extra_fields),
                    },
                )

        except Exception as e:
            self.logger.warning(
                f"Field validation failed for {data_type} {id_value}: {e}"
            )
