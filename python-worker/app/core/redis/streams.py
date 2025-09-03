"""
Redis Streams manager for event-driven architecture
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from app.core.config import settings
from app.core.exceptions import RedisStreamError
from app.core.logging import get_logger
from .client import get_redis_client_instance
from .models import RedisStreamConfig, StreamEvent

logger = get_logger(__name__)


class RedisStreamsManager:
    """Redis Streams manager for event-driven architecture"""

    def __init__(self):
        self.redis_client = get_redis_client_instance()
        self._stream_configs: Dict[str, RedisStreamConfig] = {}
        self._consumer_groups: Dict[str, str] = {}

    async def initialize(self) -> None:
        """Initialize Redis connection"""
        await self.redis_client.connect()
        logger.info("Redis Streams manager initialized")

    async def create_stream(self, stream_name: str, config: RedisStreamConfig) -> bool:
        """Create a new stream with configuration"""
        try:
            client = await self.redis_client.get_client()

            # Create stream if it doesn't exist
            # Note: Redis streams are created automatically on first XADD
            # We'll just store the configuration
            self._stream_configs[stream_name] = config

            # Create consumer group if specified
            if config.consumer_group:
                try:
                    await client.xgroup_create(
                        stream_name, config.consumer_group, id="0", mkstream=True
                    )
                    self._consumer_groups[stream_name] = config.consumer_group
                    logger.info(
                        f"Created consumer group '{config.consumer_group}' for stream '{stream_name}'"
                    )
                except Exception as e:
                    if "BUSYGROUP" not in str(e):  # Group already exists
                        logger.warning(f"Could not create consumer group: {e}")

            logger.info(f"Stream '{stream_name}' configured successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to create stream '{stream_name}': {e}")
            raise RedisStreamError(
                message=f"Failed to create stream '{stream_name}'",
                stream_name=stream_name,
                operation="create",
                cause=e,
            )

    async def publish_event(
        self,
        stream_name: str,
        event_data: Dict[str, Any],
        event_id: str = "*",
        max_len: Optional[int] = None,
    ) -> str:
        """Publish an event to a stream"""
        try:
            client = await self.redis_client.get_client()

            # Add timestamp to event data
            event_data["timestamp"] = datetime.now().isoformat()

            # Publish to stream
            stream_id = await client.xadd(
                stream_name,
                event_data,
                id=event_id,
                maxlen=max_len or self._stream_configs.get(stream_name, {}).max_len,
                approximate=True,
            )

            logger.debug(
                f"Event published to stream '{stream_name}'",
                event_id=stream_id,
                stream_name=stream_name,
            )

            return stream_id

        except Exception as e:
            logger.error(f"Failed to publish event to stream '{stream_name}': {e}")
            raise RedisStreamError(
                message=f"Failed to publish event to stream '{stream_name}'",
                stream_name=stream_name,
                operation="publish",
                cause=e,
            )

    async def read_events(
        self,
        stream_name: str,
        consumer_group: str,
        consumer_name: str,
        count: int = 10,
        block: int = 5000,
    ) -> List[StreamEvent]:
        """Read events from a stream using consumer group"""
        try:
            client = await self.redis_client.get_client()

            # Read events from stream
            events = await client.xreadgroup(
                consumer_group,
                consumer_name,
                {stream_name: ">"},
                count=count,
                block=block,
            )

            if not events:
                return []

            stream_events = []
            for stream, stream_events_data in events:
                for event_id, event_data in stream_events_data:
                    event = StreamEvent(
                        stream_name=stream,
                        event_id=event_id,
                        event_data=event_data,
                        timestamp=event_data.get("timestamp", ""),
                        consumer_group=consumer_group,
                        consumer_name=consumer_name,
                    )
                    stream_events.append(event)

            logger.debug(
                f"Read {len(stream_events)} events from stream '{stream_name}'",
                stream_name=stream_name,
                consumer_group=consumer_group,
            )

            return stream_events

        except Exception as e:
            logger.error(f"Failed to read events from stream '{stream_name}': {e}")
            raise RedisStreamError(
                message=f"Failed to read events from stream '{stream_name}'",
                stream_name=stream_name,
                operation="read",
                cause=e,
            )

    async def acknowledge_event(
        self, stream_name: str, consumer_group: str, event_id: str
    ) -> bool:
        """Acknowledge an event (mark as processed)"""
        try:
            client = await self.redis_client.get_client()

            # Acknowledge the event
            result = await client.xack(stream_name, consumer_group, event_id)

            logger.debug(
                f"Event acknowledged",
                event_id=event_id,
                stream_name=stream_name,
                consumer_group=consumer_group,
            )

            return bool(result)

        except Exception as e:
            logger.error(f"Failed to acknowledge event '{event_id}': {e}")
            raise RedisStreamError(
                message=f"Failed to acknowledge event",
                stream_name=stream_name,
                operation="acknowledge",
                cause=e,
            )

    async def get_stream_info(self, stream_name: str) -> Dict[str, Any]:
        """Get information about a stream"""
        try:
            client = await self.redis_client.get_client()

            # Get stream info
            info = await client.xinfo_stream(stream_name)

            # Get consumer groups info
            groups_info = await client.xinfo_groups(stream_name)

            return {
                "stream_name": stream_name,
                "length": info.get("length", 0),
                "groups": len(groups_info),
                "last_generated_id": info.get("last-generated-id", "0-0"),
                "first_entry": info.get("first-entry", None),
                "last_entry": info.get("last-entry", None),
                "consumer_groups": groups_info,
            }

        except Exception as e:
            logger.error(f"Failed to get stream info for '{stream_name}': {e}")
            raise RedisStreamError(
                message=f"Failed to get stream info",
                stream_name=stream_name,
                operation="info",
                cause=e,
            )

    async def get_pending_events(
        self,
        stream_name: str,
        consumer_group: str,
        consumer_name: Optional[str] = None,
        min_idle_time: int = 0,
        count: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get pending events for a consumer group"""
        try:
            client = await self.redis_client.get_client()

            # Get pending events
            pending = await client.xpending_range(
                stream_name,
                consumer_group,
                min_idle_time=min_idle_time,
                count=count,
                consumer=consumer_name,
            )

            return pending

        except Exception as e:
            logger.error(
                f"Failed to get pending events for stream '{stream_name}': {e}"
            )
            raise RedisStreamError(
                message=f"Failed to get pending events",
                stream_name=stream_name,
                operation="pending",
                cause=e,
            )

    async def claim_pending_events(
        self,
        stream_name: str,
        consumer_group: str,
        consumer_name: str,
        min_idle_time: int = 60000,  # 1 minute
        event_ids: Optional[List[str]] = None,
    ) -> List[str]:
        """Claim pending events for a consumer"""
        try:
            client = await self.redis_client.get_client()

            if event_ids:
                # Claim specific events
                claimed = await client.xclaim(
                    stream_name, consumer_group, consumer_name, min_idle_time, event_ids
                )
            else:
                # Claim all pending events
                pending = await self.get_pending_events(
                    stream_name, consumer_group, consumer_name, min_idle_time
                )

                if not pending:
                    return []

                event_ids = [event["message_id"] for event in pending]
                claimed = await client.xclaim(
                    stream_name, consumer_group, consumer_name, min_idle_time, event_ids
                )

            logger.info(
                f"Claimed {len(claimed)} events for consumer '{consumer_name}'",
                stream_name=stream_name,
                consumer_group=consumer_group,
            )

            return claimed

        except Exception as e:
            logger.error(f"Failed to claim pending events: {e}")
            raise RedisStreamError(
                message="Failed to claim pending events",
                stream_name=stream_name,
                operation="claim",
                cause=e,
            )

    async def trim_stream(self, stream_name: str, max_len: int) -> int:
        """Trim stream to specified length"""
        try:
            client = await self.redis_client.get_client()

            # Trim stream
            result = await client.xtrim(stream_name, maxlen=max_len, approximate=True)

            logger.info(
                f"Stream '{stream_name}' trimmed to max length {max_len}",
                removed_count=result,
            )

            return result

        except Exception as e:
            logger.error(f"Failed to trim stream '{stream_name}': {e}")
            raise RedisStreamError(
                message=f"Failed to trim stream '{stream_name}'",
                stream_name=stream_name,
                operation="trim",
                cause=e,
            )

    async def close(self) -> None:
        """Close Redis connection"""
        await self.redis_client.disconnect()
        logger.info("Redis Streams manager closed")
