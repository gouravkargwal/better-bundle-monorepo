"""
Feature computation consumer for processing feature engineering jobs
"""

import asyncio
import json
from typing import Dict, Any, Optional
from datetime import datetime

from app.consumers.base_consumer import BaseConsumer
from app.shared.constants.redis import FEATURES_COMPUTED_STREAM, FEATURES_CONSUMER_GROUP
from app.domains.ml.services import FeatureEngineeringService
from app.core.logging import get_logger


class FeatureComputationConsumer(BaseConsumer):
    """Consumer for processing feature computation jobs"""

    def __init__(self):
        super().__init__(
            stream_name=FEATURES_COMPUTED_STREAM,
            consumer_group=FEATURES_CONSUMER_GROUP,
            consumer_name="feature-computation-consumer",
            batch_size=5,  # Process fewer jobs as feature computation is resource-intensive
            poll_timeout=2000,  # 2 second timeout
            max_retries=3,
            retry_delay=2.0,
            circuit_breaker_failures=3,  # More sensitive for feature computation
            circuit_breaker_timeout=120,  # 2 minutes recovery
        )

        self.feature_service = FeatureEngineeringService()
        self.logger = get_logger(__name__)

        # Feature computation job tracking
        self.active_feature_jobs: Dict[str, Dict[str, Any]] = {}
        self.job_timeout = 1800  # 30 minutes for feature computation

    async def _process_single_message(self, message: Dict[str, Any]):
        """Process a single feature computation job message"""
        try:
            # Extract message data
            job_id = message.get("job_id")
            shop_id = message.get("shop_id")
            features_ready_raw = message.get("features_ready", "False")
            # Parse boolean from string (Redis streams store everything as strings)
            features_ready = features_ready_raw.lower() in ("true", "1", "yes", "on")
            metadata = message.get("metadata", {})

            if not job_id or not shop_id:
                self.logger.error("Invalid message: missing job_id or shop_id")
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
                await self._compute_features_for_shop(job_id, shop_id, metadata)

            # Mark job as completed
            if job_id in self.active_feature_jobs:
                self.active_feature_jobs[job_id]["status"] = "completed"
                self.active_feature_jobs[job_id]["completed_at"] = datetime.utcnow()

        except Exception as e:
            self.logger.error(
                f"Failed to process feature computation job: {str(e)}",
                job_id=message.get("job_id"),
                shop_id=message.get("shop_id"),
            )
            raise

    async def _compute_features_for_shop(
        self, job_id: str, shop_id: str, metadata: Dict[str, Any]
    ):
        """Compute features for a shop using the feature engineering service"""
        try:
            # Determine batch size based on metadata or use default
            batch_size = metadata.get("batch_size", 100)

            # Run the feature engineering pipeline
            # Use incremental processing by default to avoid recalculating existing features
            incremental = metadata.get(
                "incremental", True
            )  # Default to incremental processing
            await self.feature_service.run_comprehensive_pipeline_for_shop(
                shop_id=shop_id, batch_size=batch_size, incremental=incremental
            )

        except Exception as e:
            self.logger.error(
                f"Feature computation error",
                job_id=job_id,
                shop_id=shop_id,
                error=str(e),
            )
            raise

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
            "status": self.status.value,
            "active_jobs": len(self.active_feature_jobs),
            "circuit_breaker_state": self.circuit_breaker.state,
            "metrics": {
                "total_processed": self.metrics.total_processed,
                "total_failed": self.metrics.total_failed,
                "avg_processing_time": self.metrics.avg_processing_time,
                "consecutive_failures": self.consecutive_failures,
            },
            "last_health_check": self.last_health_check.isoformat(),
        }
