"""
Main Shopify API client that uses specialized clients
"""

from typing import Dict, Any, Optional, List
from app.core.logging import get_logger

from .api import (
    BaseShopifyAPIClient,
    ProductAPIClient,
    CollectionAPIClient,
    OrderAPIClient,
    CustomerAPIClient,
)
from ..interfaces.api_client import IShopifyAPIClient

logger = get_logger(__name__)


class ShopifyAPIClient(IShopifyAPIClient):
    """Main Shopify API client that delegates to specialized clients"""

    def __init__(self):
        # Initialize specialized clients
        self.product_client = ProductAPIClient()
        self.collection_client = CollectionAPIClient()
        self.order_client = OrderAPIClient()
        self.customer_client = CustomerAPIClient()

        # Access tokens cache (shared across all clients)
        self.access_tokens: Dict[str, str] = {}

    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def connect(self):
        """Initialize all clients"""
        await self.product_client.connect()
        await self.collection_client.connect()
        await self.order_client.connect()
        await self.customer_client.connect()

    async def close(self):
        """Close all clients"""
        await self.product_client.close()
        await self.collection_client.close()
        await self.order_client.close()
        await self.customer_client.close()

    async def set_access_token(self, shop_domain: str, access_token: str):
        """Set access token for all clients"""
        self.access_tokens[shop_domain] = access_token
        await self.product_client.set_access_token(shop_domain, access_token)
        await self.collection_client.set_access_token(shop_domain, access_token)
        await self.order_client.set_access_token(shop_domain, access_token)
        await self.customer_client.set_access_token(shop_domain, access_token)

    # Delegate to specialized clients
    async def get_shop_info(self, shop_domain: str) -> Dict[str, Any]:
        """Get shop information"""
        return await self.product_client.get_shop_info(shop_domain)

    async def get_products(
        self,
        shop_domain: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        query: Optional[str] = None,
        product_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get products from shop - supports both pagination and specific IDs"""
        return await self.product_client.get_products(
            shop_domain, limit, cursor, query, product_ids
        )

    async def get_collections(
        self,
        shop_domain: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        query: Optional[str] = None,
        collection_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get collections from shop - supports both pagination and specific IDs"""
        return await self.collection_client.get_collections(
            shop_domain, limit, cursor, query, collection_ids
        )

    async def get_orders(
        self,
        shop_domain: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        query: Optional[str] = None,
        order_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get orders from shop - supports both pagination and specific IDs"""
        return await self.order_client.get_orders(
            shop_domain, limit, cursor, query, order_ids
        )

    async def get_customers(
        self,
        shop_domain: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        query: Optional[str] = None,
        customer_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get customers from shop - supports both pagination and specific IDs"""
        return await self.customer_client.get_customers(
            shop_domain, limit, cursor, query, customer_ids
        )

    # Legacy methods for backward compatibility
    async def get_app_installation_scopes(self, shop_domain: str) -> List[str]:
        """Get app installation scopes"""
        # This would need to be implemented in base client
        logger.warning("get_app_installation_scopes not implemented in new client")
        return []

    async def get_api_limits(self, shop_domain: str) -> Dict[str, Any]:
        """Get API limits"""
        # This would need to be implemented in base client
        logger.warning("get_api_limits not implemented in new client")
        return {}
