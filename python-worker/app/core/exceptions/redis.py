"""
Redis-related exceptions
"""

from .base import BetterBundleException
from typing import Optional, Dict, Any


class RedisError(BetterBundleException):
    """Base exception for Redis errors"""

    def __init__(self, message: str, **kwargs):
        super().__init__(message=message, error_code="REDIS_ERROR", **kwargs)


class RedisConnectionError(RedisError):
    """Raised when Redis connection fails"""

    def __init__(
        self,
        message: str,
        connection_details: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            error_code="REDIS_CONNECTION_ERROR",
            details={"connection_details": connection_details},
            **kwargs
        )


class RedisStreamError(RedisError):
    """Raised when Redis stream operations fail"""

    def __init__(
        self,
        message: str,
        stream_name: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            error_code="REDIS_STREAM_ERROR",
            details={"stream_name": stream_name, "operation": operation},
            **kwargs
        )


class RedisTimeoutError(RedisError):
    """Raised when Redis operations timeout"""

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        timeout: Optional[float] = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            error_code="REDIS_TIMEOUT_ERROR",
            details={"operation": operation, "timeout": timeout},
            **kwargs
        )
