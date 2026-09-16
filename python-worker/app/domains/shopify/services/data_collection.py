"""
Shopify data collection service implementation for BetterBundle Python Worker
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

from app.core.logging import get_logger
from app.shared.helpers.datetime_utils import now_utc, parse_iso_timestamp
from ..interfaces.data_collector import IShopifyDataCollector
from ..interfaces.api_client import IShopifyAPIClient
from .api.base_client import page_info_of
from ..interfaces.permission_service import IShopifyPermissionService
from .data_storage import ShopifyDataStorageService

from app.repository.RawDataRepository import RawDataRepository
from app.repository.ShopRepository import ShopRepository

logger = get_logger(__name__)


class ShopifyDataCollectionService(IShopifyDataCollector):
    """Shopify data collection service with permission checking and adaptive collection"""

    def __init__(
        self,
        api_client: IShopifyAPIClient,
        permission_service: IShopifyPermissionService,
        data_storage: ShopifyDataStorageService = None,
    ):
        self.api_client = api_client
        self.permission_service = permission_service

        # Inject storage service or create default
        self.data_storage = data_storage or ShopifyDataStorageService()
        self.raw_data_repository = RawDataRepository()
        self.shop_repository = ShopRepository()

        # One long-lived Kafka publisher for the life of the service. Building
        # and tearing one down per job meant a TCP connect, metadata fetch and
        # close for every webhook — seconds of the ~5.7s each event was taking,
        # which is why the consumer fell behind its own producer.
        self._publisher = None

        # Collection settings - Industry standard constants
        self.BATCH_SIZE = 250
        self.TIMEOUT_SECONDS = 300
        self.RATE_LIMIT_DELAY = 0.1
        self.MAX_DAYS_BACK = 90

        # Full catalog sweeps running at once, across all shops. A sweep is
        # long and heavy — every page of every data type — so several shops
        # installing at the same time would otherwise multiply straight through
        # to the database pool and the API budget. Webhooks are not gated by
        # this; they are single objects and must stay responsive.
        self._backfill_slots = asyncio.Semaphore(2)

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
        on_page=None,
    ):
        """Collect one data type.

        Returns a list of items for a webhook (a handful of objects), or — for
        a full sweep with `on_page` — the number of items streamed to storage.
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
                data_type, shop_domain, config, limit, since_id, on_page=on_page
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
        on_page=None,
    ):
        """Execute full collection for a data type."""

        return await self._collect_data_generic(
            shop_domain=shop_domain,
            data_type=data_type,
            api_method=config["api"],
            query_since=None,
            query=None,
            limit=limit,
            since_id=since_id,
            on_page=on_page,
        )

    async def _has_any_raw_data(self, shop_id: str, data_type: str) -> bool:
        """Check if we have any raw data for this data type using repository."""
        try:
            count = await self.raw_data_repository.get_raw_count(shop_id, data_type)
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

            # Step 4: Collect and store the data. A full sweep queues behind
            # the backfill slots so several shops syncing at once cannot
            # multiply into the database pool; a webhook is one object and
            # goes straight through.
            is_backfill = not collection_payload.get("specific_ids")
            if is_backfill:
                async with self._backfill_slots:
                    collection_results = await self._collect_and_store_data(
                        shop_domain, access_token, shop_id,
                        collectable_data, collection_payload,
                    )
            else:
                collection_results = await self._collect_and_store_data(
                    shop_domain, access_token, shop_id,
                    collectable_data, collection_payload,
                )

            # Step 5: Trigger normalization for whatever did land. Partial
            # progress is still worth normalising, and storage is an upsert,
            # so the retry below re-collects safely.
            await self._trigger_normalization_for_results(
                shop_id, collection_results, session_info["start_time"]
            )

            # Step 6: Record how much of the catalog actually exists upstream,
            # so progress can be measured against the shop rather than against
            # our own table. Only on a full sweep — a webhook fetches one
            # object, and billing a whole extra API round-trip to every webhook
            # is exactly the per-event cost that put the consumer behind its
            # own producer.
            if not collection_payload.get("specific_ids"):
                await self._record_catalog_totals(shop_domain, shop_id)

            # Step 7: A data type that failed means an incomplete catalog.
            # Reporting success here is what let a 997-product shop sit at 251
            # rows while every status surface said the sync was fine.
            failures = collection_results.get("failures") or {}
            if failures:
                raise RuntimeError(
                    "Incomplete collection for "
                    f"{shop_domain}: " + "; ".join(
                        f"{dt}: {err}" for dt, err in failures.items()
                    )
                )

            return self._create_success_response(
                session_info, collection_results, collection_payload
            )

        except Exception as e:
            logger.error(f"Collection failed for {shop_domain}: {e}")
            raise

    async def _record_catalog_totals(self, shop_domain: str, shop_id: str) -> None:
        """Save Shopify's own product/collection counts onto the shop record.

        Best effort — never fail a collection because the counter query did.
        """
        try:
            counts = await self.api_client.get_catalog_counts(shop_domain)
            if counts:
                await self.shop_repository.update_catalog_totals(shop_id, counts)
        except Exception as e:
            logger.warning(f"Could not record catalog totals for {shop_domain}: {e}")

    def _initialize_collection_session(self, shop_id: str) -> Dict[str, Any]:
        """Initialize a new collection session with metadata."""
        collection_start_time = now_utc()
        session_id = f"collection_{shop_id}_{int(collection_start_time.timestamp())}"

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

        return collection_payload

    def _determine_collectable_data(
        self, permissions: Dict, collection_payload: Dict
    ) -> List[str]:
        """Determine which data types can be collected based on permissions and payload."""
        collectable_data = self._get_collectable_data_from_payload(
            permissions, collection_payload
        )

        if not collectable_data:
            logger.warning("No data types can be collected due to permissions")

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
        counts = collection_results.get("counts", {})
        total_items = sum(counts.values())

        return {
            "success": True,
            "message": f"Collected {total_items} items",
            "session_id": session_info["session_id"],
            "session_start_time": session_info["start_time"].isoformat(),
            "total_items": total_items,
            "orders_collected": counts.get("orders", 0),
            "products_collected": counts.get("products", 0),
            "customers_collected": counts.get("customers", 0),
            "collections_collected": counts.get("collections", 0),
            "collected_types": list(counts.keys()),
            "collection_payload": collection_payload,
        }

    async def _check_permissions(
        self, shop_domain: str, access_token: str
    ) -> Dict[str, Any]:
        """Check permissions - simplified"""
        await self.api_client.connect()
        if access_token:
            await self.api_client.set_access_token(shop_domain, access_token)
            permissions = await self.permission_service.check_shop_permissions(
                shop_domain, access_token
            )
            return permissions
        else:
            logger.warning(f"No access token provided for {shop_domain}")
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
        # Step 1: Prepare collection tasks for each data type
        collection_tasks = self._prepare_collection_tasks(
            data_types, shop_domain, shop_id, access_token, collection_payload
        )

        # Step 2: Execute all collection tasks in parallel. Each stores its
        # own data page by page and reports how many items it wrote, so
        # nothing accumulates the whole catalog in memory.
        counts, failures = await self._execute_collection_tasks(
            collection_tasks, data_types
        )

        processed_types = [
            dt for dt, n in counts.items() if n and dt not in failures
        ]

        # Step 3: Extract specific IDs for webhook events
        specific_ids = self._extract_specific_ids_from_payload(collection_payload)

        return {
            "counts": counts,
            "processed_types": processed_types,
            "specific_ids": specific_ids,
            "failures": failures,
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

        source = (
            "webhook"
            if (collection_payload or {}).get("trigger") == "webhook"
            else "backfill"
        )

        # A webhook names the objects it is about. If it named any, this is a
        # targeted fetch, and no data type in it may quietly widen into a full
        # catalog sweep — see _collect_and_store_type.
        targeted = bool((collection_payload or {}).get("specific_ids"))

        for data_type in data_types:
            # Check if this data type has specific IDs (for webhooks)
            specific_ids = self._get_specific_ids_for_data_type(
                data_type, collection_payload
            )

            tasks.append(
                self._collect_and_store_type(
                    data_type, shop_domain, shop_id, access_token,
                    specific_ids, source, targeted, collection_payload,
                )
            )

        return tasks

    async def _collect_and_store_type(
        self,
        data_type: str,
        shop_domain: str,
        shop_id: str,
        access_token: str,
        specific_ids: Optional[List[str]],
        source: str,
        targeted: bool = False,
        collection_payload: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Collect one data type, storing as it goes, and return the count.

        Storage happens per page rather than once at the end so peak memory is
        one page, not the whole catalog.
        """
        if targeted and not specific_ids:
            # This data type belongs to a targeted webhook but no ids of its
            # own came through. Inventory is the case that matters: the event
            # carries an inventory item, and the product that owns it is what
            # needs re-collecting.
            specific_ids = await self._resolve_targeted_ids(
                data_type, shop_domain, collection_payload or {}
            )

            if not specific_ids:
                # Falling through here would run a full catalog sweep for a
                # single webhook. Every stock change re-fetched all 997
                # products, which is what buried the consumer and exhausted
                # the container's memory.
                logger.warning(
                    f"Webhook for {data_type} carried no usable ids "
                    f"({(collection_payload or {}).get('specific_ids')}); "
                    f"skipping rather than sweeping the whole catalog"
                )
                return 0

        async def store_page(items: List[Dict[str, Any]]) -> None:
            if items:
                await self._store_data(data_type, items, shop_id, source)

        result = await self._collect_data_by_type(
            data_type,
            shop_domain,
            shop_id,
            access_token,
            specific_ids=specific_ids,
            on_page=None if specific_ids else store_page,
        )

        if specific_ids:
            # Webhook path: a handful of objects, returned in full.
            await store_page(result)
            return len(result)
        return result

    async def _resolve_targeted_ids(
        self, data_type: str, shop_domain: str, collection_payload: Dict[str, Any]
    ) -> Optional[List[str]]:
        """Translate ids a webhook carries under another key into this type's.

        Only inventory needs this today: inventory_updated arrives with an
        inventory item id, and products are what get collected.
        """
        ids = (collection_payload.get("specific_ids") or {})
        inventory_item_ids = ids.get("inventory_items")

        if data_type == "products" and inventory_item_ids:
            resolved = await self.api_client.get_product_ids_for_inventory_items(
                shop_domain, inventory_item_ids
            )
            if resolved:
                logger.info(
                    f"Resolved {len(inventory_item_ids)} inventory item(s) to "
                    f"{len(resolved)} product(s)"
                )
            return resolved

        return None

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
    ) -> tuple:
        """Execute all collection tasks in parallel and handle results.

        Returns (collected_data, failures). Failures are returned rather than
        swallowed: a data type that raised produced an incomplete result, and
        the caller must not report that as a successful collection.
        """

        results = await asyncio.gather(*tasks, return_exceptions=True)

        counts: Dict[str, int] = {}
        failures: Dict[str, str] = {}

        for i, result in enumerate(results):
            data_type = data_types[i]
            if isinstance(result, BaseException):
                logger.error(f"❌ Collection failed for {data_type}: {result}")
                counts[data_type] = 0
                failures[data_type] = str(result)
            else:
                counts[data_type] = result

        return counts, failures

    def _extract_specific_ids_from_payload(
        self, collection_payload: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """Extract specific IDs from collection payload for webhook events."""
        specific_ids = {}

        if collection_payload and collection_payload.get("specific_ids"):
            # The specific_ids is already a dict with data types as keys
            specific_ids = collection_payload.get("specific_ids", {})

        return specific_ids

    async def _store_data(
        self, data_type: str, data: List[Dict], shop_id: str, source: str = None
    ):
        """Store data using appropriate storage method.

        `source` records how this data reached us. It has to travel from the
        original trigger all the way to the raw row, because normalisation
        reads it to decide whether to publish an attribution job — a
        webhook-delivered order must be attributed, a historical import must
        not.
        """
        config = self.DATA_TYPES.get(data_type)
        if config:
            storage = (
                self.data_storage.with_source(source)
                if source
                else self.data_storage
            )
            storage_method = getattr(storage, config["store"])
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
            return

        try:
            # Small delay to ensure database transaction is committed
            import asyncio

            await asyncio.sleep(0.1)

            # Initialize Kafka publisher
            publisher = await self._initialize_normalization_publisher()

            # The publisher is shared and stays open; closing it here is what
            # made every job pay for a fresh Kafka connection.
            for data_type in data_types:
                await self._process_data_type_normalization(
                    publisher, shop_id, data_type, specific_ids
                )

        except Exception as e:
            logger.error(f"❌ Failed to trigger normalization via Kafka: {e}")

    async def _initialize_normalization_publisher(self):
        """Return the shared Kafka publisher, connecting it on first use."""
        if self._publisher is None:
            from app.core.messaging.event_publisher import EventPublisher
            from app.core.config.kafka_settings import kafka_settings

            publisher = EventPublisher(kafka_settings.model_dump())
            await publisher.initialize()
            self._publisher = publisher
        return self._publisher

    async def close(self):
        """Release the shared publisher."""
        if self._publisher is not None:
            await self._publisher.close()
            self._publisher = None

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

        for shopify_id in shopify_ids:
            normalization_event = self._create_webhook_normalization_event(
                shop_id, data_type, shopify_id
            )

            message_id = await publisher.publish_normalization_event(
                normalization_event
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

        # Create and publish batch normalization event
        normalization_event = self._create_batch_normalization_event(shop_id, data_type)

        message_id = await publisher.publish_normalization_event(normalization_event)

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
        last_dt = parse_iso_timestamp(iso_time)
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
        on_page=None,
        **kwargs,
    ):
        """Generic data collection.

        With `on_page`, each page is passed to that coroutine as it arrives and
        the total count is returned, so memory stays flat no matter how large
        the catalog is. Without it, every item is accumulated and returned —
        only safe for the handful of objects a webhook asks for.
        """

        raw_items = []
        collected = 0
        cursor = since_id
        batch_size = min(limit or self.BATCH_SIZE, self.BATCH_SIZE)
        start_time = now_utc()

        while True:
            # A timeout mid-pagination is a truncated catalog, not a finished
            # one. Raising makes the consumer retry and eventually DLQ it
            # instead of storing a partial catalog and reporting success.
            elapsed = (now_utc() - start_time).total_seconds()
            if elapsed > self.TIMEOUT_SECONDS:
                raise TimeoutError(
                    f"{data_type} collection for {shop_domain} exceeded "
                    f"{self.TIMEOUT_SECONDS}s after {len(raw_items)} items; "
                    f"aborting rather than reporting a partial catalog"
                )

            # Get batch from API
            try:
                api_method_func = getattr(self.api_client, api_method)
                result = await api_method_func(
                    shop_domain=shop_domain, limit=batch_size, cursor=cursor, **kwargs
                )
            except Exception as e:
                # Same reasoning: swallowing this returns the pages collected
                # so far and the caller cannot tell it from a complete run.
                logger.error(f"API call failed for {data_type}: {e}")
                raise

            if not result or "edges" not in result:
                break

            edges = result["edges"]
            if not edges:
                break

            # Extract items from edges
            page_items = [
                edge.get("node", {}) for edge in edges if edge.get("node")
            ]

            if on_page is not None:
                # Hand each page straight to storage. Holding the whole
                # catalog in memory first is what took the container out: a
                # thousand products with their variants, images, media and
                # metafields, times four data types collected in parallel,
                # before a single row was written.
                await on_page(page_items)
                collected += len(page_items)
            else:
                raw_items.extend(page_items)
                collected = len(raw_items)

            # Check pagination. The queries alias pageInfo into snake_case,
            # so reading "pageInfo"/"hasNextPage" here found nothing, defaulted
            # to False and ended every collection after the first page.
            has_next_page, cursor = page_info_of(result)
            if not has_next_page or not cursor:
                break

            # Check limit
            if limit and collected >= limit:
                break

            # Rate limiting
            await asyncio.sleep(self.RATE_LIMIT_DELAY)

        return raw_items if on_page is None else collected

    async def _collect_specific_items_by_ids(
        self, data_type: str, shop_domain: str, specific_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """Collect specific items by IDs using GraphQL - for webhooks"""
        # ✅ ADD LOGGING FOR SPECIFIC ITEM COLLECTION
        logger.info(
            f"📥 Collecting {data_type} data for IDs: {specific_ids} from {shop_domain}"
        )

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

        return collected_items

    async def _collect_single_item_by_id(
        self, data_type: str, shop_domain: str, item_id: str
    ) -> Dict[str, Any]:
        """Collect a single item by ID using existing API client methods with full data traversal"""
        try:
            # ✅ ADD LOGGING FOR SINGLE ITEM COLLECTION
            logger.info(f"🔍 Fetching {data_type} {item_id} from {shop_domain}")

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
