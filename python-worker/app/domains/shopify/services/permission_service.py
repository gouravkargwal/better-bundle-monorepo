"""
Shopify permission service implementation for BetterBundle Python Worker
"""

from typing import Dict, Any, List, Optional

from app.core.logging import get_logger
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
        logger.info(
            f"🔍 check_shop_permissions called for {shop_domain} with access_token: {'Yes' if access_token else 'No'}"
        )

        # Simple recursion guard - return basic permissions to avoid infinite loops
        if not hasattr(self, "_checking_permissions"):
            self._checking_permissions = set()

        if shop_domain in self._checking_permissions:
            logger.info(
                f"🔄 Recursion guard triggered for {shop_domain}, returning basic permissions"
            )
            return {
                "products": True,
                "orders": True,
                "customers": True,
                "collections": True,
                "has_access": True,
            }

        self._checking_permissions.add(shop_domain)

        try:
            # Check cache first
            cached = await self._get_cached_permissions(shop_domain)
            if cached:
                logger.info(f"✅ Using cached permissions for {shop_domain}: {cached}")
                return cached

            # Get actual granted scopes from Shopify
            logger.info(f"🚀 Getting scopes from Shopify for {shop_domain}")
            scopes = await self._get_shopify_scopes(shop_domain, access_token)
            logger.info(
                f"✅ Checking permissions for {shop_domain} with scopes: {scopes}"
            )

            # Check permissions based on granted scopes
            products_permission = any(
                scope in ["read_products", "write_products"] for scope in scopes
            )
            orders_permission = any(
                scope in ["read_orders", "write_orders"] for scope in scopes
            )
            customers_permission = any(
                scope in ["read_customers", "write_customers"] for scope in scopes
            )
            # Collections are part of read_products scope
            collections_permission = any(
                scope in ["read_products", "write_products"] for scope in scopes
            )

            logger.info(
                f"Permission check results for {shop_domain}: products={products_permission}, orders={orders_permission}, customers={customers_permission}, collections={collections_permission}"
            )

            permissions = {
                "products": products_permission,
                "orders": orders_permission,
                "customers": customers_permission,
                "collections": collections_permission,
            }

            # Check overall access
            permissions["has_access"] = any(permissions.values())

            # Only cache if we got scopes from the API (successful response)
            if scopes:  # Only cache when API returned actual scopes
                logger.info(
                    f"✅ Caching successful permission results for {shop_domain}"
                )
                await self._cache_permissions(shop_domain, permissions)
            else:
                logger.warning(
                    f"⚠️ Not caching permissions for {shop_domain} - API returned empty scopes"
                )

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
            missing_scopes.append("read_products")

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
            logger.info(
                f"🔍 Getting scopes for {shop_domain} with access_token: {'Yes' if access_token else 'No'}"
            )

            # Ensure API client is connected
            await self.api_client.connect()
            logger.info(f"✅ API client connected for {shop_domain}")

            # Set access token for API client
            if access_token:
                await self.api_client.set_access_token(shop_domain, access_token)
                logger.info(f"✅ Access token set for {shop_domain}")
            else:
                logger.warning(f"⚠️ No access token provided for {shop_domain}")

            # Use the API client to get scopes
            logger.info(f"🚀 Calling get_app_installation_scopes for {shop_domain}")
            scopes = await self.api_client.get_app_installation_scopes(shop_domain)
            logger.info(f"✅ Retrieved scopes for {shop_domain}: {scopes}")
            return scopes

        except Exception as e:
            logger.error(f"❌ Failed to get scopes for {shop_domain}: {e}")
            logger.error(f"❌ Error type: {type(e).__name__}")
            logger.error(f"❌ Error details: {str(e)}")
            # No fallback - return empty list to indicate API failure
            logger.warning(f"⚠️ API failed for {shop_domain}, returning empty scopes")
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

        if missing_scopes:
            logger.warning(f"Missing scopes for {shop_domain}: {missing_scopes}")
        else:
            logger.info(f"All permissions granted for {shop_domain}")

    async def _get_cached_permissions(
        self, shop_domain: str
    ) -> Optional[Dict[str, bool]]:
        """Get cached permissions if still valid"""
        await self._ensure_cache_service()
        cached = await self.cache_service.get(shop_domain)
        return cached

    async def _cache_permissions(self, shop_domain: str, permissions: Dict[str, bool]):
        """Cache permission results"""
        await self._ensure_cache_service()
        await self.cache_service.set(shop_domain, permissions, self.cache_ttl)

    async def clear_permission_cache(self, shop_domain: Optional[str] = None):
        """Clear permission cache for a specific shop or all shops"""
        await self._ensure_cache_service()

        if shop_domain:
            await self.cache_service.delete(shop_domain)
        else:
            await self.cache_service.clear_namespace()

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
