"""
Shopify data collector interface for BetterBundle Python Worker
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..models import (
    ShopifyShop,
    ShopifyProduct,
    ShopifyOrder,
    ShopifyCustomer,
    ShopifyCollection,
)


class IShopifyDataCollector(ABC):
    """Interface for Shopify data collection operations"""

    @abstractmethod
    async def collect_shop_data(self, shop_domain: str) -> Optional[ShopifyShop]:
        """
        Collect shop data from Shopify API

        Args:
            shop_domain: Shop domain to collect data from

        Returns:
            ShopifyShop instance or None if collection fails
        """
        pass

    @abstractmethod
    async def collect_products(
        self,
        shop_domain: str,
        limit: Optional[int] = None,
        since_id: Optional[str] = None,
    ) -> List[ShopifyProduct]:
        """
        Collect products data from Shopify API

        Args:
            shop_domain: Shop domain to collect data from
            limit: Maximum number of products to collect
            since_id: Collect products after this ID (for incremental updates)

        Returns:
            List of ShopifyProduct instances
        """
        pass

    @abstractmethod
    async def collect_orders(
        self,
        shop_domain: str,
        limit: Optional[int] = None,
        since_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[ShopifyOrder]:
        """
        Collect orders data from Shopify API

        Args:
            shop_domain: Shop domain to collect data from
            limit: Maximum number of orders to collect
            since_id: Collect orders after this ID (for incremental updates)
            status: Filter orders by status

        Returns:
            List of ShopifyOrder instances
        """
        pass

    @abstractmethod
    async def collect_customers(
        self,
        shop_domain: str,
        limit: Optional[int] = None,
        since_id: Optional[str] = None,
    ) -> List[ShopifyCustomer]:
        """
        Collect customers data from Shopify API

        Args:
            shop_domain: Shop domain to collect data from
            limit: Maximum number of customers to collect
            since_id: Collect customers after this ID (for incremental updates)

        Returns:
            List of ShopifyCustomer instances
        """
        pass

    @abstractmethod
    async def collect_collections(
        self,
        shop_domain: str,
        limit: Optional[int] = None,
        since_id: Optional[str] = None,
    ) -> List[ShopifyCollection]:
        """
        Collect collections data from Shopify API

        Args:
            shop_domain: Shop domain to collect data from
            limit: Maximum number of collections to collect
            since_id: Collect collections after this ID (for incremental updates)

        Returns:
            List of ShopifyCollection instances
        """
        pass

    @abstractmethod
    async def collect_all_data(
        self,
        shop_domain: str,
        include_products: bool = True,
        include_orders: bool = True,
        include_customers: bool = True,
        include_collections: bool = True,
    ) -> Dict[str, Any]:
        """
        Collect all available data from Shopify API

        Args:
            shop_domain: Shop domain to collect data from
            include_products: Whether to collect products data
            include_orders: Whether to collect orders data
            include_customers: Whether to collect customers data
            include_collections: Whether to collect collections data

        Returns:
            Dictionary containing all collected data
        """
        pass

    @abstractmethod
    async def check_permissions(self, shop_domain: str) -> Dict[str, bool]:
        """
        Check what data can be collected based on app permissions

        Args:
            shop_domain: Shop domain to check permissions for

        Returns:
            Dictionary mapping data types to permission status
        """
        pass

    @abstractmethod
    async def get_collection_status(self, shop_domain: str) -> Dict[str, Any]:
        """
        Get status of data collection for a shop

        Args:
            shop_domain: Shop domain to get status for

        Returns:
            Dictionary containing collection status information
        """
        pass

    @abstractmethod
    async def validate_shop_access(self, shop_domain: str) -> bool:
        """
        Validate that the app has access to the shop

        Args:
            shop_domain: Shop domain to validate access for

        Returns:
            True if access is valid, False otherwise
        """
        pass
