from typing import Optional
from app.core.redis_client import get_redis_client
from app.core.database.simple_db_client import get_database
from app.core.logging import get_logger

logger = get_logger(__name__)


class CategoryDetectionService:
    """Service to auto-detect product categories with caching"""

    def __init__(self):
        self.db = None
        self.redis_client = None

    async def get_database(self):
        if self.db is None:
            self.db = await get_database()
        return self.db

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
            db = await self.get_database()
            product = await db.productdata.find_first(
                where={"shopId": shop_id, "productId": product_id}
            )

            category = None
            if product:
                # Prioritize productType over collections
                if hasattr(product, "productType") and product.productType:
                    category = product.productType
                elif (
                    hasattr(product, "collections")
                    and product.collections
                    and len(product.collections) > 0
                ):
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
