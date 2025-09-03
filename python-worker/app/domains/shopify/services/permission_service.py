"""
Shopify permission service implementation for BetterBundle Python Worker
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import time

from app.core.logging import get_logger
from app.core.exceptions import ConfigurationError
from app.shared.decorators import async_timing
from app.shared.helpers import now_utc

from ..interfaces.permission_service import IShopifyPermissionService
from ..interfaces.api_client import IShopifyAPIClient

logger = get_logger(__name__)


class ShopifyPermissionService(IShopifyPermissionService):
    """Shopify permission service for checking app access and data collection capabilities"""

    def __init__(self, api_client: IShopifyAPIClient):
        self.api_client = api_client

        # Required scopes for full functionality
        self.required_scopes = [
            "read_products",
            "read_orders",
            "read_customers",
            "read_collections",
            "read_marketing_events",
        ]

        # Scope to data type mapping
        self.scope_data_mapping = {
            "read_products": ["products", "variants", "images"],
            "read_orders": ["orders", "line_items", "financials"],
            "read_customers": ["customers", "customer_addresses"],
            "read_collections": ["collections", "collection_products"],
            "read_marketing_events": ["customer_events", "marketing_events"],
        }

        # Permission cache
        self.permission_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 3600  # 1 hour

    async def check_shop_permissions(
        self, shop_domain: str, access_token: str = None
    ) -> Dict[str, bool]:
        """Check what permissions the app has for a shop"""
        logger.info(f"Starting permission check for shop: {shop_domain}")
        logger.debug(f"Access token provided: {'Yes' if access_token else 'No'}")

        # Check cache first
        cached = self._get_cached_permissions(shop_domain)
        if cached:
            logger.info(f"Using cached permissions for {shop_domain}")
            logger.debug(f"Cached permissions: {cached}")
            return cached

        logger.info(f"Checking permissions for shop: {shop_domain}")
        logger.debug(f"No cache hit, proceeding with API calls")

        permissions = {}

        # Check each data type access
        logger.debug(f"Testing products access for {shop_domain}")
        permissions["products"] = await self.can_collect_products(
            shop_domain, access_token
        )
        logger.debug(f"Products access result: {permissions['products']}")

        logger.debug(f"Testing orders access for {shop_domain}")
        permissions["orders"] = await self.can_collect_orders(shop_domain, access_token)
        logger.debug(f"Orders access result: {permissions['orders']}")

        logger.debug(f"Testing customers access for {shop_domain}")
        permissions["customers"] = await self.can_collect_customers(
            shop_domain, access_token
        )
        logger.debug(f"Customers access result: {permissions['customers']}")

        logger.debug(f"Testing collections access for {shop_domain}")
        permissions["collections"] = await self.can_collect_collections(
            shop_domain, access_token
        )
        logger.debug(f"Collections access result: {permissions['collections']}")

        logger.debug(f"Testing customer events access for {shop_domain}")
        permissions["customer_events"] = await self.can_collect_customer_events(
            shop_domain, access_token
        )
        logger.debug(f"Customer events access result: {permissions['customer_events']}")

        # Check overall access
        permissions["has_access"] = any(
            [
                permissions["products"],
                permissions["orders"],
                permissions["customers"],
                permissions["collections"],
                permissions["customer_events"],
            ]
        )
        logger.debug(f"Overall access result: {permissions['has_access']}")

        # Cache the results
        logger.debug(f"Caching permission results for {shop_domain}")
        self._cache_permissions(shop_domain, permissions)

        # Log the results
        await self.log_permission_check(shop_domain, permissions)

        return permissions

    async def check_products_access(self, shop_domain: str) -> Dict[str, Any]:
        """Check access to products data"""
        can_access = await self.can_collect_products(shop_domain)

        return {
            "can_access": can_access,
            "scope_required": "read_products",
            "data_types": self.scope_data_mapping.get("read_products", []),
            "tested_at": now_utc().isoformat(),
            "access_method": "graphql" if can_access else "none",
        }

    async def check_orders_access(self, shop_domain: str) -> Dict[str, Any]:
        """Check access to orders data"""
        can_access = await self.can_collect_orders(shop_domain)

        return {
            "can_access": can_access,
            "scope_required": "read_orders",
            "data_types": self.scope_data_mapping.get("read_orders", []),
            "tested_at": now_utc().isoformat(),
            "access_method": "graphql" if can_access else "none",
        }

    async def check_customers_access(self, shop_domain: str) -> Dict[str, Any]:
        """Check access to customers data"""
        can_access = await self.can_collect_customers(shop_domain)

        return {
            "can_access": can_access,
            "scope_required": "read_customers",
            "data_types": self.scope_data_mapping.get("read_customers", []),
            "tested_at": now_utc().isoformat(),
            "access_method": "graphql" if can_access else "none",
        }

    async def check_collections_access(self, shop_domain: str) -> Dict[str, Any]:
        """Check access to collections data"""
        can_access = await self.can_collect_collections(shop_domain)

        return {
            "can_access": can_access,
            "scope_required": "read_collections",
            "data_types": self.scope_data_mapping.get("read_collections", []),
            "tested_at": now_utc().isoformat(),
            "access_method": "graphql" if can_access else "none",
        }

    async def check_customer_events_access(self, shop_domain: str) -> Dict[str, Any]:
        """Check access to customer events data"""
        can_access = await self.can_collect_customer_events(shop_domain)

        return {
            "can_access": can_access,
            "scope_required": "read_marketing_events",
            "data_types": self.scope_data_mapping.get("read_marketing_events", []),
            "tested_at": now_utc().isoformat(),
            "access_method": "graphql" if can_access else "none",
        }

    def get_required_scopes(self) -> List[str]:
        """Get list of required Shopify scopes for the app"""
        return self.required_scopes.copy()

    async def get_missing_scopes(
        self, shop_domain: str, access_token: str = None
    ) -> List[str]:
        """Get list of missing scopes for a shop"""
        permissions = await self.check_shop_permissions(shop_domain, access_token)
        missing_scopes = []

        if not permissions.get("products"):
            missing_scopes.append("read_products")
        if not permissions.get("orders"):
            missing_scopes.append("read_orders")
        if not permissions.get("customers"):
            missing_scopes.append("read_customers")
        if not permissions.get("collections"):
            missing_scopes.append("read_collections")
        if not permissions.get("customer_events"):
            missing_scopes.append("read_marketing_events")

        return missing_scopes

    async def validate_scope_coverage(self, shop_domain: str) -> Dict[str, Any]:
        """Validate that app has sufficient scope coverage for data collection"""
        permissions = await self.check_shop_permissions(shop_domain)
        missing_scopes = await self.get_missing_scopes(shop_domain)

        # Calculate coverage percentage
        total_scopes = len(self.required_scopes)
        available_scopes = total_scopes - len(missing_scopes)
        coverage_percentage = (
            (available_scopes / total_scopes) * 100 if total_scopes > 0 else 0
        )

        # Determine coverage level
        if coverage_percentage >= 80:
            coverage_level = "excellent"
        elif coverage_percentage >= 60:
            coverage_level = "good"
        elif coverage_percentage >= 40:
            coverage_level = "fair"
        elif coverage_percentage >= 20:
            coverage_level = "poor"
        else:
            coverage_level = "minimal"

        return {
            "shop_domain": shop_domain,
            "total_scopes": total_scopes,
            "available_scopes": available_scopes,
            "missing_scopes": missing_scopes,
            "coverage_percentage": coverage_percentage,
            "coverage_level": coverage_level,
            "can_collect_data": permissions.get("has_access", False),
            "recommendations": self._get_scope_recommendations(missing_scopes),
            "validated_at": now_utc().isoformat(),
        }

    async def can_collect_products(
        self, shop_domain: str, access_token: str = None
    ) -> bool:
        """Check if app can collect products data"""
        try:
            # Try to get a single product as a test
            result = await self.api_client.get_products(
                shop_domain, access_token=access_token, limit=1
            )
            return "edges" in result and len(result["edges"]) >= 0
        except Exception as e:
            logger.debug(
                f"Products access test failed", shop_domain=shop_domain, error=str(e)
            )
            return False

    async def can_collect_orders(
        self, shop_domain: str, access_token: str = None
    ) -> bool:
        """Check if app can collect orders data"""
        try:
            # Try to get a single order as a test
            result = await self.api_client.get_orders(
                shop_domain, access_token=access_token, limit=1
            )
            return "edges" in result and len(result["edges"]) >= 0
        except Exception as e:
            logger.debug(
                f"Orders access test failed", shop_domain=shop_domain, error=str(e)
            )
            return False

    async def can_collect_customers(
        self, shop_domain: str, access_token: str = None
    ) -> bool:
        """Check if app can collect customers data"""
        try:
            # Try to get a single customer as a test
            result = await self.api_client.get_customers(
                shop_domain, access_token=access_token, limit=1
            )
            return "edges" in result and len(result["edges"]) >= 0
        except Exception as e:
            logger.debug(
                f"Customers access test failed", shop_domain=shop_domain, error=str(e)
            )
            return False

    async def can_collect_collections(
        self, shop_domain: str, access_token: str = None
    ) -> bool:
        """Check if app can collect collections data"""
        try:
            # Try to get a single collection as a test
            result = await self.api_client.get_collections(
                shop_domain, access_token=access_token, limit=1
            )
            return "edges" in result and len(result["edges"]) >= 0
        except Exception as e:
            logger.debug(
                f"Collections access test failed", shop_domain=shop_domain, error=str(e)
            )
            return False

    async def can_collect_customer_events(
        self, shop_domain: str, access_token: str = None
    ) -> bool:
        """Check if app can collect customer events data"""
        try:
            # Try to get a single customer event as a test
            result = await self.api_client.get_customer_events(
                shop_domain, access_token=access_token, limit=1
            )
            return "edges" in result and len(result["edges"]) >= 0
        except Exception as e:
            logger.debug(
                f"Customer events access test failed",
                shop_domain=shop_domain,
                error=str(e),
            )
            return False

    async def get_collection_strategy(
        self, shop_domain: str, access_token: str = None
    ) -> Dict[str, Any]:
        """Get optimal data collection strategy based on available permissions"""
        permissions = await self.check_shop_permissions(shop_domain, access_token)
        missing_scopes = await self.get_missing_scopes(shop_domain, access_token)

        # Determine what data to collect
        collectable_data = []
        if permissions.get("products"):
            collectable_data.append("products")
        if permissions.get("orders"):
            collectable_data.append("orders")
        if permissions.get("customers"):
            collectable_data.append("customers")
        if permissions.get("collections"):
            collectable_data.append("collections")
        if permissions.get("customer_events"):
            collectable_data.append("customer_events")

        # Determine collection priority
        collection_priority = self._get_collection_priority(collectable_data)

        # Determine collection method
        collection_method = "full" if len(collectable_data) >= 3 else "partial"

        return {
            "shop_domain": shop_domain,
            "collectable_data": collectable_data,
            "collection_priority": collection_priority,
            "collection_method": collection_method,
            "missing_scopes": missing_scopes,
            "estimated_collection_time": self._estimate_collection_time(
                collectable_data
            ),
            "recommendations": self._get_collection_recommendations(
                collectable_data, missing_scopes
            ),
            "strategy_generated_at": now_utc().isoformat(),
        }

    async def log_permission_check(
        self, shop_domain: str, permissions: Dict[str, bool]
    ) -> None:
        """Log permission check results for monitoring"""
        missing_scopes = await self.get_missing_scopes(shop_domain)

        log_data = {
            "shop_domain": shop_domain,
            "permissions": permissions,
            "missing_scopes": missing_scopes,
            "total_scopes": len(self.required_scopes),
            "available_scopes": len(self.required_scopes) - len(missing_scopes),
            "coverage_percentage": (
                (len(self.required_scopes) - len(missing_scopes))
                / len(self.required_scopes)
            )
            * 100,
        }

        if missing_scopes:
            logger.warning(
                f"Permission check completed with missing scopes", **log_data
            )
        else:
            logger.info(
                f"Permission check completed - all scopes available", **log_data
            )

    def _get_cached_permissions(self, shop_domain: str) -> Optional[Dict[str, bool]]:
        """Get cached permissions if still valid"""
        logger.debug(f"Checking cache for {shop_domain}")
        logger.debug(f"Current cache keys: {list(self.permission_cache.keys())}")

        if shop_domain not in self.permission_cache:
            logger.debug(f"No cache entry found for {shop_domain}")
            return None

        cache_entry = self.permission_cache[shop_domain]
        cache_time = cache_entry.get("cached_at", 0)
        current_time = time.time()

        logger.debug(
            f"Cache entry found for {shop_domain}, cached_at: {cache_time}, current_time: {current_time}, ttl: {self.cache_ttl}"
        )

        if current_time - cache_time > self.cache_ttl:
            # Cache expired, remove it
            logger.debug(f"Cache expired for {shop_domain}, removing")
            del self.permission_cache[shop_domain]
            return None

        logger.debug(
            f"Using cached permissions for {shop_domain}: {cache_entry.get('permissions')}"
        )
        return cache_entry.get("permissions")

    def _cache_permissions(self, shop_domain: str, permissions: Dict[str, bool]):
        """Cache permission results"""
        logger.debug(f"Caching permissions for {shop_domain}: {permissions}")
        self.permission_cache[shop_domain] = {
            "permissions": permissions,
            "cached_at": time.time(),
        }
        logger.debug(f"Cache after storing: {list(self.permission_cache.keys())}")

    def clear_permission_cache(self, shop_domain: Optional[str] = None):
        """Clear permission cache for a specific shop or all shops"""
        logger.debug(f"Clearing permission cache for: {shop_domain if shop_domain else 'all shops'}")
        logger.debug(f"Cache before clearing: {list(self.permission_cache.keys())}")
        
        if shop_domain:
            if shop_domain in self.permission_cache:
                del self.permission_cache[shop_domain]
                logger.info(f"Cleared permission cache for {shop_domain}")
            else:
                logger.debug(f"No cache entry found for {shop_domain}")
        else:
            self.permission_cache.clear()
            logger.info("Cleared all permission cache")
        
        logger.debug(f"Cache after clearing: {list(self.permission_cache.keys())}")

    def _get_scope_recommendations(self, missing_scopes: List[str]) -> List[str]:
        """Get recommendations for missing scopes"""
        recommendations = []

        if "read_products" in missing_scopes:
            recommendations.append(
                "Request 'read_products' scope to access product catalog and inventory data"
            )

        if "read_orders" in missing_scopes:
            recommendations.append(
                "Request 'read_orders' scope to access order history and customer purchase patterns"
            )

        if "read_customers" in missing_scopes:
            recommendations.append(
                "Request 'read_customers' scope to access customer profiles and behavior data"
            )

        if "read_collections" in missing_scopes:
            recommendations.append(
                "Request 'read_collections' scope to access product collections and categorization"
            )

        if "read_marketing_events" in missing_scopes:
            recommendations.append(
                "Request 'read_marketing_events' scope to access customer engagement and marketing data"
            )

        if len(missing_scopes) >= 3:
            recommendations.append(
                "Consider requesting all missing scopes for comprehensive data collection and ML training"
            )

        return recommendations

    def _get_collection_priority(self, collectable_data: List[str]) -> List[str]:
        """Determine priority order for data collection"""
        # Priority based on ML training importance
        priority_order = [
            "products",
            "orders",
            "customers",
            "collections",
            "customer_events",
        ]

        # Filter to only include collectable data and maintain priority order
        return [
            data_type for data_type in priority_order if data_type in collectable_data
        ]

    def _estimate_collection_time(self, collectable_data: List[str]) -> Dict[str, Any]:
        """Estimate time needed for data collection"""
        # Rough estimates based on data type complexity
        time_estimates = {
            "products": {"minutes": 5, "complexity": "medium"},
            "orders": {"minutes": 10, "complexity": "high"},
            "customers": {"minutes": 3, "complexity": "low"},
            "collections": {"minutes": 2, "complexity": "low"},
            "customer_events": {"minutes": 3, "complexity": "medium"},
        }

        total_minutes = sum(
            time_estimates.get(data_type, {}).get("minutes", 0)
            for data_type in collectable_data
        )

        return {
            "total_minutes": total_minutes,
            "breakdown": {
                data_type: time_estimates.get(data_type, {})
                for data_type in collectable_data
            },
            "estimated_at": now_utc().isoformat(),
        }

    def _get_collection_recommendations(
        self, collectable_data: List[str], missing_scopes: List[str]
    ) -> List[str]:
        """Get recommendations for data collection strategy"""
        recommendations = []

        if len(collectable_data) == 0:
            recommendations.append(
                "No data can be collected. Request missing scopes from shop owner."
            )
            return recommendations

        if len(collectable_data) < 3:
            recommendations.append(
                "Limited data available. Consider requesting additional scopes for better ML training."
            )

        if "products" in collectable_data and "orders" in collectable_data:
            recommendations.append(
                "Good foundation available. Can train product recommendation models."
            )

        if "customers" in collectable_data and "orders" in collectable_data:
            recommendations.append(
                "Customer behavior analysis possible. Can train customer segmentation models."
            )

        if len(missing_scopes) > 0:
            recommendations.append(
                f"Request missing scopes: {', '.join(missing_scopes)}"
            )

        return recommendations
