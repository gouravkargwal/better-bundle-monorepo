"""
Kafka consumer with enterprise features and error handling
Industry-standard implementation with proper error handling and resilience
"""

import json
import logging
import time
import uuid
from typing import Dict, Any, List, Optional, AsyncIterator
from aiokafka import AIOKafkaConsumer
from aiokafka.structs import TopicPartition
from aiokafka.errors import (
    KafkaError,
    KafkaTimeoutError,
    ConsumerStoppedError,
    KafkaConnectionError,
    KafkaProtocolError,
    IllegalGenerationError,
    RebalanceInProgressError,
)
import asyncio

logger = logging.getLogger(__name__)


class KafkaConsumer:
    """Industry-standard Kafka consumer with enterprise features"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._message_count = 0
        self._error_count = 0
        self._committed_count = 0
        self._topics: List[str] = []
        self._group_id: str = ""
        self._static_group_instance_id: Optional[str] = None
        self._client_id: Optional[str] = None
        self._is_initialized = False
        self._last_heartbeat = time.time()
        self._consecutive_errors = 0
        self._max_consecutive_errors = 5

    async def initialize(self, topics: List[str], group_id: str):
        """Initialize consumer with industry-standard configuration"""
        if self._is_initialized:
            logger.warning(f"Consumer already initialized for group: {group_id}")
            return

        try:
            self._topics = topics
            self._group_id = group_id

            # Generate unique identifiers for this consumer instance
            worker_id = self.config.get("worker_id", "worker-1")
            instance_uuid = str(uuid.uuid4())[:8]  # Short UUID for readability
            timestamp = int(time.time() * 1000)

            # Create unique static group instance ID (industry standard)
            self._static_group_instance_id = (
                f"betterbundle-{worker_id}-{group_id}-{instance_uuid}"
            )
            self._client_id = f"betterbundle-{group_id}-{instance_uuid}"

            # Industry-standard consumer configuration
            consumer_config = {
                "bootstrap_servers": self.config["bootstrap_servers"],
                "group_id": group_id,
                "client_id": self._client_id,
                "group_instance_id": self._static_group_instance_id,
                "value_deserializer": lambda m: json.loads(m.decode("utf-8")),
                "key_deserializer": lambda k: k.decode("utf-8") if k else None,
                **self.config.get("consumer_config", {}),
            }

            # Create and start consumer
            self._consumer = AIOKafkaConsumer(*topics, **consumer_config)
            await self._consumer.start()

            self._is_initialized = True
            self._last_heartbeat = time.time()

        except Exception as e:
            logger.exception(f"❌ Failed to initialize Kafka consumer: {e}")
            self._is_initialized = False
            raise

    async def consume(self, timeout_ms: int = 1000) -> AsyncIterator[Dict[str, Any]]:
        """Consume messages with industry-standard error handling"""
        if not self._consumer:
            raise RuntimeError("Consumer not initialized. Call initialize() first.")

        try:
            async for message in self._consumer:
                try:
                    # Reset consecutive errors on successful message processing
                    self._consecutive_errors = 0
                    self._last_heartbeat = time.time()

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
                    self._consecutive_errors += 1
                    logger.error(f"JSON decode error processing message: {e}")
                    continue
                except Exception as e:
                    self._error_count += 1
                    self._consecutive_errors += 1
                    logger.error(f"Error processing message: {e}")
                    continue

        except KafkaTimeoutError as e:
            logger.debug(f"Consumer timeout: {e}")
            # This is normal, just continue
        except ConsumerStoppedError as e:
            logger.debug(f"Consumer stopped (normal during shutdown): {e}")
            return  # Exit gracefully
        except Exception as e:
            self._error_count += 1
            self._consecutive_errors += 1
            error_msg = str(e)

            # Industry-standard error handling for Kafka consumer group coordination
            if self._handle_coordination_error(error_msg, e):
                return  # Error was handled gracefully
            else:
                logger.exception(f"Unexpected consumer error: {e}")
                raise

    def _handle_coordination_error(self, error_msg: str, exception: Exception) -> bool:
        """Handle Kafka consumer group coordination errors gracefully"""
        error_handled = False

        # Heartbeat and member recognition errors
        if (
            "Heartbeat failed" in error_msg
            or "member_id was not recognized" in error_msg
            or "member was not recognized" in error_msg
        ):
            logger.warning(f"Consumer group coordination issue: {exception}")
            error_handled = True

        # SyncGroup and UnknownError handling
        elif (
            "UnknownError" in error_msg
            or "SyncGroup" in error_msg
            or "SyncGroupRequest" in error_msg
        ):
            logger.warning(f"Consumer group sync issue: {exception}")
            error_handled = True

        # Coordinator changes and dead coordinator
        elif (
            "NotCoordinatorForGroup" in error_msg
            or "coordinator dead" in error_msg.lower()
            or "marking coordinator dead" in error_msg.lower()
        ):
            logger.warning(f"Consumer group coordinator changed: {exception}")
            error_handled = True

        # Request timeout errors
        elif (
            "RequestTimedOutError" in error_msg
            or "RequestTimedOut" in error_msg
            or "Request timed out" in error_msg
        ):
            logger.warning(f"Request timeout: {exception}")
            error_handled = True

        # Rebalancing in progress
        elif "RebalanceInProgress" in error_msg or "rebalancing" in error_msg.lower():
            logger.warning(f"Consumer group rebalancing: {exception}")
            error_handled = True

        # Connection errors
        elif "ConnectionError" in error_msg or "KafkaConnectionError" in error_msg:
            logger.warning(f"Kafka connection issue: {exception}")
            error_handled = True

        # Protocol errors
        elif "ProtocolError" in error_msg or "KafkaProtocolError" in error_msg:
            logger.warning(f"Kafka protocol issue: {exception}")
            error_handled = True

        # Illegal generation errors (consumer group generation mismatch)
        elif "IllegalGeneration" in error_msg or "generation" in error_msg.lower():
            logger.warning(f"Consumer group generation issue: {exception}")
            error_handled = True

        return error_handled

    async def commit(self, message=None) -> bool:
        """Commit message offset with error handling"""
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
            logger.exception(f"Failed to commit offset: {e}")
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
            logger.exception(f"Failed to sync commit: {e}")
            return False

    async def seek_to_beginning(self, topics: Optional[List[str]] = None):
        """Seek to beginning of specified topics"""
        try:
            if self._consumer:
                topics_to_seek = topics or self._topics
                for topic in topics_to_seek:
                    partitions = self._consumer.partitions_for_topic(topic)
                    if partitions:
                        topic_partitions = [
                            TopicPartition(topic, p) for p in partitions
                        ]
                        self._consumer.seek_to_beginning(*topic_partitions)
        except Exception as e:
            logger.exception(f"Failed to seek to beginning: {e}")

    async def close(self):
        """Close consumer with proper cleanup"""
        if self._consumer:
            try:
                # Stop the consumer gracefully
                await self._consumer.stop()
                # Ensure the consumer is properly closed
                if hasattr(self._consumer, "_closed") and not self._consumer._closed:
                    await self._consumer.close()
                self._consumer = None
                self._is_initialized = False
                logger.debug("Kafka consumer closed successfully")
            except Exception as e:
                logger.exception(f"Error closing consumer: {e}")
                # Force cleanup even if stop fails
                try:
                    if self._consumer and hasattr(self._consumer, "close"):
                        await self._consumer.close()
                except Exception:
                    pass
                self._consumer = None
                self._is_initialized = False

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
            "consecutive_errors": self._consecutive_errors,
            "is_initialized": self._is_initialized,
            "static_group_instance_id": self._static_group_instance_id,
            "client_id": self._client_id,
        }

    @property
    def is_initialized(self) -> bool:
        """Check if consumer is initialized"""
        return self._is_initialized and self._consumer is not None

    @property
    def health_status(self) -> Dict[str, Any]:
        """Get consumer health status"""
        current_time = time.time()
        time_since_heartbeat = current_time - self._last_heartbeat

        return {
            "is_healthy": self._consecutive_errors < self._max_consecutive_errors,
            "consecutive_errors": self._consecutive_errors,
            "time_since_heartbeat": time_since_heartbeat,
            "is_initialized": self._is_initialized,
            "message_count": self._message_count,
            "error_count": self._error_count,
        }
