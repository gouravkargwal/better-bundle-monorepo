"""
Kafka client manager for connection lifecycle and health monitoring
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.errors import KafkaError

logger = logging.getLogger(__name__)


class KafkaClientManager:
    """Manages Kafka client connections and lifecycle"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._producer: Optional[AIOKafkaProducer] = None
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._connected = False
        self._connection_retries = 0
        self._max_retries = 3

    async def initialize(self):
        """Initialize Kafka connections"""
        try:
            # Mark as connected; defer actual client startup to get_producer/get_consumer
            self._connected = True
            self._connection_retries = 0

        except Exception as e:
            self._connection_retries += 1
            logger.error(
                f"Failed to initialize Kafka client (attempt {self._connection_retries}): {e}"
            )

            if self._connection_retries < self._max_retries:
                await asyncio.sleep(2**self._connection_retries)  # Exponential backoff
                await self.initialize()
            else:
                raise

    async def get_producer(self) -> AIOKafkaProducer:
        """Get or create producer instance"""
        if not self._producer:
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.config["bootstrap_servers"],
                client_id=self.config.get("client_id", "betterbundle-producer"),
                **self.config.get("producer_config", {}),
            )
            await self._producer.start()
        return self._producer

    async def get_consumer(self, group_id: str) -> AIOKafkaConsumer:
        """Get or create consumer instance"""
        if not self._consumer:
            self._consumer = AIOKafkaConsumer(
                bootstrap_servers=self.config["bootstrap_servers"],
                group_id=group_id,
                client_id=self.config.get("client_id", "betterbundle-consumer"),
                **self.config.get("consumer_config", {}),
            )
            await self._consumer.start()
        return self._consumer

    async def close(self):
        """Close all connections"""
        try:
            if self._producer:
                await self._producer.stop()
                self._producer = None
            if self._consumer:
                await self._consumer.stop()
                self._consumer = None
            self._connected = False
        except Exception as e:
            logger.error(f"Error closing Kafka connections: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if connected to Kafka"""
        return self._connected

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        try:
            # Test connection by creating a temporary producer
            test_producer = AIOKafkaProducer(
                bootstrap_servers=self.config["bootstrap_servers"],
                client_id=self.config.get("client_id", "betterbundle-health-check"),
            )
            await test_producer.start()
            await test_producer.stop()

            return {
                "status": "healthy",
                "bootstrap_servers": self.config["bootstrap_servers"],
                "connected": self._connected,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "connected": self._connected,
            }
