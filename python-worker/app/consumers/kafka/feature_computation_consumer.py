"""
Kafka-based feature computation consumer for processing feature engineering jobs
"""

from typing import Dict, Any
from datetime import datetime

from app.shared.helpers import now_utc

from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.domains.ml.services import FeatureEngineeringService
from app.core.logging import get_logger
from app.repository.ShopRepository import ShopRepository
from app.core.services.dlq_service import DLQService

logger = get_logger(__name__)


class FeatureComputationKafkaConsumer:
    """Kafka consumer for feature computation jobs"""

    def __init__(self):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self.feature_service = FeatureEngineeringService()
        self._initialized = False
        self.shop_repo = ShopRepository()
        self.dlq_service = DLQService()

    async def initialize(self):
        """Initialize consumer"""
        try:
            # Initialize Kafka consumer
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
        """Handle individual feature computation messages"""
        try:

            payload = message.get("value") or message
            if isinstance(payload, str):
                try:
                    import json

                    payload = json.loads(payload)
                except Exception:
                    pass

            # Extract message data
            job_id = payload.get("job_id")
            shop_id = payload.get("shop_id")
            features_ready_raw = payload.get("features_ready", False)

            if isinstance(features_ready_raw, bool):
                features_ready = features_ready_raw
            elif isinstance(features_ready_raw, (int, float)):
                features_ready = bool(features_ready_raw)
            else:
                try:
                    features_ready = str(features_ready_raw).strip().lower() in (
                        "true",
                        "1",
                        "yes",
                        "on",
                    )
                except Exception:
                    features_ready = False
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

            # Only process if features are not ready (need to be computed)
            if not features_ready:
                await self._compute_features_for_shop(job_id, shop_id, metadata)

        except Exception as e:
            logger.error(
                f"Failed to process feature computation job: {str(e)}",
                job_id=payload.get("job_id"),
                shop_id=payload.get("shop_id"),
            )
            raise

    async def _compute_features_for_shop(
        self, job_id: str, shop_id: str, metadata: Dict[str, Any]
    ):
        """Compute features for a shop using full computation"""
        try:
            # Determine batch size based on metadata or use default
            batch_size = metadata.get("batch_size", 100)

            await self.feature_service.run_comprehensive_pipeline_for_shop(
                shop_id=shop_id, batch_size=batch_size
            )

        except Exception as e:
            logger.error(
                f"Feature computation error",
                job_id=job_id,
                shop_id=shop_id,
                error=str(e),
            )
            raise
