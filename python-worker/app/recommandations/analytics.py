from typing import Optional, List
from datetime import datetime
import json
from app.core.logging import get_logger
from app.core.redis_client import get_redis_client

logger = get_logger(__name__)


class RecommendationAnalytics:
    """Service to track recommendation performance and analytics"""

    def __init__(self):
        self.redis_client = None

    async def get_redis_client(self):
        if self.redis_client is None:
            self.redis_client = await get_redis_client()
        return self.redis_client

    async def log_recommendation_request(
        self,
        shop_id: str,
        context: str,
        source: str,
        count: int,
        user_id: Optional[str] = None,
        product_ids: Optional[List[str]] = None,
        category: Optional[str] = None,
    ) -> None:
        """
        Log recommendation request for analytics

        Args:
            shop_id: Shop ID
            context: Recommendation context
            source: Recommendation source (gorse, cache, fallback, etc.)
            count: Number of recommendations returned
            user_id: User ID (if available)
            product_ids: Product IDs (if available)
            category: Category (if available)
        """
        try:
            redis_client = await self.get_redis_client()

            # Create analytics data
            analytics_data = {
                "timestamp": datetime.now().isoformat(),
                "shop_id": shop_id,
                "context": context,
                "source": source,
                "count": count,
                "user_id": user_id,
                "product_ids": product_ids,
                "category": category,
            }

            # Store in Redis with TTL (keep for 30 days)
            analytics_key = (
                f"analytics:recommendations:{datetime.now().strftime('%Y-%m-%d')}"
            )
            await redis_client.lpush(analytics_key, json.dumps(analytics_data))
            await redis_client.expire(analytics_key, 30 * 24 * 3600)  # 30 days

            logger.debug(
                f"Logged recommendation analytics: {context} -> {source} ({count} items)"
            )

        except Exception as e:
            logger.error(f"Failed to log recommendation analytics: {str(e)}")
