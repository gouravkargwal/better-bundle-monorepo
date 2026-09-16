"""
Kafka topic management utilities
"""

import asyncio
import logging
from typing import Dict, Any, List
from aiokafka.admin import AIOKafkaAdminClient, NewTopic, NewPartitions
from app.core.config.kafka_settings import kafka_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class KafkaTopicManager:
    """Manages Kafka topic creation and configuration"""

    def __init__(self):
        self.admin_client = None
        self.topics_created = False

    async def initialize(self):
        """Initialize the admin client"""
        try:
            self.admin_client = AIOKafkaAdminClient(
                bootstrap_servers=kafka_settings.bootstrap_servers_list,
                client_id=f"{kafka_settings.client_id}-admin",
                **kafka_settings.admin_config,
            )
            await self.admin_client.start()
        except Exception as e:
            logger.error(f"Failed to initialize Kafka admin client: {e}")
            raise

    async def create_topics_if_not_exist(self):
        """Create all required topics if they don't exist"""
        if self.topics_created:
            return

        try:
            if not self.admin_client:
                await self.initialize()

            # Get existing topics
            existing_topics = await self.admin_client.list_topics()

            # Replication factor cannot exceed the number of brokers. Asking
            # for more fails the create, and Kafka then auto-creates the topic
            # on first produce using broker defaults — one partition — with
            # the configured partition count silently discarded. A
            # single-partition topic admits exactly one consumer, so no amount
            # of extra workers can drain a backlog on it.
            broker_count = await self._broker_count()

            new_topics = []
            for topic_name, topic_config in kafka_settings.topics.items():
                if topic_name in existing_topics:
                    continue

                wanted_rf = min(
                    topic_config.get("replication_factor", 1), max(broker_count, 1)
                )
                if wanted_rf != topic_config.get("replication_factor", 1):
                    logger.warning(
                        f"Topic '{topic_name}': replication_factor "
                        f"{topic_config.get('replication_factor')} exceeds "
                        f"{broker_count} broker(s); creating with {wanted_rf}"
                    )

                new_topic = NewTopic(
                    name=topic_name,
                    num_partitions=topic_config.get("partitions", 1),
                    replication_factor=wanted_rf,
                    topic_configs={
                        "retention.ms": str(
                            topic_config.get("retention_ms", 604800000)
                        ),
                        "cleanup.policy": topic_config.get(
                            "cleanup_policy", "delete"
                        ),
                    },
                )
                new_topics.append(new_topic)

            if new_topics:
                # Create topics
                try:
                    result = await self.admin_client.create_topics(new_topics)

                    # List topics to verify creation
                    created_topics = await self.admin_client.list_topics()
                except Exception as e:
                    logger.error(f"Failed to create topics: {e}")
                    # Continue anyway - topics might already exist

            # Topics that already exist may still be too narrow — either
            # auto-created at one partition by a failed create above, or
            # created before the configured count was raised.
            await self._widen_existing_topics()

            self.topics_created = True

        except Exception as e:
            logger.error(f"Failed to create topics: {e}")
            raise

    async def _broker_count(self) -> int:
        """Number of brokers in the cluster, for capping replication factor."""
        try:
            cluster = await self.admin_client.describe_cluster()
            return max(len(cluster.get("brokers") or []), 1)
        except Exception as e:
            logger.warning(f"Could not describe cluster, assuming 1 broker: {e}")
            return 1

    async def _widen_existing_topics(self) -> None:
        """Grow any existing topic that has fewer partitions than configured.

        Partitions can be added but never removed. Adding them changes which
        partition a given key hashes to, so per-key ordering holds only from
        here on — acceptable here, where the key is the shop and ordering is
        best effort.
        """
        try:
            metadata = await self.admin_client.describe_topics()
        except Exception as e:
            logger.warning(f"Could not read topic metadata: {e}")
            return

        current = {
            t["topic"]: len(t.get("partitions") or []) for t in metadata
        }

        for topic_name, topic_config in kafka_settings.topics.items():
            wanted = topic_config.get("partitions", 1)
            have = current.get(topic_name)
            if have is None or have >= wanted:
                continue
            try:
                await self.admin_client.create_partitions(
                    {topic_name: NewPartitions(total_count=wanted)}
                )
                logger.warning(
                    f"Grew topic '{topic_name}' from {have} to {wanted} partitions"
                )
            except Exception as e:
                logger.error(
                    f"Could not grow topic '{topic_name}' to {wanted} partitions: {e}"
                )

    async def close(self):
        """Close the admin client"""
        if self.admin_client:
            await self.admin_client.close()

    async def get_topic_info(self, topic_name: str) -> Dict[str, Any]:
        """Get information about a specific topic"""
        try:
            if not self.admin_client:
                await self.initialize()

            metadata = await self.admin_client.describe_topics([topic_name])
            return metadata.get(topic_name, {})
        except Exception as e:
            logger.error(f"Failed to get topic info for {topic_name}: {e}")
            return {}

    async def list_all_topics(self) -> List[str]:
        """List all topics in the cluster"""
        try:
            if not self.admin_client:
                await self.initialize()

            topics = await self.admin_client.list_topics()
            return list(topics)
        except Exception as e:
            logger.error(f"Failed to list topics: {e}")
            return []


# Global topic manager instance
topic_manager = KafkaTopicManager()
