"""
Flat Fee Billing Service

Manages Shopify recurring subscriptions using AppRecurringPricing
instead of the legacy AppUsagePricing (usage-based billing).

For flat fee pricing, merchants choose a plan (Basic/Pro/Enterprise)
and are charged a fixed monthly fee via Shopify's recurring subscription model.
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.billing_repository_v2 import BillingRepositoryV2
from app.core.database.models import (
    SubscriptionStatus,
    BillingCycleStatus,
    BillingCycle,
)
from app.core.database.models.shop_subscription import ShopSubscription
from app.shared.helpers import now_utc

logger = logging.getLogger(__name__)


@dataclass
class RecurringSubscription:
    """Shopify recurring subscription data"""

    id: str
    name: str
    status: str
    created_at: str
    updated_at: str
    current_period_end: Optional[str] = None
    trial_days: Optional[int] = None


class FlatFeeBillingService:
    """
    Service for creating and managing Shopify flat fee recurring subscriptions.

    Uses Shopify's AppRecurringPricing to create fixed monthly subscriptions
    instead of the legacy usage-based AppUsagePricing model.
    """

    def __init__(self, session: AsyncSession, billing_repository: BillingRepositoryV2):
        self.session = session
        self.billing_repository = billing_repository
        self.base_url = "https://{shop_domain}/admin/api/2024-01/graphql.json"

    async def create_recurring_subscription(
        self,
        shop_id: str,
        shop_domain: str,
        access_token: str,
        plan_name: str,
        monthly_fee: Decimal,
        currency: str = "USD",
        trial_days: int = 14,
        return_url: Optional[str] = None,
    ) -> Optional[RecurringSubscription]:
        """
        Create a recurring subscription using Shopify AppRecurringPricing.

        Args:
            shop_id: Shop ID
            shop_domain: Shop domain
            access_token: Shop access token
            plan_name: Display name for the plan
            monthly_fee: Monthly fee amount
            currency: Store currency code
            trial_days: Number of free trial days
            return_url: URL to redirect after approval

        Returns:
            Created subscription or None if failed
        """
        try:
            if not return_url:
                return_url = (
                    f"https://admin.shopify.com/store/{shop_domain}/apps/better-bundle/app/billing"
                )

            # GraphQL mutation for recurring subscription
            mutation = """
            mutation appSubscriptionCreate($name: String!, $returnUrl: URL!, $lineItems: [AppSubscriptionLineItemInput!]!, $trialDays: Int!) {
                appSubscriptionCreate(
                    name: $name,
                    returnUrl: $returnUrl,
                    lineItems: $lineItems,
                    trialDays: $trialDays
                ) {
                    userErrors {
                        field
                        message
                    }
                    confirmationUrl
                    appSubscription {
                        id
                        name
                        status
                        createdAt
                        currentPeriodEnd
                        trialDays
                        lineItems {
                            id
                            plan {
                                pricingDetails {
                                    __typename
                                    ... on AppRecurringPricing {
                                        price {
                                            amount
                                            currencyCode
                                        }
                                        interval
                                    }
                                }
                            }
                        }
                    }
                }
            }
            """

            # Prepare variables
            variables = {
                "name": f"Better Bundle - {plan_name}",
                "returnUrl": return_url,
                "trialDays": trial_days,
                "lineItems": [
                    {
                        "plan": {
                            "appRecurringPricingDetails": {
                                "price": {
                                    "amount": float(monthly_fee),
                                    "currencyCode": currency,
                                },
                                "interval": "EVERY_30_DAYS",
                            }
                        }
                    }
                ],
            }

            # Make GraphQL request
            response = await self._make_graphql_request(
                shop_domain, access_token, mutation, variables
            )

            if response.get("errors"):
                logger.error(f"GraphQL errors: {response['errors']}")
                return None

            data = response.get("data", {}).get("appSubscriptionCreate", {})

            if data.get("userErrors"):
                logger.error(f"User errors: {data['userErrors']}")
                return None

            subscription_data = data.get("appSubscription")
            if not subscription_data:
                logger.error("No subscription data returned")
                return None

            # Store subscription in database
            await self._store_shopify_subscription(
                shop_id,
                subscription_data,
                plan_name,
                monthly_fee,
                currency,
                data.get("confirmationUrl"),
            )

            logger.info(
                f"✅ Created recurring subscription for shop {shop_id}: {subscription_data['id']} "
                f"(plan={plan_name}, fee=${monthly_fee}, trial={trial_days}d)"
            )

            return RecurringSubscription(
                id=subscription_data["id"],
                name=subscription_data["name"],
                status=subscription_data["status"],
                created_at=subscription_data["createdAt"],
                updated_at=subscription_data.get("createdAt"),
                current_period_end=subscription_data.get("currentPeriodEnd"),
                trial_days=subscription_data.get("trialDays", trial_days),
            )

        except Exception as e:
            logger.error(
                f"❌ Error creating recurring subscription for shop {shop_id}: {e}"
            )
            return None

    async def cancel_subscription(
        self,
        shop_id: str,
        shop_domain: str,
        access_token: str,
        shopify_subscription_id: str,
    ) -> bool:
        """
        Cancel an existing Shopify recurring subscription.

        Args:
            shop_id: Shop ID
            shop_domain: Shop domain
            access_token: Shop access token
            shopify_subscription_id: Shopify subscription ID

        Returns:
            True if cancelled successfully
        """
        try:
            mutation = """
            mutation appSubscriptionCancel($id: ID!) {
                appSubscriptionCancel(id: $id) {
                    userErrors {
                        field
                        message
                    }
                    appSubscription {
                        id
                        status
                    }
                }
            }
            """

            variables = {"id": shopify_subscription_id}

            response = await self._make_graphql_request(
                shop_domain, access_token, mutation, variables
            )

            if response.get("errors"):
                logger.error(f"GraphQL errors cancelling: {response['errors']}")
                return False

            data = response.get("data", {}).get("appSubscriptionCancel", {})
            if data.get("userErrors"):
                logger.error(f"User errors cancelling: {data['userErrors']}")
                return False

            # Update local subscription status
            shop_subscription = await self.billing_repository.get_shop_subscription(
                shop_id
            )
            if shop_subscription:
                await self.billing_repository.update_shop_subscription_status(
                    shop_subscription.id, SubscriptionStatus.CANCELLED
                )

            logger.info(
                f"✅ Cancelled subscription {shopify_subscription_id} for shop {shop_id}"
            )
            return True

        except Exception as e:
            logger.error(f"❌ Error cancelling subscription: {e}")
            return False

    async def get_subscription_status(
        self,
        shop_domain: str,
        access_token: str,
        subscription_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get subscription status from Shopify.

        Args:
            shop_domain: Shop domain
            access_token: Shop access token
            subscription_id: Shopify subscription ID

        Returns:
            Subscription status data or None
        """
        try:
            query = """
            query getSubscription($id: ID!) {
                node(id: $id) {
                    ... on AppSubscription {
                        id
                        name
                        status
                        createdAt
                        currentPeriodEnd
                        trialDays
                        lineItems {
                            id
                            plan {
                                pricingDetails {
                                    __typename
                                    ... on AppRecurringPricing {
                                        price {
                                            amount
                                            currencyCode
                                        }
                                        interval
                                    }
                                }
                            }
                        }
                    }
                }
            }
            """

            variables = {"id": subscription_id}

            response = await self._make_graphql_request(
                shop_domain, access_token, query, variables
            )

            if response.get("errors"):
                logger.error(f"GraphQL errors: {response['errors']}")
                return None

            return response.get("data", {}).get("node")

        except Exception as e:
            logger.error(f"Error getting subscription status: {e}")
            return None

    # ============= INTERNAL METHODS =============

    async def _make_graphql_request(
        self,
        shop_domain: str,
        access_token: str,
        query: str,
        variables: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Make a GraphQL request to Shopify"""
        url = self.base_url.format(shop_domain=shop_domain)

        headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }

        payload = {"query": query, "variables": variables}

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

    async def _store_shopify_subscription(
        self,
        shop_id: str,
        subscription_data: Dict[str, Any],
        plan_name: str,
        monthly_fee: Decimal,
        currency: str,
        confirmation_url: Optional[str] = None,
    ) -> None:
        """Store Shopify subscription data in database"""
        try:
            shop_subscription = await self.billing_repository.get_shop_subscription(
                shop_id
            )
            if not shop_subscription:
                logger.error(f"No active subscription found for shop {shop_id}")
                return

            # Get the line item ID from the response
            line_item_id = None
            if subscription_data.get("lineItems"):
                line_item_id = subscription_data["lineItems"][0].get("id")

            # Update shop subscription with Shopify info using repository
            await self.billing_repository.session.execute(
                update(ShopSubscription)
                .where(and_(ShopSubscription.id == shop_subscription.id))
                .values(
                    shopify_subscription_id=subscription_data["id"],
                    shopify_line_item_id=line_item_id,
                    confirmation_url=confirmation_url,
                    shopify_status="PENDING",
                    status=SubscriptionStatus.PENDING_APPROVAL,
                    updated_at=now_utc(),
                )
            )

            await self.session.flush()
            logger.info(f"Stored Shopify recurring subscription for shop {shop_id}")

        except Exception as e:
            logger.error(f"Error storing Shopify subscription data: {e}")

    async def create_flat_fee_billing_cycle(
        self,
        subscription_id: str,
        cycle_number: int = 1,
        period_fee: Optional[Decimal] = None,
    ) -> Optional[Any]:
        """
        Create a billing cycle for a flat fee subscription.

        This tracks the 30-day billing period for the subscription.
        The billing_cycles table is used to record each monthly period.

        Args:
            subscription_id: Shop subscription ID
            cycle_number: Cycle number (starts at 1)
            period_fee: Monthly fee for this period (from pricing tier)

        Returns:
            Created billing cycle or None
        """
        from app.core.database.models import BillingCycle

        try:
            now = now_utc()
            end_date = now + timedelta(days=30)

            billing_cycle = BillingCycle(
                shop_subscription_id=subscription_id,
                cycle_number=cycle_number,
                start_date=now,
                end_date=end_date,
                status=BillingCycleStatus.ACTIVE,
                period_fee=period_fee,
                activated_at=now,
            )

            self.session.add(billing_cycle)
            await self.session.flush()

            logger.info(
                f"✅ Created billing cycle #{cycle_number} for subscription {subscription_id} "
                f"(fee=${period_fee or 'N/A'})"
            )
            return billing_cycle

        except Exception as e:
            logger.error(f"Error creating billing cycle: {e}")
            return None

    async def complete_trial_by_time(
        self, shop_id: str
    ) -> bool:
        """
        Complete trial based on time elapsed, not revenue threshold.

        Delegates to the repository method to keep trial logic in one place.

        Args:
            shop_id: Shop ID

        Returns:
            True if trial was completed
        """
        return await self.billing_repository.check_trial_expiry_by_time(shop_id)

    async def check_monthly_renewals(self) -> List[Dict[str, Any]]:
        """
        Check for subscriptions that need monthly billing cycle renewal.

        Finds active billing cycles that have expired and creates new ones.

        Returns:
            List of renewed subscription info
        """
        from app.core.database.models import BillingCycle, ShopSubscription
        from sqlalchemy import select, and_, func

        renewed = []

        try:
            # Find subscriptions with expired active cycles
            query = (
                select(BillingCycle, ShopSubscription)
                .join(
                    ShopSubscription,
                    BillingCycle.shop_subscription_id == ShopSubscription.id,
                )
                .where(
                    and_(
                        BillingCycle.status == BillingCycleStatus.ACTIVE,
                        BillingCycle.end_date <= now_utc(),
                        ShopSubscription.status == SubscriptionStatus.ACTIVE,
                    )
                )
            )
            result = await self.session.execute(query)
            expired_cycles = result.fetchall()

            for cycle, sub in expired_cycles:
                # Close current cycle
                cycle.status = BillingCycleStatus.COMPLETED
                cycle.completed_at = now_utc()

                # Create new cycle
                new_cycle = BillingCycle(
                    shop_subscription_id=sub.id,
                    cycle_number=cycle.cycle_number + 1,
                    start_date=now_utc(),
                    end_date=now_utc() + timedelta(days=30),
                    period_fee=sub.effective_monthly_fee,
                    status=BillingCycleStatus.ACTIVE,
                    activated_at=now_utc(),
                )
                self.session.add(new_cycle)

                renewed.append(
                    {
                        "shop_id": sub.shop_id,
                        "subscription_id": sub.id,
                        "cycle_number": new_cycle.cycle_number,
                        "monthly_fee": float(sub.effective_monthly_fee),
                    }
                )

            if renewed:
                await self.session.flush()
                logger.info(f"🔄 Renewed {len(renewed)} billing cycles")

            return renewed

        except Exception as e:
            logger.error(f"Error checking monthly renewals: {e}")
            return []
