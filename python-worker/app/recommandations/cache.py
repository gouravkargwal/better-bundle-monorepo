import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional, List


from app.core.logging import get_logger
from app.core.redis_client import get_redis_client

logger = get_logger(__name__)


class RecommendationCacheService:
    """Service to handle recommendation caching with context-specific TTL"""

    def __init__(self):
        self.redis_client = None

    async def get_redis_client(self):
        if self.redis_client is None:
            self.redis_client = await get_redis_client()
        return self.redis_client

    # Context-specific TTL configuration
    CACHE_TTL = {
        "product_page": 0,  # 30 minutes (product-specific)
        "homepage": 0,  # 1 hour (general)
        "cart": 0,  # 5 minutes (dynamic)
        "profile": 0,  # 15 minutes (user-specific)
        "checkout": 0,  # No cache (fast, fresh)
        "order_history": 0,  # Temporarily disable caching
        "order_status": 0,  # 15 minutes (order-specific)
    }

    def generate_cache_key(
        self,
        shop_id: str,
        context: str,
        product_ids: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 6,
        exclude_items: Optional[List[str]] = None,
    ) -> str:
        """
        Generate a unique cache key for recommendations

        Args:
            shop_id: Shop ID
            context: Recommendation context
            product_id: Product ID
            user_id: User ID
            session_id: Session ID
            category: Category filter
            limit: Number of recommendations

        Returns:
            Cache key string
        """
        # Create a deterministic key based on all parameters
        product_ids_str = ",".join(sorted(product_ids)) if product_ids else ""
        exclude_items_str = ",".join(sorted(exclude_items)) if exclude_items else ""
        key_parts = [
            "recommendations",
            shop_id,
            context,
            product_ids_str,
            str(user_id or ""),
            str(session_id or ""),
            str(category or ""),
            str(limit),
            exclude_items_str,  # Include cart contents in cache key
        ]

        # Join and hash to create a consistent key
        key_string = ":".join(key_parts)
        return f"rec:{hashlib.md5(key_string.encode()).hexdigest()}"

    async def get_cached_recommendations(
        self, cache_key: str, context: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached recommendations if available

        Args:
            cache_key: Cache key
            context: Recommendation context

        Returns:
            Cached recommendations or None
        """
        try:
            # Skip caching for checkout context
            if self.CACHE_TTL[context] == 0:
                return None

            redis_client = await self.get_redis_client()
            cached_data = await redis_client.get(cache_key)

            if cached_data:
                logger.debug(f"Recommendation cache hit for context {context}")
                return json.loads(
                    cached_data.decode("utf-8")
                    if isinstance(cached_data, bytes)
                    else cached_data
                )

            return None

        except Exception as e:
            logger.error(f"Failed to get cached recommendations: {str(e)}")
            return None

    async def cache_recommendations(
        self, cache_key: str, recommendations: Dict[str, Any], context: str
    ) -> None:
        """
        Cache recommendations with context-specific TTL

        Args:
            cache_key: Cache key
            recommendations: Recommendations data to cache
            context: Recommendation context
        """
        try:
            # Skip caching for checkout context
            if self.CACHE_TTL[context] == 0:
                return

            redis_client = await self.get_redis_client()
            ttl = self.CACHE_TTL[context]

            # Add metadata to cached data
            cached_data = {
                "recommendations": recommendations,
                "cached_at": datetime.now().isoformat(),
                "context": context,
                "ttl": ttl,
            }

            await redis_client.setex(cache_key, ttl, json.dumps(cached_data))
            logger.debug(
                f"Cached recommendations for context {context} with TTL {ttl}s"
            )

        except Exception as e:
            logger.error(f"Failed to cache recommendations: {str(e)}")
