"""
Kafka consumer manager for orchestrating multiple consumers
"""

import asyncio
import logging
from typing import List, Dict, Any
from app.core.config.kafka_settings import kafka_settings
from app.consumers.kafka.shopify_events_consumer import ShopifyEventsKafkaConsumer
from app.consumers.kafka.data_collection_consumer import DataCollectionKafkaConsumer
from app.consumers.kafka.normalization_consumer import NormalizationKafkaConsumer
from app.consumers.kafka.billing_consumer import BillingKafkaConsumer
from app.consumers.kafka.customer_linking_consumer import CustomerLinkingKafkaConsumer
from app.consumers.kafka.feature_computation_consumer import (
    FeatureComputationKafkaConsumer,
)
from app.consumers.kafka.purchase_attribution_consumer import (
    PurchaseAttributionKafkaConsumer,
)
from app.consumers.kafka.refund_attribution_consumer import (
    RefundAttributionKafkaConsumer,
)

logger = logging.getLogger(__name__)


class KafkaConsumerManager:
    """Manages multiple Kafka consumers"""

    def __init__(self):
        self.consumers: List[Any] = []
        self.running = False
        self.tasks: List[asyncio.Task] = []

    async def initialize(self, services=None):
        """Initialize all consumers in parallel"""
        try:
            # Create all consumers first
            consumers_to_init = []

            # Shopify events consumer
            shopify_consumer = ShopifyEventsKafkaConsumer()
            consumers_to_init.append(shopify_consumer)

            # Data collection consumer with shopify service
            if services and "shopify" in services:
                data_collection_consumer = DataCollectionKafkaConsumer(
                    shopify_service=services["shopify"]
                )
            else:
                data_collection_consumer = DataCollectionKafkaConsumer()
            consumers_to_init.append(data_collection_consumer)

            # Normalization consumer
            normalization_consumer = NormalizationKafkaConsumer()
            consumers_to_init.append(normalization_consumer)

            # Billing consumer
            billing_consumer = BillingKafkaConsumer()
            consumers_to_init.append(billing_consumer)

            # Customer linking consumer
            customer_linking_consumer = CustomerLinkingKafkaConsumer()
            consumers_to_init.append(customer_linking_consumer)

            # Feature computation consumer
            feature_computation_consumer = FeatureComputationKafkaConsumer()
            consumers_to_init.append(feature_computation_consumer)

            # Purchase attribution consumer
            purchase_attribution_consumer = PurchaseAttributionKafkaConsumer()
            consumers_to_init.append(purchase_attribution_consumer)

            # Refund attribution consumer
            refund_attribution_consumer = RefundAttributionKafkaConsumer()
            consumers_to_init.append(refund_attribution_consumer)

            # Initialize all consumers in parallel with staggered start
            logger.info(
                f"Initializing {len(consumers_to_init)} Kafka consumers in parallel..."
            )

            # Create initialization tasks with small delays to reduce coordinator pressure
            init_tasks = []
            for i, consumer in enumerate(consumers_to_init):

                async def init_with_delay(consumer, delay):
                    await asyncio.sleep(delay)
                    return await consumer.initialize()

                # Stagger starts by 100ms each
                init_tasks.append(init_with_delay(consumer, i * 0.1))

            await asyncio.gather(*init_tasks)

            # Add all consumers to the list
            self.consumers.extend(consumers_to_init)
            logger.info(
                f"✅ Initialized {len(self.consumers)} Kafka consumers in parallel"
            )

        except Exception as e:
            logger.error(f"Failed to initialize consumers: {e}")
            raise

    async def start_all(self):
        """Start all consumers"""
        if self.running:
            logger.warning("Consumers are already running")
            return

        try:
            self.running = True
            logger.info("Starting all Kafka consumers...")

            # Start each consumer in a separate task
            for consumer in self.consumers:
                task = asyncio.create_task(consumer.start_consuming())
                self.tasks.append(task)
                logger.info(f"Started consumer: {consumer.__class__.__name__}")

            # Don't wait for tasks to complete - they run forever
            # Just start them and return immediately
            logger.info("✅ All Kafka consumers started successfully")

        except Exception as e:
            logger.error(f"Error starting consumers: {e}")
            await self.stop_all()
            raise

    async def stop_all(self):
        """Stop all consumers"""
        if not self.running:
            return

        try:
            self.running = False
            logger.info("Stopping all Kafka consumers...")

            # Cancel all tasks
            for task in self.tasks:
                if not task.done():
                    task.cancel()

            # Wait for tasks to complete
            await asyncio.gather(*self.tasks, return_exceptions=True)

            # Close all consumers
            for consumer in self.consumers:
                await consumer.close()

            self.tasks.clear()
            logger.info("All consumers stopped")

        except Exception as e:
            logger.error(f"Error stopping consumers: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """Check health of all consumers"""
        health_status = {
            "running": self.running,
            "consumers": len(self.consumers),
            "tasks": len(self.tasks),
            "consumer_status": [],
        }

        for i, consumer in enumerate(self.consumers):
            try:
                # Check if consumer is healthy
                consumer_health = {
                    "name": consumer.__class__.__name__,
                    "status": (
                        "healthy"
                        if hasattr(consumer, "consumer") and consumer.consumer
                        else "unhealthy"
                    ),
                }
                health_status["consumer_status"].append(consumer_health)
            except Exception as e:
                health_status["consumer_status"].append(
                    {
                        "name": consumer.__class__.__name__,
                        "status": "error",
                        "error": str(e),
                    }
                )

        return health_status

    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics for all consumers"""
        metrics = {
            "total_consumers": len(self.consumers),
            "running": self.running,
            "consumer_metrics": [],
        }

        for consumer in self.consumers:
            try:
                if hasattr(consumer, "get_metrics"):
                    consumer_metrics = consumer.get_metrics()
                    metrics["consumer_metrics"].append(
                        {
                            "name": consumer.__class__.__name__,
                            "metrics": consumer_metrics,
                        }
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to get metrics for {consumer.__class__.__name__}: {e}"
                )

        return metrics
