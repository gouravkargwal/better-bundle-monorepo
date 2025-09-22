"""
Kafka consumer with enterprise features and error handling
"""

import json
import logging
from typing import Dict, Any, List, Optional, AsyncIterator
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError, KafkaTimeoutError
import asyncio

logger = logging.getLogger(__name__)


class KafkaConsumer:
    """Kafka consumer with enterprise features"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._message_count = 0
        self._error_count = 0
        self._committed_count = 0
        self._topics: List[str] = []
        self._group_id: str = ""

    async def initialize(self, topics: List[str], group_id: str):
        """Initialize consumer"""
        try:
            self._topics = topics
            self._group_id = group_id

            consumer_config = {
                "bootstrap_servers": self.config["bootstrap_servers"],
                "group_id": group_id,
                "value_deserializer": lambda m: json.loads(m.decode("utf-8")),
                "key_deserializer": lambda k: k.decode("utf-8") if k else None,
                **self.config.get("consumer_config", {}),
            }

            self._consumer = AIOKafkaConsumer(*topics, **consumer_config)
            await self._consumer.start()
            logger.info(
                f"Kafka consumer initialized for topics: {topics}, group: {group_id}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Kafka consumer: {e}")
            raise

    async def consume(self, timeout_ms: int = 1000) -> AsyncIterator[Dict[str, Any]]:
        """Consume messages"""
        if not self._consumer:
            raise RuntimeError("Consumer not initialized. Call initialize() first.")

        try:
            async for message in self._consumer:
                try:
                    # Convert Kafka message to our format
                    kafka_message = {
                        "topic": message.topic,
                        "partition": message.partition,
                        "offset": message.offset,
                        "key": message.key,
                        "value": message.value,
                        "timestamp": message.timestamp,
                        "headers": dict(message.headers) if message.headers else {},
                        "message_id": message.value.get(
                            "message_id",
                            f"{message.topic}:{message.partition}:{message.offset}",
                        ),
                    }

                    self._message_count += 1
                    yield kafka_message

                except json.JSONDecodeError as e:
                    self._error_count += 1
                    logger.error(f"JSON decode error processing message: {e}")
                    continue
                except Exception as e:
                    self._error_count += 1
                    logger.error(f"Error processing message: {e}")
                    continue

        except KafkaTimeoutError as e:
            logger.debug(f"Consumer timeout: {e}")
            # This is normal, just continue
        except KafkaError as e:
            self._error_count += 1
            logger.error(f"Kafka consumer error: {e}")
            raise
        except Exception as e:
            self._error_count += 1
            logger.error(f"Unexpected consumer error: {e}")
            raise

    async def commit(self, message=None) -> bool:
        """Commit message offset"""
        try:
            if self._consumer:
                await self._consumer.commit()
                self._committed_count += 1
                if message:
                    # Handle both dict and message object
                    if hasattr(message, "topic"):
                        logger.debug(
                            f"Committed offset for {message.topic}:{message.partition}:{message.offset}"
                        )
                    elif isinstance(message, dict):
                        logger.debug(
                            f"Committed offset for {message.get('topic', 'unknown')}:{message.get('partition', 'unknown')}:{message.get('offset', 'unknown')}"
                        )
                    else:
                        logger.debug("Committed offset for message")
                else:
                    logger.debug("Committed current offset")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to commit offset: {e}")
            return False

    async def commit_sync(self) -> bool:
        """Synchronously commit current offsets"""
        try:
            if self._consumer:
                self._consumer.commit()
                self._committed_count += 1
                logger.debug("Synchronously committed offsets")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to sync commit: {e}")
            return False

    async def seek_to_beginning(self, topics: Optional[List[str]] = None):
        """Seek to beginning of specified topics"""
        try:
            if self._consumer:
                topics_to_seek = topics or self._topics
                for topic in topics_to_seek:
                    partitions = self._consumer.partitions_for_topic(topic)
                    if partitions:
                        from kafka import TopicPartition

                        topic_partitions = [
                            TopicPartition(topic, p) for p in partitions
                        ]
                        self._consumer.seek_to_beginning(*topic_partitions)
                        logger.info(f"Seeked to beginning of topic: {topic}")
        except Exception as e:
            logger.error(f"Failed to seek to beginning: {e}")

    async def close(self):
        """Close consumer"""
        if self._consumer:
            try:
                await self._consumer.stop()
                logger.info(
                    f"Consumer closed. Processed {self._message_count} messages, {self._error_count} errors, {self._committed_count} commits"
                )
            except Exception as e:
                logger.error(f"Error closing consumer: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get consumer metrics"""
        return {
            "messages_processed": self._message_count,
            "errors": self._error_count,
            "commits": self._committed_count,
            "topics": self._topics,
            "group_id": self._group_id,
            "success_rate": (self._message_count - self._error_count)
            / max(self._message_count, 1)
            * 100,
        }

    @property
    def is_initialized(self) -> bool:
        """Check if consumer is initialized"""
        return self._consumer is not None
