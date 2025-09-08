"""
Distributed Rate Limiter using Redis for horizontal scaling and durability.

This module provides a Redis-based rate limiter that works across multiple
application instances, ensuring consistent rate limiting and preventing
single points of failure.
"""

import asyncio
import json
from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

from app.core.logging import get_logger
from app.core.redis_client import get_redis_client
from app.shared.helpers import now_utc

logger = get_logger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""

    window_seconds: int = 60
    max_requests_per_shop: int = 1000
    max_requests_per_client: int = 100
    max_requests_per_ip: int = 500


@dataclass
class RateLimitResult:
    """Result of rate limit check"""

    allowed: bool
    remaining: int
    reset_time: datetime
    retry_after: Optional[int] = None
    reason: Optional[str] = None


class DistributedRateLimiter:
    """
    Redis-based distributed rate limiter that works across multiple instances.

    Features:
    - Sliding window rate limiting
    - Multiple rate limit tiers (shop, client, IP)
    - Atomic operations using Redis Lua scripts
    - Automatic cleanup of expired entries
    - Circuit breaker pattern for Redis failures
    """

    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self.redis_client = None
        self._circuit_breaker_failures = 0
        self._circuit_breaker_threshold = 5
        self._circuit_breaker_timeout = 60  # seconds
        self._circuit_breaker_reset_time = None

        # Lua script for atomic rate limiting
        self._rate_limit_script = """
        local key = KEYS[1]
        local window = tonumber(ARGV[1])
        local limit = tonumber(ARGV[2])
        local now = tonumber(ARGV[3])
        
        -- Remove expired entries
        redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
        
        -- Count current requests
        local current = redis.call('ZCARD', key)
        
        if current >= limit then
            -- Rate limited
            local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
            local retry_after = 0
            if #oldest > 0 then
                retry_after = math.ceil(oldest[2] + window - now)
            end
            return {0, current, retry_after}
        else
            -- Add current request
            redis.call('ZADD', key, now, now .. ':' .. math.random())
            redis.call('EXPIRE', key, window + 10)  -- Extra buffer for cleanup
            return {1, limit - current - 1, 0}
        end
        """

    async def _get_redis_client(self):
        """Get Redis client with circuit breaker protection"""
        if self._is_circuit_breaker_open():
            raise Exception("Rate limiter circuit breaker is open")

        if self.redis_client is None:
            try:
                self.redis_client = await get_redis_client()
                self._circuit_breaker_failures = 0
            except Exception as e:
                self._circuit_breaker_failures += 1
                if self._circuit_breaker_failures >= self._circuit_breaker_threshold:
                    self._circuit_breaker_reset_time = now_utc() + timedelta(
                        seconds=self._circuit_breaker_timeout
                    )
                raise e

        return self.redis_client

    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is open"""
        if self._circuit_breaker_reset_time is None:
            return False

        if now_utc() > self._circuit_breaker_reset_time:
            self._circuit_breaker_reset_time = None
            self._circuit_breaker_failures = 0
            return False

        return True

    async def check_rate_limit(
        self,
        shop_id: str,
        client_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> RateLimitResult:
        """
        Check if request is within rate limits

        Args:
            shop_id: Shop identifier
            client_id: Optional client identifier
            ip_address: Optional IP address for IP-based limiting

        Returns:
            RateLimitResult with decision and metadata
        """
        try:
            redis = await self._get_redis_client()
            now = now_utc().timestamp()

            # Check shop-level rate limit
            shop_result = await self._check_single_limit(
                redis,
                f"rate_limit:shop:{shop_id}",
                self.config.window_seconds,
                self.config.max_requests_per_shop,
                now,
            )

            if not shop_result[0]:  # Rate limited
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_time=now_utc() + timedelta(seconds=shop_result[2]),
                    retry_after=shop_result[2],
                    reason=f"Shop {shop_id} rate limit exceeded",
                )

            # Check client-level rate limit
            if client_id:
                client_result = await self._check_single_limit(
                    redis,
                    f"rate_limit:client:{client_id}",
                    self.config.window_seconds,
                    self.config.max_requests_per_client,
                    now,
                )

                if not client_result[0]:  # Rate limited
                    return RateLimitResult(
                        allowed=False,
                        remaining=0,
                        reset_time=now_utc() + timedelta(seconds=client_result[2]),
                        retry_after=client_result[2],
                        reason=f"Client {client_id} rate limit exceeded",
                    )

            # Check IP-level rate limit
            if ip_address:
                ip_result = await self._check_single_limit(
                    redis,
                    f"rate_limit:ip:{ip_address}",
                    self.config.window_seconds,
                    self.config.max_requests_per_ip,
                    now,
                )

                if not ip_result[0]:  # Rate limited
                    return RateLimitResult(
                        allowed=False,
                        remaining=0,
                        reset_time=now_utc() + timedelta(seconds=ip_result[2]),
                        retry_after=ip_result[2],
                        reason=f"IP {ip_address} rate limit exceeded",
                    )

            # All checks passed
            return RateLimitResult(
                allowed=True,
                remaining=min(
                    shop_result[1], client_result[1] if client_id else shop_result[1]
                ),
                reset_time=now_utc() + timedelta(seconds=self.config.window_seconds),
                reason="Rate limit check passed",
            )

        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            # Fail open - allow request if rate limiter is down
            return RateLimitResult(
                allowed=True,
                remaining=999,
                reset_time=now_utc() + timedelta(seconds=self.config.window_seconds),
                reason="Rate limiter unavailable, allowing request",
            )

    async def _check_single_limit(
        self, redis, key: str, window: int, limit: int, now: float
    ) -> Tuple[int, int, int]:
        """
        Check a single rate limit using Lua script

        Returns:
            Tuple of (allowed, remaining, retry_after)
        """
        try:
            result = await redis.eval(
                self._rate_limit_script, keys=[key], args=[window, limit, now]
            )
            return (int(result[0]), int(result[1]), int(result[2]))
        except Exception as e:
            logger.error(f"Redis rate limit check failed for key {key}: {e}")
            # Fail open
            return (1, limit, 0)

    async def get_rate_limit_status(
        self,
        shop_id: str,
        client_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get current rate limit status without incrementing counters

        Returns:
            Dictionary with current rate limit status
        """
        try:
            redis = await self._get_redis_client()
            now = now_utc().timestamp()

            status = {
                "shop_id": shop_id,
                "client_id": client_id,
                "ip_address": ip_address,
                "timestamp": now_utc().isoformat(),
                "limits": {},
            }

            # Check shop limit
            shop_key = f"rate_limit:shop:{shop_id}"
            shop_count = await redis.zcard(shop_key)
            status["limits"]["shop"] = {
                "current": shop_count,
                "limit": self.config.max_requests_per_shop,
                "remaining": max(0, self.config.max_requests_per_shop - shop_count),
                "window_seconds": self.config.window_seconds,
            }

            # Check client limit
            if client_id:
                client_key = f"rate_limit:client:{client_id}"
                client_count = await redis.zcard(client_key)
                status["limits"]["client"] = {
                    "current": client_count,
                    "limit": self.config.max_requests_per_client,
                    "remaining": max(
                        0, self.config.max_requests_per_client - client_count
                    ),
                    "window_seconds": self.config.window_seconds,
                }

            # Check IP limit
            if ip_address:
                ip_key = f"rate_limit:ip:{ip_address}"
                ip_count = await redis.zcard(ip_key)
                status["limits"]["ip"] = {
                    "current": ip_count,
                    "limit": self.config.max_requests_per_ip,
                    "remaining": max(0, self.config.max_requests_per_ip - ip_count),
                    "window_seconds": self.config.window_seconds,
                }

            return status

        except Exception as e:
            logger.error(f"Failed to get rate limit status: {e}")
            return {"error": str(e), "timestamp": now_utc().isoformat()}

    async def reset_rate_limits(
        self,
        shop_id: Optional[str] = None,
        client_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Reset rate limits for specific identifiers

        Returns:
            Dictionary with reset results
        """
        try:
            redis = await self._get_redis_client()
            results = {}

            if shop_id:
                shop_key = f"rate_limit:shop:{shop_id}"
                await redis.delete(shop_key)
                results["shop"] = "reset"

            if client_id:
                client_key = f"rate_limit:client:{client_id}"
                await redis.delete(client_key)
                results["client"] = "reset"

            if ip_address:
                ip_key = f"rate_limit:ip:{ip_address}"
                await redis.delete(ip_key)
                results["ip"] = "reset"

            return {
                "status": "success",
                "reset_limits": results,
                "timestamp": now_utc().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to reset rate limits: {e}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": now_utc().isoformat(),
            }

    async def cleanup_expired_entries(self) -> Dict[str, Any]:
        """
        Clean up expired rate limit entries

        Returns:
            Dictionary with cleanup results
        """
        try:
            redis = await self._get_redis_client()
            now = now_utc().timestamp()

            # Find all rate limit keys
            pattern = "rate_limit:*"
            keys = await redis.keys(pattern)

            cleaned_count = 0
            for key in keys:
                # Remove expired entries
                removed = await redis.zremrangebyscore(
                    key, 0, now - self.config.window_seconds
                )
                cleaned_count += removed

                # Delete empty keys
                if await redis.zcard(key) == 0:
                    await redis.delete(key)

            return {
                "status": "success",
                "cleaned_entries": cleaned_count,
                "processed_keys": len(keys),
                "timestamp": now_utc().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to cleanup expired entries: {e}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": now_utc().isoformat(),
            }
