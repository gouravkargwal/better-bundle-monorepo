"""
Kafka Consumer Manager for BetterBundle Python Worker
Manages all Kafka consumers and their lifecycle
"""

import asyncio
from typing import Dict, Any
from app.core.logging import get_logger

# Import all Kafka consumers
from app.consumers.kafka.normalization_consumer import NormalizationKafkaConsumer
from app.consumers.kafka.feature_computation_consumer import (
    FeatureComputationKafkaConsumer,
)
from app.consumers.kafka.data_collection_consumer import DataCollectionKafkaConsumer
from app.consumers.kafka.purchase_attribution_consumer import (
    PurchaseAttributionKafkaConsumer,
)
from app.consumers.kafka.customer_linking_consumer import CustomerLinkingKafkaConsumer
from app.consumers.kafka.billing_consumer import BillingKafkaConsumer

logger = get_logger(__name__)


class KafkaConsumerManager:
    """Manages all Kafka consumers and their lifecycle"""

    def __init__(self, shopify_service: Any | None = None):
        self.consumers: Dict[str, Any] = {}
        self._initialized = False
        self._running = False
        # Optional dependencies for specific consumers
        self.shopify_service = shopify_service
        # Circuit breaker for restart loops
        self._restart_counts: Dict[str, int] = {}
        self._last_restart: Dict[str, float] = {}

    async def initialize(self):
        """Initialize all Kafka consumers"""
        if self._initialized:
            return

        try:

            # Initialize all consumers
            self.consumers = {
                "data_collection": DataCollectionKafkaConsumer(
                    shopify_service=self.shopify_service
                ),
                "normalization": NormalizationKafkaConsumer(),
                "feature_computation": FeatureComputationKafkaConsumer(),
                "purchase_attribution": PurchaseAttributionKafkaConsumer(),
                "customer_linking": CustomerLinkingKafkaConsumer(),
                "billing": BillingKafkaConsumer(),
            }

            # Initialize each consumer in parallel to reduce overall startup time
            async def _init_one(name: str, consumer: Any):
                try:
                    await consumer.initialize()
                except Exception as e:
                    logger.exception(f"❌ Failed to initialize {name} consumer: {e}")
                    raise

            await asyncio.gather(
                *(
                    _init_one(name, consumer)
                    for name, consumer in self.consumers.items()
                )
            )

            self._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize consumer manager: {e}")
            await self.close()
            raise

    async def start_all_consumers(self):
        """Start all consumers in background tasks"""
        if not self._initialized:
            await self.initialize()

        if self._running:
            return

        try:

            # Start each consumer in a background task
            for name, consumer in self.consumers.items():
                try:
                    # Create background task for each consumer
                    asyncio.create_task(self._run_consumer(name, consumer))
                except Exception as e:
                    logger.error(f"❌ Failed to start {name} consumer: {e}")

            self._running = True

        except Exception as e:
            logger.error(f"Failed to start consumers: {e}")
            raise

    async def _run_consumer(self, name: str, consumer: Any):
        """Run a single consumer with error handling and restart logic"""
        import time

        while self._running:
            try:
                await consumer.start_consuming()
            except Exception as e:
                # Check if this is a ConsumerStoppedError (normal during shutdown)
                if "ConsumerStoppedError" in str(type(e).__name__):
                    logger.debug(f"🛑 {name} consumer stopped (normal during shutdown)")
                    break

                logger.exception(f"❌ {name} consumer failed: {e}")
                if self._running:
                    # Circuit breaker logic
                    current_time = time.time()
                    last_restart = self._last_restart.get(name, 0)
                    restart_count = self._restart_counts.get(name, 0)

                    # Reset counter if it's been more than 5 minutes since last restart
                    if current_time - last_restart > 300:  # 5 minutes
                        restart_count = 0

                    restart_count += 1
                    self._restart_counts[name] = restart_count
                    self._last_restart[name] = current_time

                    # Exponential backoff with circuit breaker
                    if restart_count > 10:  # Circuit breaker threshold
                        logger.error(
                            f"🚨 Circuit breaker activated for {name} consumer after {restart_count} failures"
                        )
                        await asyncio.sleep(60)  # Wait 1 minute before trying again
                        restart_count = 0  # Reset counter
                        self._restart_counts[name] = restart_count
                    else:
                        # Exponential backoff: 5s, 10s, 20s, 40s, max 60s
                        delay = min(5 * (2 ** min(restart_count - 1, 4)), 60)

                        await asyncio.sleep(delay)
                else:
                    break

    async def stop_all_consumers(self):
        """Stop all consumers gracefully"""
        if not self._running:
            return

        try:
            self._running = False  # Signal consumers to stop

            # Close each consumer with timeout
            for name, consumer in self.consumers.items():
                try:
                    await asyncio.wait_for(consumer.close(), timeout=10.0)
                except asyncio.TimeoutError:
                    logger.warning(f"⚠️ Timeout stopping {name} consumer")
                except Exception as e:
                    logger.exception(f"❌ Error stopping {name} consumer: {e}")

        except Exception as e:
            logger.exception(f"Error stopping consumers: {e}")

    async def close(self):
        """Close all consumers and cleanup"""
        await self.stop_all_consumers()
        self.consumers.clear()
        self._initialized = False

    async def get_health_status(self) -> Dict[str, Any]:
        """Get health status of all consumers"""
        status = {
            "manager_initialized": self._initialized,
            "consumers_running": self._running,
            "consumers": {},
        }

        for name, consumer in self.consumers.items():
            try:
                if hasattr(consumer, "get_health_status"):
                    status["consumers"][name] = await consumer.get_health_status()
                else:
                    status["consumers"][name] = {"status": "unknown"}
            except Exception as e:
                status["consumers"][name] = {"status": "error", "error": str(e)}

        return status

    async def restart_consumer(self, consumer_name: str):
        """Restart a specific consumer"""
        if consumer_name not in self.consumers:
            raise ValueError(f"Consumer {consumer_name} not found")

        try:

            # Stop the consumer
            await self.consumers[consumer_name].close()

            # Reinitialize
            await self.consumers[consumer_name].initialize()

            # Start in background
            asyncio.create_task(
                self._run_consumer(consumer_name, self.consumers[consumer_name])
            )

        except Exception as e:
            logger.exception(f"❌ Failed to restart {consumer_name} consumer: {e}")
            raise


# Global consumer manager instance
consumer_manager = KafkaConsumerManager()
