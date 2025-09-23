from typing import Dict, Any
from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.core.messaging.event_subscriber import EventSubscriber
from app.core.logging import get_logger
from app.repository.ShopRepository import ShopRepository

logger = get_logger(__name__)


class DataCollectionKafkaConsumer:
    """Kafka consumer for data collection jobs - handles events directly"""

    def __init__(self, shopify_service=None, shop_repo: ShopRepository = None):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self.event_subscriber = EventSubscriber(kafka_settings.model_dump())
        self.shopify_service = shopify_service
        self.shop_repo = (
            shop_repo or ShopRepository()
        )  # Repository handles its own sessions
        self._initialized = False

    async def initialize(self):
        """Initialize consumer"""
        try:
            if not self.shopify_service:
                raise ValueError(
                    "Shopify service is required for data collection consumer"
                )

            await self.consumer.initialize(
                topics=["data-collection-jobs"], group_id="data-collection-processors"
            )

            await self.event_subscriber.initialize(
                topics=["data-collection-jobs"],
                group_id="data-collection-processors",
                existing_consumer=self.consumer,  # Reuse existing consumer
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
                topics=["data-collection-jobs"], group_id="data-collection-processors"
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
        """Handle data collection events directly"""
        try:
            job_id = event.get("job_id")
            shop_id = event.get("shop_id")
            if not job_id or not shop_id:
                logger.error(
                    "❌ Invalid data collection message: missing required fields",
                    job_id=job_id,
                    shop_id=shop_id,
                )
                return False

            return await self._process_data_collection_job(job_id, shop_id)

        except Exception as e:
            logger.exception(
                f"Failed to process data collection message",
                job_id=event.get("job_id"),
                error=str(e),
            )
            return False

    def can_handle(self, event_type: str) -> bool:
        """Indicate which event types this consumer can handle"""
        return event_type == "data_collection"

    # Data collection business logic methods
    async def _process_data_collection_job(self, job_id: str, shop_id: str):
        """Process comprehensive data collection job"""
        try:
            shop_record = await self.shop_repo.get_active_by_id(shop_id)
            if not shop_record or not shop_record.access_token:
                logger.error(
                    "❌ Unknown shop_id. Aborting data collection",
                    shop_id=shop_id,
                )
                return False

            result = await self.shopify_service.collect_all_data(
                shop_domain=shop_record.shop_domain,
                shop_id=shop_id,
                access_token=shop_record.access_token,  # Pass the access token
            )
            logger.info(
                "✅ Data collection completed successfully",
                job_id=job_id,
                result_keys=(
                    list(result.keys())
                    if isinstance(result, dict)
                    else "non-dict result"
                ),
            )
            return True

        except Exception as e:
            logger.exception(
                f"Data collection job failed",
                job_id=job_id,
                shop_id=shop_id,
                error=str(e),
            )
            return False
