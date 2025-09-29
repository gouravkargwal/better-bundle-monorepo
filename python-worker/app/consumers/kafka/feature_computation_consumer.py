"""
Kafka-based feature computation consumer for processing feature engineering jobs
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.domains.ml.services import FeatureEngineeringService
from app.core.logging import get_logger

logger = get_logger(__name__)


class FeatureComputationKafkaConsumer:
    """Kafka consumer for feature computation jobs"""

    def __init__(self):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self.feature_service = FeatureEngineeringService()
        self._initialized = False

        # Feature computation job tracking
        self.active_feature_jobs: Dict[str, Dict[str, Any]] = {}
        self.job_timeout = 1800  # 30 minutes for feature computation

    async def initialize(self):
        """Initialize consumer"""
        try:
            # Initialize Kafka consumer
            await self.consumer.initialize(
                topics=["feature-computation-jobs"],
                group_id="feature-computation-processors",
            )

            self._initialized = True
            logger.info("Feature computation Kafka consumer initialized")

        except Exception as e:
            logger.error(f"Failed to initialize feature computation consumer: {e}")
            raise

    async def start_consuming(self):
        """Start consuming messages"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info("Starting feature computation consumer...")
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
        logger.info("Feature computation consumer closed")

    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a feature computation job"""
        return self.active_feature_jobs.get(job_id)

    async def cleanup_old_jobs(self):
        """Clean up old completed jobs to prevent memory leaks"""
        current_time = datetime.utcnow()
        jobs_to_remove = []

        for job_id, job_data in self.active_feature_jobs.items():
            # Remove jobs older than timeout or completed more than 1 hour ago
            if job_data["status"] == "completed":
                completed_at = job_data.get("completed_at", current_time)
                if (current_time - completed_at).total_seconds() > 3600:  # 1 hour
                    jobs_to_remove.append(job_id)
            elif (
                current_time - job_data["started_at"]
            ).total_seconds() > self.job_timeout:
                # Mark timed out jobs as failed
                job_data["status"] = "timeout"
                jobs_to_remove.append(job_id)

        for job_id in jobs_to_remove:
            del self.active_feature_jobs[job_id]

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the feature computation consumer"""
        await self.cleanup_old_jobs()

        return {
            "status": "running" if self._initialized else "stopped",
            "active_jobs": len(self.active_feature_jobs),
            "last_health_check": datetime.utcnow().isoformat(),
        }

    async def _handle_message(self, message: Dict[str, Any]):
        """Handle individual feature computation messages"""
        try:
            logger.info(f"🔄 Processing feature computation message: {message}")

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
            # Robust boolean parsing (handles bool/str/int)
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

            logger.info(
                f"📋 Extracted: job_id={job_id}, shop_id={shop_id}, features_ready={features_ready}"
            )

            if not job_id or not shop_id:
                logger.error("Invalid message: missing job_id or shop_id")
                return

            # Track the job
            self.active_feature_jobs[job_id] = {
                "shop_id": shop_id,
                "started_at": datetime.utcnow(),
                "status": "processing",
                "metadata": metadata,
            }

            # Only process if features are not ready (need to be computed)
            if not features_ready:
                logger.info(f"🚀 Starting feature computation for shop {shop_id}")
                await self._compute_features_for_shop(job_id, shop_id, metadata)
            else:
                logger.info(
                    f"⏭️ Skipping feature computation - features already ready for shop {shop_id}"
                )

            # Mark job as completed
            if job_id in self.active_feature_jobs:
                self.active_feature_jobs[job_id]["status"] = "completed"
                self.active_feature_jobs[job_id]["completed_at"] = datetime.utcnow()

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

            logger.info(f"🚀 Full feature computation for shop {shop_id}")
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
