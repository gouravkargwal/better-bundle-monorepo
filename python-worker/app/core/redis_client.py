"""
Redis client and Redis Streams utilities for event-driven architecture
"""

import asyncio
import json
from typing import Dict, Any, Optional, List
from redis.asyncio import Redis
from redis.exceptions import RedisError, ConnectionError

from app.core.config import settings
from app.core.logging import get_logger, log_error, log_performance, log_stream_event

logger = get_logger(__name__)

# Global Redis instance
_redis_instance: Optional[Redis] = None


async def get_redis_client() -> Redis:
    """Get or create Redis connection"""
    global _redis_instance

    if _redis_instance is None:
        logger.info("Initializing Redis connection")

        # Simplified Redis configuration for local development
        redis_config = {
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT,
            "password": settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
            "db": settings.REDIS_DB,
            "decode_responses": True,
            "socket_connect_timeout": 5,
            "socket_timeout": 5,
        }

        # Only add TLS if explicitly enabled and not localhost
        if settings.REDIS_TLS and settings.REDIS_HOST != "localhost":
            redis_config["ssl"] = True
            redis_config["ssl_cert_reqs"] = None

        try:
            start_time = asyncio.get_event_loop().time()
            _redis_instance = Redis(**redis_config)

            # Test connection with shorter timeout
            await asyncio.wait_for(_redis_instance.ping(), timeout=5.0)

            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_performance("redis_connection", duration_ms)
            logger.info("Redis connection established successfully")

        except RedisError as e:
            log_error(e, {"operation": "redis_connection"})
            raise Exception(f"Failed to connect to Redis: {str(e)}")
        except asyncio.TimeoutError as e:
            log_error(e, {"operation": "redis_connection"})
            raise Exception(f"Redis connection timeout: {str(e)}")

    return _redis_instance


async def close_redis_client() -> None:
    """Close Redis connection"""
    global _redis_instance

    if _redis_instance:
        logger.info("Closing Redis connection")
        try:
            await _redis_instance.close()
            _redis_instance = None
            logger.info("Redis connection closed successfully")
        except Exception as e:
            log_error(e, {"operation": "redis_disconnection"})


async def check_redis_health() -> bool:
    """Check Redis connection health"""
    try:
        redis = await get_redis_client()
        await redis.ping()
        return True
    except Exception as e:
        log_error(e, {"operation": "redis_health_check"})
        return False


