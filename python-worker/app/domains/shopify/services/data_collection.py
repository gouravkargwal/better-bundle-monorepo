"""
Shopify data collection service implementation for BetterBundle Python Worker
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

from app.core.logging import get_logger
from app.shared.helpers import now_utc
from ..interfaces.data_collector import IShopifyDataCollector
from ..interfaces.api_client import IShopifyAPIClient
from ..interfaces.permission_service import IShopifyPermissionService
from .data_storage import ShopifyDataStorageService
from app.repository.PipelineWatermarkRepository import (
    PipelineWatermarkRepository,
)
from app.repository.RawDataRepository import RawDataRepository

logger = get_logger(__name__)


class ShopifyDataCollectionService(IShopifyDataCollector):
    """Shopify data collection service with permission checking and adaptive collection"""

    def __init__(
        self,
        api_client: IShopifyAPIClient,
        permission_service: IShopifyPermissionService,
        data_storage: ShopifyDataStorageService = None,
        pipeline_watermark_repository: PipelineWatermarkRepository = None,
    ):
        self.api_client = api_client
        self.permission_service = permission_service
        self.pipeline_watermark_repository = (
            pipeline_watermark_repository or PipelineWatermarkRepository()
        )

        # Inject storage service or create default
        self.data_storage = data_storage or ShopifyDataStorageService()
        self.raw_data_repository = RawDataRepository()

        # Collection settings - Industry standard constants
        self.BATCH_SIZE = 250
        self.TIMEOUT_SECONDS = 300
        self.RATE_LIMIT_DELAY = 0.1
        self.MAX_DAYS_BACK = 90

        # Simplified data type mapping
        self.DATA_TYPES = {
            "products": {
                "api": "get_products",
                "field": "updated_at",
                "store": "store_products_data",
            },
            "orders": {
                "api": "get_orders",
                "field": "created_at",
                "store": "store_orders_data",
            },
            "customers": {
                "api": "get_customers",
                "field": "updated_at",
                "store": "store_customers_data",
            },
            "collections": {
                "api": "get_collections",
                "field": "updated_at",
                "store": "store_collections_data",
            },
        }

    def _ensure_aware_utc(self, dt: Optional[datetime]) -> Optional[datetime]:
        """Normalize a datetime to timezone-aware UTC. If naive, assume UTC.
        Returns None if input is None.
        """
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    async def _collect_data_by_type(
        self,
        data_type: str,
        shop_domain: str,
        shop_id: str,
        access_token: str = None,
        limit: Optional[int] = None,
        since_id: Optional[str] = None,
        specific_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Unified data collection - no complex mode switching
        Just collect data chunks like a proper Kafka system
        """
        # Step 1: Get data type configuration
        config = self._get_data_type_config(data_type)

        # Step 2: Execute collection - no complex mode switching
        if specific_ids:
            # Webhook collection for specific IDs
            return await self._execute_webhook_collection(
                data_type, shop_domain, specific_ids
            )
        else:
            # Full collection for all data
            return await self._execute_full_collection(
                data_type, shop_domain, config, limit, since_id
            )

    def _get_data_type_config(self, data_type: str) -> Dict[str, str]:
        """Get configuration for a data type."""
        config = self.DATA_TYPES.get(data_type)
        if not config:
            raise ValueError(f"Unsupported data type: {data_type}")
        return config

    async def _execute_webhook_collection(
        self, data_type: str, shop_domain: str, specific_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Execute webhook collection for specific IDs."""
        logger.info(f"🎯 Collecting specific {data_type} IDs: {specific_ids}")
        return await self._collect_specific_items_by_ids(
            data_type, shop_domain, specific_ids
        )

    async def _execute_full_collection(
        self,
        data_type: str,
        shop_domain: str,
        config: Dict[str, str],
        limit: Optional[int],
        since_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        """Execute full collection for a data type."""
        logger.info(f"🔄 Full collection for {data_type}")

        return await self._collect_data_generic(
            shop_domain=shop_domain,
            data_type=data_type,
            api_method=config["api"],
            query_since=None,
            query=None,
            limit=limit,
            since_id=since_id,
        )

    async def _has_any_raw_data(self, shop_id: str, data_type: str) -> bool:
        """Check if we have any raw data for this data type using repository."""
        try:
            count = await self.raw_data_repository.get_raw_count(shop_id, data_type)
            logger.info(f"🔍 Raw {data_type} count for shop {shop_id}: {count}")
            return count > 0
        except Exception as e:
            logger.warning(f"⚠️ Error checking raw data count for {data_type}: {e}")
            return False

    def _calculate_query_since(self, last_updated_at: Optional[datetime]) -> datetime:
        """Calculate the query_since date for incremental collection."""
        now = now_utc()
        max_days_back = now - timedelta(days=self.MAX_DAYS_BACK)

        if last_updated_at:
            last_aware = self._ensure_aware_utc(last_updated_at)
            return max(last_aware, max_days_back)
        else:
            return max_days_back

    async def collect_all_data(
        self,
        shop_domain: str,
        access_token: str,
        shop_id: str,
        collection_payload: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Unified data collection - process all available data for a shop
        No complex modes - just collect data chunks like a proper Kafka system

        Args:
            shop_domain: Shopify shop domain
            access_token: Shopify access token
            shop_id: Internal shop ID
            collection_payload: Payload specifying what data to collect

        Returns:
            Dict containing collection results and metadata
        """
        # Step 1: Initialize collection session
        session_info = self._initialize_collection_session(shop_id)

        try:
            # Step 2: Check permissions and validate access
            permissions = await self._check_permissions(shop_domain, access_token)

            # Step 3: Determine what data to collect
            collection_payload = self._prepare_collection_payload(collection_payload)
            collectable_data = self._determine_collectable_data(
                permissions, collection_payload
            )

            if not collectable_data:
                return self._create_no_permissions_response()

            # Step 4: Collect and store the data
            collection_results = await self._collect_and_store_data(
                shop_domain, access_token, shop_id, collectable_data, collection_payload
            )

            # Step 5: Trigger normalization for the collected data
            await self._trigger_normalization_for_results(
                shop_id, collection_results, session_info["start_time"]
            )

            # Step 6: Create success response
            return self._create_success_response(
                session_info, collection_results, collection_payload
            )

        except Exception as e:
            logger.error(f"Collection failed for {shop_domain}: {e}")
            raise

    def _initialize_collection_session(self, shop_id: str) -> Dict[str, Any]:
        """Initialize a new collection session with metadata."""
        collection_start_time = now_utc()
        session_id = f"collection_{shop_id}_{int(collection_start_time.timestamp())}"

        logger.info(f"🚀 Starting collection session: {session_id}")

        return {
            "session_id": session_id,
            "start_time": collection_start_time,
        }

    def _prepare_collection_payload(
        self, collection_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare the collection payload with defaults if needed."""
        if not collection_payload:
            collection_payload = {
                "data_types": ["products", "orders", "customers", "collections"]
            }
            logger.info("📋 Using default collection payload for all data types")
        else:
            logger.info(f"📋 Using provided collection payload: {collection_payload}")

        return collection_payload

    def _determine_collectable_data(
        self, permissions: Dict, collection_payload: Dict
    ) -> List[str]:
        """Determine which data types can be collected based on permissions and payload."""
        collectable_data = self._get_collectable_data_from_payload(
            permissions, collection_payload
        )

        if collectable_data:
            logger.info(f"✅ Can collect data types: {collectable_data}")
        else:
            logger.warning("❌ No data types can be collected due to permissions")

        return collectable_data

    def _create_no_permissions_response(self) -> Dict[str, Any]:
        """Create a response when no permissions are available."""
        return {
            "success": False,
            "message": "No permissions for data collection",
        }

    async def _trigger_normalization_for_results(
        self, shop_id: str, collection_results: Dict, start_time: datetime
    ):
        """Trigger normalization for the collected data."""
        specific_ids = collection_results.get("specific_ids", {})
        processed_types = collection_results.get("processed_types", [])

        await self._trigger_normalization(
            shop_id, processed_types, start_time, specific_ids
        )

    def _create_success_response(
        self, session_info: Dict, collection_results: Dict, collection_payload: Dict
    ) -> Dict[str, Any]:
        """Create a success response with collection metadata."""
        total_items = sum(
            len(data)
            for data in collection_results.get("collected_data", {}).values()
            if data
        )

        logger.info(
            f"✅ Collection session {session_info['session_id']} completed: {total_items} items"
        )

        return {
            "success": True,
            "message": f"Collected {total_items} items",
            "session_id": session_info["session_id"],
            "session_start_time": session_info["start_time"].isoformat(),
            "total_items": total_items,
            "collected_types": list(
                collection_results.get("collected_data", {}).keys()
            ),
            "collection_payload": collection_payload,
        }

    async def _check_permissions(
        self, shop_domain: str, access_token: str
    ) -> Dict[str, Any]:
        """Check permissions - simplified"""
        logger.info(
            f"🔍 _check_permissions called for {shop_domain} with access_token: {'Yes' if access_token else 'No'}"
        )

        await self.api_client.connect()
        if access_token:
            await self.api_client.set_access_token(shop_domain, access_token)
            logger.info(
                f"✅ Access token set for {shop_domain}, calling permission service"
            )
            permissions = await self.permission_service.check_shop_permissions(
                shop_domain, access_token
            )
            logger.info(f"✅ Permission service returned: {permissions}")
            return permissions
        else:
            logger.warning(f"⚠️ No access token provided for {shop_domain}")
        return {}

    def _get_collectable_data_types(
        self, permissions: Dict, includes: Dict
    ) -> List[str]:
        """Get list of collectable data types based on permissions and includes"""
        collectable = []
        for data_type, include in includes.items():
            if include and permissions.get(data_type):
                collectable.append(data_type)
        return collectable

    def _get_collectable_data_from_payload(
        self, permissions: Dict, collection_payload: Dict[str, Any]
    ) -> List[str]:
        """Get collectable data types based on collection payload - single flow"""
        collectable = []

        # Handle specific data_types array (unified for both webhook and analysis)
        if "data_types" in collection_payload:
            data_types = collection_payload["data_types"]
            for data_type in data_types:
                if permissions.get(data_type, False):
                    collectable.append(data_type)
                else:
                    logger.warning(f"No permission for {data_type}")

        # Handle individual include flags (for analysis triggers)
        else:
            includes = {
                "products": collection_payload.get("include_products", True),
                "orders": collection_payload.get("include_orders", True),
                "customers": collection_payload.get("include_customers", True),
                "collections": collection_payload.get("include_collections", True),
            }

            for data_type, include in includes.items():
                if include and permissions.get(data_type):
                    collectable.append(data_type)

        # Handle additional data types from payload
        additional_types = collection_payload.get("additional_data_types", [])
        for data_type in additional_types:
            if data_type not in collectable:
                collectable.append(data_type)

        logger.info(f"Collectable data types from payload: {collectable}")
        return collectable

    async def _collect_and_store_data(
        self,
        shop_domain: str,
        access_token: str,
        shop_id: str,
        data_types: List[str],
        collection_payload: Dict[str, Any] = None,
    ) -> Dict:
        """
        Collect and store data for multiple data types in parallel.

        This method handles both webhook events (specific IDs) and bulk collection
        by processing all data types concurrently for better performance.
        """
        logger.info(
            f"🔄 Starting parallel collection for {len(data_types)} data types: {data_types}"
        )

        # Step 1: Prepare collection tasks for each data type
        collection_tasks = self._prepare_collection_tasks(
            data_types, shop_domain, shop_id, access_token, collection_payload
        )

        # Step 2: Execute all collection tasks in parallel
        collection_results = await self._execute_collection_tasks(
            collection_tasks, data_types
        )

        # Step 3: Store the collected data
        processed_types = await self._store_collected_data(collection_results, shop_id)

        # Step 4: Extract specific IDs for webhook events
        specific_ids = self._extract_specific_ids_from_payload(collection_payload)

        return {
            "collected_data": collection_results,
            "processed_types": processed_types,
            "specific_ids": specific_ids,
        }

    def _prepare_collection_tasks(
        self,
        data_types: List[str],
        shop_domain: str,
        shop_id: str,
        access_token: str,
        collection_payload: Dict[str, Any],
    ) -> List:
        """Prepare collection tasks for each data type."""
        tasks = []

        for data_type in data_types:
            # Check if this data type has specific IDs (for webhooks)
            specific_ids = self._get_specific_ids_for_data_type(
                data_type, collection_payload
            )

            task = self._collect_data_by_type(
                data_type, shop_domain, shop_id, access_token, specific_ids=specific_ids
            )
            tasks.append(task)

            if specific_ids:
                logger.info(f"🎯 Will collect specific {data_type} IDs: {specific_ids}")
            else:
                logger.info(f"📦 Will collect all {data_type} data")

        return tasks

    def _get_specific_ids_for_data_type(
        self, data_type: str, collection_payload: Dict[str, Any]
    ) -> Optional[List[str]]:
        """Get specific IDs for a data type if this is a webhook event."""
        if collection_payload and "specific_ids" in collection_payload:
            specific_ids = collection_payload.get("specific_ids", {})
            return specific_ids.get(data_type)
        return None

    async def _execute_collection_tasks(
        self, tasks: List, data_types: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Execute all collection tasks in parallel and handle results."""
        logger.info(f"⚡ Executing {len(tasks)} collection tasks in parallel")

        results = await asyncio.gather(*tasks, return_exceptions=True)

        collected_data = {}

        for i, result in enumerate(results):
            data_type = data_types[i]
            if isinstance(result, Exception):
                logger.error(f"❌ Collection failed for {data_type}: {result}")
                collected_data[data_type] = []
            else:
                collected_data[data_type] = result
                logger.info(f"✅ Collected {len(result)} {data_type} items")

        return collected_data

    async def _store_collected_data(
        self, collected_data: Dict[str, List[Dict]], shop_id: str
    ) -> List[str]:
        """Store all collected data in the database."""
        processed_types = []

        for data_type, data in collected_data.items():
            if data and len(data) > 0:
                try:
                    await self._store_data(data_type, data, shop_id)
                    processed_types.append(data_type)
                    logger.info(f"💾 Stored {len(data)} {data_type} items in database")
                except Exception as e:
                    logger.error(f"❌ Failed to store {data_type} data: {e}")
            else:
                logger.info(f"📭 No {data_type} data to store")

        return processed_types

    def _extract_specific_ids_from_payload(
        self, collection_payload: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """Extract specific IDs from collection payload for webhook events."""
        specific_ids = {}

        if collection_payload and collection_payload.get("specific_ids"):
            # The specific_ids is already a dict with data types as keys
            specific_ids = collection_payload.get("specific_ids", {})
            logger.info(f"🎯 Extracted specific IDs: {specific_ids}")

        return specific_ids

    async def _store_data(self, data_type: str, data: List[Dict], shop_id: str):
        """Store data using appropriate storage method"""
        config = self.DATA_TYPES.get(data_type)
        if config:
            storage_method = getattr(self.data_storage, config["store"])
            await storage_method(data, shop_id)

    async def _trigger_normalization(
        self,
        shop_id: str,
        data_types: List[str],
        collection_start_time: datetime,
        specific_ids: Dict[str, List[str]] = None,
    ):
        """
        Unified normalization trigger - no complex mode switching
        Just process data chunks like a proper Kafka system
        """
        if not data_types:
            logger.info("No data types to normalize")
            return

        logger.info(
            f"🔄 Triggering normalization for shop {shop_id}",
            data_types=data_types,
            has_specific_ids=bool(specific_ids),
        )

        try:
            # Small delay to ensure database transaction is committed
            import asyncio

            await asyncio.sleep(0.1)

            # Initialize Kafka publisher
            publisher = await self._initialize_normalization_publisher()

            try:
                # Process each data type
                for data_type in data_types:
                    await self._process_data_type_normalization(
                        publisher, shop_id, data_type, specific_ids
                    )
            finally:
                await publisher.close()

        except Exception as e:
            logger.error(f"❌ Failed to trigger normalization via Kafka: {e}")

    async def _initialize_normalization_publisher(self):
        """Initialize the Kafka event publisher for normalization events."""
        from app.core.messaging.event_publisher import EventPublisher
        from app.core.config.kafka_settings import kafka_settings

        publisher = EventPublisher(kafka_settings.model_dump())
        await publisher.initialize()
        return publisher

    async def _process_data_type_normalization(
        self,
        publisher,
        shop_id: str,
        data_type: str,
        specific_ids: Dict[str, List[str]],
    ):
        """Process normalization for a single data type - unified approach."""
        # Check if this is a webhook event with specific IDs
        if specific_ids and specific_ids.get(data_type):
            await self._execute_webhook_normalization(
                publisher, shop_id, data_type, specific_ids[data_type]
            )
        else:
            await self._execute_batch_normalization(publisher, shop_id, data_type)

    async def _execute_webhook_normalization(
        self,
        publisher,
        shop_id: str,
        data_type: str,
        shopify_ids: List[str],
    ):
        """Execute webhook normalization for specific IDs."""
        logger.info(
            f"🎯 Processing webhook normalization for {data_type} IDs: {shopify_ids}"
        )

        for shopify_id in shopify_ids:
            normalization_event = self._create_webhook_normalization_event(
                shop_id, data_type, shopify_id
            )

            message_id = await publisher.publish_normalization_event(
                normalization_event
            )

            logger.info(
                f"✅ Webhook normalization event published for {data_type} {shopify_id}",
                shop_id=shop_id,
                data_type=data_type,
                shopify_id=shopify_id,
                message_id=message_id,
            )

    def _create_webhook_normalization_event(
        self, shop_id: str, data_type: str, shopify_id: str
    ) -> Dict[str, Any]:
        """Create a normalization event for webhook processing."""
        return {
            "event_type": "normalize_data",
            "shop_id": shop_id,
            "data_type": data_type,
            "format": "graphql",  # Webhook events use GraphQL format
            "shopify_id": shopify_id,  # Specific ID for webhook processing
            "timestamp": now_utc().isoformat(),
            "source": "data_collection_service_webhook",
        }

    async def _execute_batch_normalization(
        self,
        publisher,
        shop_id: str,
        data_type: str,
    ):
        """Execute batch normalization for time-based processing."""
        logger.info(f"📦 Processing batch normalization for {data_type}")

        # Create and publish batch normalization event
        normalization_event = self._create_batch_normalization_event(shop_id, data_type)

        message_id = await publisher.publish_normalization_event(normalization_event)

        logger.info(
            f"✅ Batch normalization event published for {data_type}",
            shop_id=shop_id,
            data_type=data_type,
            message_id=message_id,
        )

    async def _update_collection_watermark(self, shop_id: str, data_type: str):
        """Update the collection watermark for batch processing."""
        try:
            # Find the latest timestamp from collected data
            latest = await self.raw_data_repository.get_latest_shopify_timestamp(
                shop_id=shop_id, data_type=data_type
            )

            if not latest:
                logger.warning(
                    f"⚠️ No collected data found for {data_type}, skipping watermark update"
                )
                return

            # Update the watermark
            latest_aware = self._ensure_aware_utc(latest)
            end_iso = latest_aware.isoformat()

            await self._upsert_processing_watermark(
                shop_id=shop_id, data_type=data_type, iso_time=end_iso
            )

            logger.info(
                "💾 Collection watermark updated",
                extra={
                    "shop_id": shop_id,
                    "data_type": data_type,
                    "lastCollectedAt": end_iso,
                },
            )

        except Exception as e:
            logger.error(f"Failed to update watermark for {data_type}: {e}")

    def _create_batch_normalization_event(
        self, shop_id: str, data_type: str
    ) -> Dict[str, Any]:
        """Create a normalization event for batch processing."""
        return {
            "event_type": "normalize_data",
            "shop_id": shop_id,
            "data_type": data_type,
            "format": "graphql",
            "timestamp": now_utc().isoformat(),
            "source": "data_collection_service",
        }

    async def _upsert_processing_watermark(
        self, shop_id: str, data_type: str, iso_time: str
    ) -> None:
        """Common watermark writer used by collection to mark last collected window end.
        Uses existing NormalizationWatermark table to avoid schema churn.
        """
        # Accept both Z and +00:00 formats
        last_dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
        # Normalize to aware UTC
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        else:
            last_dt = last_dt.astimezone(timezone.utc)
        # Delegate to repository for upsert
        await self.pipeline_watermark_repository.upsert_collection_watermark(
            shop_id=shop_id, data_type=data_type, last_dt=last_dt
        )

    async def _collect_data_generic(
        self,
        shop_domain: str,
        data_type: str,
        api_method: str,
        query_since: Optional[datetime],
        limit: Optional[int] = None,
        since_id: Optional[str] = None,
        query: Optional[str] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Generic data collection method - Industry Standard Simplified"""
        logger.info(f"Collecting {data_type} for {shop_domain}")

        raw_items = []
        cursor = since_id
        batch_size = min(limit or self.BATCH_SIZE, self.BATCH_SIZE)
        start_time = now_utc()

        while True:
            # Check timeout
            if (now_utc() - start_time).seconds > self.TIMEOUT_SECONDS:
                logger.warning(f"Timeout for {data_type} collection")
                break

            # Get batch from API
            try:
                api_method_func = getattr(self.api_client, api_method)
                result = await api_method_func(
                    shop_domain=shop_domain, limit=batch_size, cursor=cursor, **kwargs
                )
            except Exception as e:
                logger.error(f"API call failed for {data_type}: {e}")
                break

            if not result or "edges" not in result:
                break

            edges = result["edges"]
            if not edges:
                break

            # Extract items from edges
            for edge in edges:
                item_data = edge.get("node", {})
                if item_data:
                    raw_items.append(item_data)

            # Check pagination
            page_info = result.get("pageInfo", {})
            if not page_info.get("hasNextPage", False):
                break

            cursor = page_info.get("endCursor")
            if not cursor:
                break

            # Check limit
            if limit and len(raw_items) >= limit:
                break

            # Rate limiting
            await asyncio.sleep(self.RATE_LIMIT_DELAY)

        logger.info(f"Collected {len(raw_items)} {data_type} items")
        return raw_items

    async def _collect_specific_items_by_ids(
        self, data_type: str, shop_domain: str, specific_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Collect specific items by IDs using GraphQL - for webhooks"""
        collected_items = []

        for item_id in specific_ids:
            try:
                item_data = await self._collect_single_item_by_id(
                    data_type, shop_domain, item_id
                )
                if item_data:
                    collected_items.append(item_data)
            except Exception as e:
                logger.error(f"Failed to collect {data_type} {item_id}: {e}")

        logger.info(f"Collected {len(collected_items)} specific {data_type} items")
        return collected_items

    async def _collect_single_item_by_id(
        self, data_type: str, shop_domain: str, item_id: str
    ) -> Dict[str, Any]:
        """Collect a single item by ID using existing API client methods with full data traversal"""
        try:
            if data_type == "products":
                # Use the modified get_products method with product_ids parameter
                result = await self.api_client.get_products(
                    shop_domain=shop_domain, product_ids=[item_id]
                )
                # Extract the product from the edges format
                edges = result.get("edges", [])
                if edges:
                    return edges[0]["node"]
                return None
            elif data_type == "collections":
                # Use the modified get_collections method with collection_ids parameter
                result = await self.api_client.get_collections(
                    shop_domain=shop_domain, collection_ids=[item_id]
                )
                # Extract the collection from the edges format
                edges = result.get("edges", [])
                if edges:
                    return edges[0]["node"]
                return None
            elif data_type == "orders":
                # Use the modified get_orders method with order_ids parameter
                result = await self.api_client.get_orders(
                    shop_domain=shop_domain, order_ids=[item_id]
                )
                # Extract the order from the edges format
                edges = result.get("edges", [])
                if edges:
                    return edges[0]["node"]
                return None
            elif data_type == "customers":
                # Use the modified get_customers method with customer_ids parameter
                result = await self.api_client.get_customers(
                    shop_domain=shop_domain, customer_ids=[item_id]
                )
                # Extract the customer from the edges format
                edges = result.get("edges", [])
                if edges:
                    return edges[0]["node"]
                return None
            else:
                logger.warning(
                    f"Unknown data type for specific collection: {data_type}"
                )
                return None
        except Exception as e:
            logger.error(f"Failed to collect {data_type} {item_id}: {e}")
            return None
