"""
Redis client and Redis Streams utilities for event-driven architecture
"""

import asyncio
from typing import Optional
from redis.asyncio import Redis
from redis.exceptions import RedisError

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
