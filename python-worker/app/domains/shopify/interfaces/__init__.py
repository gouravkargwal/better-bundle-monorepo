"""
Shopify domain interfaces for BetterBundle Python Worker
"""

from .data_collector import IShopifyDataCollector
from .api_client import IShopifyAPIClient
from .permission_service import IShopifyPermissionService

__all__ = [
    "IShopifyDataCollector",
    "IShopifyAPIClient", 
    "IShopifyPermissionService",
]
