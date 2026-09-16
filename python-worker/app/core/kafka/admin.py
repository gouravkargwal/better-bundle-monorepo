"""
Kafka admin operations for topic management
"""

import logging
from typing import Dict, Any, List, Optional
from aiokafka.admin import AIOKafkaAdminClient, NewTopic

logger = logging.getLogger(__name__)


class KafkaAdmin:
    """Kafka admin operations"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._admin: Optional[AIOKafkaAdminClient] = None

    async def initialize(self):
        """Initialize admin client"""
        try:
            self._admin = AIOKafkaAdminClient(
                bootstrap_servers=self.config["bootstrap_servers"],
                client_id=self.config.get("client_id", "betterbundle-admin"),
                **self.config.get("admin_config", {}),
            )
            await self._admin.start()
        except Exception as e:
            logger.exception(f"Failed to initialize Kafka admin: {e}")
            raise

    async def create_topics(self, topics: Dict[str, Dict[str, Any]]) -> Dict[str, bool]:
        """Create topics with configurations"""
        if not self._admin:
            raise RuntimeError("Admin client not initialized")

        results = {}
        broker_count = await self._broker_count()
        existing = await self._partition_counts()

        for topic_name, topic_config in topics.items():
            wanted_partitions = topic_config.get("partitions", 1)

            # Asking for more replicas than there are brokers fails the whole
            # create. Kafka then auto-creates the topic on first produce with
            # broker defaults — one partition — and the configured partition
            # count is silently ignored. A single-partition topic can only ever
            # have one consumer, so the pipeline cannot scale out no matter how
            # many workers run.
            wanted_rf = min(
                topic_config.get("replication_factor", 1), max(broker_count, 1)
            )
            if wanted_rf != topic_config.get("replication_factor", 1):
                logger.warning(
                    f"Topic '{topic_name}': replication_factor "
                    f"{topic_config.get('replication_factor')} exceeds "
                    f"{broker_count} broker(s); using {wanted_rf}"
                )

            if topic_name in existing:
                # Topic is already there — widen it if it is too narrow.
                results[topic_name] = await self._ensure_partitions(
                    topic_name, existing[topic_name], wanted_partitions
                )
                continue

            try:
                new_topic = NewTopic(
                    name=topic_name,
                    num_partitions=wanted_partitions,
                    replication_factor=wanted_rf,
                    topic_configs=topic_config.get("config", {}),
                )

                await self._admin.create_topics([new_topic])

                results[topic_name] = True

            except Exception as e:
                # aiokafka raises generic errors for existing topics depending on broker
                if "TopicExistsError" in str(e) or "already exists" in str(e):
                    results[topic_name] = True
                else:
                    results[topic_name] = False
                    logger.exception(f"Failed to create topic '{topic_name}': {e}")

        return results

    async def _broker_count(self) -> int:
        """How many brokers the cluster actually has."""
        try:
            cluster = await self._admin.describe_cluster()
            return max(len(cluster.get("brokers", []) or []), 1)
        except Exception as e:
            logger.warning(f"Could not describe cluster, assuming 1 broker: {e}")
            return 1

    async def _partition_counts(self) -> Dict[str, int]:
        """Current partition count per existing topic."""
        try:
            metadata = await self._admin.describe_topics()
            return {
                t["topic"]: len(t.get("partitions", []) or []) for t in metadata
            }
        except Exception as e:
            logger.warning(f"Could not read topic metadata: {e}")
            return {}

    async def _ensure_partitions(
        self, topic_name: str, current: int, wanted: int
    ) -> bool:
        """Grow an existing topic to the configured partition count.

        Partitions can only be added, never removed. Adding them changes which
        partition a key lands on, so per-key ordering is only preserved going
        forward — acceptable here, where ordering is per shop and best effort.
        """
        if current >= wanted:
            return True
        try:
            from aiokafka.admin import NewPartitions

            await self._admin.create_partitions(
                {topic_name: NewPartitions(total_count=wanted)}
            )
            logger.warning(
                f"Grew topic '{topic_name}' from {current} to {wanted} partitions"
            )
            return True
        except Exception as e:
            logger.error(
                f"Could not grow topic '{topic_name}' to {wanted} partitions: {e}"
            )
            return False

    async def delete_topics(self, topic_names: List[str]) -> Dict[str, bool]:
        """Delete topics"""
        if not self._admin:
            raise RuntimeError("Admin client not initialized")

        results = {}

        try:
            await self._admin.delete_topics(topic_names)
            for topic_name in topic_names:
                results[topic_name] = True
        except Exception as e:
            logger.exception(f"Failed to delete topics: {e}")
            for topic_name in topic_names:
                results[topic_name] = False

        return results

    async def list_topics(self) -> List[str]:
        """List all topics"""
        if not self._admin:
            raise RuntimeError("Admin client not initialized")

        try:
            topics = await self._admin.list_topics()
            return list(topics)
        except Exception as e:
            logger.exception(f"Failed to list topics: {e}")
            return []

    async def get_topic_info(self, topic_name: str) -> Optional[Dict[str, Any]]:
        """Get topic information"""
        if not self._admin:
            raise RuntimeError("Admin client not initialized")

        try:
            # aiokafka does not expose rich topic metadata uniformly; return basic info
            topics = await self._admin.list_topics()
            if topic_name in topics:
                return {"name": topic_name}
        except Exception as e:
            logger.exception(f"Failed to get topic info for '{topic_name}': {e}")

        return None

    async def update_topic_config(
        self, topic_name: str, config: Dict[str, str]
    ) -> bool:
        """Update topic configuration (not supported uniformly in aiokafka)."""
        logger.warning("update_topic_config not supported with aiokafka; no-op")
        return True

    async def get_consumer_groups(self) -> List[Dict[str, Any]]:
        """Get consumer group information"""
        if not self._admin:
            raise RuntimeError("Admin client not initialized")

        try:
            groups = self._admin.list_consumer_groups()
            return [
                {
                    "group_id": group.group_id,
                    "state": group.state,
                    "coordinator": group.coordinator,
                }
                for group in groups
            ]
        except Exception as e:
            logger.error(f"Failed to get consumer groups: {e}")
            return []

    async def close(self):
        """Close admin client"""
        if self._admin:
            try:
                await self._admin.close()
            except Exception as e:
                logger.exception(f"Error closing admin client: {e}")
