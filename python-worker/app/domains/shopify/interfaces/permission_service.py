"""
Shopify permission service interface for BetterBundle Python Worker
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class IShopifyPermissionService(ABC):
    """Interface for Shopify permission and access management"""
    
    @abstractmethod
    async def check_shop_permissions(self, shop_domain: str) -> Dict[str, bool]:
        """
        Check what permissions the app has for a shop
        
        Args:
            shop_domain: Shop domain to check permissions for
            
        Returns:
            Dictionary mapping permission types to availability
        """
        pass
    
    @abstractmethod
    async def check_products_access(self, shop_domain: str) -> Dict[str, Any]:
        """
        Check access to products data
        
        Args:
            shop_domain: Shop domain
            
        Returns:
            Products access information including permissions and limits
        """
        pass
    
    @abstractmethod
    async def check_orders_access(self, shop_domain: str) -> Dict[str, Any]:
        """
        Check access to orders data
        
        Args:
            shop_domain: Shop domain
            
        Returns:
            Orders access information including permissions and limits
        """
        pass
    
    @abstractmethod
    async def check_customers_access(self, shop_domain: str) -> Dict[str, Any]:
        """
        Check access to customers data
        
        Args:
            shop_domain: Shop domain
            
        Returns:
            Customers access information including permissions and limits
        """
        pass
    
    @abstractmethod
    async def check_collections_access(self, shop_domain: str) -> Dict[str, Any]:
        """
        Check access to collections data
        
        Args:
            shop_domain: Shop domain
            
        Returns:
            Collections access information including permissions and limits
        """
        pass
    
    @abstractmethod
    async def check_customer_events_access(self, shop_domain: str) -> Dict[str, Any]:
        """
        Check access to customer events data
        
        Args:
            shop_domain: Shop domain
            
        Returns:
            Customer events access information including permissions and limits
        """
        pass
    
    @abstractmethod
    async def get_required_scopes(self) -> List[str]:
        """
        Get list of required Shopify scopes for the app
        
        Returns:
            List of required scope strings
        """
        pass
    
    @abstractmethod
    async def get_missing_scopes(self, shop_domain: str) -> List[str]:
        """
        Get list of missing scopes for a shop
        
        Args:
            shop_domain: Shop domain
            
        Returns:
            List of missing scope strings
        """
        pass
    
    @abstractmethod
    async def validate_scope_coverage(self, shop_domain: str) -> Dict[str, Any]:
        """
        Validate that app has sufficient scope coverage for data collection
        
        Args:
            shop_domain: Shop domain
            
        Returns:
            Scope validation results
        """
        pass
    
    @abstractmethod
    async def can_collect_products(self, shop_domain: str) -> bool:
        """
        Check if app can collect products data
        
        Args:
            shop_domain: Shop domain
            
        Returns:
            True if products can be collected
        """
        pass
    
    @abstractmethod
    async def can_collect_orders(self, shop_domain: str) -> bool:
        """
        Check if app can collect orders data
        
        Args:
            shop_domain: Shop domain
            
        Returns:
            True if orders can be collected
        """
        pass
    
    @abstractmethod
    async def can_collect_customers(self, shop_domain: str) -> bool:
        """
        Check if app can collect customers data
        
        Args:
            shop_domain: Shop domain
            
        Returns:
            True if customers can be collected
        """
        pass
    
    @abstractmethod
    async def can_collect_collections(self, shop_domain: str) -> bool:
        """
        Check if app can collect collections data
        
        Args:
            shop_domain: Shop domain
            
        Returns:
            True if collections can be collected
        """
        pass
    
    @abstractmethod
    async def can_collect_customer_events(self, shop_domain: str) -> bool:
        """
        Check if app can collect customer events data
        
        Args:
            shop_domain: Shop domain
            
        Returns:
            True if customer events can be collected
        """
        pass
    
    @abstractmethod
    async def get_collection_strategy(self, shop_domain: str) -> Dict[str, Any]:
        """
        Get optimal data collection strategy based on available permissions
        
        Args:
            shop_domain: Shop domain
            
        Returns:
            Collection strategy including what data to collect and how
        """
        pass
    
    @abstractmethod
    async def log_permission_check(self, shop_domain: str, permissions: Dict[str, bool]) -> None:
        """
        Log permission check results for monitoring
        
        Args:
            shop_domain: Shop domain
            permissions: Permission check results
        """
        pass
