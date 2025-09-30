from datetime import datetime
from typing import Dict, Any
from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.core.logging import get_logger
from app.repository.ShopRepository import ShopRepository
from app.services.shop_cache_service import get_shop_cache_service
from app.core.services.dlq_service import DLQService

logger = get_logger(__name__)


class DataCollectionKafkaConsumer:
    """Kafka consumer for data collection jobs - handles events directly"""

    def __init__(self, shopify_service=None):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self.shopify_service = shopify_service
        self.shop_repo = ShopRepository()
        self._initialized = False
        self.dlq_service = DLQService()

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

            self._initialized = True

        except Exception as e:
            logger.exception(f"❌ Failed to initialize data collection consumer: {e}")
            raise

    async def start_consuming(self):
        """Start consuming messages"""
        if not self._initialized:
            await self.initialize()
        try:
            async for message in self.consumer.consume():
                try:
                    await self._handle_message(message)
                    await self.consumer.commit(message)
                except Exception as e:
                    logger.error(f"Error processing data collection message: {e}")
                    continue
        except Exception as e:
            logger.exception(f"❌ Error in data collection consumer: {e}")
            raise

    async def close(self):
        """Close consumer"""
        if self.consumer:
            await self.consumer.close()

    async def _handle_message(self, message: Dict[str, Any]):
        """Handle individual data collection messages"""
        try:

            payload = message.get("value") or message
            if isinstance(payload, str):
                try:
                    import json

                    payload = json.loads(payload)
                except Exception:
                    pass

            event_type = payload.get("event_type")

            # Resolve shop data once for all event types
            shop_data = await self._resolve_shop_data(payload)
            if not shop_data:
                return
            if not shop_data.get("is_active"):
                logger.warning(f"❌ Shop {shop_data.get('id')} is suspended")
                await self.dlq_service.send_to_dlq(
                    original_message=payload,
                    reason="shop_suspended",
                    original_topic="data-collection-jobs",
                    error_details=f"Shop suspended at {datetime.utcnow().isoformat()}",
                )
                await self.consumer.commit(message)
                logger.info(f"✅ Shop {shop_data.get('id')} is suspended")
                return
            # Route to appropriate handler
            if event_type == "data_collection":
                await self._handle_data_collection_job(payload, shop_data)
            elif event_type in [
                "product_updated",
                "product_created",
                "product_deleted",
                "collection_updated",
                "collection_created",
                "collection_deleted",
                "order_paid",
                "refund_created",
                "customer_created",
                "customer_updated",
                "inventory_updated",
            ]:
                await self._handle_webhook_event(payload, shop_data)
            else:
                logger.warning(f"❌ Unknown event type: {event_type}")

        except Exception as e:
            logger.exception(f"Failed to process data collection message: {e}")
            raise

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
            "refund_created",
            "customer_created",
            "customer_updated",
            "inventory_updated",
        ]

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
                "is_active": shop_record.is_active,
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
            "refund_created",
            "customer_created",
            "customer_updated",
            "inventory_updated",
        ]

    async def _handle_data_collection_job(
        self, event: Dict[str, Any], shop_data: Dict[str, Any]
    ):
        """Handle data collection jobs from analysis triggers"""
        job_id = event.get("job_id")
        collection_payload = event.get("collection_payload", {})

        if not job_id:
            logger.error("❌ Missing job_id for data collection job")
            return

        await self._process_data_collection_job(
            job_id, shop_data["id"], collection_payload, shop_data
        )

    async def _handle_webhook_event(
        self, event: Dict[str, Any], shop_data: Dict[str, Any]
    ):
        """Handle webhook events and convert to data collection jobs"""
        try:
            event_type = event.get("event_type")
            shopify_id = event.get("shopify_id")

            if not shopify_id:
                logger.error(f"❌ No shopify_id in webhook event: {event_type}")
                return

            # Check if this is a deletion event
            if event_type.endswith("_deleted"):
                await self._handle_deletion_event(
                    event_type, shopify_id, shop_data["id"]
                )
                return

            # Create collection payload based on event type
            collection_payload = self._create_collection_payload(event_type, shopify_id)
            if not collection_payload:
                logger.warning(f"❌ No collection payload for event type: {event_type}")
                return

            # Create data collection job
            job_id = f"webhook_{event_type}_{shopify_id}_{event.get('timestamp', '')}"

            # Process as data collection job with resolved shop data
            await self._process_data_collection_job(
                job_id, shop_data["id"], collection_payload, shop_data
            )

        except Exception as e:
            logger.exception(f"Failed to handle webhook event: {e}")
            raise

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
            "refund_created": {
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
            "inventory_updated": {
                "data_types": ["products"],
                "specific_ids": {"inventory_items": [shopify_id]},
                "include_inventory": True,
            },
        }
        return event_mapping.get(event_type)

    async def _process_data_collection_job(
        self,
        job_id: str,
        shop_id: str,
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

        except Exception as e:
            logger.exception(f"Data collection job failed: {e}")
            raise

    async def _handle_deletion_event(
        self, event_type: str, shopify_id: str, shop_id: str
    ):
        """Handle deletion events by marking entities as inactive"""
        try:
            # Determine data type from event type
            if event_type == "product_deleted":
                data_type = "products"
            elif event_type == "collection_deleted":
                data_type = "collections"
            elif event_type == "customer_deleted":
                data_type = "customers"
            elif event_type == "order_deleted":
                data_type = "orders"
            else:
                logger.warning(f"❌ Unknown deletion event type: {event_type}")
                return

            # Use the normalization service to handle deletion
            from app.domains.shopify.services.normalisation_service import (
                NormalizationService,
            )

            normalization_service = NormalizationService()

            # Create deletion job
            deletion_job = {
                "event_type": event_type,
                "data_type": data_type,
                "shop_id": shop_id,
                "shopify_id": shopify_id,
            }

            # Handle the deletion using the existing deletion service
            await normalization_service.deletion_service.handle_entity_deletion(
                deletion_job, None  # db parameter not needed for SQLAlchemy
            )

            logger.info(
                f"✅ Successfully processed {data_type} deletion for {shopify_id}"
            )

        except Exception as e:
            logger.exception(f"❌ Failed to handle deletion event: {e}")
            raise