class RedisStreamsManager:
    """Redis Streams manager for event-driven architecture"""

    def __init__(self):
        self.redis: Optional[Redis] = None

    async def initialize(self):
        """Initialize Redis connection"""
        self.redis = await get_redis_client()

    async def publish_event(
        self, stream_name: str, event_data: Dict[str, Any], event_id: str = "*"
    ) -> str:
        """Publish an event to a Redis stream"""
        if not self.redis:
            await self.initialize()

        try:
            start_time = asyncio.get_event_loop().time()

            # Serialize complex data structures
            serialized_data = {}
            for key, value in event_data.items():
                if isinstance(value, (dict, list)):
                    serialized_data[key] = json.dumps(value)
                else:
                    serialized_data[key] = str(value)

            # Add metadata
            serialized_data["timestamp"] = str(asyncio.get_event_loop().time())
            serialized_data["worker_id"] = settings.WORKER_ID

            # Publish to stream
            message_id = await self.redis.xadd(
                stream_name, serialized_data, id=event_id
            )

            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            log_performance(
                "stream_publish",
                duration_ms,
                {"stream_name": stream_name, "message_id": message_id},
            )

            log_stream_event(
                stream_name=stream_name, event_type="published", event_id=message_id
            )

            return message_id

        except RedisError as e:
            log_error(
                e,
                {
                    "operation": "stream_publish",
                    "stream_name": stream_name,
                    "event_data": event_data,
                },
            )
            raise

    async def consume_events(
        self,
        stream_name: str,
        consumer_group: str,
        consumer_name: str,
        count: int = 1,
        block: int = 1000,
    ) -> List[Dict[str, Any]]:
        """Consume events from a Redis stream"""
        if not self.redis:
            await self.initialize()

        try:
            # Ensure consumer group exists
            try:
                await self.redis.xgroup_create(
                    stream_name, consumer_group, id="0", mkstream=True
                )
            except RedisError as e:
                # Group already exists
                if "BUSYGROUP" not in str(e):
                    raise

            # Read from stream
            messages = await self.redis.xreadgroup(
                consumer_group,
                consumer_name,
                {stream_name: ">"},
                count=count,
                block=block,
            )

            events = []
            for stream, msgs in messages:
                for msg_id, fields in msgs:
                    # Deserialize data
                    event_data = {}
                    for key, value in fields.items():
                        try:
                            # Try to parse as JSON
                            event_data[key] = json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            # Keep as string
                            event_data[key] = value

                    event_data["_message_id"] = msg_id
                    event_data["_stream_name"] = stream
                    events.append(event_data)

                    log_stream_event(
                        stream_name=stream, event_type="consumed", event_id=msg_id
                    )

            return events

        except RedisError as e:
            log_error(
                e,
                {
                    "operation": "stream_consume",
                    "stream_name": stream_name,
                    "consumer_group": consumer_group,
                },
            )
            raise

    async def acknowledge_event(
        self, stream_name: str, consumer_group: str, message_id: str
    ) -> bool:
        """Acknowledge successful processing of an event"""
        if not self.redis:
            await self.initialize()

        try:
            result = await self.redis.xack(stream_name, consumer_group, message_id)

            log_stream_event(
                stream_name=stream_name, event_type="acknowledged", event_id=message_id
            )

            return result > 0

        except RedisError as e:
            log_error(
                e,
                {
                    "operation": "stream_acknowledge",
                    "stream_name": stream_name,
                    "message_id": message_id,
                },
            )
            raise

    async def publish_data_job_event(
        self,
        job_id: str,
        shop_id: str,
        shop_domain: str,
        access_token: str,
        job_type: str = "data_collection",
    ) -> str:
        """Publish a data job event"""
        event_data = {
            "job_id": job_id,
            "shop_id": shop_id,
            "shop_domain": shop_domain,
            "access_token": access_token,
            "job_type": job_type,
            "status": "queued",
        }

        return await self.publish_event(settings.DATA_JOB_STREAM, event_data)

    async def publish_ml_training_event(
        self,
        job_id: str,
        shop_id: str,
        shop_domain: str,
        data_collection_completed: bool = True,
    ) -> str:
        """Publish an ML training event"""
        event_data = {
            "job_id": job_id,
            "shop_id": shop_id,
            "shop_domain": shop_domain,
            "data_collection_completed": data_collection_completed,
            "training_status": "queued",
        }

        return await self.publish_event(settings.ML_TRAINING_STREAM, event_data)

    async def publish_analysis_results_event(
        self,
        job_id: str,
        shop_id: str,
        results: Dict[str, Any],
        status: str = "completed",
    ) -> str:
        """Publish analysis results event"""
        event_data = {
            "job_id": job_id,
            "shop_id": shop_id,
            "status": status,
            "results": results,
        }

        return await self.publish_event(settings.ANALYSIS_RESULTS_STREAM, event_data)

    async def publish_user_notification_event(
        self,
        shop_id: str,
        notification_type: str,
        message: str,
        data: Dict[str, Any] = None,
    ) -> str:
        """Publish user notification event"""
        event_data = {
            "shop_id": shop_id,
            "notification_type": notification_type,
            "message": message,
            "data": data or {},
        }

        return await self.publish_event(settings.USER_NOTIFICATIONS_STREAM, event_data)

    async def publish_features_computed_event(
        self,
        job_id: str,
        shop_id: str,
        features_ready: bool = True,
        metadata: Dict[str, Any] = None,
    ) -> str:
        """Publish features computed event for decoupling transforms and training"""
        event_data = {
            "job_id": job_id,
            "shop_id": shop_id,
            "features_ready": features_ready,
            "metadata": metadata or {},
        }
        return await self.publish_event(settings.FEATURES_COMPUTED_STREAM, event_data)


# Global streams manager instance
streams_manager = RedisStreamsManager()
