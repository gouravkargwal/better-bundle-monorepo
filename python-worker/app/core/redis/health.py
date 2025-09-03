"""
Redis health monitoring utilities
"""

import asyncio
import time
from typing import Optional
from datetime import datetime

from app.core.config import settings
from app.core.exceptions import RedisConnectionError
from app.core.logging import get_logger
from .client import get_redis_client_instance
from .models import RedisHealthStatus

logger = get_logger(__name__)


async def check_redis_health() -> RedisHealthStatus:
    """Check Redis connection health with detailed status"""
    start_time = time.time()

    try:
        redis_client = get_redis_client_instance()
        client = await redis_client.get_client()

        # Test connection with a simple ping
        await client.ping()

        response_time = (time.time() - start_time) * 1000

        # Get connection info
        connection_info = {
            "host": redis_client.config.host,
            "port": redis_client.config.port,
            "db": redis_client.config.db,
            "tls_enabled": redis_client.config.tls,
        }

        return RedisHealthStatus(
            is_healthy=True,
            connection_info=connection_info,
            last_check=datetime.now().isoformat(),
            response_time_ms=response_time,
        )

    except Exception as e:
        response_time = (time.time() - start_time) * 1000

        logger.error(
            "Redis health check failed", error=str(e), response_time_ms=response_time
        )

        return RedisHealthStatus(
            is_healthy=False,
            connection_info={},
            last_check=datetime.now().isoformat(),
            error_message=str(e),
            response_time_ms=response_time,
        )


async def wait_for_redis_ready(
    max_attempts: int = 30, delay_seconds: float = 2.0
) -> bool:
    """Wait for Redis to be ready (useful for container startup)"""
    logger.info(
        "Waiting for Redis to be ready",
        max_attempts=max_attempts,
        delay_seconds=delay_seconds,
    )

    for attempt in range(max_attempts):
        try:
            health_status = await check_redis_health()

            if health_status.is_healthy:
                logger.info("Redis is ready", attempt=attempt + 1)
                return True

        except Exception as e:
            logger.debug("Redis not ready yet", attempt=attempt + 1, error=str(e))

        if attempt < max_attempts - 1:
            await asyncio.sleep(delay_seconds)

    logger.error(
        "Redis failed to become ready",
        max_attempts=max_attempts,
        total_wait_time=max_attempts * delay_seconds,
    )
    return False


async def monitor_redis_health(interval_seconds: int = 60) -> None:
    """Continuous Redis health monitoring"""
    logger.info("Starting Redis health monitoring", interval_seconds=interval_seconds)

    while True:
        try:
            health_status = await check_redis_health()

            if not health_status.is_healthy:
                logger.warning(
                    "Redis health check failed",
                    error=health_status.error_message,
                    response_time_ms=health_status.response_time_ms,
                )

            await asyncio.sleep(interval_seconds)

        except Exception as e:
            logger.error("Error in Redis health monitoring", error=str(e))
            await asyncio.sleep(interval_seconds)
