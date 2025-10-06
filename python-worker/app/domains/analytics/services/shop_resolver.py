"""
Shop Resolver Service - Resolves shop domain/customer to shop_id using Redis cache
"""

from typing import Optional

from app.core.database import get_database
from app.core.logging.logger import get_logger
from app.services.shop_cache_service import get_shop_cache_service

logger = get_logger(__name__)


class ShopResolverService:
    """Service for resolving shop info using Redis-backed cache only"""

    async def get_shop_id_from_domain(self, shop_domain: str) -> Optional[str]:
        """
        Get shop ID from domain using Redis-backed ShopCacheService.

        Args:
            shop_domain: Shop domain (e.g., 'mystore.myshopify.com')

        Returns:
            str: Shop ID if found, None otherwise
        """
        normalized_domain = self._normalize_domain(shop_domain)

        # Use Redis-backed cache service exclusively
        cache_service = await get_shop_cache_service()
        shop = await cache_service.get_active_shop_by_domain(normalized_domain)
        if shop and shop.get("id"):
            return shop["id"]

        # Fallback to DB only if cache layer returns None and no negative cache present
        # (ShopCacheService already caches negative results.)
        return await self._fetch_shop_id_from_db(normalized_domain)

    async def get_shop_details_from_domain(self, shop_domain: str) -> Optional[dict]:
        """
        Get complete shop details from domain using Redis-backed ShopCacheService.

        Returns:
            dict: Shop details if found, None otherwise
        """
        normalized_domain = self._normalize_domain(shop_domain)

        cache_service = await get_shop_cache_service()
        shop = await cache_service.get_active_shop_by_domain(normalized_domain)
        if shop:
            return shop

        # Fallback to database (and let cache service negative-cache future lookups)
        return await self._fetch_shop_details_from_db(normalized_domain)

    async def get_shop_id_from_customer_id(self, customer_id: str) -> Optional[str]:
        """
        Get shop ID from customer ID without any in-memory caching.

        Args:
            customer_id: Customer ID

        Returns:
            str: Shop ID if found, None otherwise
        """
        return await self._fetch_shop_id_from_customer_id_db(customer_id)

    async def _fetch_shop_id_from_customer_id_db(
        self, customer_id: str
    ) -> Optional[str]:
        """Fetch shop ID from database using customer ID"""
        try:
            from app.core.database.session import get_transaction_context
            from app.core.database.models.customer_data import CustomerData
            from sqlalchemy import select

            async with get_transaction_context() as session:
                # Query customer data using SQLAlchemy
                result = await session.execute(
                    select(CustomerData).where(CustomerData.customer_id == customer_id)
                )
                customer = result.scalar_one_or_none()

                if customer and customer.shop_id:

                    return customer.shop_id
                else:
                    logger.warning(
                        f"Could not find shop_id for customer_id: {customer_id}"
                    )
                    return None

        except Exception as e:
            logger.error(f"Error resolving shop_id from customer_id {customer_id}: {e}")
            return None

    async def invalidate_cache(self, shop_domain: str) -> None:
        """Invalidate Redis cache for a specific domain"""
        cache_service = await get_shop_cache_service()
        await cache_service.invalidate_shop_cache(self._normalize_domain(shop_domain))

    def _normalize_domain(self, domain: str) -> str:
        """Normalize domain for consistent caching"""
        # Remove protocol
        if domain.startswith(("http://", "https://")):
            domain = domain.split("://", 1)[1]

        # Remove trailing slash
        domain = domain.rstrip("/")

        # Convert to lowercase
        return domain.lower()

    async def _fetch_shop_id_from_db(self, normalized_domain: str) -> Optional[str]:
        """Fetch shop ID from database"""
        try:
            from app.core.database.session import get_transaction_context
            from app.core.database.models.shop import Shop
            from sqlalchemy import select

            async with get_transaction_context() as session:
                result = await session.execute(
                    select(Shop).where(Shop.shop_domain == normalized_domain)
                )
                shop = result.scalar_one_or_none()

                return shop.id if shop else None

        except Exception as e:
            logger.error(
                f"Error fetching shop ID for domain {normalized_domain}: {str(e)}"
            )
            return None

    async def _fetch_shop_details_from_db(
        self, normalized_domain: str
    ) -> Optional[dict]:
        """Fetch complete shop details from database"""
        try:
            from app.core.database.session import get_transaction_context
            from app.core.database.models.shop import Shop
            from sqlalchemy import select

            async with get_transaction_context() as session:
                result = await session.execute(
                    select(Shop).where(Shop.shop_domain == normalized_domain)
                )
                shop = result.scalar_one_or_none()

                if shop:
                    return {
                        "id": shop.id,
                        "shopDomain": shop.shop_domain,
                        "customDomain": shop.custom_domain,
                        "accessToken": shop.access_token,
                        "planType": shop.plan_type,
                        "isActive": shop.is_active,
                        "createdAt": shop.created_at,
                        "updatedAt": shop.updated_at,
                    }

                return None

        except Exception as e:
            logger.error(
                f"Error fetching shop details for domain {normalized_domain}: {str(e)}"
            )
            return None


# Global instance
shop_resolver = ShopResolverService()
