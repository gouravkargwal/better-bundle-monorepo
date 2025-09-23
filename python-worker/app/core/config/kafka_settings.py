"""
Kafka configuration settings
"""

from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Dict, Any, List


class KafkaSettings(BaseSettings):
    """Kafka configuration settings"""

    # Connection settings
    bootstrap_servers: List[str] = Field(
        default=["localhost:9092"], env="KAFKA_BOOTSTRAP_SERVERS"
    )
    client_id: str = Field(default="betterbundle", env="KAFKA_CLIENT_ID")
    worker_id: str = Field(default="worker-1", env="KAFKA_WORKER_ID")

    # Static membership settings to reduce rebalancing
    group_instance_id: str = Field(
        default="betterbundle-worker-1", env="KAFKA_GROUP_INSTANCE_ID"
    )

    # Producer settings (aiokafka compatible)
    producer_config: Dict[str, Any] = Field(
        default={
            "acks": "all",
            "max_batch_size": 16384,
            "linger_ms": 10,
            # "compression_type": "snappy",  # Removed - requires python-snappy
            "request_timeout_ms": 30000,
            "retry_backoff_ms": 100,
        }
    )

    # Consumer settings (aiokafka compatible)
    consumer_config: Dict[str, Any] = Field(
        default={
            "auto_offset_reset": "latest",
            "enable_auto_commit": False,
            "max_poll_records": 500,
            "session_timeout_ms": 30000,  # Increased from 10s to 30s
            "heartbeat_interval_ms": 10000,  # Increased from 3s to 10s (1/3 of session timeout)
            "max_poll_interval_ms": 300000,
            "request_timeout_ms": 30000,  # Increased from 10s to 30s
            "rebalance_timeout_ms": 60000,  # Added rebalance timeout
            "group_instance_id": "betterbundle-worker-1",  # Static membership
        }
    )

    # Admin settings
    admin_config: Dict[str, Any] = Field(
        default={
            "request_timeout_ms": 30000,
            "connections_max_idle_ms": 540000,
        }
    )

    # Topic settings
    topics: Dict[str, Dict[str, Any]] = Field(
        default={
            "shopify-events": {
                "partitions": 6,
                "replication_factor": 3,
                "retention_ms": 604800000,  # 7 days
                "compression_type": "snappy",
                "cleanup_policy": "delete",
            },
            "data-collection-jobs": {
                "partitions": 4,
                "replication_factor": 3,
                "retention_ms": 259200000,  # 3 days
                "compression_type": "snappy",
                "cleanup_policy": "delete",
            },
            "normalization-jobs": {
                "partitions": 4,
                "replication_factor": 3,
                "retention_ms": 259200000,  # 3 days
                "compression_type": "snappy",
                "cleanup_policy": "delete",
            },
            "billing-events": {
                "partitions": 4,
                "replication_factor": 3,
                "retention_ms": 259200000,  # 3 days
                "compression_type": "snappy",
                "cleanup_policy": "delete",
            },
            "feature-computation-jobs": {
                "partitions": 2,
                "replication_factor": 3,
                "retention_ms": 86400000,  # 1 day
                "compression_type": "snappy",
                "cleanup_policy": "delete",
            },
            "customer-linking-jobs": {
                "partitions": 4,
                "replication_factor": 3,
                "retention_ms": 259200000,  # 3 days
                "compression_type": "snappy",
                "cleanup_policy": "delete",
            },
            "purchase-attribution-jobs": {
                "partitions": 6,
                "replication_factor": 3,
                "retention_ms": 259200000,  # 3 days
                "compression_type": "snappy",
                "cleanup_policy": "delete",
            },
            "refund-attribution-jobs": {
                "partitions": 4,
                "replication_factor": 3,
                "retention_ms": 259200000,  # 3 days
                "compression_type": "snappy",
                "cleanup_policy": "delete",
            },
        }
    )

    # Consumer groups
    consumer_groups: Dict[str, str] = Field(
        default={
            "shopify-events-processors": "shopify-events",
            "data-collection-processors": "data-collection-jobs",
            "normalization-processors": "normalization-jobs",
            "billing-processors": "billing-events",
            "feature-computation-processors": "feature-computation-jobs",
            "customer-linking-processors": "customer-linking-jobs",
            "purchase-attribution-processors": "purchase-attribution-jobs",
            "refund-attribution-processors": "refund-attribution-jobs",
        }
    )

    # Health check settings
    health_check_interval: int = Field(default=30, env="KAFKA_HEALTH_CHECK_INTERVAL")
    health_check_timeout: int = Field(default=5, env="KAFKA_HEALTH_CHECK_TIMEOUT")

    class Config:
        env_prefix = "KAFKA_"
        case_sensitive = False


# Global settings instance
kafka_settings = KafkaSettings()
