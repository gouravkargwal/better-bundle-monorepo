"""
Redis client and Redis Streams utilities for event-driven architecture
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List
from redis.asyncio import Redis
from redis.exceptions import RedisError
from datetime import datetime

from app.core.config.settings import settings
from app.core.logging import get_logger

logger = get_logger("redis-client")

# Global Redis instance
_redis_instance: Optional[Redis] = None


async def get_redis_client() -> Redis:
    """Get or create Redis connection"""
    global _redis_instance

    if _redis_instance is None:

        # Optimized Redis configuration for better performance and stability
        redis_config = {
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT,
            "password": settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
            "db": settings.REDIS_DB,
            "decode_responses": True,
            "socket_connect_timeout": 60,  # Increased from 30 to 60 seconds
            "socket_timeout": 60,  # Increased from 30 to 60 seconds
            "socket_keepalive": True,  # Enable TCP keepalive
            "retry_on_timeout": True,  # Retry on timeout
            "health_check_interval": 30,  # Health check every 30 seconds
        }

        # Only add TLS if explicitly enabled and not localhost
        if settings.REDIS_TLS and settings.REDIS_HOST != "localhost":
            redis_config["ssl"] = True
            redis_config["ssl_cert_reqs"] = None

        # Add health check interval for better connection stability
        if "health_check_interval" in redis_config:
            redis_config["health_check_interval"] = 30

        try:
            _redis_instance = Redis(**redis_config)
            # Test connection with shorter timeout
            await asyncio.wait_for(_redis_instance.ping(), timeout=5.0)

        except RedisError as e:
            logger.error(
                f"Redis operation: connection_failed | error={str(e)} | error_type={type(e).__name__}"
            )
            raise Exception(f"Failed to connect to Redis: {str(e)}")
        except asyncio.TimeoutError as e:
            logger.error(
                f"Redis operation: connection_timeout | error={str(e)} | error_type={type(e).__name__}"
            )
            raise Exception(f"Redis connection timeout: {str(e)}")

    return _redis_instance


async def close_redis_client() -> None:
    """Close Redis connection"""
    global _redis_instance

    if _redis_instance:
        try:
            await _redis_instance.close()
            _redis_instance = None
        except Exception as e:
            logger.error(f"Redis operation: connection_close_error | error={str(e)}")


async def check_redis_health() -> bool:
    """Check Redis connection health"""
    try:
        redis = await get_redis_client()
        await redis.ping()
        return True
    except Exception as e:
        logger.error(f"Redis operation: health_check_failed | error={str(e)}")
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
            # Serialize complex data structures with proper datetime handling
            serialized_data = {}
            for key, value in event_data.items():
                if isinstance(value, (dict, list)):
                    # Convert datetime objects to ISO strings before JSON serialization
                    cleaned_value = self._clean_for_serialization(value)
                    serialized_data[key] = json.dumps(cleaned_value)
                else:
                    serialized_data[key] = str(value)

            # Add metadata
            serialized_data["timestamp"] = str(time.time())
            serialized_data["worker_id"] = settings.WORKER_ID

            # Publish to stream
            message_id = await self.redis.xadd(
                stream_name, serialized_data, id=event_id
            )

            return message_id

        except RedisError as e:
            logger.error(
                f"Redis operation: publish_failed | stream_name={stream_name} | error={str(e)} | error_type={type(e).__name__}"
            )
            raise

    def _clean_for_serialization(self, obj: Any) -> Any:
        """
        Recursively clean objects for JSON serialization by converting datetime objects to ISO strings.
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {
                key: self._clean_for_serialization(value) for key, value in obj.items()
            }
        elif isinstance(obj, list):
            return [self._clean_for_serialization(item) for item in obj]
        else:
            return obj

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
                    logger.error(
                        f"Redis operation: consumer_group_creation_failed | stream_name={stream_name} | consumer_group={consumer_group} | error={str(e)}"
                    )
                    raise

            # First, try to read pending messages (messages that were processed but not acknowledged)
            try:
                pending_messages = await self.redis.xreadgroup(
                    consumer_group,
                    consumer_name,
                    {stream_name: "0"},  # "0" means read pending messages
                    count=count,
                    block=0,  # Don't block for pending messages
                )

                if pending_messages and any(msgs for _, msgs in pending_messages):
                    # Process pending messages first
                    messages = pending_messages
                else:
                    messages = await asyncio.wait_for(
                        self.redis.xreadgroup(
                            consumer_group,
                            consumer_name,
                            {stream_name: ">"},  # ">" means new messages only
                            count=count,
                            block=block,
                        ),
                        timeout=(block / 1000)
                        + settings.REDIS_TIMEOUT_BUFFER_SECONDS,  # Configurable buffer
                    )

            except asyncio.TimeoutError:
                # Timeout is expected when no messages are available
                return []

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

            return events

        except RedisError as e:
            logger.error(
                f"Redis operation: consume_failed | stream_name={stream_name} | consumer_group={consumer_group} | error={str(e)} | error_type={type(e).__name__}"
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
            return result > 0

        except RedisError as e:
            logger.error(
                f"Redis operation: acknowledge_failed | stream_name={stream_name} | message_id={message_id} | error={str(e)} | error_type={type(e).__name__}"
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

    async def publish_behavioral_event(
        self,
        event_id: str,
        shop_id: str,
        payload: Dict[str, Any],
    ) -> str:
        """Publish a behavioral event for background processing"""
        event_data = {
            "event_id": event_id,
            "shop_id": shop_id,
            "payload": payload,
            "received_at": time.time(),
            "status": "queued",
        }

        return await self.publish_event(settings.BEHAVIORAL_EVENTS_STREAM, event_data)


# Global streams manager instance
streams_manager = RedisStreamsManager()
