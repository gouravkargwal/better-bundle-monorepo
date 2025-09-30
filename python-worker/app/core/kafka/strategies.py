"""
Partitioning strategies for Kafka messages
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import hashlib


class PartitioningStrategy(ABC):
    """Strategy for message partitioning"""

    @abstractmethod
    def get_partition(
        self, message: Dict[str, Any], topic: str, num_partitions: int
    ) -> int:
        """Determine partition for message"""
        pass


class RoundRobinPartitioning(PartitioningStrategy):
    """Round-robin partitioning strategy"""

    def __init__(self):
        self._counter = 0

    def get_partition(
        self, message: Dict[str, Any], topic: str, num_partitions: int
    ) -> int:
        partition = self._counter % num_partitions
        self._counter += 1
        return partition


class KeyBasedPartitioning(PartitioningStrategy):
    """Key-based partitioning strategy"""

    def get_partition(
        self, message: Dict[str, Any], topic: str, num_partitions: int
    ) -> int:
        key = message.get("key") or message.get("shop_id", "default")
        return hash(key) % num_partitions


class ShopBasedPartitioning(PartitioningStrategy):
    """Shop-based partitioning for consistent ordering per shop"""

    def get_partition(
        self, message: Dict[str, Any], topic: str, num_partitions: int
    ) -> int:
        shop_id = message.get("shop_id")
        if not shop_id:
            # Fallback to key or round-robin
            key = message.get("key", "default")
            return hash(key) % num_partitions

        # Use shop_id for consistent partitioning
        return hash(shop_id) % num_partitions


class EventTypePartitioning(PartitioningStrategy):
    """Partition by event type for better load distribution"""

    def get_partition(
        self, message: Dict[str, Any], topic: str, num_partitions: int
    ) -> int:
        event_type = message.get("event_type", "unknown")
        # Hash event type for consistent partitioning
        return hash(event_type) % num_partitions


class CompositePartitioning(PartitioningStrategy):
    """Composite partitioning using multiple strategies"""

    def __init__(
        self,
        primary_strategy: PartitioningStrategy,
        fallback_strategy: PartitioningStrategy,
    ):
        self.primary = primary_strategy
        self.fallback = fallback_strategy

    def get_partition(
        self, message: Dict[str, Any], topic: str, num_partitions: int
    ) -> int:
        try:
            return self.primary.get_partition(message, topic, num_partitions)
        except Exception:
            return self.fallback.get_partition(message, topic, num_partitions)


class HashBasedPartitioning(PartitioningStrategy):
    """Hash-based partitioning for even distribution"""

    def get_partition(
        self, message: Dict[str, Any], topic: str, num_partitions: int
    ) -> int:
        # Create a composite key from multiple fields
        key_parts = [
            message.get("shop_id", ""),
            message.get("event_type", ""),
            message.get("timestamp", ""),
            str(message.get("shopify_id", "")),
        ]

        composite_key = "_".join(str(part) for part in key_parts)
        hash_value = int(hashlib.md5(composite_key.encode()).hexdigest(), 16)
        return hash_value % num_partitions
