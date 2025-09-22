"""
Kafka admin operations for topic management
"""

import logging
from typing import Dict, Any, List, Optional
from kafka import KafkaAdminClient
from kafka.admin import ConfigResource, ConfigResourceType, NewTopic
from kafka.errors import KafkaError, TopicAlreadyExistsError

logger = logging.getLogger(__name__)


class KafkaAdmin:
    """Kafka admin operations"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._admin: Optional[KafkaAdminClient] = None

    async def initialize(self):
        """Initialize admin client"""
        try:
            self._admin = KafkaAdminClient(
                bootstrap_servers=self.config["bootstrap_servers"],
                client_id=self.config.get("client_id", "betterbundle-admin"),
                **self.config.get("admin_config", {}),
            )
            logger.info("Kafka admin client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka admin: {e}")
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

                # Create topic
                future = self._admin.create_topics([new_topic])
                future[topic_name].result()  # Wait for completion

                results[topic_name] = True
                logger.info(f"Topic '{topic_name}' created successfully")

            except TopicAlreadyExistsError:
                results[topic_name] = True
                logger.info(f"Topic '{topic_name}' already exists")
            except Exception as e:
                results[topic_name] = False
                logger.error(f"Failed to create topic '{topic_name}': {e}")

        return results

    async def delete_topics(self, topic_names: List[str]) -> Dict[str, bool]:
        """Delete topics"""
        if not self._admin:
            raise RuntimeError("Admin client not initialized")

        results = {}

        try:
            future = self._admin.delete_topics(topic_names)
            for topic_name in topic_names:
                try:
                    future[topic_name].result()
                    results[topic_name] = True
                    logger.info(f"Topic '{topic_name}' deleted successfully")
                except Exception as e:
                    results[topic_name] = False
                    logger.error(f"Failed to delete topic '{topic_name}': {e}")
        except Exception as e:
            logger.error(f"Failed to delete topics: {e}")
            for topic_name in topic_names:
                results[topic_name] = False

        return results

    async def list_topics(self) -> List[str]:
        """List all topics"""
        if not self._admin:
            raise RuntimeError("Admin client not initialized")

        try:
            metadata = self._admin.describe_topics()
            return list(metadata.keys())
        except Exception as e:
            logger.error(f"Failed to list topics: {e}")
            return []

    async def get_topic_info(self, topic_name: str) -> Optional[Dict[str, Any]]:
        """Get topic information"""
        if not self._admin:
            raise RuntimeError("Admin client not initialized")

        try:
            metadata = self._admin.describe_topics([topic_name])
            if topic_name in metadata:
                topic_metadata = metadata[topic_name]
                return {
                    "name": topic_name,
                    "partitions": len(topic_metadata.partitions),
                    "replication_factor": (
                        len(topic_metadata.partitions[0].replicas)
                        if topic_metadata.partitions
                        else 0
                    ),
                    "partition_details": [
                        {
                            "partition_id": p.id,
                            "leader": p.leader,
                            "replicas": p.replicas,
                            "isr": p.isr,
                        }
                        for p in topic_metadata.partitions
                    ],
                }
        except Exception as e:
            logger.error(f"Failed to get topic info for '{topic_name}': {e}")

        return None

    async def update_topic_config(
        self, topic_name: str, config: Dict[str, str]
    ) -> bool:
        """Update topic configuration"""
        if not self._admin:
            raise RuntimeError("Admin client not initialized")

        try:
            resource = ConfigResource(ConfigResourceType.TOPIC, topic_name)
            future = self._admin.alter_configs({resource: config})
            future[resource].result()  # Wait for completion

            logger.info(f"Topic '{topic_name}' configuration updated")
            return True
        except Exception as e:
            logger.error(f"Failed to update topic config for '{topic_name}': {e}")
            return False

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
                self._admin.close()
                logger.info("Kafka admin client closed")
            except Exception as e:
                logger.error(f"Error closing admin client: {e}")
