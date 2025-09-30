"""
Kafka producer with enterprise features and error handling
"""

import json
import time
import logging
from typing import Dict, Any, Optional, List
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError, KafkaTimeoutError
from .strategies import PartitioningStrategy, ShopBasedPartitioning

logger = logging.getLogger(__name__)


class KafkaProducer:
    """Kafka producer with enterprise features"""

    def __init__(
        self, config: Dict[str, Any], partitioning_strategy: PartitioningStrategy = None
    ):
        self.config = config
        self.partitioning_strategy = partitioning_strategy or ShopBasedPartitioning()
        self._producer: Optional[AIOKafkaProducer] = None
        self._message_count = 0
        self._error_count = 0
        self._batch_count = 0

    async def initialize(self):
        """Initialize producer"""
        try:
            producer_config = {
                "bootstrap_servers": self.config["bootstrap_servers"],
                "value_serializer": lambda v: json.dumps(v).encode("utf-8"),
                "key_serializer": lambda k: k.encode("utf-8") if k else None,
                **self.config.get("producer_config", {}),
            }

            self._producer = AIOKafkaProducer(**producer_config)
            await self._producer.start()
            logger.info("Kafka producer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka producer: {e}")
            raise

    async def send(
        self, topic: str, message: Dict[str, Any], key: Optional[str] = None
    ) -> str:
        """Send single message"""
        try:
            # Add metadata
            message_with_metadata = {
                **message,
                "timestamp": int(time.time() * 1000),
                "message_id": f"msg_{int(time.time() * 1000)}_{self._message_count}",
                "worker_id": self.config.get("worker_id", "unknown"),
                "topic": topic,
            }

            # Decide partitioning strategy: default to key-based (no explicit partition)
            use_explicit_partition = self.config.get("producer_config", {}).get(
                "use_explicit_partition", False
            )

            record_metadata = None
            if use_explicit_partition:
                # Determine partition only if explicitly enabled
                partition = self._get_partition(topic, message_with_metadata)
                logger.debug(
                    f"🔍 Partition strategy result: partition={partition}, topic={topic}"
                )

                if partition is not None:
                    try:
                        future = self._producer.send(
                            topic,
                            value=message_with_metadata,
                            key=key,
                            partition=partition,
                        )
                        record_metadata = await future
                    except Exception as partition_error:
                        # If partition-specific error, retry without specifying partition
                        if (
                            "partition" in str(partition_error).lower()
                            or "unrecognized" in str(partition_error).lower()
                        ):
                            logger.warning(
                                f"⚠️ Partition error for {topic}, retrying without partition: {partition_error}"
                            )
                            logger.info(
                                f"🔍 Partition details: requested_partition={partition}, topic={topic}"
                            )
                            logger.info(
                                f"🔍 Message details: key={key}, has_key={bool(key)}"
                            )
                            future = self._producer.send(
                                topic, value=message_with_metadata, key=key
                            )
                            record_metadata = await future
                        else:
                            raise
                else:
                    # No partition determined, let Kafka choose
                    future = self._producer.send(
                        topic, value=message_with_metadata, key=key
                    )
                    record_metadata = await future
            else:
                # Industry practice: rely on key-based partitioning; do not specify partition
                future = self._producer.send(
                    topic, value=message_with_metadata, key=key
                )
                record_metadata = await future

            self._message_count += 1
            # Handle case where partition might not be available
            partition_info = getattr(record_metadata, "partition", "unknown")
            offset_info = getattr(record_metadata, "offset", "unknown")
            logger.debug(
                f"Message sent to {topic}:{partition_info} at offset {offset_info} (explicit_partition={use_explicit_partition})"
            )

            return str(getattr(record_metadata, "offset", "unknown"))

        except KafkaTimeoutError as e:
            self._error_count += 1
            logger.error(f"Timeout sending message to {topic}: {e}")
            raise
        except KafkaError as e:
            self._error_count += 1
            logger.error(f"Kafka error sending message to {topic}: {e}")
            raise
        except Exception as e:
            self._error_count += 1
            logger.error(f"Unexpected error sending message to {topic}: {e}")
            raise

    async def send_batch(self, messages: List[Dict[str, Any]]) -> List[str]:
        """Send multiple messages"""
        results = []
        successful = 0

        for message in messages:
            try:
                result = await self.send(
                    message["topic"], message["data"], message.get("key")
                )
                results.append(result)
                successful += 1
            except Exception as e:
                logger.error(f"Failed to send batch message: {e}")
                results.append(None)

        self._batch_count += 1
        logger.info(f"Batch sent: {successful}/{len(messages)} messages successful")

        return results

    def _get_partition(self, topic: str, message: Dict[str, Any]) -> Optional[int]:
        """Get partition for message"""
        try:
            # Get topic partition count from config
            num_partitions = (
                self.config.get("topics", {}).get(topic, {}).get("partitions", 1)
            )
            partition = self.partitioning_strategy.get_partition(
                message, topic, num_partitions
            )
            # Ensure partition is within valid range
            if partition >= num_partitions:
                logger.warning(
                    f"Partition {partition} >= num_partitions {num_partitions} for topic {topic}, using 0"
                )
                return 0
            return partition
        except Exception as e:
            logger.warning(f"Failed to determine partition for {topic}: {e}")
            return None

    async def flush(self):
        """Flush all pending messages"""
        if self._producer:
            await self._producer.flush()
            logger.debug("Producer flushed")

    async def close(self):
        """Close producer"""
        if self._producer:
            try:
                await self._producer.stop()
                logger.info(
                    f"Producer closed. Sent {self._message_count} messages, {self._error_count} errors, {self._batch_count} batches"
                )
            except Exception as e:
                logger.error(f"Error closing producer: {e}")

    def get_metrics(self) -> Dict[str, Any]:
        """Get producer metrics"""
        return {
            "messages_sent": self._message_count,
            "errors": self._error_count,
            "batches_sent": self._batch_count,
            "success_rate": (self._message_count - self._error_count)
            / max(self._message_count, 1)
            * 100,
        }
