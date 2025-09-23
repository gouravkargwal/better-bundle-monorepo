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
            line_items = canonical_data.get("lineItems", [])

            # Use canonical data directly - it's already aligned with DB schema
            order_data = canonical_data.copy()

            # Remove line items since they're handled separately
            order_data.pop("lineItems", None)
            order_data.pop("line_items", None)

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

        processed_count = 0

        async with get_transaction_context() as session:
            for canonical_data in canonical_data_list:
                try:
                    order_id = canonical_data.get("order_id")
                    if not order_id:
                        continue

                    line_items = canonical_data.get("lineItems", [])

                    # Use canonical data directly - it's already aligned with DB schema
                    order_data = canonical_data.copy()

                    # Remove line items since they're handled separately
                    order_data.pop("lineItems", None)
                    order_data.pop("line_items", None)

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
                        await session.execute(
                            update(OrderData)
                            .where(OrderData.id == existing.id)
                            .values(**order_data)
                        )
                        order_record_id = existing.id
                    else:
                        order_instance = OrderData(**order_data)
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

        async with get_transaction_context() as session:
            for canonical_data in canonical_data_list:
                try:
                    # Use canonical data directly - it's already aligned with DB schema
                    id_value = canonical_data.get(id_field)
                    if not id_value:
                        self.logger.warning(
                            f"Missing {id_field} in canonical data: {list(canonical_data.keys())}"
                        )
                        continue

                    # Use canonical data directly
                    entity_data = canonical_data.copy()

                    # Remove fields that shouldn't be in the main table
                    entity_data.pop("lineItems", None)  # For orders
                    entity_data.pop("line_items", None)  # Alternative name

                    # Clean internal fields
                    self._clean_internal_fields(entity_data)

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
                    # Log the actual error for debugging
                    self.logger.error(f"Failed to upsert {data_type} entity: {e}")
                    continue

            await session.commit()

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
