"""
Kafka client manager for connection lifecycle and health monitoring
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from kafka import KafkaProducer, KafkaConsumer, KafkaAdminClient
from kafka.errors import KafkaError
from kafka.admin import ConfigResource, ConfigResourceType

logger = logging.getLogger(__name__)


class KafkaClientManager:
    """Manages Kafka client connections and lifecycle"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._producer: Optional[KafkaProducer] = None
        self._consumer: Optional[KafkaConsumer] = None
        self._admin: Optional[KafkaAdminClient] = None
        self._connected = False
        self._connection_retries = 0
        self._max_retries = 3

    async def initialize(self):
        """Initialize Kafka connections"""
        try:
            # Initialize admin client
            self._admin = KafkaAdminClient(
                bootstrap_servers=self.config["bootstrap_servers"],
                client_id=self.config.get("client_id", "betterbundle-admin"),
                **self.config.get("admin_config", {}),
            )

            # Test connection
            await self._test_connection()
            self._connected = True
            self._connection_retries = 0
            logger.info("Kafka client manager initialized successfully")

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

    async def _test_connection(self):
        """Test Kafka connection"""
        try:
            # Get cluster metadata
            metadata = self._admin.describe_cluster()
            logger.info(f"Connected to Kafka cluster: {metadata}")
        except Exception as e:
            logger.error(f"Kafka connection test failed: {e}")
            raise

    def get_producer(self) -> KafkaProducer:
        """Get or create producer instance"""
        if not self._producer:
            self._producer = KafkaProducer(
                bootstrap_servers=self.config["bootstrap_servers"],
                client_id=self.config.get("client_id", "betterbundle-producer"),
                **self.config.get("producer_config", {}),
            )
        return self._producer

    def get_consumer(self, group_id: str) -> KafkaConsumer:
        """Get or create consumer instance"""
        if not self._consumer:
            self._consumer = KafkaConsumer(
                bootstrap_servers=self.config["bootstrap_servers"],
                group_id=group_id,
                client_id=self.config.get("client_id", "betterbundle-consumer"),
                **self.config.get("consumer_config", {}),
            )
        return self._consumer

    async def close(self):
        """Close all connections"""
        try:
            if self._producer:
                self._producer.close()
                self._producer = None
            if self._consumer:
                self._consumer.close()
                self._consumer = None
            if self._admin:
                self._admin.close()
                self._admin = None
            self._connected = False
            logger.info("Kafka connections closed")
        except Exception as e:
            logger.error(f"Error closing Kafka connections: {e}")

    @property
    def is_connected(self) -> bool:
        """Check if connected to Kafka"""
        return self._connected

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        try:
            if not self._admin:
                return {"status": "unhealthy", "error": "Admin client not initialized"}

            # Test admin operations
            metadata = self._admin.describe_cluster()

            return {
                "status": "healthy",
                "bootstrap_servers": self.config["bootstrap_servers"],
                "cluster_id": getattr(metadata, "cluster_id", "unknown"),
                "connected": self._connected,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "connected": self._connected,
            }
