"""
Redis client and Redis Streams utilities for event-driven architecture
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List
from redis.asyncio import Redis
from redis.exceptions import RedisError, ConnectionError

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger("redis-client")

# Global Redis instance
_redis_instance: Optional[Redis] = None


async def get_redis_client() -> Redis:
    """Get or create Redis connection"""
    global _redis_instance

    if _redis_instance is None:
        logger.log_redis_operation(
            "initializing_connection",
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
        )

        # Simplified Redis configuration for local development
        redis_config = {
            "host": settings.REDIS_HOST,
            "port": settings.REDIS_PORT,
            "password": settings.REDIS_PASSWORD if settings.REDIS_PASSWORD else None,
            "db": settings.REDIS_DB,
            "decode_responses": True,
            "socket_connect_timeout": 10,  # Increased from 5 to 10 seconds
            "socket_timeout": 10,  # Increased from 5 to 10 seconds
            "retry_on_timeout": True,  # Retry on timeout
            "health_check_interval": 30,  # Health check every 30 seconds
        }

        # Only add TLS if explicitly enabled and not localhost
        if settings.REDIS_TLS and settings.REDIS_HOST != "localhost":
            redis_config["ssl"] = True
            redis_config["ssl_cert_reqs"] = None

        try:
            start_time = time.time()
            _redis_instance = Redis(**redis_config)

            # Test connection with shorter timeout
            await asyncio.wait_for(_redis_instance.ping(), timeout=5.0)

            duration_ms = (time.time() - start_time) * 1000
            logger.log_performance("redis_connection", duration_ms)
            logger.log_redis_operation(
                "connection_established",
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
            )

        except RedisError as e:
            logger.log_redis_operation(
                "connection_failed", error=str(e), error_type=type(e).__name__
            )
            raise Exception(f"Failed to connect to Redis: {str(e)}")
        except asyncio.TimeoutError as e:
            logger.log_redis_operation(
                "connection_timeout", error=str(e), error_type=type(e).__name__
            )
            raise Exception(f"Redis connection timeout: {str(e)}")

    return _redis_instance


async def close_redis_client() -> None:
    """Close Redis connection"""
    global _redis_instance

    if _redis_instance:
        logger.log_redis_operation("closing_connection")
        try:
            await _redis_instance.close()
            _redis_instance = None
            logger.log_redis_operation("connection_closed")
        except Exception as e:
            logger.log_redis_operation("connection_close_error", error=str(e))


async def check_redis_health() -> bool:
    """Check Redis connection health"""
    try:
        redis = await get_redis_client()
        start_time = time.time()
        await redis.ping()
        duration_ms = (time.time() - start_time) * 1000

        logger.log_redis_operation("health_check_success", duration_ms=duration_ms)
        return True
    except Exception as e:
        logger.log_redis_operation("health_check_failed", error=str(e))
        return False


class RedisStreamsManager:
    """Redis Streams manager for event-driven architecture"""

    def __init__(self):
        self.redis: Optional[Redis] = None

    async def initialize(self):
        """Initialize Redis connection"""
        logger.log_redis_operation("streams_manager_initializing")
        self.redis = await get_redis_client()
        logger.log_redis_operation("streams_manager_initialized")

    async def publish_event(
        self, stream_name: str, event_data: Dict[str, Any], event_id: str = "*"
    ) -> str:
        """Publish an event to a Redis stream"""
        if not self.redis:
            await self.initialize()

        try:
            start_time = time.time()

            # Serialize complex data structures
            serialized_data = {}
            for key, value in event_data.items():
                if isinstance(value, (dict, list)):
                    serialized_data[key] = json.dumps(value)
                else:
                    serialized_data[key] = str(value)

            # Add metadata
            serialized_data["timestamp"] = str(time.time())
            serialized_data["worker_id"] = settings.WORKER_ID

            logger.log_redis_operation(
                "publishing_event",
                stream_name=stream_name,
                event_data_keys=list(serialized_data.keys()),
            )

            # Publish to stream
            message_id = await self.redis.xadd(
                stream_name, serialized_data, id=event_id
            )

            duration_ms = (time.time() - start_time) * 1000
            logger.log_performance(
                "stream_publish",
                duration_ms,
                stream_name=stream_name,
                message_id=message_id,
            )
            logger.log_redis_operation(
                "event_published",
                stream_name=stream_name,
                message_id=message_id,
                duration_ms=duration_ms,
            )

            return message_id

        except RedisError as e:
            logger.log_redis_operation(
                "publish_failed",
                stream_name=stream_name,
                error=str(e),
                error_type=type(e).__name__,
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
            logger.log_redis_operation(
                "consuming_events",
                stream_name=stream_name,
                consumer_group=consumer_group,
                consumer_name=consumer_name,
                count=count,
                block=block,
            )

            # Ensure consumer group exists
            try:
                await self.redis.xgroup_create(
                    stream_name, consumer_group, id="0", mkstream=True
                )
                logger.log_redis_operation(
                    "consumer_group_created",
                    stream_name=stream_name,
                    consumer_group=consumer_group,
                )
            except RedisError as e:
                # Group already exists
                if "BUSYGROUP" not in str(e):
                    logger.log_redis_operation(
                        "consumer_group_creation_failed",
                        stream_name=stream_name,
                        consumer_group=consumer_group,
                        error=str(e),
                    )
                    raise
                else:
                    logger.log_redis_operation(
                        "consumer_group_already_exists",
                        stream_name=stream_name,
                        consumer_group=consumer_group,
                    )

            # First, try to read pending messages (messages that were processed but not acknowledged)
            try:
                logger.log_redis_operation(
                    "checking_pending_messages",
                    stream_name=stream_name,
                    consumer_group=consumer_group,
                )

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
                    logger.log_redis_operation(
                        "found_pending_messages",
                        stream_name=stream_name,
                        count=len(pending_messages[0][1]) if pending_messages else 0,
                    )
                else:
                    # No pending messages, read new messages
                    logger.log_redis_operation(
                        "reading_new_messages", stream_name=stream_name, block=block
                    )

                    messages = await asyncio.wait_for(
                        self.redis.xreadgroup(
                            consumer_group,
                            consumer_name,
                            {stream_name: ">"},  # ">" means new messages only
                            count=count,
                            block=block,
                        ),
                        timeout=(block / 1000) + 1,  # Add 1 second buffer
                    )
                    logger.log_redis_operation(
                        "new_messages_read",
                        stream_name=stream_name,
                        count=len(messages[0][1]) if messages else 0,
                    )

            except asyncio.TimeoutError:
                # Timeout is expected when no messages are available
                logger.log_redis_operation(
                    "consume_timeout", stream_name=stream_name, block=block
                )
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

                    logger.log_redis_operation(
                        "event_deserialized",
                        stream_name=stream,
                        message_id=msg_id,
                        fields_count=len(fields),
                    )

            logger.log_redis_operation(
                "consume_completed", stream_name=stream_name, events_count=len(events)
            )
            return events

        except RedisError as e:
            logger.log_redis_operation(
                "consume_failed",
                stream_name=stream_name,
                consumer_group=consumer_group,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    async def acknowledge_event(
        self, stream_name: str, consumer_group: str, message_id: str
    ) -> bool:
        """Acknowledge successful processing of an event"""
        if not self.redis:
            await self.initialize()

        try:
            logger.log_redis_operation(
                "acknowledging_event",
                stream_name=stream_name,
                consumer_group=consumer_group,
                message_id=message_id,
            )

            result = await self.redis.xack(stream_name, consumer_group, message_id)

            logger.log_redis_operation(
                "event_acknowledged",
                stream_name=stream_name,
                message_id=message_id,
                result=result,
            )

            return result > 0

        except RedisError as e:
            logger.log_redis_operation(
                "acknowledge_failed",
                stream_name=stream_name,
                message_id=message_id,
                error=str(e),
                error_type=type(e).__name__,
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
