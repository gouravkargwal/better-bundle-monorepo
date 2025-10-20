"""
Kafka topic management utilities
"""

import asyncio
import logging
from typing import Dict, Any, List
from aiokafka.admin import AIOKafkaAdminClient, NewTopic
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

            # Create new topics
            new_topics = []
            for topic_name, topic_config in kafka_settings.topics.items():
                if topic_name not in existing_topics:
                    new_topic = NewTopic(
                        name=topic_name,
                        num_partitions=topic_config.get("partitions", 1),
                        replication_factor=topic_config.get("replication_factor", 1),
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

            self.topics_created = True

        except Exception as e:
            logger.error(f"Failed to create topics: {e}")
            raise

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
