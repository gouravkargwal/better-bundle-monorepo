"""
Message bus implementation for Kafka
"""

import logging
from typing import Dict, Any, List, Optional, AsyncIterator
from .interfaces import MessageBus, Message
from ..kafka.producer import KafkaProducer
from ..kafka.consumer import KafkaConsumer
from ..kafka.strategies import ShopBasedPartitioning

logger = logging.getLogger(__name__)


class KafkaMessageBus(MessageBus):
    """Kafka implementation of message bus"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._producer: Optional[KafkaProducer] = None
        self._consumer: Optional[KafkaConsumer] = None
        self._initialized = False

    async def initialize(self):
        """Initialize message bus"""
        try:
            # Initialize producer
            self._producer = KafkaProducer(
                self.config, partitioning_strategy=ShopBasedPartitioning()
            )
            await self._producer.initialize()

            # Consumer will be initialized per subscription
            self._initialized = True
            logger.info("Kafka message bus initialized")

        except Exception as e:
            logger.error(f"Failed to initialize message bus: {e}")
            raise

    async def publish(self, message: Message) -> str:
        """Publish a message"""
        if not self._initialized:
            await self.initialize()

        try:
            # Add headers to message value
            message_value = {
                **message.value,
                "headers": message.headers or {},
                "message_id": message.message_id,
            }

            message_id = await self._producer.send(
                message.topic, message_value, message.key
            )

            logger.debug(f"Message published to {message.topic}: {message_id}")
            return message_id

        except Exception as e:
            logger.error(f"Failed to publish message to {message.topic}: {e}")
            raise

    async def subscribe(
        self, topics: List[str], group_id: str
    ) -> AsyncIterator[Message]:
        """Subscribe to topics"""
        if not self._initialized:
            await self.initialize()

        # Initialize consumer for this subscription
        consumer = KafkaConsumer(self.config)
        await consumer.initialize(topics, group_id)

        try:
            async for kafka_message in consumer.consume():
                # Convert Kafka message to our Message format
                message = Message(
                    topic=kafka_message["topic"],
                    key=kafka_message["key"],
                    value=kafka_message["value"],
                    headers=kafka_message.get("headers", {}),
                    partition=kafka_message["partition"],
                    offset=kafka_message["offset"],
                    timestamp=kafka_message["timestamp"],
                    message_id=kafka_message.get("message_id"),
                )

                yield message

        except Exception as e:
            logger.error(f"Error in subscription to {topics}: {e}")
            raise
        finally:
            await consumer.close()

    async def acknowledge(self, message_id: str) -> bool:
        """Acknowledge message processing"""
        # Note: In Kafka, acknowledgment is handled by the consumer
        # This is a placeholder for interface compatibility
        logger.debug(f"Acknowledged message: {message_id}")
        return True

    async def close(self):
        """Close message bus"""
        if self._producer:
            await self._producer.close()
        if self._consumer:
            await self._consumer.close()
        self._initialized = False
        logger.info("Message bus closed")
