"""
Kafka health monitoring and diagnostics
"""

import logging
import time
from typing import Dict, Any, List, Optional
from kafka import KafkaAdminClient
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)


class KafkaHealthChecker:
    """Kafka health monitoring and diagnostics"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._admin: Optional[KafkaAdminClient] = None
        self._last_health_check = 0
        self._health_check_interval = 30  # seconds
        self._health_status = "unknown"

    async def initialize(self):
        """Initialize health checker"""
        try:
            self._admin = KafkaAdminClient(
                bootstrap_servers=self.config["bootstrap_servers"],
                client_id=self.config.get("client_id", "betterbundle-health"),
                **self.config.get("admin_config", {}),
            )
            logger.info("Kafka health checker initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka health checker: {e}")
            raise

    async def check_health(self, force: bool = False) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        current_time = time.time()

        # Use cached result if not forced and recent
        if (
            not force
            and (current_time - self._last_health_check) < self._health_check_interval
        ):
            return self._get_cached_health()

        try:
            health_status = await self._perform_health_check()
            self._health_status = health_status["status"]
            self._last_health_check = current_time

            return health_status

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self._health_status = "unhealthy"
            return {"status": "unhealthy", "error": str(e), "timestamp": current_time}

    async def _perform_health_check(self) -> Dict[str, Any]:
        """Perform actual health check"""
        if not self._admin:
            return {
                "status": "unhealthy",
                "error": "Admin client not initialized",
                "timestamp": time.time(),
            }

        try:
            # Test basic connectivity
            start_time = time.time()
            metadata = self._admin.describe_cluster()
            response_time = (time.time() - start_time) * 1000  # ms

            # Get cluster information
            cluster_info = {
                "cluster_id": getattr(metadata, "cluster_id", "unknown"),
                "controller": getattr(metadata, "controller", "unknown"),
                "brokers": len(getattr(metadata, "brokers", [])),
                "response_time_ms": response_time,
            }

            # Check topic accessibility
            topics = await self._check_topics()

            # Determine overall health
            status = "healthy"
            if response_time > 5000:  # 5 seconds
                status = "degraded"
            if not topics["accessible"]:
                status = "unhealthy"

            return {
                "status": status,
                "cluster": cluster_info,
                "topics": topics,
                "timestamp": time.time(),
                "bootstrap_servers": self.config["bootstrap_servers"],
            }

        except KafkaError as e:
            return {
                "status": "unhealthy",
                "error": f"Kafka error: {str(e)}",
                "timestamp": time.time(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": f"Unexpected error: {str(e)}",
                "timestamp": time.time(),
            }

    async def _check_topics(self) -> Dict[str, Any]:
        """Check topic accessibility"""
        try:
            # Get list of expected topics
            expected_topics = list(self.config.get("topics", {}).keys())

            # Get actual topics
            metadata = self._admin.describe_topics()
            actual_topics = list(metadata.keys())

            # Check which expected topics exist
            missing_topics = [
                topic for topic in expected_topics if topic not in actual_topics
            ]
            extra_topics = [
                topic for topic in actual_topics if topic not in expected_topics
            ]

            return {
                "accessible": len(missing_topics) == 0,
                "expected_count": len(expected_topics),
                "actual_count": len(actual_topics),
                "missing_topics": missing_topics,
                "extra_topics": extra_topics,
                "expected_topics": expected_topics,
                "actual_topics": actual_topics,
            }

        except Exception as e:
            logger.error(f"Failed to check topics: {e}")
            return {"accessible": False, "error": str(e)}

    def _get_cached_health(self) -> Dict[str, Any]:
        """Get cached health status"""
        return {
            "status": self._health_status,
            "cached": True,
            "timestamp": self._last_health_check,
        }

    async def get_metrics(self) -> Dict[str, Any]:
        """Get Kafka metrics"""
        try:
            if not self._admin:
                return {"error": "Admin client not initialized"}

            # Get cluster metrics
            metadata = self._admin.describe_cluster()

            # Get topic metrics
            topics_info = {}
            for topic_name in self.config.get("topics", {}).keys():
                try:
                    topic_metadata = self._admin.describe_topics([topic_name])
                    if topic_name in topic_metadata:
                        topic_info = topic_metadata[topic_name]
                        topics_info[topic_name] = {
                            "partitions": len(topic_info.partitions),
                            "replication_factor": (
                                len(topic_info.partitions[0].replicas)
                                if topic_info.partitions
                                else 0
                            ),
                        }
                except Exception as e:
                    logger.warning(f"Failed to get metrics for topic {topic_name}: {e}")

            return {
                "cluster": {
                    "brokers": len(getattr(metadata, "brokers", [])),
                    "cluster_id": getattr(metadata, "cluster_id", "unknown"),
                },
                "topics": topics_info,
                "timestamp": time.time(),
            }

        except Exception as e:
            logger.error(f"Failed to get metrics: {e}")
            return {"error": str(e)}

    async def close(self):
        """Close health checker"""
        if self._admin:
            try:
                self._admin.close()
                logger.info("Kafka health checker closed")
            except Exception as e:
                logger.error(f"Error closing health checker: {e}")
