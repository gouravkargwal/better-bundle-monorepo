"""
Shopify Plus Validation Service

This service validates if a store is on Shopify Plus plan.
Required for Mercury checkout extensions.
"""

import asyncio
from typing import Optional, Dict, Any
from app.core.logging import get_logger
from app.domains.shopify.services.shopify_api_client import ShopifyAPIClient
from app.core.config.settings import settings

logger = get_logger(__name__)


class ShopifyPlusValidationService:
    """Service for validating Shopify Plus status"""

    def __init__(self, api_client: ShopifyAPIClient):
        self.api_client = api_client

    async def validate_shopify_plus_store(self, shop_domain: str) -> Dict[str, Any]:
        """
        Validate if a store is on Shopify Plus plan.

        Args:
            shop_domain: The shop domain to validate

        Returns:
            Dict containing validation results
        """
        try:
            logger.info(f"🔍 Shopify Plus Validation: Checking {shop_domain}")

            # Get shop information
            shop_info = await self._get_shop_info(shop_domain)
            if not shop_info:
                return {
                    "is_shopify_plus": False,
                    "mercury_eligible": False,
                    "reason": "Shop not found",
                    "shop_domain": shop_domain,
                }

            # Check plan name for Shopify Plus
            plan_name = shop_info.get("plan_name", "").lower()
            is_plus = "plus" in plan_name or "enterprise" in plan_name

            # Additional checks for Plus features
            plus_features = await self._check_plus_features(shop_domain, shop_info)

            result = {
                "is_shopify_plus": is_plus,
                "mercury_eligible": is_plus and plus_features["checkout_extensions"],
                "plan_name": shop_info.get("plan_name", "Unknown"),
                "shop_domain": shop_domain,
                "plus_features": plus_features,
                "validation_timestamp": shop_info.get("updated_at"),
            }

            if is_plus:
                logger.info(
                    f"✅ Shopify Plus Validation: {shop_domain} is on Plus plan"
                )
            else:
                logger.warning(
                    f"⚠️ Shopify Plus Validation: {shop_domain} is not on Plus plan"
                )

            return result

        except Exception as e:
            logger.error(f"❌ Shopify Plus Validation failed for {shop_domain}: {e}")
            return {
                "is_shopify_plus": False,
                "mercury_eligible": False,
                "reason": f"Validation error: {str(e)}",
                "shop_domain": shop_domain,
            }

    async def _get_shop_info(self, shop_domain: str) -> Optional[Dict[str, Any]]:
        """Get shop information from Shopify API"""
        try:
            # Use GraphQL to get shop information
            query = """
            query getShopInfo {
                shop {
                    id
                    name
                    myshopifyDomain
                    plan {
                        displayName
                        partnerDevelopment
                        shopifyPlus
                    }
                    features {
                        checkoutUiExtension
                        customerAccounts
                    }
                    updatedAt
                }
            }
            """

            response = await self.api_client.execute_graphql_query(
                shop_domain=shop_domain, query=query
            )

            if response and "data" in response:
                shop_data = response["data"].get("shop", {})
                plan = shop_data.get("plan", {})

                return {
                    "id": shop_data.get("id"),
                    "name": shop_data.get("name"),
                    "myshopify_domain": shop_data.get("myshopifyDomain"),
                    "plan_name": plan.get("displayName", ""),
                    "is_shopify_plus": plan.get("shopifyPlus", False),
                    "partner_development": plan.get("partnerDevelopment", False),
                    "features": shop_data.get("features", {}),
                    "updated_at": shop_data.get("updatedAt"),
                }

            return None

        except Exception as e:
            logger.error(f"Failed to get shop info for {shop_domain}: {e}")
            return None

    async def _check_plus_features(
        self, shop_domain: str, shop_info: Dict[str, Any]
    ) -> Dict[str, bool]:
        """Check for Shopify Plus specific features"""
        try:
            features = shop_info.get("features", {})

            return {
                "checkout_extensions": features.get("checkoutUiExtension", False),
                "customer_accounts": features.get("customerAccounts", False),
                "advanced_checkout": True,  # Plus stores have advanced checkout
                "script_tags": True,  # Plus stores can use script tags
            }

        except Exception as e:
            logger.error(f"Failed to check Plus features for {shop_domain}: {e}")
            return {
                "checkout_extensions": False,
                "customer_accounts": False,
                "advanced_checkout": False,
                "script_tags": False,
            }

    async def get_mercury_eligibility(self, shop_domain: str) -> Dict[str, Any]:
        """
        Check if a store is eligible for Mercury checkout extensions.

        Args:
            shop_domain: The shop domain to check

        Returns:
            Dict containing eligibility information
        """
        validation_result = await self.validate_shopify_plus_store(shop_domain)

        return {
            "shop_domain": shop_domain,
            "mercury_eligible": validation_result["mercury_eligible"],
            "is_shopify_plus": validation_result["is_shopify_plus"],
            "plan_name": validation_result.get("plan_name", "Unknown"),
            "required_features": {
                "shopify_plus": validation_result["is_shopify_plus"],
                "checkout_extensions": validation_result.get("plus_features", {}).get(
                    "checkout_extensions", False
                ),
            },
            "validation_timestamp": validation_result.get("validation_timestamp"),
            "reason": validation_result.get("reason", "Validated successfully"),
        }


# Global instance
_shopify_plus_service: Optional[ShopifyPlusValidationService] = None


async def get_shopify_plus_service() -> ShopifyPlusValidationService:
    """Get or create the global Shopify Plus validation service"""
    global _shopify_plus_service

    if _shopify_plus_service is None:
        from app.domains.shopify.services.shopify_api_client import ShopifyAPIClient

        api_client = ShopifyAPIClient()
        _shopify_plus_service = ShopifyPlusValidationService(api_client)

    return _shopify_plus_service
