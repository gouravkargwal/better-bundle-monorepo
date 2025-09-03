"""
Features Consumer Service
Automatically triggers feature transformations after data collection completes
"""

import asyncio
import time
from typing import Dict, Any

from app.core.config import settings
from app.core.redis_client import streams_manager
from app.services.transformations import run_transformations_for_shop
from app.core.logger import get_logger

logger = get_logger("features-consumer")


class FeaturesConsumer:
    """Consumer for automatically triggering feature transformations"""

    def __init__(self):
        self._shutdown_event = asyncio.Event()
        self._consumer_task = None

    async def initialize(self):
        """Initialize the consumer"""
        logger.info("Initializing features consumer")
        await streams_manager.initialize()
        logger.info("Features consumer initialized")

    async def shutdown(self):
        """Gracefully shutdown the consumer"""
        logger.info("Shutting down features consumer")
        self._shutdown_event.set()

        if self._consumer_task and not self._consumer_task.done():
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass

        logger.info("Features consumer shutdown complete")

    def is_shutdown_requested(self) -> bool:
        """Check if shutdown has been requested"""
        return self._shutdown_event.is_set()

    async def start_consumer(self):
        """Start the consumer in a separate task"""
        if self._consumer_task and not self._consumer_task.done():
            logger.warning("Features consumer is already running")
            return

        self._consumer_task = asyncio.create_task(
            self.consume_features_events(), name="features-consumer"
        )
        logger.info("Features consumer started")

    async def stop_consumer(self):
        """Stop the consumer task"""
        if self._consumer_task and not self._consumer_task.done():
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            logger.info("Features consumer stopped")

    async def consume_features_events(self):
        """Main consumer loop for features computation events"""
        consumer_name = f"{settings.WORKER_ID}-features"
        consecutive_failures = 0
        max_consecutive_failures = 3

        # Sleep intervals - configurable for resource optimization
        idle_sleep_interval = settings.CONSUMER_IDLE_SLEEP_SECONDS
        error_sleep_interval = settings.CONSUMER_ERROR_SLEEP_SECONDS

        # Circuit breaker state
        circuit_breaker_open = False
        circuit_breaker_open_time = 0
        circuit_breaker_timeout = 300  # 5 minutes

        loop_iteration = 0

        while not self.is_shutdown_requested():
            loop_iteration += 1
            loop_start_time = time.time()

            try:
                # Check circuit breaker
                if circuit_breaker_open:
                    current_time = time.time()
                    if (
                        current_time - circuit_breaker_open_time
                        > circuit_breaker_timeout
                    ):
                        logger.info(
                            "Circuit breaker timeout reached, resuming operations"
                        )
                        circuit_breaker_open = False
                        consecutive_failures = 0
                    else:
                        remaining_time = circuit_breaker_timeout - (
                            current_time - circuit_breaker_open_time
                        )
                        logger.info(
                            f"Circuit breaker open, waiting {remaining_time:.0f}s"
                        )
                        await asyncio.sleep(min(30, remaining_time))
                        continue

                # Try to read events from the features computation stream
                events = await streams_manager.consume_events(
                    stream_name=settings.FEATURES_COMPUTED_STREAM,
                    consumer_group=settings.DATA_PROCESSOR_GROUP,
                    consumer_name=consumer_name,
                    count=settings.CONSUMER_BATCH_SIZE,  # Configurable batch size
                    block=settings.CONSUMER_POLLING_INTERVAL_MS,  # Configurable polling interval
                )

                if events:
                    consecutive_failures = 0

                    for event in events:
                        if self.is_shutdown_requested():
                            logger.info("Shutdown requested during event processing")
                            return

                        try:
                            # Process the event
                            await self._process_features_event(event)

                            # Acknowledge successful processing
                            await streams_manager.acknowledge_event(
                                stream_name=settings.FEATURES_COMPUTED_STREAM,
                                consumer_group=settings.DATA_PROCESSOR_GROUP,
                                message_id=event["_message_id"],
                            )

                        except Exception as e:
                            logger.error(f"Error processing features event: {e}")
                            # Acknowledge failed events to prevent infinite retries
                            await self._acknowledge_event_safely(event)

                else:
                    consecutive_failures = 0

            except Exception as e:
                consecutive_failures += 1
                error_duration_ms = (time.time() - loop_start_time) * 1000

                logger.error(
                    f"Features consumer error (iteration {loop_iteration}): {e}",
                    consecutive_failures=consecutive_failures,
                    duration_ms=error_duration_ms,
                )

                # Implement exponential backoff with circuit breaker
                if consecutive_failures >= max_consecutive_failures:
                    logger.error(
                        f"Circuit breaker triggered after {consecutive_failures} consecutive failures"
                    )
                    circuit_breaker_open = True
                    circuit_breaker_open_time = time.time()
                    retry_delay = min(60, 2**consecutive_failures)
                    logger.info(f"Circuit breaker wait: {retry_delay}s")
                    await asyncio.sleep(retry_delay)
                else:
                    retry_delay = min(30, 2**consecutive_failures)
                    logger.info(f"Exponential backoff wait: {retry_delay}s")
                    await asyncio.sleep(retry_delay)

                # Wait before retrying
                if consecutive_failures > 0:
                    await asyncio.sleep(error_sleep_interval)

        logger.info("Features consumer loop ended")

    async def _process_features_event(self, event: Dict[str, Any]):
        """Process a single features event"""
        try:
            # Extract job details from features computation event
            event_type = event.get("event_type")
            shop_id = event.get("shop_id")
            shop_domain = event.get("shop_domain")
            data_collection_results = event.get("data_collection_results", {})

            # Check if this is a data collection completion event
            if not shop_id:
                logger.warning("No shop_id found in event, skipping")
                return

            logger.info(
                "Processing features computation event",
                event_type=event_type,
                shop_id=shop_id,
                shop_domain=shop_domain,
            )

            if event_type == "DATA_COLLECTION_COMPLETED":
                # Trigger feature transformations for this shop
                await self._trigger_feature_transformations(
                    shop_id, shop_domain, data_collection_results
                )
            else:
                logger.warning(f"Unknown event type: {event_type}, skipping")

        except Exception as e:
            logger.error(f"Error processing features event: {e}")
            raise

    async def _trigger_feature_transformations(
        self, shop_id: str, shop_domain: str, data_collection_results: Dict[str, Any]
    ):
        """Trigger feature transformations for a shop"""
        try:
            logger.info(
                "Triggering feature transformations",
                shop_id=shop_id,
                shop_domain=shop_domain,
            )

            # Run transformations
            stats = await run_transformations_for_shop(shop_id, backfill_if_needed=True)

            if stats.get("success"):
                logger.info(
                    "Feature transformations completed successfully",
                    shop_id=shop_id,
                    stats=stats,
                )

                # Publish ML training event
                await self._publish_ml_training_event(shop_id, shop_domain, stats)
            else:
                logger.error(
                    "Feature transformations failed",
                    shop_id=shop_id,
                    error=stats.get("error"),
                )

        except Exception as e:
            logger.error(
                f"Error triggering feature transformations: {e}", shop_id=shop_id
            )
            raise

    async def _publish_ml_training_event(
        self, shop_id: str, shop_domain: str, transformation_stats: Dict[str, Any]
    ):
        """Publish ML training event after successful transformations"""
        try:
            event_data = {
                "event_type": "ML_TRAINING_REQUESTED",
                "shop_id": shop_id,
                "shop_domain": shop_domain,
                "training_type": "gorse_recommendations",
                "transformation_stats": transformation_stats,
                "timestamp": time.time(),
            }

            await streams_manager.publish_event(
                stream_name=settings.ML_TRAINING_STREAM,
                event_data=event_data,
            )

            logger.info(
                "ML training event published",
                shop_id=shop_id,
                shop_domain=shop_domain,
            )

        except Exception as e:
            logger.error(f"Error publishing ML training event: {e}", shop_id=shop_id)
            raise

    async def _acknowledge_event_safely(self, event: dict):
        """Safely acknowledge an event even if it failed"""
        try:
            await streams_manager.acknowledge_event(
                stream_name=settings.FEATURES_COMPUTED_STREAM,
                consumer_group=settings.DATA_PROCESSOR_GROUP,
                message_id=event["_message_id"],
            )
        except Exception as e:
            logger.error(f"Failed to acknowledge features event: {e}")


# Global features consumer instance
features_consumer = FeaturesConsumer()
