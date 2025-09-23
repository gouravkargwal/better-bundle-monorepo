"""
Shopify data collection service implementation for BetterBundle Python Worker
"""

import asyncio
from datetime import datetime, timedelta
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

    async def _collect_data_by_type(
        self,
        data_type: str,
        shop_domain: str,
        shop_id: str,
        access_token: str = None,
        limit: Optional[int] = None,
        since_id: Optional[str] = None,
        force_full_collection: bool = False,
    ) -> List[Dict[str, Any]]:
        """Collect data by type - Simplified Industry Standard"""
        config = self.DATA_TYPES.get(data_type)
        if not config:
            raise ValueError(f"Unsupported data type: {data_type}")

        force_full_collection = bool(force_full_collection)

        pw = await self.pipeline_watermark_repository.get_by_shop_and_data_type(
            shop_id=shop_id, data_type=data_type
        )
        should_do_full = force_full_collection or (pw is None)

        if should_do_full:
            logger.info(f"Full collection for {data_type}")
            return await self._collect_data_generic(
                shop_domain=shop_domain,
                data_type=data_type,
                api_method=config["api"],
                query_since=None,
                query=None,
                limit=limit,
                since_id=since_id,
            )
        else:
            # Incremental collection - Only collect recent data using PipelineWatermark
            logger.info(f"Incremental collection for {data_type}")
            from datetime import timedelta

            # Read watermark
            last_collected = pw.last_collected_at if pw else None
            # Add epsilon and clamp to last 7 days
            safe_since = (
                (last_collected + timedelta(seconds=1)) if last_collected else None
            )
            query_since = (
                max(safe_since, now_utc() - timedelta(days=7))
                if safe_since
                else now_utc() - timedelta(days=7)
            )
            # Use strict greater-than for GraphQL-style filters
            query_filter = f"{config['field']}:>'{query_since.isoformat()}'"

            logger.info(
                "📅 Collection watermark window",
                extra={
                    "data_type": data_type,
                    "lastCollectedAt": (
                        last_collected.isoformat() if last_collected else None
                    ),
                    "query_since": query_since.isoformat(),
                    "filter": query_filter,
                },
            )

            result = await self._collect_data_generic(
                shop_domain=shop_domain,
                data_type=data_type,
                api_method=config["api"],
                query_since=query_since,
                query=query_filter,
                limit=limit,
                since_id=since_id,
            )

            if result and len(result) > 0:
                logger.info(
                    f"✅ Incremental collection found {len(result)} new/updated {data_type}"
                )
                return result
            else:
                logger.info(
                    f"📭 No new/updated data found for {data_type} in incremental collection"
                )
                return []

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
            return max(last_updated_at, max_days_back)
        else:
            return max_days_back

    async def collect_all_data(
        self,
        shop_domain: str,
        access_token: str,
        shop_id: str,
    ) -> Dict[str, Any]:
        """Collect all available data from Shopify API with session tracking"""
        # Start collection session
        collection_start_time = now_utc()
        session_id = f"collection_{shop_id}_{int(collection_start_time.timestamp())}"

        try:
            # 1. Check permissions
            permissions = await self._check_permissions(shop_domain, access_token)
            collectable_data = self._get_collectable_data_types(
                permissions,
                {
                    "products": True,
                    "orders": True,
                    "customers": True,
                    "collections": True,
                },
            )

            if not collectable_data:
                return {
                    "success": False,
                    "message": "No permissions for data collection",
                }

            results = await self._collect_and_store_data(
                shop_domain, access_token, shop_id, collectable_data
            )

            # await self._trigger_normalization(
            #     shop_id, results.get("processed_types", []), collection_start_time
            # )

            total_items = sum(
                len(data) for data in results.get("collected_data", {}).values() if data
            )
            logger.info(
                f"✅ Collection session {session_id} completed: {total_items} items"
            )

            return {
                "success": True,
                "message": f"Collected {total_items} items",
                "session_id": session_id,
                "session_start_time": collection_start_time.isoformat(),
                "total_items": total_items,
            }

        except Exception as e:
            logger.error(f"Collection failed for {shop_domain}: {e}")
            raise

    async def _check_permissions(
        self, shop_domain: str, access_token: str
    ) -> Dict[str, Any]:
        """Check permissions - simplified"""
        await self.api_client.connect()
        if access_token:
            await self.api_client.set_access_token(shop_domain, access_token)
            return await self.permission_service.check_shop_permissions(
                shop_domain, access_token
            )
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

    async def _collect_and_store_data(
        self, shop_domain: str, access_token: str, shop_id: str, data_types: List[str]
    ) -> Dict:
        """Collect and store data in parallel - simplified"""
        # Collect data in parallel
        tasks = [
            self._collect_data_by_type(dt, shop_domain, access_token)
            for dt in data_types
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        collected_data = {}
        processed_types = []

        for i, result in enumerate(results):
            data_type = data_types[i]
            if isinstance(result, Exception):
                logger.error(f"Collection failed for {data_type}: {result}")
            else:
                collected_data[data_type] = result
                # Store data
                if result and len(result) > 0:
                    await self._store_data(data_type, result, shop_id)
                    processed_types.append(data_type)

        return {"collected_data": collected_data, "processed_types": processed_types}

    async def _store_data(self, data_type: str, data: List[Dict], shop_id: str):
        """Store data using appropriate storage method"""
        config = self.DATA_TYPES.get(data_type)
        if config:
            storage_method = getattr(self.data_storage, config["store"])
            await storage_method(data, shop_id)

    async def _trigger_normalization(
        self, shop_id: str, data_types: List[str], collection_start_time: datetime
    ):
        """Trigger normalization for processed data types using Kafka with per-data-type watermarks"""
        if not data_types:
            return

        try:
            from app.core.messaging.event_publisher import EventPublisher
            from app.core.config.kafka_settings import kafka_settings

            logger.info(
                f"🔄 Triggering normalization via Kafka for shop {shop_id}",
                data_types=data_types,
            )

            # Initialize event publisher
            publisher = EventPublisher(kafka_settings.model_dump())
            await publisher.initialize()

            try:
                # For each data type, compute the latest collected end (from RAW) and upsert watermark
                for data_type in data_types:
                    # Find the latest shopify_updated_at we've stored via repository
                    latest = (
                        await self.raw_data_repository.get_latest_shopify_timestamp(
                            shop_id=shop_id, data_type=data_type
                        )
                    )

                    if not latest:
                        logger.warning(
                            f"⚠️ No collected window found for {data_type}, skipping watermark update"
                        )
                    else:
                        end_iso = latest.isoformat()
                        # Upsert collection watermark to PipelineWatermark
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

                    # Publish normalization event (window will be derived from watermark by consumer)
                    normalization_event = {
                        "event_type": "normalize_data",
                        "shop_id": shop_id,
                        "data_type": data_type,
                        "format": "graphql",
                        "timestamp": now_utc().isoformat(),
                        "source": "data_collection_service",
                    }

                    message_id = await publisher.publish_normalization_event(
                        normalization_event
                    )

                    logger.info(
                        f"✅ Normalization event published for {data_type}",
                        shop_id=shop_id,
                        data_type=data_type,
                        message_id=message_id,
                    )

            finally:
                await publisher.close()

        except Exception as e:
            logger.error(f"❌ Failed to trigger normalization via Kafka: {e}")

    async def _upsert_processing_watermark(
        self, shop_id: str, data_type: str, iso_time: str
    ) -> None:
        """Common watermark writer used by collection to mark last collected window end.
        Uses existing NormalizationWatermark table to avoid schema churn.
        """
        # Accept both Z and +00:00 formats
        last_dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
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
