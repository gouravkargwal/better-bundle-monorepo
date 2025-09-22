"""
Kafka Consumer Manager for BetterBundle Python Worker
Manages all Kafka consumers and their lifecycle
"""

import asyncio
from typing import Dict, Any, List
from app.core.logging import get_logger
from app.core.config.kafka_settings import kafka_settings

# Import all Kafka consumers
from app.consumers.kafka.shopify_events_consumer import ShopifyEventsKafkaConsumer
from app.consumers.kafka.normalization_consumer import NormalizationKafkaConsumer
from app.consumers.kafka.feature_computation_consumer import (
    FeatureComputationKafkaConsumer,
)
from app.consumers.kafka.data_collection_consumer import DataCollectionKafkaConsumer
from app.consumers.kafka.purchase_attribution_consumer import (
    PurchaseAttributionKafkaConsumer,
)
from app.consumers.kafka.refund_normalization_consumer import (
    RefundNormalizationKafkaConsumer,
)
from app.consumers.kafka.refund_attribution_consumer import (
    RefundAttributionKafkaConsumer,
)

logger = get_logger(__name__)


class KafkaConsumerManager:
    """Manages all Kafka consumers and their lifecycle"""

    def __init__(self):
        self.consumers: Dict[str, Any] = {}
        self._initialized = False
        self._running = False

    async def initialize(self):
        """Initialize all Kafka consumers"""
        if self._initialized:
            logger.info("Consumer manager already initialized")
            return

        try:
            logger.info("Initializing Kafka consumer manager...")

            # Initialize all consumers
            self.consumers = {
                "shopify_events": ShopifyEventsKafkaConsumer(),
                "normalization": NormalizationKafkaConsumer(),
                "feature_computation": FeatureComputationKafkaConsumer(),
                "data_collection": DataCollectionKafkaConsumer(),
                "purchase_attribution": PurchaseAttributionKafkaConsumer(),
                "refund_normalization": RefundNormalizationKafkaConsumer(),
                "refund_attribution": RefundAttributionKafkaConsumer(),
            }

            # Initialize each consumer
            for name, consumer in self.consumers.items():
                try:
                    await consumer.initialize()
                    logger.info(f"✅ Initialized {name} consumer")
                except Exception as e:
                    logger.error(f"❌ Failed to initialize {name} consumer: {e}")
                    raise

            self._initialized = True
            logger.info("🎉 All Kafka consumers initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize consumer manager: {e}")
            await self.close()
            raise

    async def start_all_consumers(self):
        """Start all consumers in background tasks"""
        if not self._initialized:
            await self.initialize()

        if self._running:
            logger.info("Consumers already running")
            return

        try:
            logger.info("Starting all Kafka consumers...")

            # Start each consumer in a background task
            for name, consumer in self.consumers.items():
                try:
                    # Create background task for each consumer
                    asyncio.create_task(self._run_consumer(name, consumer))
                    logger.info(f"🚀 Started {name} consumer")
                except Exception as e:
                    logger.error(f"❌ Failed to start {name} consumer: {e}")

            self._running = True
            logger.info("🎉 All Kafka consumers started successfully")

        except Exception as e:
            logger.error(f"Failed to start consumers: {e}")
            raise

    async def _run_consumer(self, name: str, consumer: Any):
        """Run a single consumer with error handling and restart logic"""
        while True:
            try:
                logger.info(f"🔄 Starting {name} consumer...")
                await consumer.start_consuming()
            except Exception as e:
                logger.error(f"❌ {name} consumer failed: {e}")
                logger.info(f"🔄 Restarting {name} consumer in 5 seconds...")
                await asyncio.sleep(5)

    async def stop_all_consumers(self):
        """Stop all consumers gracefully"""
        if not self._running:
            logger.info("No consumers running")
            return

        try:
            logger.info("Stopping all Kafka consumers...")

            # Close each consumer
            for name, consumer in self.consumers.items():
                try:
                    await consumer.close()
                    logger.info(f"✅ Stopped {name} consumer")
                except Exception as e:
                    logger.error(f"❌ Error stopping {name} consumer: {e}")

            self._running = False
            logger.info("🎉 All Kafka consumers stopped")

        except Exception as e:
            logger.error(f"Error stopping consumers: {e}")

    async def close(self):
        """Close all consumers and cleanup"""
        await self.stop_all_consumers()
        self.consumers.clear()
        self._initialized = False
        logger.info("Consumer manager closed")

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
            logger.info(f"Restarting {consumer_name} consumer...")

            # Stop the consumer
            await self.consumers[consumer_name].close()

            # Reinitialize
            await self.consumers[consumer_name].initialize()

            # Start in background
            asyncio.create_task(
                self._run_consumer(consumer_name, self.consumers[consumer_name])
            )

            logger.info(f"✅ {consumer_name} consumer restarted")

        except Exception as e:
            logger.error(f"❌ Failed to restart {consumer_name} consumer: {e}")
            raise


# Global consumer manager instance
consumer_manager = KafkaConsumerManager()
