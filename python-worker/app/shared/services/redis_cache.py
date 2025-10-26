"""
Enterprise-grade Redis cache service for BetterBundle Python Worker

This service provides a robust, configurable caching layer that can be used
across all application domains for consistent caching behavior.
"""

import asyncio
import json
import pickle
import hashlib
from typing import Any, Optional, Dict, List, Union, TypeVar, Generic
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from app.core.logging import get_logger
from app.core.redis.client import get_redis_client_instance, RedisClient
from app.core.exceptions import RedisConnectionError, RedisTimeoutError

logger = get_logger(__name__)

T = TypeVar("T")


class CacheKey:
    """Cache key builder with namespace support"""

    def __init__(self, namespace: str, prefix: str = "cache"):
        self.namespace = namespace
        self.prefix = prefix

    def build(self, key: str, *args, **kwargs) -> str:
        """Build a cache key with namespace and optional parameters"""
        # Create a hash of additional parameters for consistent key generation
        if args or kwargs:
            param_str = json.dumps([args, kwargs], sort_keys=True)
            param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
            key = f"{key}:{param_hash}"

        return f"{self.prefix}:{self.namespace}:{key}"

    def build_pattern(self, pattern: str = "*") -> str:
        """Build a pattern for key scanning"""
        return f"{self.prefix}:{self.namespace}:{pattern}"


class CacheSerializer:
    """Handles serialization and deserialization of cache data"""

    @staticmethod
    def serialize(value: Any) -> str:
        """Serialize value to JSON string"""
        try:
            return json.dumps(value, default=str)
        except (TypeError, ValueError) as e:
            logger.error(f"JSON serialization failed, falling back to pickle: {e}")
            return pickle.dumps(value).hex()

    @staticmethod
    def deserialize(value: str, use_pickle: bool = False) -> Any:
        """Deserialize value from string"""
        try:
            if use_pickle:
                return pickle.loads(bytes.fromhex(value))
            return json.loads(value)
        except (json.JSONDecodeError, ValueError, pickle.PickleError) as e:
            logger.error(f"Deserialization failed: {e}")
            return None


class CacheMetadata:
    """Metadata for cache entries"""

    def __init__(self, created_at: datetime, ttl: int, access_count: int = 0):
        self.created_at = created_at
        self.ttl = ttl
        self.access_count = access_count
        self.last_accessed = created_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "created_at": self.created_at.isoformat(),
            "ttl": self.ttl,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat(),
            "expires_at": (self.created_at + timedelta(seconds=self.ttl)).isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheMetadata":
        """Create from dictionary"""
        return cls(
            created_at=datetime.fromisoformat(data["created_at"]),
            ttl=data["ttl"],
            access_count=data.get("access_count", 0),
        )


