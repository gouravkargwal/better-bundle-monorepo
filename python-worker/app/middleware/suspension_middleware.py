"""
Suspension middleware for Python worker
Checks shop suspension status before processing data
"""

import json
import asyncio
from typing import Dict, Any, Optional
from app.core.redis_client import get_redis_client
from app.core.database.session import get_session_context
from app.core.database.models.shop import Shop
from app.core.database.models.shop_subscription import ShopSubscription
from sqlalchemy import select
from app.core.logging import get_logger

logger = get_logger(__name__)


class SuspensionMiddleware:
    """Middleware to check shop suspension status before processing"""

    def __init__(self):
        self.cache_ttl = 300  # 5 minutes cache TTL

    async def check_shop_suspension(self, shop_identifier: str | int) -> Dict[str, Any]:
        """Check if shop is suspended using Redis cache"""
        try:
            redis = await get_redis_client()
            cache_key = f"suspension:{shop_identifier}"

            # Check cache first
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)

            # If not cached, check database
            async with get_session_context() as session:
                # Determine if shop_identifier is a shop_id or shop_domain
                # Try shop_id first (UUID format), then shop_domain
                if len(shop_identifier) == 36 and "-" in shop_identifier:
                    # Looks like a UUID (shop_id)
                    where_clause = Shop.id == shop_identifier
                else:
                    # Looks like a domain
                    where_clause = Shop.shop_domain == shop_identifier

                # Get shop and subscription data in single query
                result = await session.execute(
                    select(Shop, ShopSubscription)
                    .join(ShopSubscription, Shop.id == ShopSubscription.shop_id)
                    .where(where_clause)
                    .where(ShopSubscription.is_active == True)
                )

                shop, subscription = result.first() or (None, None)

                if not shop:
                    status = {
                        "isSuspended": True,
                        "reason": "shop_not_found",
                        "subscriptionActive": False,
                    }
                elif not shop.is_active:
                    status = {
                        "isSuspended": True,
                        "reason": shop.suspension_reason or "service_suspended",
                        "requiresBillingSetup": shop.suspension_reason
                        == "trial_completed_subscription_required",
                        "requiresCapIncrease": shop.suspension_reason
                        == "monthly_cap_reached",
                        "subscriptionActive": False,
                    }
                elif subscription and subscription.status == "TRIAL_COMPLETED":
                    status = {
                        "isSuspended": True,
                        "reason": "trial_completed_awaiting_setup",
                        "requiresBillingSetup": True,
                        "subscriptionActive": False,
                    }
                else:
                    status = {
                        "isSuspended": False,
                        "reason": "active",
                        "subscriptionActive": (
                            subscription.status == "ACTIVE" if subscription else False
                        ),
                    }

                # Cache the result
                await redis.setex(cache_key, self.cache_ttl, json.dumps(status))
                return status

        except Exception as e:
            logger.error(f"Error checking suspension for shop {shop_identifier}: {e}")
            # Default to suspended on error for safety
            return {
                "isSuspended": True,
                "reason": "suspension_check_error",
                "subscriptionActive": False,
            }

    async def should_process_shop(self, shop_identifier: str) -> bool:
        """Check if shop should be processed (not suspended)"""
        status = await self.check_shop_suspension(shop_identifier)
        return not status.get("isSuspended", True)

    async def get_suspension_message(self, shop_identifier: str) -> str:
        """Get suspension message for logging"""
        status = await self.check_shop_suspension(shop_identifier)
        if not status.get("isSuspended", True):
            return ""

        reason = status.get("reason", "service_suspended")
        if reason == "trial_completed_subscription_required":
            return "Trial completed. Please set up billing to continue using services."
        elif reason == "monthly_cap_reached":
            return (
                "Monthly spending limit reached. Please increase your cap to continue."
            )
        elif reason == "subscription_suspended":
            return "Subscription suspended. Please contact support."
        else:
            return "Services are currently suspended. Please contact support."

    async def invalidate_cache(self, shop_identifier: str) -> None:
        """Invalidate suspension cache for a shop"""
        try:
            redis = await get_redis_client()
            cache_key = f"suspension:{shop_identifier}"
            await redis.delete(cache_key)
            logger.info(f"✅ Suspension cache invalidated for shop {shop_identifier}")
        except Exception as e:
            logger.error(
                f"❌ Error invalidating suspension cache for shop {shop_identifier}: {e}"
            )


# Global middleware instance
suspension_middleware = SuspensionMiddleware()
