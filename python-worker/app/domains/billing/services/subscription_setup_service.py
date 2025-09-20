"""
Subscription Setup Service

This service handles creating usage-based subscriptions for new app installations
and managing subscription lifecycle.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional, Any

from prisma import Prisma

from .shopify_usage_billing_service import ShopifyUsageBillingService
from ..repositories.billing_repository import BillingRepository

logger = logging.getLogger(__name__)


class SubscriptionSetupService:
    """Service for setting up usage-based subscriptions"""

    def __init__(self, prisma: Prisma):
        self.prisma = prisma
        self.billing_repository = BillingRepository(prisma)
        self.shopify_usage_billing_service = ShopifyUsageBillingService(
            prisma, self.billing_repository
        )

    async def create_trial_subscription(
        self, shop_id: str, shop_domain: str, access_token: str, currency: str = "USD"
    ) -> Optional[Dict[str, Any]]:
        """
        Create a usage-based subscription for a new shop with trial settings.

        Args:
            shop_id: Shop ID
            shop_domain: Shop domain
            access_token: Shop access token
            currency: Store currency

        Returns:
            Subscription creation result or None if failed
        """
        try:
            logger.info(f"Creating trial subscription for shop {shop_id}")

            # Create usage-based subscription with high cap for trial
            subscription = (
                await self.shopify_usage_billing_service.create_usage_subscription(
                    shop_id=shop_id,
                    shop_domain=shop_domain,
                    access_token=access_token,
                    currency=currency,
                    capped_amount=1000.0,  # High cap for trial period
                )
            )

            if not subscription:
                logger.error(f"Failed to create subscription for shop {shop_id}")
                return None

            # Create trial billing plan
            billing_plan = await self.prisma.billingplan.create(
                {
                    "data": {
                        "shopId": shop_id,
                        "shopDomain": shop_domain,
                        "name": "Usage-Based Trial Plan",
                        "type": "usage_based",
                        "status": "active",
                        "configuration": {
                            "subscription_id": subscription.id,
                            "subscription_status": subscription.status,
                            "line_items": subscription.line_items,
                            "usage_based": True,
                            "trial_active": True,
                            "trial_threshold": 200.0,
                            "trial_revenue": 0.0,
                            "capped_amount": 1000.0,
                            "currency": currency,
                            "revenue_share_rate": 0.03,
                        },
                        "effectiveFrom": datetime.utcnow(),
                        "isTrialActive": True,
                        "trialThreshold": 200.0,
                        "trialRevenue": 0.0,
                    }
                }
            )

            logger.info(
                f"Created trial billing plan {billing_plan.id} for shop {shop_id}"
            )

            return {
                "subscription": subscription,
                "billing_plan": billing_plan,
                "confirmation_url": subscription.id,  # This would be the confirmation URL
                "trial_active": True,
                "trial_threshold": 200.0,
                "currency": currency,
            }

        except Exception as e:
            logger.error(f"Error creating trial subscription for shop {shop_id}: {e}")
            return None

    async def activate_subscription(self, shop_id: str, subscription_id: str) -> bool:
        """
        Activate a subscription after merchant approval.

        Args:
            shop_id: Shop ID
            subscription_id: Subscription ID

        Returns:
            True if activated successfully, False otherwise
        """
        try:
            # Get shop information
            shop = await self.prisma.shop.find_unique(
                where={"id": shop_id}, select={"domain": True, "accessToken": True}
            )

            if not shop or not shop.accessToken:
                logger.error(f"Shop {shop_id} not found or no access token")
                return False

            # Get subscription status
            subscription_status = (
                await self.shopify_usage_billing_service.get_subscription_status(
                    shop_domain=shop.domain,
                    access_token=shop.accessToken,
                    subscription_id=subscription_id,
                )
            )

            if not subscription_status:
                logger.error(f"Failed to get subscription status for {subscription_id}")
                return False

            # Update billing plan with subscription status
            await self.prisma.billingplan.update_many(
                where={"shopId": shop_id, "status": "active"},
                data={
                    "configuration": {
                        "subscription_id": subscription_id,
                        "subscription_status": subscription_status["status"],
                        "line_items": subscription_status["lineItems"],
                        "usage_based": True,
                        "activated_at": datetime.utcnow().isoformat(),
                    }
                },
            )

            # Create billing event
            await self.prisma.billingevent.create(
                {
                    "data": {
                        "shopId": shop_id,
                        "type": "subscription_activated",
                        "data": {
                            "subscription_id": subscription_id,
                            "status": subscription_status["status"],
                            "activated_at": datetime.utcnow().isoformat(),
                        },
                        "metadata": {
                            "subscription_id": subscription_id,
                            "event_type": "subscription_activation",
                        },
                    }
                }
            )

            logger.info(f"Activated subscription {subscription_id} for shop {shop_id}")
            return True

        except Exception as e:
            logger.error(f"Error activating subscription for shop {shop_id}: {e}")
            return False

    async def handle_trial_completion(self, shop_id: str, final_revenue: float) -> bool:
        """
        Handle trial completion and transition to paid billing.

        Args:
            shop_id: Shop ID
            final_revenue: Final attributed revenue that completed the trial

        Returns:
            True if handled successfully, False otherwise
        """
        try:
            # Update billing plan to mark trial as completed
            await self.prisma.billingplan.update_many(
                where={"shopId": shop_id, "status": "active"},
                data={
                    "isTrialActive": False,
                    "trialRevenue": final_revenue,
                    "configuration": {
                        "trial_active": False,
                        "trial_completed_at": datetime.utcnow().isoformat(),
                        "trial_completion_revenue": final_revenue,
                    },
                },
            )

            # Create billing event
            await self.prisma.billingevent.create(
                {
                    "data": {
                        "shopId": shop_id,
                        "type": "trial_completed",
                        "data": {
                            "final_revenue": final_revenue,
                            "completed_at": datetime.utcnow().isoformat(),
                        },
                        "metadata": {
                            "trial_completion": True,
                            "final_revenue": final_revenue,
                        },
                    }
                }
            )

            logger.info(
                f"Trial completed for shop {shop_id} with revenue {final_revenue}"
            )
            return True

        except Exception as e:
            logger.error(f"Error handling trial completion for shop {shop_id}: {e}")
            return False

    async def get_subscription_status(self, shop_id: str) -> Optional[Dict[str, Any]]:
        """
        Get subscription status for a shop.

        Args:
            shop_id: Shop ID

        Returns:
            Subscription status data or None if not found
        """
        try:
            # Get billing plan
            billing_plan = await self.prisma.billingplan.find_first(
                where={"shopId": shop_id, "status": "active"}
            )

            if not billing_plan:
                return None

            # Get shop information
            shop = await self.prisma.shop.find_unique(
                where={"id": shop_id}, select={"domain": True, "accessToken": True}
            )

            if not shop or not shop.accessToken:
                return None

            # Get subscription status from Shopify
            subscription_id = billing_plan.configuration.get("subscription_id")
            if not subscription_id:
                return None

            subscription_status = (
                await self.shopify_usage_billing_service.get_subscription_status(
                    shop_domain=shop.domain,
                    access_token=shop.accessToken,
                    subscription_id=subscription_id,
                )
            )

            return {
                "billing_plan": billing_plan,
                "subscription_status": subscription_status,
                "trial_active": billing_plan.isTrialActive,
                "trial_threshold": billing_plan.trialThreshold,
                "trial_revenue": billing_plan.trialRevenue,
            }

        except Exception as e:
            logger.error(f"Error getting subscription status for shop {shop_id}: {e}")
            return None
