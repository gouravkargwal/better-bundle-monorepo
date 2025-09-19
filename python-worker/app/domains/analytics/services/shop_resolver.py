"""
Shop Resolver Service - Handles shop domain to ID resolution with caching
"""

from typing import Optional, Dict
from datetime import datetime, timedelta
import asyncio

from app.core.database import get_database
from app.core.logging.logger import get_logger

logger = get_logger(__name__)


class ShopResolverService:
    """Service for resolving shop domains to shop IDs with caching"""

    def __init__(self):
        self._cache: Dict[str, dict] = {}
        self._cache_ttl = timedelta(hours=1)  # Cache for 1 hour
        self._lock = asyncio.Lock()

    async def get_shop_id_from_domain(self, shop_domain: str) -> Optional[str]:
        """
        Get shop ID from domain with caching

        Args:
            shop_domain: Shop domain (e.g., 'mystore.myshopify.com')

        Returns:
            str: Shop ID if found, None otherwise
        """
        # Normalize domain (remove protocol, trailing slashes, etc.)
        normalized_domain = self._normalize_domain(shop_domain)

        # Check cache first
        async with self._lock:
            if normalized_domain in self._cache:
                cache_entry = self._cache[normalized_domain]
                if datetime.utcnow() < cache_entry["expires_at"]:
                    logger.debug(f"Cache hit for domain: {normalized_domain}")
                    return cache_entry["shop_id"]
                else:
                    # Cache expired, remove it
                    del self._cache[normalized_domain]

        # Cache miss or expired, fetch from database
        shop_id = await self._fetch_shop_id_from_db(normalized_domain)

        if shop_id:
            # Cache the result
            async with self._lock:
                self._cache[normalized_domain] = {
                    "shop_id": shop_id,
                    "expires_at": datetime.utcnow() + self._cache_ttl,
                }
            logger.debug(f"Cached shop ID for domain: {normalized_domain}")

        return shop_id

    async def get_shop_details_from_domain(self, shop_domain: str) -> Optional[dict]:
        """
        Get complete shop details from domain with caching

        Returns:
            dict: Shop details if found, None otherwise
        """
        normalized_domain = self._normalize_domain(shop_domain)

        # Check cache for full details
        cache_key = f"{normalized_domain}:details"
        async with self._lock:
            if cache_key in self._cache:
                cache_entry = self._cache[cache_key]
                if datetime.utcnow() < cache_entry["expires_at"]:
                    return cache_entry["data"]
                else:
                    del self._cache[cache_key]

        # Fetch from database
        shop_details = await self._fetch_shop_details_from_db(normalized_domain)

        if shop_details:
            # Cache the result
            async with self._lock:
                self._cache[cache_key] = {
                    "data": shop_details,
                    "expires_at": datetime.utcnow() + self._cache_ttl,
                }

        return shop_details

    async def get_shop_id_from_customer_id(self, customer_id: str) -> Optional[str]:
        """
        Get shop ID from customer ID with caching

        Args:
            customer_id: Customer ID

        Returns:
            str: Shop ID if found, None otherwise
        """
        # Check cache first
        cache_key = f"customer:{customer_id}"
        async with self._lock:
            if cache_key in self._cache:
                cache_entry = self._cache[cache_key]
                if datetime.utcnow() < cache_entry["expires_at"]:
                    logger.debug(f"Cache hit for customer_id: {customer_id}")
                    return cache_entry["shop_id"]
                else:
                    # Cache expired, remove it
                    del self._cache[cache_key]

        # Cache miss or expired, fetch from database
        shop_id = await self._fetch_shop_id_from_customer_id_db(customer_id)

        if shop_id:
            # Cache the result
            async with self._lock:
                self._cache[cache_key] = {
                    "shop_id": shop_id,
                    "expires_at": datetime.utcnow() + self._cache_ttl,
                }
            logger.debug(f"Cached shop ID for customer_id: {customer_id}")

        return shop_id

    async def _fetch_shop_id_from_customer_id_db(
        self, customer_id: str
    ) -> Optional[str]:
        """Fetch shop ID from database using customer ID"""
        try:
            db = await get_database()

            customer = await db.customerdata.find_first(
                where={"customerId": customer_id}
            )

            if customer and customer.shopId:
                logger.info(
                    f"Found shop_id from customer_id via customerdata: {customer_id} -> {customer.shopId}"
                )
                return customer.shopId
            else:
                logger.warning(f"Could not find shop_id for customer_id: {customer_id}")
                return None

        except Exception as e:
            logger.error(f"Error resolving shop_id from customer_id {customer_id}: {e}")
            return None

    async def invalidate_cache(self, shop_domain: str) -> None:
        """Invalidate cache for a specific domain"""
        normalized_domain = self._normalize_domain(shop_domain)
        async with self._lock:
            keys_to_remove = [
                key for key in self._cache.keys() if key.startswith(normalized_domain)
            ]
            for key in keys_to_remove:
                del self._cache[key]
        logger.info(f"Cache invalidated for domain: {normalized_domain}")

    async def clear_expired_cache(self) -> None:
        """Clear expired cache entries (call periodically)"""
        now = datetime.utcnow()
        async with self._lock:
            expired_keys = [
                key for key, value in self._cache.items() if now >= value["expires_at"]
            ]
            for key in expired_keys:
                del self._cache[key]

        if expired_keys:
            logger.info(f"Cleared {len(expired_keys)} expired cache entries")

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
            db = await get_database()

            shop = await db.shop.find_unique(
                where={
                    "shopDomain": normalized_domain,
                },
            )

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
            db = await get_database()

            shop = await db.shop.find_unique(
                where={
                    "shopDomain": normalized_domain,
                }
            )

            if shop:
                return {
                    "id": shop.id,
                    "shopDomain": shop.shopDomain,
                    "customDomain": shop.customDomain,
                    "accessToken": shop.accessToken,
                    "planType": shop.planType,
                    "isActive": shop.isActive,
                    "createdAt": shop.createdAt,
                    "updatedAt": shop.updatedAt,
                }

            return None

        except Exception as e:
            logger.error(
                f"Error fetching shop details for domain {normalized_domain}: {str(e)}"
            )
            return None


# Global instance
shop_resolver = ShopResolverService()
