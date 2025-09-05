"""
Consumer manager for orchestrating all Redis consumers
"""

import asyncio
import signal
from typing import Dict, List, Optional

from app.consumers.base_consumer import BaseConsumer
from app.consumers.data_collection_consumer import DataCollectionConsumer
from app.consumers.ml_training_consumer import MLTrainingConsumer
from app.consumers.analytics_consumer import AnalyticsConsumer
from app.consumers.feature_computation_consumer import FeatureComputationConsumer
from app.consumers.behavioral_events_consumer import BehavioralEventsConsumer
from app.core.logging import get_logger


class ConsumerManager:
    """Manages all Redis consumers in the system"""

    def __init__(self):
        self.logger = get_logger(__name__)

        # Consumer instances
        self.consumers: Dict[str, BaseConsumer] = {}

        # State management
        self.is_running = False
        self._shutdown_event = asyncio.Event()
        self._manager_task: Optional[asyncio.Task] = None

        # Signal handlers
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def signal_handler(signum, frame):
            asyncio.create_task(self.shutdown())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def register_consumers(
        self,
        data_collection_consumer: Optional[DataCollectionConsumer] = None,
        ml_training_consumer: Optional[MLTrainingConsumer] = None,
        analytics_consumer: Optional[AnalyticsConsumer] = None,
        feature_computation_consumer: Optional[FeatureComputationConsumer] = None,
        behavioral_events_consumer: Optional[BehavioralEventsConsumer] = None,
    ):
        """Register consumers with the manager (all parameters are optional)"""
        if data_collection_consumer:
            self.consumers["data_collection"] = data_collection_consumer
        if ml_training_consumer:
            self.consumers["ml_training"] = ml_training_consumer
        if analytics_consumer:
            self.consumers["analytics"] = analytics_consumer
        if feature_computation_consumer:
            self.consumers["feature_computation"] = feature_computation_consumer
        if behavioral_events_consumer:
            self.consumers["behavioral_events"] = behavioral_events_consumer

    async def start_all_consumers(self):
        """Start all registered consumers"""
        if self.is_running:
            self.logger.warning("Consumer manager is already running")
            return

        try:
            # Start each consumer
            start_tasks = []
            for name, consumer in self.consumers.items():
                start_tasks.append(self._start_consumer(name, consumer))

            # Wait for all consumers to start
            await asyncio.gather(*start_tasks)

            self.is_running = True
            self.logger.info("All consumers started")

        except Exception as e:
            self.logger.error(f"Failed to start consumers: {e}")
            raise

    async def stop_all_consumers(self):
        """Stop all registered consumers"""
        if not self.is_running:
            self.logger.warning("Consumer manager is not running")
            return

        try:
            # Stop each consumer
            stop_tasks = []
            for name, consumer in self.consumers.items():
                stop_tasks.append(self._stop_consumer(name, consumer))

            # Wait for all consumers to stop
            await asyncio.gather(*stop_tasks, return_exceptions=True)

            self.is_running = False
            self.logger.info("All consumers stopped")

        except Exception as e:
            self.logger.error(f"Failed to stop consumers: {e}")
            raise

    async def _start_consumer(self, name: str, consumer: BaseConsumer):
        """Start a single consumer"""
        try:
            await consumer.start()
        except Exception as e:
            self.logger.error(f"Failed to start consumer {name}: {e}")
            raise

    async def _stop_consumer(self, name: str, consumer: BaseConsumer):
        """Stop a single consumer"""
        try:
            await consumer.stop()
        except Exception as e:
            self.logger.error(f"Failed to stop consumer {name}: {e}")
            # Don't raise - we want to stop other consumers even if one fails

    async def start(self):
        """Start the consumer manager"""
        if self._manager_task and not self._manager_task.done():
            self.logger.warning("Consumer manager is already running")
            return

        try:
            # Start all consumers
            await self.start_all_consumers()

            # Start the manager task
            self._manager_task = asyncio.create_task(
                self._manager_loop(), name="consumer-manager-loop"
            )

            self.logger.info("Consumer manager started")

        except Exception as e:
            self.logger.error(f"Failed to start consumer manager: {e}")
            raise

    async def stop(self):
        """Stop the consumer manager"""
        try:
            # Signal shutdown
            self._shutdown_event.set()

            # Stop all consumers
            await self.stop_all_consumers()

            # Wait for manager task to complete
            if self._manager_task and not self._manager_task.done():
                await asyncio.wait_for(self._manager_task, timeout=30.0)

            self.logger.info("Consumer manager stopped")

        except Exception as e:
            self.logger.error(f"Failed to stop consumer manager: {e}")
            raise

    async def shutdown(self):
        """Graceful shutdown"""
        await self.stop()

    async def _manager_loop(self):
        """Main manager loop for monitoring consumers"""
        while not self._shutdown_event.is_set():
            try:
                # Monitor consumer health
                await self._monitor_consumers()

                # Wait before next check
                await asyncio.sleep(30)  # Check every 30 seconds

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in consumer manager loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    async def _monitor_consumers(self):
        """Monitor health of all consumers"""
        for name, consumer in self.consumers.items():
            try:
                # Get consumer metrics
                metrics = consumer.get_metrics()

                # Only log if there are issues
                if (
                    metrics["status"] == "error"
                    or metrics["metrics"]["messages_failed"] > 0
                ):
                    self.logger.warning(
                        f"Consumer {name} issues: {metrics['status']}, failed: {metrics['metrics']['messages_failed']}"
                    )

                # Check if consumer needs restart
                if metrics["status"] == "error":
                    self.logger.warning(
                        f"Consumer {name} is in error state, attempting restart"
                    )
                    await self._restart_consumer(name, consumer)

            except Exception as e:
                self.logger.error(f"Failed to monitor consumer {name}: {e}")

    async def _restart_consumer(self, name: str, consumer: BaseConsumer):
        """Restart a consumer"""
        try:
            self.logger.info(f"Restarting consumer {name}")

            # Stop the consumer
            await consumer.stop()

            # Wait a bit before restarting
            await asyncio.sleep(5)

            # Start the consumer
            await consumer.start()

        except Exception as e:
            self.logger.error(f"Failed to restart consumer {name}: {e}")

    def get_consumer_status(self, name: str) -> Optional[Dict]:
        """Get status of a specific consumer"""
        if name not in self.consumers:
            return None

        consumer = self.consumers[name]
        return consumer.get_metrics()

    def get_all_consumers_status(self) -> Dict[str, Dict]:
        """Get status of all consumers"""
        return {
            name: consumer.get_metrics() for name, consumer in self.consumers.items()
        }

    def get_consumer_names(self) -> List[str]:
        """Get names of all registered consumers"""
        return list(self.consumers.keys())

    def get_consumer(self, name: str) -> Optional[BaseConsumer]:
        """Get a specific consumer instance"""
        return self.consumers.get(name)

    def is_consumer_running(self, name: str) -> bool:
        """Check if a specific consumer is running"""
        if name not in self.consumers:
            return False

        consumer = self.consumers[name]
        return consumer.status.value == "running"

    async def wait_for_shutdown(self):
        """Wait for shutdown signal"""
        await self._shutdown_event.wait()


# Global consumer manager instance
consumer_manager = ConsumerManager()
