"""
Simplified data storage service for Shopify data with essential batching and parallel processing
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from app.core.logging import get_logger
from app.core.database.session import get_session_context, get_transaction_context
from app.core.database.models import (
    Shop,
    RawOrder,
    RawProduct,
    RawCustomer,
    RawCollection,
)

# Using string values directly for database insertion
from sqlalchemy import select, update, insert
from app.shared.helpers.datetime_utils import now_utc, parse_iso_timestamp

logger = get_logger(__name__)


class ShopifyDataStorageService:
    """
    Simplified data storage service with:
    - Essential batching for large data volumes
    - Parallel processing for performance
    - Incremental updates with timestamps
    - Basic error handling
    """

    def __init__(self):
        self.batch_size = 100  # Essential batching
        self.chunk_size = 50  # Chunked queries to avoid timeouts

    async def store_products_data(
        self, products: List[Any], shop_id: str, incremental: bool = True
    ) -> Dict[str, int]:
        """Store products data using generic storage method"""
        return await self._store_raw_data_generic(
            "products", products, shop_id, incremental
        )

    async def store_orders_data(
        self, orders: List[Any], shop_id: str, incremental: bool = True
    ) -> Dict[str, int]:
        """Store orders data using generic storage method"""
        return await self._store_raw_data_generic(
            "orders", orders, shop_id, incremental
        )

    async def store_customers_data(
        self, customers: List[Any], shop_id: str, incremental: bool = True
    ) -> Dict[str, int]:
        """Store customers data using generic storage method"""
        return await self._store_raw_data_generic(
            "customers", customers, shop_id, incremental
        )

    async def store_collections_data(
        self, collections: List[Any], shop_id: str, incremental: bool = True
    ) -> Dict[str, int]:
        """Store collections data using generic storage method"""
        return await self._store_raw_data_generic(
            "collections", collections, shop_id, incremental
        )

    async def _store_raw_data_generic(
        self, data_type: str, items: List[Any], shop_id: str, incremental: bool = True
    ) -> Dict[str, int]:
        """Generic method to store any type of raw data with essential batching and parallel processing"""
        if not items:
            return {"new": 0, "updated": 0}

        try:
            # Process in batches for performance
            batches = self._create_batches(items, self.batch_size)

            # Process batches in parallel for speed
            batch_tasks = [
                self._process_batch_generic(data_type, batch, shop_id, incremental)
                for batch in batches
            ]

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Simple aggregation
            total_new = 0
            total_updated = 0

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Batch processing failed for {data_type}: {result}")
                    continue

                if isinstance(result, dict):
                    total_new += result.get("new", 0)
                    total_updated += result.get("updated", 0)
                else:
                    logger.warning(f"Unexpected batch result type: {type(result)}")

            return {"new": total_new, "updated": total_updated}

        except Exception as e:
            logger.error(f"Failed to store {data_type} data: {e}")
            raise

    async def _process_batch_generic(
        self, data_type: str, items: List[Any], shop_id: str, incremental: bool
    ) -> Dict[str, int]:
        """Generic batch processor for any data type"""
        try:
            return await self._process_items_simple(
                data_type, items, shop_id, incremental
            )
        except Exception as e:
            logger.error(f"{data_type.title()} batch processing failed: {e}")
            return {"new": 0, "updated": 0}

    async def _process_items_simple(
        self, data_type: str, items: List[Any], shop_id: str, incremental: bool
    ) -> Dict[str, int]:
        """Generic method to process any type of items with essential batching"""
        current_time = now_utc()

        # Store raw data with full GraphQL ID - no extraction here
        item_data_map = {}
        for item in items:
            # Get the full GraphQL ID from the item
            full_id = self._get_full_graphql_id(item)
            if not full_id:
                continue

            created_at, updated_at = self._extract_shopify_timestamps(item)
            item_data_map[full_id] = {
                "shop_id": shop_id,  # Use camelCase to match Prisma schema
                "payload": self._serialize_item_generic(item),
                "extracted_at": current_time,  # Use camelCase to match Prisma schema
                "shopify_id": full_id,  # Use camelCase to match Prisma schema
                "shopify_created_at": created_at,  # Use camelCase to match Prisma schema
                "shopify_updated_at": updated_at,  # Use camelCase to match Prisma schema
                # Correctly mark collected data as GraphQL backfill (not webhook/rest)
                "source": "backfill",
                "format": "graphql",
            }

        if not item_data_map:
            return {"new": 0, "updated": 0}

        # Batch lookup existing items using full GraphQL IDs
        existing_items = await self._batch_lookup_existing_items(
            data_type, shop_id, list(item_data_map.keys())
        )

        # Separate new vs updated
        new_items = []
        updated_items = []

        for item_id, item_data in item_data_map.items():
            existing = existing_items.get(item_id)

            if not existing:
                new_items.append(item_data)
            else:
                # Ensure both datetimes are timezone-aware for comparison
                item_updated_at = item_data["shopify_updated_at"]
                existing_updated_at = existing.shopify_updated_at

                # Make both timezone-aware (assume UTC if naive)
                if item_updated_at and item_updated_at.tzinfo is None:
                    item_updated_at = item_updated_at.replace(tzinfo=timezone.utc)
                if existing_updated_at and existing_updated_at.tzinfo is None:
                    existing_updated_at = existing_updated_at.replace(
                        tzinfo=timezone.utc
                    )

                if (
                    item_updated_at
                    and existing_updated_at
                    and item_updated_at > existing_updated_at
                ):
                    updated_items.append(item_data)

        # Batch operations using SQLAlchemy models
        model_class = self._get_model_class(data_type)

        if new_items:
            async with get_transaction_context() as session:
                for item_data in new_items:
                    model_instance = model_class(**item_data)
                    session.add(model_instance)
                await session.commit()

        if updated_items:
            async with get_transaction_context() as session:
                for item_data in updated_items:
                    await session.execute(
                        update(model_class)
                        .where(
                            (model_class.shop_id == shop_id)
                            & (model_class.shopify_id == item_data["shopify_id"])
                        )
                        .values(
                            payload=item_data["payload"],
                            extracted_at=item_data["extracted_at"],
                            shopify_updated_at=item_data["shopify_updated_at"],
                            source="backfill",
                            format="graphql",
                        )
                    )
                await session.commit()

        return {"new": len(new_items), "updated": len(updated_items)}

    def _get_model_class(self, data_type: str) -> type:
        """Get the SQLAlchemy model class for a data type"""
        model_mapping = {
            "products": RawProduct,
            "orders": RawOrder,
            "customers": RawCustomer,
            "collections": RawCollection,
        }
        model_class = model_mapping.get(data_type)
        if not model_class:
            raise ValueError(f"Unknown data type: {data_type}")
        return model_class

    def _serialize_item_generic(self, item: Any) -> Dict[str, Any]:
        """Generic serialization for any item type - return dict for JSON column"""
        return self._serialize_to_dict(item)

    async def _batch_lookup_existing_items(
        self, data_type: str, shop_id: str, item_ids: List[str]
    ) -> Dict[str, Any]:
        """Generic batch lookup for any data type"""
        existing_items = {}
        model_class = self._get_model_class(data_type)

        # Process in chunks to avoid query timeouts
        for i in range(0, len(item_ids), self.chunk_size):
            chunk_ids = item_ids[i : i + self.chunk_size]
            async with get_session_context() as session:
                result = await session.execute(
                    select(model_class).where(
                        (model_class.shop_id == shop_id)
                        & (model_class.shopify_id.in_(chunk_ids))
                    )
                )
                existing_records = result.scalars().all()
                for record in existing_records:
                    existing_items[record.shopify_id] = record

        return existing_items

    def _create_batches(self, items: List[Any], batch_size: int) -> List[List[Any]]:
        """Create batches from a list of items"""
        return [items[i : i + batch_size] for i in range(0, len(items), batch_size)]

    def _serialize_to_dict(self, item: Any) -> Dict[str, Any]:
        """Serialize item to dictionary for JSON column storage"""
        try:
            if isinstance(item, str):
                # JSON string - parse and return as dict
                return json.loads(item)
            elif hasattr(item, "model_dump"):
                # Pydantic model
                return item.model_dump()
            elif isinstance(item, dict):
                # Already a dictionary
                return item
            elif hasattr(item, "__dict__"):
                # Object with __dict__ attribute
                return item.__dict__
            else:
                # Fallback: try to serialize as-is
                return dict(item) if hasattr(item, "__iter__") else {"data": str(item)}
        except (TypeError, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to serialize item: {e}")
            return {"error": "serialization_failed", "data": str(item)}

    def _get_full_graphql_id(self, item: Any) -> Optional[str]:
        """Get the full GraphQL ID from Shopify item without extraction"""
        try:
            if hasattr(item, "id"):
                return str(item.id)
            elif isinstance(item, dict) and "id" in item:
                return str(item["id"])
            return None
        except Exception as e:
            logger.warning(f"Failed to get GraphQL ID: {e}")
            return None

    def _extract_shopify_timestamps(
        self, data: Any
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        """Extract createdAt and updatedAt timestamps from Shopify GraphQL data"""
        created_at = self._extract_timestamp(data, ["created_at", "createdAt"])
        updated_at = self._extract_timestamp(data, ["updated_at", "updatedAt"])
        return created_at, updated_at

    def _extract_timestamp(
        self, data: Any, field_names: List[str]
    ) -> Optional[datetime]:
        """Extract timestamp from data using multiple possible field names"""
        try:
            for field_name in field_names:
                # Handle object attributes
                if hasattr(data, field_name):
                    timestamp_value = getattr(data, field_name)
                    if timestamp_value:
                        return self._parse_timestamp_value(timestamp_value)

                # Handle dictionary keys
                elif isinstance(data, dict) and field_name in data and data[field_name]:
                    return self._parse_timestamp_value(data[field_name])

        except Exception as e:
            logger.warning(f"Failed to extract timestamp from {field_names}: {e}")

        return None

    def _parse_timestamp_value(self, timestamp_value: Any) -> Optional[datetime]:
        """Parse a timestamp value to datetime object"""
        if isinstance(timestamp_value, datetime):
            return timestamp_value
        else:
            return self._parse_shopify_timestamp(str(timestamp_value))

    def _parse_shopify_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse Shopify timestamp string to datetime object"""
        try:
            if isinstance(timestamp_str, str):
                # Handle various Shopify timestamp formats
                if timestamp_str.endswith("Z"):
                    # ISO format with Z - keep timezone-aware
                    return parse_iso_timestamp(timestamp_str)
                elif "+" in timestamp_str or timestamp_str.endswith("T"):
                    # ISO format with timezone - keep timezone-aware
                    dt = datetime.fromisoformat(timestamp_str)
                    return dt
                else:
                    # Try parsing as ISO format
                    return datetime.fromisoformat(timestamp_str)
        except Exception as e:
            logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}")
        return None

    async def get_shop_by_domain(self, shop_domain: str) -> Optional[Any]:
        """Get shop by domain for incremental collection"""
        try:
            async with get_session_context() as session:
                result = await session.execute(
                    select(Shop).where(Shop.shop_domain == shop_domain)
                )
                shop = result.scalar_one_or_none()
                return shop
        except Exception as e:
            logger.error(f"Failed to get shop by domain {shop_domain}: {e}")
            return None

    async def get_shop_by_id(self, shop_id: str) -> Optional[Any]:
        """Get shop by ID for validation"""
        try:
            async with get_session_context() as session:
                result = await session.execute(select(Shop).where(Shop.id == shop_id))
                shop = result.scalar_one_or_none()
                return shop
        except Exception as e:
            logger.error(f"Failed to get shop by ID {shop_id}: {e}")
            return None

    async def _get_latest_update(self, data_type: str, shop_id: str) -> Optional[Any]:
        """Generic method to get latest update for any data type"""
        try:
            model_class = self._get_model_class(data_type)
            async with get_session_context() as session:
                result = await session.execute(
                    select(model_class)
                    .where(model_class.shop_id == shop_id)
                    .order_by(model_class.extracted_at.desc())
                    .limit(1)
                )
                latest_record = result.scalar_one_or_none()
                return latest_record
        except Exception as e:
            logger.error(
                f"Failed to get latest {data_type} update for shop {shop_id}: {e}"
            )
            return None

    async def get_latest_product_update(self, shop_id: str) -> Optional[Any]:
        """Get the most recently updated product for incremental collection"""
        return await self._get_latest_update("products", shop_id)

    async def get_latest_order_update(self, shop_id: str) -> Optional[Any]:
        """Get the most recently updated order for incremental collection"""
        return await self._get_latest_update("orders", shop_id)

    async def get_latest_customer_update(self, shop_id: str) -> Optional[Any]:
        """Get the most recently updated customer for incremental collection"""
        return await self._get_latest_update("customers", shop_id)

    async def get_latest_collection_update(self, shop_id: str) -> Optional[Any]:
        """Get the most recently updated collection for incremental collection"""
        return await self._get_latest_update("collections", shop_id)
