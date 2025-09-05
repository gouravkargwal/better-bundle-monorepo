"""
Redis client for BetterBundle Python Worker
"""

import asyncio
import time
import json
from typing import Optional, Dict, Any, List
from contextlib import asynccontextmanager
from redis.asyncio import Redis
from redis.exceptions import RedisError, ConnectionError, TimeoutError

from app.core.config.settings import settings
from app.core.exceptions import RedisConnectionError, RedisTimeoutError
from app.core.logging import get_logger
from .models import RedisConnectionConfig, RedisMetrics

logger = get_logger(__name__)


class RedisClient:
    """Enterprise-grade Redis client with connection pooling and health monitoring"""

    def __init__(self, config: Optional[RedisConnectionConfig] = None):
        self.config = config or RedisConnectionConfig(
            host=settings.redis.REDIS_HOST,
            port=settings.redis.REDIS_PORT,
            password=settings.redis.REDIS_PASSWORD,
            db=settings.redis.REDIS_DB,
            tls=settings.redis.REDIS_TLS,
        )
        self._client: Optional[Redis] = None
        self._connection_time: Optional[float] = None
        self._metrics = RedisMetrics(last_reset=str(time.time()))
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        """Establish Redis connection with retry logic"""
        async with self._lock:
            if self._client is not None:
                return

            try:
                logger.info(
                    "Establishing Redis connection",
                    host=self.config.host,
                    port=self.config.port,
                )

                # Build Redis configuration
                redis_config = {
                    "host": self.config.host,
                    "port": self.config.port,
                    "password": self.config.password,
                    "db": self.config.db,
                    "decode_responses": self.config.decode_responses,
                    "socket_connect_timeout": self.config.socket_connect_timeout,
                    "socket_timeout": self.config.socket_timeout,
                    "socket_keepalive": self.config.socket_keepalive,
                    "retry_on_timeout": self.config.retry_on_timeout,
                    "health_check_interval": self.config.health_check_interval,
                }

                # Add TLS if enabled and not localhost
                if self.config.tls and self.config.host != "localhost":
                    redis_config["ssl"] = True
                    redis_config["ssl_cert_reqs"] = None

                self._client = Redis(**redis_config)

                # Test connection
                await asyncio.wait_for(self._client.ping(), timeout=5.0)

                self._connection_time = time.time()
                logger.info("Redis connection established successfully")

            except asyncio.TimeoutError as e:
                self._metrics.connection_errors += 1
                error_msg = f"Redis connection timeout after 5 seconds"
                logger.error(error_msg, host=self.config.host, port=self.config.port)

                raise RedisTimeoutError(
                    message=error_msg, operation="connect", timeout=5.0, cause=e
                )

            except Exception as e:
                self._metrics.connection_errors += 1
                error_msg = f"Failed to connect to Redis: {str(e)}"
                logger.error(
                    error_msg,
                    host=self.config.host,
                    port=self.config.port,
                    error=str(e),
                    error_type=type(e).__name__,
                )

                raise RedisConnectionError(
                    message=error_msg, connection_details=self.config.to_dict(), cause=e
                )

    async def disconnect(self) -> None:
        """Close Redis connection"""
        async with self._lock:
            if self._client is None:
                return

            try:
                await self._client.close()
                self._client = None
                self._connection_time = None
                logger.info("Redis connection closed")

            except Exception as e:
                logger.warning("Error closing Redis connection", error=str(e))

    async def _test_connection(self) -> None:
        """Test Redis connection with a simple ping"""
        try:
            start_time = time.time()
            await self._client.ping()
            response_time = (time.time() - start_time) * 1000

            self._metrics.total_operations += 1
            self._metrics.successful_operations += 1
            self._metrics.average_response_time_ms = (
                self._metrics.average_response_time_ms
                * (self._metrics.total_operations - 1)
                + response_time
            ) / self._metrics.total_operations

            if response_time > 50:  # Consider operations > 50ms as slow
                self._metrics.slow_operations_count += 1

        except Exception as e:
            self._metrics.total_operations += 1
            self._metrics.failed_operations += 1
            raise RedisConnectionError(
                message="Connection test failed",
                connection_details=self.config.to_dict(),
                cause=e,
            )

    async def get_client(self) -> Redis:
        """Get Redis client, creating connection if needed"""
        if self._client is None:
            await self.connect()

        # Check if connection is still alive
        try:
            await self._test_connection()
        except Exception:
            logger.warning("Redis connection lost, reconnecting...")
            await self.disconnect()
            await self.connect()

        return self._client

    async def execute_operation(self, operation: str, *args, **kwargs) -> Any:
        """Execute a Redis operation with metrics tracking"""
        start_time = time.time()

        try:
            client = await self.get_client()

            # Get the method from Redis client
            method = getattr(client, operation)
            result = await method(*args, **kwargs)

            response_time = (time.time() - start_time) * 1000
            self._metrics.total_operations += 1
            self._metrics.successful_operations += 1
            self._metrics.average_response_time_ms = (
                self._metrics.average_response_time_ms
                * (self._metrics.total_operations - 1)
                + response_time
            ) / self._metrics.total_operations

            if response_time > 50:
                self._metrics.slow_operations_count += 1
                logger.warning(
                    "Slow Redis operation detected",
                    operation=operation,
                    response_time_ms=response_time,
                )

            return result

        except TimeoutError as e:
            self._metrics.total_operations += 1
            self._metrics.failed_operations += 1

            raise RedisTimeoutError(
                message=f"Redis operation '{operation}' timed out",
                operation=operation,
                timeout=kwargs.get("timeout"),
                cause=e,
            )

        except Exception as e:
            self._metrics.total_operations += 1
            self._metrics.failed_operations += 1

            raise RedisConnectionError(
                message=f"Redis operation '{operation}' failed",
                connection_details=self.config.to_dict(),
                cause=e,
            )

    async def set(self, key: str, value: Any, **kwargs) -> bool:
        """Set a key-value pair"""
        if isinstance(value, (dict, list)):
            value = json.dumps(value)
        return await self.execute_operation("set", key, value, **kwargs)

    async def get(self, key: str) -> Any:
        """Get a value by key"""
        return await self.execute_operation("get", key)

    async def delete(self, *keys) -> int:
        """Delete one or more keys"""
        return await self.execute_operation("delete", *keys)

    async def exists(self, *keys) -> int:
        """Check if keys exist"""
        return await self.execute_operation("exists", *keys)

    async def expire(self, key: str, time: int) -> bool:
        """Set key expiration"""
        return await self.execute_operation("expire", key, time)

    def get_metrics(self) -> RedisMetrics:
        """Get Redis performance metrics"""
        return self._metrics

    def reset_metrics(self) -> None:
        """Reset performance metrics"""
        self._metrics = RedisMetrics(last_reset=str(time.time()))
        logger.info("Redis metrics reset")


# Global Redis client instance
_redis_client: Optional[RedisClient] = None


async def get_redis_client() -> Redis:
    """Get Redis client (backward compatibility)"""
    global _redis_client

    if _redis_client is None:
        _redis_client = RedisClient()

    return await _redis_client.get_client()


async def close_redis_client() -> None:
    """Close Redis connection (backward compatibility)"""
    global _redis_client

    if _redis_client:
        await _redis_client.disconnect()
        _redis_client = None


def get_redis_client_instance() -> RedisClient:
    """Get the global Redis client instance"""
    global _redis_client

    if _redis_client is None:
        _redis_client = RedisClient()

    return _redis_client
