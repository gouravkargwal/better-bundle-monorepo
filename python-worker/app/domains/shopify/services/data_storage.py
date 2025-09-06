"""
Simplified data storage service for Shopify data with essential batching and parallel processing
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.core.logging import get_logger
from app.core.database.simple_db_client import get_database
from app.shared.helpers import now_utc

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
                else:
                    total_new += result.get("new", 0)
                    total_updated += result.get("updated", 0)

            return {"new": total_new, "updated": total_updated}

        except Exception as e:
            logger.error(f"Failed to store {data_type} data: {e}")
            raise

    async def _process_batch_generic(
        self, data_type: str, items: List[Any], shop_id: str, incremental: bool
    ) -> Dict[str, int]:
        """Generic batch processor for any data type"""
        try:
            db = await get_database()
            return await self._process_items_simple(
                db, data_type, items, shop_id, incremental
            )
        except Exception as e:
            logger.error(f"{data_type.title()} batch processing failed: {e}")
            return {"new": 0, "updated": 0}

    async def _process_items_simple(
        self, db, data_type: str, items: List[Any], shop_id: str, incremental: bool
    ) -> Dict[str, int]:
        """Generic method to process any type of items with essential batching"""
        current_time = now_utc()

        # Extract item data using generic methods
        item_data_map = {}
        for item in items:
            item_id = self._extract_id_generic(data_type, item)
            if not item_id:
                continue

            created_at, updated_at = self._extract_shopify_timestamps(item)
            item_data_map[item_id] = {
                "shopId": shop_id,
                "payload": self._serialize_item_generic(item),
                "extractedAt": current_time,
                "shopifyId": item_id,
                "shopifyCreatedAt": created_at,
                "shopifyUpdatedAt": updated_at,
            }

        if not item_data_map:
            return {"new": 0, "updated": 0}

        # Batch lookup existing items (chunked to avoid timeouts)
        existing_items = await self._batch_lookup_existing_items(
            db, data_type, shop_id, list(item_data_map.keys())
        )

        # Separate new vs updated
        new_items = []
        updated_items = []

        for item_id, item_data in item_data_map.items():
            existing = existing_items.get(item_id)

            if not existing:
                new_items.append(item_data)
            elif item_data["shopifyUpdatedAt"] > existing.shopifyUpdatedAt:
                updated_items.append(item_data)

        # Batch operations using generic table names
        table_name = self._get_table_name(data_type)

        if new_items:
            await getattr(db, table_name).create_many(data=new_items)

        if updated_items:
            # Simple batch update
            for item_data in updated_items:
                await getattr(db, table_name).update_many(
                    where={"shopId": shop_id, "shopifyId": item_data["shopifyId"]},
                    data={
                        "payload": item_data["payload"],
                        "extractedAt": item_data["extractedAt"],
                        "shopifyUpdatedAt": item_data["shopifyUpdatedAt"],
                    },
                )

        return {"new": len(new_items), "updated": len(updated_items)}

    def _get_table_name(self, data_type: str) -> str:
        """Get the database table name for a data type"""
        table_mapping = {
            "products": "rawproduct",
            "orders": "raworder",
            "customers": "rawcustomer",
            "collections": "rawcollection",
        }
        return table_mapping.get(data_type, f"raw{data_type}")

    def _extract_id_generic(self, data_type: str, item: Any) -> Optional[str]:
        """Generic ID extraction for any data type"""
        extractors = {
            "products": self._extract_product_id,
            "orders": self._extract_order_id,
            "customers": self._extract_customer_id,
            "collections": self._extract_collection_id,
        }
        extractor = extractors.get(data_type)
        return extractor(item) if extractor else None

    def _serialize_item_generic(self, item: Any) -> str:
        """Generic serialization for any item type"""
        return self._serialize_product(item)  # All use the same serialization logic

    async def _batch_lookup_existing_items(
        self, db, data_type: str, shop_id: str, item_ids: List[str]
    ) -> Dict[str, Any]:
        """Generic batch lookup for any data type"""
        existing_items = {}
        table_name = self._get_table_name(data_type)

        # Process in chunks to avoid query timeouts
        for i in range(0, len(item_ids), self.chunk_size):
            chunk_ids = item_ids[i : i + self.chunk_size]
            existing_records = await getattr(db, table_name).find_many(
                where={"shopId": shop_id, "shopifyId": {"in": chunk_ids}}
            )
            for record in existing_records:
                existing_items[record.shopifyId] = record

        return existing_items

    def _create_batches(self, items: List[Any], batch_size: int) -> List[List[Any]]:
        """Create batches from a list of items"""
        return [items[i : i + batch_size] for i in range(0, len(items), batch_size)]

    def _serialize_product(self, product: Any) -> str:
        """Serialize product to JSON string for storage"""
        try:
            if isinstance(product, str):
                # Already a JSON string, validate and return
                json.loads(product)  # Validate it's valid JSON
                return product
            elif hasattr(product, "dict"):
                # Pydantic model
                return json.dumps(product.dict(), default=str)
            elif isinstance(product, dict):
                # Already a dictionary
                return json.dumps(product, default=str)
            elif hasattr(product, "__dict__"):
                # Object with __dict__ attribute
                return json.dumps(product.__dict__, default=str)
            else:
                # Fallback: try to serialize as-is
                return json.dumps(product, default=str)
        except (TypeError, ValueError, json.JSONDecodeError) as e:
            # If all else fails, convert to string representation
            logger.warning(
                f"Failed to serialize product, using string representation: {e}"
            )
            return json.dumps(
                {"error": "serialization_failed", "data": str(product)}, default=str
            )

    def _extract_id_generic(self, data_type: str, item: Any) -> Optional[str]:
        """Generic method to extract ID from any Shopify item"""
        try:
            if hasattr(item, "id"):
                item_id = str(item.id)
            elif isinstance(item, dict) and "id" in item:
                item_id = str(item["id"])
            else:
                return None

            # Extract numeric ID from Shopify GraphQL ID format (gid://shopify/Product/123456789)
            graphql_prefix = f"gid://shopify/{data_type.title()}/"
            if item_id.startswith(graphql_prefix):
                return item_id.split("/")[-1]
            return item_id
        except Exception as e:
            logger.warning(f"Failed to extract {data_type} ID: {e}")
            return None

    def _extract_product_id(self, product: Any) -> Optional[str]:
        """Extract product ID from product object"""
        return self._extract_id_generic("Product", product)

    def _extract_order_id(self, order: Any) -> Optional[str]:
        """Extract order ID from order object"""
        return self._extract_id_generic("Order", order)

    def _extract_customer_id(self, customer: Any) -> Optional[str]:
        """Extract customer ID from customer object"""
        return self._extract_id_generic("Customer", customer)

    def _extract_collection_id(self, collection: Any) -> Optional[str]:
        """Extract collection ID from collection object"""
        return self._extract_id_generic("Collection", collection)

    def _extract_shopify_timestamps(
        self, data: Any
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        """Extract createdAt and updatedAt timestamps from Shopify GraphQL data"""
        created_at = None
        updated_at = None

        try:
            # Handle Pydantic models (snake_case) - this is what we get from data collection
            if hasattr(data, "created_at") and data.created_at:
                if isinstance(data.created_at, datetime):
                    created_at = data.created_at
                else:
                    created_at = self._parse_shopify_timestamp(str(data.created_at))
            elif isinstance(data, dict) and "created_at" in data and data["created_at"]:
                if isinstance(data["created_at"], datetime):
                    created_at = data["created_at"]
                else:
                    created_at = self._parse_shopify_timestamp(str(data["created_at"]))

            # Handle raw GraphQL data (camelCase) - fallback for direct API responses
            elif hasattr(data, "createdAt") and data.createdAt:
                created_at = self._parse_shopify_timestamp(str(data.createdAt))
            elif isinstance(data, dict) and "createdAt" in data and data["createdAt"]:
                created_at = self._parse_shopify_timestamp(str(data["createdAt"]))

            # Handle Pydantic models (snake_case) - this is what we get from data collection
            if hasattr(data, "updated_at") and data.updated_at:
                if isinstance(data.updated_at, datetime):
                    updated_at = data.updated_at
                else:
                    updated_at = self._parse_shopify_timestamp(str(data.updated_at))
            elif isinstance(data, dict) and "updated_at" in data and data["updated_at"]:
                if isinstance(data["updated_at"], datetime):
                    updated_at = data["updated_at"]
                else:
                    updated_at = self._parse_shopify_timestamp(str(data["updated_at"]))

            # Handle raw GraphQL data (camelCase) - fallback for direct API responses
            elif hasattr(data, "updatedAt") and data.updatedAt:
                updated_at = self._parse_shopify_timestamp(str(data.updatedAt))
            elif isinstance(data, dict) and "updatedAt" in data and data["updatedAt"]:
                updated_at = self._parse_shopify_timestamp(str(data["updatedAt"]))

        except Exception as e:
            logger.warning(f"Failed to extract timestamps: {e}")

        return created_at, updated_at

    def _parse_shopify_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse Shopify timestamp string to datetime object"""
        try:
            if isinstance(timestamp_str, str):
                # Handle various Shopify timestamp formats
                if timestamp_str.endswith("Z"):
                    # ISO format with Z
                    return datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                elif "+" in timestamp_str or timestamp_str.endswith("T"):
                    # ISO format with timezone
                    return datetime.fromisoformat(timestamp_str)
                else:
                    # Try parsing as ISO format
                    return datetime.fromisoformat(timestamp_str)
        except Exception as e:
            logger.warning(f"Failed to parse timestamp '{timestamp_str}': {e}")
        return None

    async def get_shop_by_domain(self, shop_domain: str) -> Optional[Any]:
        """Get shop by domain for incremental collection"""
        try:
            db = await get_database()
            shop = await db.shop.find_first(where={"shopDomain": shop_domain})
            return shop
        except Exception as e:
            logger.error(f"Failed to get shop by domain {shop_domain}: {e}")
            return None

    async def get_shop_by_id(self, shop_id: str) -> Optional[Any]:
        """Get shop by ID for validation"""
        try:
            db = await get_database()
            shop = await db.shop.find_first(where={"id": shop_id})
            return shop
        except Exception as e:
            logger.error(f"Failed to get shop by ID {shop_id}: {e}")
            return None

    async def _get_latest_update(self, data_type: str, shop_id: str) -> Optional[Any]:
        """Generic method to get latest update for any data type"""
        try:
            db = await get_database()
            table_name = self._get_table_name(data_type)
            latest_record = await getattr(db, table_name).find_first(
                where={"shopId": shop_id}, order={"extractedAt": "desc"}
            )
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
