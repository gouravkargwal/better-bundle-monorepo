"""
Shopify API client interface for BetterBundle Python Worker
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime


class IShopifyAPIClient(ABC):
    """Interface for Shopify API client operations"""

    @abstractmethod
    async def execute_query(
        self,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
        shop_domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL query against Shopify API

        Args:
            query: GraphQL query string
            variables: Query variables
            shop_domain: Shop domain for the request

        Returns:
            API response data
        """
        pass

    @abstractmethod
    async def execute_mutation(
        self,
        mutation: str,
        variables: Optional[Dict[str, Any]] = None,
        shop_domain: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute a GraphQL mutation against Shopify API

        Args:
            mutation: GraphQL mutation string
            variables: Mutation variables
            shop_domain: Shop domain for the request

        Returns:
            API response data
        """
        pass

    @abstractmethod
    async def get_shop_info(self, shop_domain: str) -> Dict[str, Any]:
        """
        Get basic shop information

        Args:
            shop_domain: Shop domain

        Returns:
            Shop information
        """
        pass

    @abstractmethod
    async def get_products(
        self,
        shop_domain: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get products from shop

        Args:
            shop_domain: Shop domain
            limit: Maximum number of products
            cursor: Pagination cursor
            query: Search query

        Returns:
            Products data with pagination info
        """
        pass

    @abstractmethod
    async def get_orders(
        self,
        shop_domain: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
        created_at_min: Optional[datetime] = None,
        created_at_max: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get orders from shop

        Args:
            shop_domain: Shop domain
            limit: Maximum number of orders
            cursor: Pagination cursor
            status: Order status filter
            created_at_min: Minimum creation date
            created_at_max: Maximum creation date

        Returns:
            Orders data with pagination info
        """
        pass

    @abstractmethod
    async def get_customers(
        self,
        shop_domain: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get customers from shop

        Args:
            shop_domain: Shop domain
            limit: Maximum number of customers
            cursor: Pagination cursor
            query: Search query

        Returns:
            Customers data with pagination info
        """
        pass

    @abstractmethod
    async def get_collections(
        self,
        shop_domain: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get collections from shop

        Args:
            shop_domain: Shop domain
            limit: Maximum number of collections
            cursor: Pagination cursor

        Returns:
            Collections data with pagination info
        """
        pass

    @abstractmethod
    async def check_rate_limit(self, shop_domain: str) -> Dict[str, Any]:
        """
        Check current rate limit status

        Args:
            shop_domain: Shop domain

        Returns:
            Rate limit information
        """
        pass

    @abstractmethod
    async def wait_for_rate_limit(self, shop_domain: str) -> None:
        """
        Wait for rate limit to reset if needed

        Args:
            shop_domain: Shop domain
        """
        pass

    @abstractmethod
    async def validate_access_token(self, shop_domain: str) -> bool:
        """
        Validate access token for shop

        Args:
            shop_domain: Shop domain

        Returns:
            True if token is valid, False otherwise
        """
        pass

    @abstractmethod
    async def refresh_access_token(self, shop_domain: str) -> bool:
        """
        Refresh access token for shop

        Args:
            shop_domain: Shop domain

        Returns:
            True if refresh successful, False otherwise
        """
        pass

    @abstractmethod
    async def get_api_limits(self, shop_domain: str) -> Dict[str, Any]:
        """
        Get API usage limits and quotas

        Args:
            shop_domain: Shop domain

        Returns:
            API limits information
        """
        pass
