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
            logger.info("Kafka admin client initialized")
        except Exception as e:
            logger.exception(f"Failed to initialize Kafka admin: {e}")
            raise

    async def create_topics(self, topics: Dict[str, Dict[str, Any]]) -> Dict[str, bool]:
        """Create topics with configurations"""
        if not self._admin:
            raise RuntimeError("Admin client not initialized")

        results = {}

        for topic_name, topic_config in topics.items():
            try:
                new_topic = NewTopic(
                    name=topic_name,
                    num_partitions=topic_config.get("partitions", 1),
                    replication_factor=topic_config.get("replication_factor", 1),
                    topic_configs=topic_config.get("config", {}),
                )

                await self._admin.create_topics([new_topic])

                results[topic_name] = True
                logger.info(f"Topic '{topic_name}' created successfully")

            except Exception as e:
                # aiokafka raises generic errors for existing topics depending on broker
                if "TopicExistsError" in str(e) or "already exists" in str(e):
                    results[topic_name] = True
                    logger.info(f"Topic '{topic_name}' already exists")
                else:
                    results[topic_name] = False
                    logger.exception(f"Failed to create topic '{topic_name}': {e}")

        return results

    async def delete_topics(self, topic_names: List[str]) -> Dict[str, bool]:
        """Delete topics"""
        if not self._admin:
            raise RuntimeError("Admin client not initialized")

        results = {}

        try:
            await self._admin.delete_topics(topic_names)
            for topic_name in topic_names:
                results[topic_name] = True
                logger.info(f"Topic '{topic_name}' deleted successfully")
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
                logger.info("Kafka admin client closed")
            except Exception as e:
                logger.exception(f"Error closing admin client: {e}")
