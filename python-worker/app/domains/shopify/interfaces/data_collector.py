"""
Shopify data collector interface for BetterBundle Python Worker
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime


class IShopifyDataCollector(ABC):
    """Interface for Shopify data collection operations"""

    @abstractmethod
    async def collect_all_data(
        self,
        shop_domain: str,
        access_token: str = None,
        shop_id: str = None,
        include_products: bool = True,
        include_orders: bool = True,
        include_customers: bool = True,
        include_collections: bool = True,
    ) -> Dict[str, Any]:
        """
        Collect all available data from Shopify API

        Args:
            shop_domain: Shop domain to collect data from
            access_token: Shopify access token
            shop_id: Internal shop ID (optional, will be retrieved if not provided)
            include_products: Whether to collect products data
            include_orders: Whether to collect orders data
            include_customers: Whether to collect customers data
            include_collections: Whether to collect collections data

        Returns:
            Dictionary containing all collected data
        """
        pass
