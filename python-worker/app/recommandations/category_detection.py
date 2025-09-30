from typing import Optional
from app.core.redis_client import get_redis_client
from app.core.database.session import get_transaction_context
from app.core.database.models.product_data import ProductData
from app.core.logging import get_logger
from sqlalchemy import select

logger = get_logger(__name__)


class CategoryDetectionService:
    """Service to auto-detect product categories with caching"""

    def __init__(self):
        self.redis_client = None

    async def get_redis_client(self):
        if self.redis_client is None:
            self.redis_client = await get_redis_client()
        return self.redis_client

    async def get_product_category(
        self, product_id: str, shop_id: str
    ) -> Optional[str]:
        """
        Get product category with Redis caching

        Args:
            product_id: Product ID
            shop_id: Shop ID

        Returns:
            Product category (productType or first collection) or None
        """
        try:
            # Create cache key
            cache_key = f"product_category:{shop_id}:{product_id}"

            # Check cache first
            redis_client = await self.get_redis_client()
            cached_category = await redis_client.get(cache_key)
            if cached_category:
                logger.debug(f"Category cache hit for product {product_id}")
                return (
                    cached_category.decode("utf-8")
                    if isinstance(cached_category, bytes)
                    else cached_category
                )

            # Query database
            async with get_transaction_context() as session:
                product_result = await session.execute(
                    select(ProductData).where(
                        ProductData.shop_id == shop_id,
                        ProductData.product_id == product_id,
                    )
                )
                product = product_result.scalar_one_or_none()

            category = None
            if product:
                # Prioritize product_type over collections
                if product.product_type:
                    category = product.product_type
                elif product.collections and len(product.collections) > 0:
                    # Use first collection as category
                    category = (
                        product.collections[0].get("title")
                        if isinstance(product.collections[0], dict)
                        else str(product.collections[0])
                    )

            # Cache for 1 hour (3600 seconds)
            if category:
                await redis_client.setex(cache_key, 3600, category)
                logger.debug(f"Cached category '{category}' for product {product_id}")

            return category

        except Exception as e:
            logger.error(f"Failed to get product category: {str(e)}")
            return None
