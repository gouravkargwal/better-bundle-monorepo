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
from app.shared.services.redis_cache import create_cache_service

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
            "read_customer_events",
        ]

        # Scope to data type mapping
        self.scope_data_mapping = {
            "read_products": [
                "products",
                "variants",
                "images",
                "collections",
                "collection_products",
            ],
            "read_orders": ["orders", "line_items", "financials"],
            "read_customers": ["customers", "customer_addresses"],
            "read_customer_events": ["customer_events", "browsing_behavior"],
        }

        # Redis cache service for permissions
        self.cache_service = None
        self.cache_ttl = 3600  # 1 hour

    async def _ensure_cache_service(self):
        """Ensure cache service is initialized"""
        if self.cache_service is None:
            self.cache_service = await create_cache_service(
                "permissions", self.cache_ttl
            )
            logger.debug("Permission cache service initialized")

    async def check_shop_permissions(
        self, shop_domain: str, access_token: str = None
    ) -> Dict[str, bool]:
        """Check what permissions the app has for a shop"""
        logger.info(f"Starting permission check for shop: {shop_domain}")
        logger.debug(f"Access token provided: {'Yes' if access_token else 'No'}")

        # Simple recursion guard - return basic permissions to avoid infinite loops
        if not hasattr(self, "_checking_permissions"):
            self._checking_permissions = set()

        if shop_domain in self._checking_permissions:
            logger.warning(
                f"Recursion detected for {shop_domain}, returning basic permissions"
            )
            return {
                "products": True,
                "orders": True,
                "customers": True,
                "collections": True,
                "customer_events": True,
                "has_access": True,
            }

        self._checking_permissions.add(shop_domain)

        try:
            # Check cache first
            cached = await self._get_cached_permissions(shop_domain)
            if cached:
                logger.info(f"Using cached permissions for {shop_domain}")
                logger.debug(f"Cached permissions: {cached}")
                return cached

            logger.info(f"Checking permissions for shop: {shop_domain}")
            logger.debug(f"No cache hit, proceeding with scopes API call")

            # Get actual granted scopes from Shopify
            scopes = await self._get_shopify_scopes(shop_domain, access_token)
            logger.debug(f"Granted scopes for {shop_domain}: {scopes}")

            # Check permissions based on granted scopes
            logger.info(f"Checking permissions against granted scopes: {scopes}")

            # Check each permission individually with detailed logging
            products_permission = any(
                scope in ["read_products", "write_products"] for scope in scopes
            )
            logger.info(
                f"Products permission check: {products_permission} (looking for: read_products, write_products)"
            )

            orders_permission = any(
                scope in ["read_orders", "write_orders"] for scope in scopes
            )
            logger.info(
                f"Orders permission check: {orders_permission} (looking for: read_orders, write_orders)"
            )

            customers_permission = any(
                scope in ["read_customers", "write_customers"] for scope in scopes
            )
            logger.info(
                f"Customers permission check: {customers_permission} (looking for: read_customers, write_customers)"
            )

            # Collections are part of read_products scope
            collections_permission = any(
                scope in ["read_products", "write_products"] for scope in scopes
            )
            logger.info(
                f"Collections permission check: {collections_permission} (collections are part of read_products scope)"
            )

            # Customer events use read_customer_events scope
            customer_events_permission = any(
                scope in ["read_customer_events", "write_customer_events"]
                for scope in scopes
            )
            logger.info(
                f"Customer events permission check: {customer_events_permission} (looking for: read_customer_events, write_customer_events)"
            )

            permissions = {
                "products": products_permission,
                "orders": orders_permission,
                "customers": customers_permission,
                "collections": collections_permission,
                "customer_events": customer_events_permission,
            }

            # Check overall access
            permissions["has_access"] = any(permissions.values())
            logger.debug(f"Overall access result: {permissions['has_access']}")

            # Cache the results
            logger.debug(f"Caching permission results for {shop_domain}")
            await self._cache_permissions(shop_domain, permissions)

            # Log the results
            await self.log_permission_check(shop_domain, permissions)

            return permissions

        finally:
            # Clean up recursion guard
            self._checking_permissions.discard(shop_domain)

    def get_required_scopes(self) -> List[str]:
        """Get list of required Shopify scopes for the app"""
        return self.required_scopes.copy()

    async def get_missing_scopes(
        self, shop_domain: str, access_token: str = None
    ) -> List[str]:
        """Get list of missing scopes for a shop"""
        permissions = await self.check_shop_permissions(shop_domain, access_token)
        return self._get_missing_scopes_from_permissions(permissions)

    def _get_missing_scopes_from_permissions(
        self, permissions: Dict[str, bool]
    ) -> List[str]:
        """Get list of missing scopes from permissions dict"""
        missing_scopes = []

        if not permissions.get("products"):
            missing_scopes.append("read_products")
        if not permissions.get("orders"):
            missing_scopes.append("read_orders")
        if not permissions.get("customers"):
            missing_scopes.append("read_customers")
        if not permissions.get("collections"):
            missing_scopes.append(
                "read_products"
            )  # Collections are part of read_products
        if not permissions.get("customer_events"):
            missing_scopes.append("read_customer_events")

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

    async def _get_shopify_scopes(
        self, shop_domain: str, access_token: str = None
    ) -> List[str]:
        """Get the actual scopes granted to the app from Shopify GraphQL API"""
        try:
            # Ensure API client is connected
            await self.api_client.connect()

            # Set access token for API client
            if access_token:
                await self.api_client.set_access_token(shop_domain, access_token)

            # Use the API client to get scopes
            scopes = await self.api_client.get_app_installation_scopes(shop_domain)

            logger.info(f"Retrieved {len(scopes)} scopes for {shop_domain}: {scopes}")

            # Log each scope individually for debugging
            for i, scope in enumerate(scopes):
                logger.debug(f"Scope {i+1}: {scope}")

            return scopes

        except Exception as e:
            logger.error(f"Error getting scopes for {shop_domain}: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    async def get_collection_strategy(
        self, shop_domain: str, access_token: str = None
    ) -> Dict[str, Any]:
        """Get optimal data collection strategy based on available permissions"""
        permissions = await self.check_shop_permissions(shop_domain, access_token)
        missing_scopes = self._get_missing_scopes_from_permissions(permissions)

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

    async def _get_cached_permissions(
        self, shop_domain: str
    ) -> Optional[Dict[str, bool]]:
        """Get cached permissions if still valid"""
        await self._ensure_cache_service()

        logger.debug(f"Checking Redis cache for {shop_domain}")

        cached = await self.cache_service.get(shop_domain)
        if cached:
            logger.debug(f"Cache hit for {shop_domain}: {cached}")
            return cached

        logger.debug(f"Cache miss for {shop_domain}")
        return None

    async def _cache_permissions(self, shop_domain: str, permissions: Dict[str, bool]):
        """Cache permission results"""
        await self._ensure_cache_service()

        logger.debug(f"Caching permissions for {shop_domain}: {permissions}")
        success = await self.cache_service.set(shop_domain, permissions, self.cache_ttl)
        if success:
            logger.debug(f"Successfully cached permissions for {shop_domain}")
        else:
            logger.warning(f"Failed to cache permissions for {shop_domain}")

    async def clear_permission_cache(self, shop_domain: Optional[str] = None):
        """Clear permission cache for a specific shop or all shops"""
        await self._ensure_cache_service()

        logger.debug(
            f"Clearing permission cache for: {shop_domain if shop_domain else 'all shops'}"
        )

        if shop_domain:
            # Clear specific shop cache
            success = await self.cache_service.delete(shop_domain)
            if success:
                logger.info(f"Cleared permission cache for {shop_domain}")
            else:
                logger.debug(f"No cache entry found for {shop_domain}")
        else:
            # Clear all permission cache
            success = await self.cache_service.clear_namespace()
            if success:
                logger.info("Cleared all permission cache")
            else:
                logger.warning("Failed to clear all permission cache")

        # Get current cache keys for debugging
        current_keys = await self.cache_service.get_keys()
        logger.debug(f"Cache after clearing: {current_keys}")

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

        if "read_products" in missing_scopes and "collections" in str(missing_scopes):
            recommendations.append(
                "Request 'read_products' scope to access product collections and categorization"
            )

        if "read_customer_events" in missing_scopes:
            recommendations.append(
                "Request 'read_customer_events' scope to access customer browsing behavior and engagement data"
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
