"""
Feature computation consumer — triggers TFRS model training after data normalization.

Replaces the old FeatureEngineeringService pipeline. Instead of computing
intermediate feature tables (which are no longer needed), it directly triggers
TFRS training which reads from canonical tables (ProductData, UserInteraction).
"""

from typing import Dict, Any

from app.shared.helpers import now_utc

from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.core.logging import get_logger
from app.repository.ShopRepository import ShopRepository
from app.core.services.dlq_service import DLQService
from app.recommandations.tfrs.scheduler import TfrsScheduler

logger = get_logger(__name__)


class FeatureComputationKafkaConsumer:
    """Kafka consumer for feature computation jobs — triggers TFRS training."""

    def __init__(self):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self.tfrs_scheduler = TfrsScheduler()
        self._initialized = False
        self.shop_repo = ShopRepository()
        self.dlq_service = DLQService()

    async def initialize(self):
        """Initialize consumer"""
        try:
            await self.consumer.initialize(
                topics=["feature-computation-jobs"],
                group_id="feature-computation-processors",
            )
            self._initialized = True
        except Exception as e:
            logger.error(f"Failed to initialize feature computation consumer: {e}")
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
                    logger.error(f"Error processing feature computation message: {e}")
                    continue
        except Exception as e:
            logger.error(f"Error in feature computation consumer: {e}")
            raise

    async def close(self):
        """Close consumer"""
        if self.consumer:
            await self.consumer.close()

    async def _handle_message(self, message: Dict[str, Any]):
        """Handle individual feature computation messages."""
        try:
            payload = message.get("value") or message
            if isinstance(payload, str):
                import json

                try:
                    payload = json.loads(payload)
                except Exception:
                    pass

            job_id = payload.get("job_id")
            shop_id = payload.get("shop_id")
            metadata = payload.get("metadata", {})

            if not job_id or not shop_id:
                logger.error("Invalid message: missing job_id or shop_id")
                return

            if not await self.shop_repo.is_shop_active(shop_id):
                logger.warning(
                    "Shop is not active for feature computation",
                    shop_id=shop_id,
                )
                await self.dlq_service.send_to_dlq(
                    original_message=message,
                    reason="shop_suspended",
                    original_topic="feature-computation-jobs",
                    error_details=f"Shop suspended at {now_utc().isoformat()}",
                )
                await self.consumer.commit(message)
                return

            # Trigger TFRS training for this shop
            # TFRS reads directly from ProductData, UserInteraction, PurchaseAttribution
            await self._trigger_tfrs_training(job_id, shop_id, metadata)

        except Exception as e:
            logger.error(
                f"Failed to process feature computation job: {str(e)}",
                job_id=payload.get("job_id"),
                shop_id=payload.get("shop_id"),
            )
            raise

    async def _trigger_tfrs_training(
        self, job_id: str, shop_id: str, metadata: Dict[str, Any]
    ):
        """Trigger TFRS model training for a shop after data normalization."""
        try:
            logger.info(
                f"🧠 Triggering TFRS training for shop {shop_id} (job: {job_id})"
            )

            result = await self.tfrs_scheduler.train_shop(shop_id)

            if result.get("status") == "success":
                logger.info(
                    f"✅ TFRS training complete for shop {shop_id}: "
                    f"{result.get('training_time_seconds', 0):.1f}s, "
                    f"loss={result.get('final_loss', 'N/A')}"
                )
            elif result.get("status") == "skipped":
                logger.info(
                    f"⏭️ TFRS training skipped for shop {shop_id}: {result.get('reason')}"
                )
            else:
                logger.warning(f"⚠️ TFRS training result for shop {shop_id}: {result}")

        except Exception as e:
            logger.error(
                f"TFRS training failed for shop {shop_id}",
                job_id=job_id,
                shop_id=shop_id,
                error=str(e),
            )
            raise