class RedisCacheService(Generic[T]):
    """
    Enterprise-grade Redis cache service with advanced features:
    - TTL management
    - Key namespacing
    - Serialization/deserialization
    - Error handling and retries
    - Cache statistics and monitoring
    - Bulk operations
    """

    def __init__(self, namespace: str, default_ttl: int = 3600):
        self.namespace = namespace
        self.default_ttl = default_ttl
        self.cache_key = CacheKey(namespace)
        self.serializer = CacheSerializer()
        self._redis_client = None
        self._stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0, "errors": 0}

    async def _get_redis_client(self):
        """Get Redis client with lazy initialization"""
        if self._redis_client is None:
            self._redis_client = await get_shared_redis_client()
        return await self._redis_client.get_client()

    async def get(self, key: str, *args, **kwargs) -> Optional[T]:
        """
        Get value from cache

        Args:
            key: Cache key
            *args, **kwargs: Additional parameters for key building

        Returns:
            Cached value or None if not found/expired
        """
        cache_key = self.cache_key.build(key, *args, **kwargs)

        try:
            redis_client = await self._get_redis_client()

            # Get value and metadata
            value_data = await redis_client.get(f"{cache_key}:value")
            metadata_data = await redis_client.get(f"{cache_key}:metadata")

            if not value_data or not metadata_data:
                self._stats["misses"] += 1
                return None

            # Parse metadata
            try:
                metadata = CacheMetadata.from_dict(json.loads(metadata_data))
            except (json.JSONDecodeError, KeyError):
                logger.error(
                    f"Invalid metadata for key {cache_key}, treating as cache miss"
                )
                self._stats["misses"] += 1
                return None

            # Check if expired
            if datetime.now() > metadata.created_at + timedelta(seconds=metadata.ttl):
                await self.delete(key, *args, **kwargs)
                self._stats["misses"] += 1
                return None

            # Update access statistics
            metadata.access_count += 1
            metadata.last_accessed = datetime.now()
            await redis_client.setex(
                f"{cache_key}:metadata", metadata.ttl, json.dumps(metadata.to_dict())
            )

            # Deserialize value
            value = self.serializer.deserialize(value_data)
            self._stats["hits"] += 1

            return value

        except Exception as e:
            logger.error(f"Cache get error for key {cache_key}: {e}")
            self._stats["errors"] += 1
            return None

    async def set(
        self, key: str, value: T, ttl: Optional[int] = None, *args, **kwargs
    ) -> bool:
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if None)
            *args, **kwargs: Additional parameters for key building

        Returns:
            True if successful, False otherwise
        """
        cache_key = self.cache_key.build(key, *args, **kwargs)
        ttl = ttl or self.default_ttl

        try:
            redis_client = await self._get_redis_client()

            # Serialize value
            serialized_value = self.serializer.serialize(value)

            # Create metadata
            metadata = CacheMetadata(created_at=datetime.now(), ttl=ttl)

            # Store value and metadata atomically
            async with redis_client.pipeline() as pipe:
                await pipe.setex(f"{cache_key}:value", ttl, serialized_value)
                await pipe.setex(
                    f"{cache_key}:metadata", ttl, json.dumps(metadata.to_dict())
                )
                await pipe.execute()

            self._stats["sets"] += 1
            return True

        except Exception as e:
            logger.error(f"Cache set error for key {cache_key}: {e}")
            self._stats["errors"] += 1
            return False

    async def delete(self, key: str, *args, **kwargs) -> bool:
        """
        Delete value from cache

        Args:
            key: Cache key
            *args, **kwargs: Additional parameters for key building

        Returns:
            True if successful, False otherwise
        """
        cache_key = self.cache_key.build(key, *args, **kwargs)

        try:
            redis_client = await self._get_redis_client()

            # Delete both value and metadata
            async with redis_client.pipeline() as pipe:
                await pipe.delete(f"{cache_key}:value")
                await pipe.delete(f"{cache_key}:metadata")
                await pipe.execute()

            self._stats["deletes"] += 1
            return True

        except Exception as e:
            logger.error(f"Cache delete error for key {cache_key}: {e}")
            self._stats["errors"] += 1
            return False

    async def clear_namespace(self) -> bool:
        """
        Clear all keys in the namespace

        Returns:
            True if successful, False otherwise
        """
        try:
            redis_client = await self._get_redis_client()

            # Scan for all keys in namespace
            pattern = self.cache_key.build_pattern()
            keys_to_delete = []

            async for key in redis_client.scan_iter(match=pattern):
                keys_to_delete.append(key)

                # Batch delete in chunks to avoid blocking
                if len(keys_to_delete) >= 100:
                    await redis_client.delete(*keys_to_delete)
                    keys_to_delete = []

            # Delete remaining keys
            if keys_to_delete:
                await redis_client.delete(*keys_to_delete)

            return True

        except Exception as e:
            logger.error(f"Cache clear namespace error for {self.namespace}: {e}")
            self._stats["errors"] += 1
            return False

    async def get_keys(self, pattern: str = "*") -> List[str]:
        """
        Get all keys matching pattern in namespace

        Args:
            pattern: Key pattern to match

        Returns:
            List of matching keys
        """
        try:
            redis_client = await self._get_redis_client()
            scan_pattern = self.cache_key.build_pattern(pattern)

            keys = []
            async for key in redis_client.scan_iter(match=scan_pattern):
                # Remove the namespace prefix for cleaner output
                clean_key = key.replace(f"cache:{self.namespace}:", "")
                keys.append(clean_key)

            return keys

        except Exception as e:
            logger.error(f"Cache get keys error for namespace {self.namespace}: {e}")
            self._stats["errors"] += 1
            return []

    async def exists(self, key: str, *args, **kwargs) -> bool:
        """
        Check if key exists in cache

        Args:
            key: Cache key
            *args, **kwargs: Additional parameters for key building

        Returns:
            True if key exists and is not expired, False otherwise
        """
        try:
            redis_client = await self._get_redis_client()
            cache_key = self.cache_key.build(key, *args, **kwargs)

            # Check if metadata exists (indicates key exists)
            exists = await redis_client.exists(f"{cache_key}:metadata")
            return bool(exists)

        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            self._stats["errors"] += 1
            return False

    async def get_ttl(self, key: str, *args, **kwargs) -> Optional[int]:
        """
        Get remaining TTL for key

        Args:
            key: Cache key
            *args, **kwargs: Additional parameters for key building

        Returns:
            Remaining TTL in seconds, or None if key doesn't exist
        """
        try:
            redis_client = await self._get_redis_client()
            cache_key = self.cache_key.build(key, *args, **kwargs)

            ttl = await redis_client.ttl(f"{cache_key}:value")
            return ttl if ttl > 0 else None

        except Exception as e:
            logger.error(f"Cache TTL error for key {key}: {e}")
            self._stats["errors"] += 1
            return None

    async def extend_ttl(self, key: str, new_ttl: int, *args, **kwargs) -> bool:
        """
        Extend TTL for existing key

        Args:
            key: Cache key
            new_ttl: New TTL in seconds
            *args, **kwargs: Additional parameters for key building

        Returns:
            True if successful, False otherwise
        """
        try:
            redis_client = await self._get_redis_client()
            cache_key = self.cache_key.build(key, *args, **kwargs)

            # Get current metadata
            metadata_data = await redis_client.get(f"{cache_key}:metadata")
            if not metadata_data:
                return False

            metadata = CacheMetadata.from_dict(json.loads(metadata_data))
            metadata.ttl = new_ttl

            # Update TTL for both value and metadata
            async with redis_client.pipeline() as pipe:
                await pipe.expire(f"{cache_key}:value", new_ttl)
                await pipe.expire(f"{cache_key}:metadata", new_ttl)
                await pipe.execute()

            return True

        except Exception as e:
            logger.error(f"Cache extend TTL error for key {key}: {e}")
            self._stats["errors"] += 1
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_operations = sum(self._stats.values())
        hit_rate = (
            (self._stats["hits"] / total_operations * 100)
            if total_operations > 0
            else 0
        )

        return {
            **self._stats,
            "total_operations": total_operations,
            "hit_rate_percent": round(hit_rate, 2),
            "namespace": self.namespace,
        }

    def reset_stats(self) -> None:
        """Reset cache statistics"""
        self._stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0, "errors": 0}

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on cache service"""
        try:
            redis_client = await self._get_redis_client()
            await redis_client.ping()

            return {
                "status": "healthy",
                "namespace": self.namespace,
                "redis_connected": True,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "namespace": self.namespace,
                "redis_connected": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    async def close(self) -> None:
        """Close Redis connection (only closes local reference)"""
        # Don't disconnect the shared client, just clear local reference
        self._redis_client = None


# Global Redis client instance - SINGLE INSTANCE FOR ALL CACHE SERVICES
_shared_redis_client: Optional[RedisClient] = None


async def get_shared_redis_client() -> RedisClient:
    """Get the shared Redis client instance for all cache services"""
    global _shared_redis_client

    if _shared_redis_client is None:
        _shared_redis_client = get_redis_client_instance()
        await _shared_redis_client.connect()

    return _shared_redis_client


# Factory function for creating cache services
async def create_cache_service(
    namespace: str, default_ttl: int = 3600
) -> RedisCacheService:
    """
    Factory function to create a Redis cache service

    Args:
        namespace: Cache namespace
        default_ttl: Default TTL in seconds

    Returns:
        Configured Redis cache service
    """
    cache_service = RedisCacheService(namespace, default_ttl)

    # Test connection using shared client
    health = await cache_service.health_check()
    if health["status"] != "healthy":
        logger.error(f"Cache service health check failed for namespace {namespace}")

    return cache_service


async def close_all_cache_services() -> None:
    """Close all cache services and the shared Redis connection"""
    global _shared_redis_client

    if _shared_redis_client:
        await _shared_redis_client.disconnect()
        _shared_redis_client = None
