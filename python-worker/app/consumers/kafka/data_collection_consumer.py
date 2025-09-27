from typing import Dict, Any
from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.core.messaging.event_subscriber import EventSubscriber
from app.core.logging import get_logger
from app.repository.ShopRepository import ShopRepository
from app.services.shop_cache_service import get_shop_cache_service

logger = get_logger(__name__)


class DataCollectionKafkaConsumer:
    """Kafka consumer for data collection jobs - handles events directly"""

    def __init__(self, shopify_service=None, shop_repo: ShopRepository = None):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self.event_subscriber = EventSubscriber(kafka_settings.model_dump())
        self.shopify_service = shopify_service
        self.shop_repo = shop_repo or ShopRepository()
        self._initialized = False

    async def initialize(self):
        """Initialize consumer"""
        try:
            if not self.shopify_service:
                raise ValueError(
                    "Shopify service is required for data collection consumer"
                )

            await self.consumer.initialize(
                topics=["data-collection-jobs", "shopify-events"],
                group_id="data-collection-processors",
            )

            await self.event_subscriber.initialize(
                topics=["data-collection-jobs", "shopify-events"],
                group_id="data-collection-processors",
                existing_consumer=self.consumer,
            )

            self.event_subscriber.add_handler(self)
            self._initialized = True

        except Exception as e:
            logger.exception(f"❌ Failed to initialize data collection consumer: {e}")
            raise

    async def start_consuming(self):
        """Start consuming messages"""
        if not self._initialized:
            await self.initialize()
        try:
            await self.event_subscriber.consume_and_handle(
                topics=["data-collection-jobs", "shopify-events"],
                group_id="data-collection-processors",
            )
        except Exception as e:
            logger.exception(f"❌ Error in data collection consumer: {e}")
            raise

    async def close(self):
        """Close consumer"""
        if self.consumer:
            await self.consumer.close()
        if self.event_subscriber:
            await self.event_subscriber.close()

    async def handle(self, event: Dict[str, Any]) -> bool:
        """Handle both data collection jobs and webhook events"""
        try:
            event_type = event.get("event_type")

            # Resolve shop data once for all event types
            shop_data = await self._resolve_shop_data(event)
            if not shop_data:
                return False

            # Route to appropriate handler
            if event_type == "data_collection":
                return await self._handle_data_collection_job(event, shop_data)
            elif event_type in [
                "product_updated",
                "product_created",
                "product_deleted",
                "collection_updated",
                "collection_created",
                "collection_deleted",
                "order_paid",
                "order_created",
                "order_updated",
                "order_cancelled",
                "customer_created",
                "customer_updated",
            ]:
                return await self._handle_webhook_event(event, shop_data)
            else:
                logger.warning(f"❌ Unknown event type: {event_type}")
                return False

        except Exception as e:
            logger.exception(f"Failed to process event: {e}")
            return False

    async def _resolve_shop_data(self, event: Dict[str, Any]) -> Dict[str, Any] | None:
        """Resolve shop data for any event type"""
        event_type = event.get("event_type")

        # For data collection jobs, use shop_id
        if event_type == "data_collection":
            shop_id = event.get("shop_id")
            if not shop_id:
                logger.error("❌ No shop_id for data collection job")
                return None

            shop_record = await self.shop_repo.get_active_by_id(shop_id)
            if not shop_record or not shop_record.access_token:
                logger.error(f"❌ Shop not found for shop_id: {shop_id}")
                return None

            return {
                "id": shop_record.id,
                "domain": shop_record.shop_domain,
                "access_token": shop_record.access_token,
            }

        # For webhook events, use shop_domain
        else:
            shop_domain = event.get("shop_domain")
            if not shop_domain:
                logger.error("❌ No shop_domain for webhook event")
                return None

            shop_cache = await get_shop_cache_service()
            shop_data = await shop_cache.get_active_shop_by_domain(shop_domain)
            if not shop_data:
                logger.error(f"❌ Shop not found for domain: {shop_domain}")
                return None

            return shop_data

    def can_handle(self, event_type: str) -> bool:
        """Indicate which event types this consumer can handle"""
        return event_type in [
            "data_collection",
            "product_updated",
            "product_created",
            "product_deleted",
            "collection_updated",
            "collection_created",
            "collection_deleted",
            "order_paid",
            "order_created",
            "order_updated",
            "order_cancelled",
            "customer_created",
            "customer_updated",
        ]

    async def _handle_data_collection_job(
        self, event: Dict[str, Any], shop_data: Dict[str, Any]
    ) -> bool:
        """Handle data collection jobs from analysis triggers"""
        job_id = event.get("job_id")
        mode = event.get("mode", "incremental")
        collection_payload = event.get("collection_payload", {})

        if not job_id:
            logger.error("❌ Missing job_id for data collection job")
            return False

        return await self._process_data_collection_job(
            job_id, shop_data["id"], mode, collection_payload, shop_data
        )

    async def _handle_webhook_event(
        self, event: Dict[str, Any], shop_data: Dict[str, Any]
    ) -> bool:
        """Handle webhook events and convert to data collection jobs"""
        try:
            event_type = event.get("event_type")
            shopify_id = event.get("shopify_id")

            if not shopify_id:
                logger.error(f"❌ No shopify_id in webhook event: {event_type}")
                return False

            # Create collection payload based on event type
            collection_payload = self._create_collection_payload(event_type, shopify_id)
            if not collection_payload:
                logger.warning(f"❌ No collection payload for event type: {event_type}")
                return False

            # Create data collection job
            job_id = f"webhook_{event_type}_{shopify_id}_{event.get('timestamp', '')}"

            logger.info(
                "🔄 Converting webhook event to data collection job",
                event_type=event_type,
                shopify_id=shopify_id,
                job_id=job_id,
            )

            # Process as data collection job with resolved shop data
            return await self._process_data_collection_job(
                job_id, shop_data["id"], "incremental", collection_payload, shop_data
            )

        except Exception as e:
            logger.exception(f"Failed to handle webhook event: {e}")
            return False

    def _create_collection_payload(
        self, event_type: str, shopify_id: str
    ) -> Dict[str, Any]:
        """Create collection payload based on event type"""
        event_mapping = {
            # Product events
            "product_created": {
                "data_types": ["products"],
                "specific_ids": {"products": [shopify_id]},
            },
            "product_updated": {
                "data_types": ["products"],
                "specific_ids": {"products": [shopify_id]},
            },
            "product_deleted": {
                "data_types": ["products"],
                "specific_ids": {"products": [shopify_id]},
            },
            # Collection events
            "collection_created": {
                "data_types": ["collections"],
                "specific_ids": {"collections": [shopify_id]},
            },
            "collection_updated": {
                "data_types": ["collections"],
                "specific_ids": {"collections": [shopify_id]},
            },
            "collection_deleted": {
                "data_types": ["collections"],
                "specific_ids": {"collections": [shopify_id]},
            },
            # Order events
            "order_paid": {
                "data_types": ["orders"],
                "specific_ids": {"orders": [shopify_id]},
            },
            "order_created": {
                "data_types": ["orders"],
                "specific_ids": {"orders": [shopify_id]},
            },
            "order_updated": {
                "data_types": ["orders"],
                "specific_ids": {"orders": [shopify_id]},
            },
            "order_cancelled": {
                "data_types": ["orders"],
                "specific_ids": {"orders": [shopify_id]},
            },
            # Customer events
            "customer_created": {
                "data_types": ["customers"],
                "specific_ids": {"customers": [shopify_id]},
            },
            "customer_updated": {
                "data_types": ["customers"],
                "specific_ids": {"customers": [shopify_id]},
            },
        }
        return event_mapping.get(event_type)

    async def _process_data_collection_job(
        self,
        job_id: str,
        shop_id: str,
        mode: str = "incremental",
        collection_payload: Dict[str, Any] = None,
        shop_data: Dict[str, Any] = None,
    ):
        """Process data collection job with collection payload"""
        try:
            # Use resolved shop data (already validated)
            if not shop_data or not shop_data.get("access_token"):
                logger.error("❌ Shop not found or inactive. Aborting data collection")
                return False

            # Single flow - always use collect_all_data with payload
            result = await self.shopify_service.collect_all_data(
                shop_domain=shop_data["domain"],
                shop_id=shop_data["id"],
                access_token=shop_data["access_token"],
                mode=mode,
                collection_payload=collection_payload,
            )

            logger.info(
                "✅ Data collection completed successfully",
                job_id=job_id,
                collection_payload=collection_payload,
                result_keys=(
                    list(result.keys())
                    if isinstance(result, dict)
                    else "non-dict result"
                ),
            )
            return True

        except Exception as e:
            logger.exception(f"Data collection job failed: {e}")
            return False
