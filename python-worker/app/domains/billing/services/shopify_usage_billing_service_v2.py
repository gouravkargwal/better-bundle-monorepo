"""
Shopify Usage-Based Billing Service V2

Updated service to work with the new redesigned billing system.
Uses shopify_subscriptions table instead of billing_plans.
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.billing_repository_v2 import BillingRepositoryV2
from app.core.database.models import (
    SubscriptionStatus,
)

logger = logging.getLogger(__name__)


@dataclass
class UsageRecord:
    """Shopify usage record data"""

    id: str
    subscription_line_item_id: str
    description: str
    price: Dict[str, Any]
    created_at: str


class ShopifyUsageBillingServiceV2:
    """
    Posts usage charges to Shopify.

    Creating the subscription is the Remix app's job — it has the admin session
    and has to hand the merchant a confirmation URL. This service only records
    usage against the line item that subscription produced.
    """

    def __init__(self, session: AsyncSession, billing_repository: BillingRepositoryV2):
        self.session = session
        self.billing_repository = billing_repository
        self.base_url = "https://{shop_domain}/admin/api/{api_version}/graphql.json"
        self._api_version = None

    def _get_api_version(self):
        if self._api_version is None:
            try:
                from app.core.config.settings import settings
                self._api_version = settings.shopify.SHOPIFY_API_VERSION
            except Exception:
                self._api_version = "2026-07"
        return self._api_version

    async def record_usage(
        self,
        shop_id: str,
        shop_domain: str,
        access_token: str,
        subscription_line_item_id: str,
        description: str,
        amount: Decimal,
        currency: str,
        idempotency_key: str = None,
        commission_ids: List[str] = None,
        billing_period: Dict[str, str] = None,
    ) -> Optional[UsageRecord]:
        """
        Record usage for a subscription line item.

        Args:
            shop_id: Shop ID
            shop_domain: Shop domain
            access_token: Shop access token
            subscription_line_item_id: Line item ID from subscription
            description: Description of the usage
            amount: Amount to charge
            currency: Currency code
            idempotency_key: Unique identifier to prevent duplicate charges

        Returns:
            Created usage record or None if failed
        """
        try:
            # GraphQL mutation for recording usage
            mutation = """
            mutation appUsageRecordCreate($subscriptionLineItemId: ID!, $description: String!, $price: MoneyInput!, $idempotencyKey: String) {
                appUsageRecordCreate(
                    subscriptionLineItemId: $subscriptionLineItemId,
                    description: $description,
                    price: $price,
                    idempotencyKey: $idempotencyKey
                ) {
                    userErrors {
                        field
                        message
                    }
                    appUsageRecord {
                        id
                        createdAt
                    }
                }
            }
            """

            # Prepare variables
            variables = {
                "subscriptionLineItemId": subscription_line_item_id,
                "description": description,
                "price": {"amount": float(amount), "currencyCode": currency},
                "idempotencyKey": idempotency_key,
            }

            # Make GraphQL request
            response = await self._make_graphql_request(
                shop_domain, access_token, mutation, variables
            )

            if response.get("errors"):
                logger.error(f"GraphQL errors: {response['errors']}")
                return None

            data = response.get("data", {}).get("appUsageRecordCreate", {})

            if data.get("userErrors"):
                user_errors = data["userErrors"]
                logger.error(f"User errors: {user_errors}")
                # Check if error is due to capped amount exceeded
                error_messages = [
                    error.get("message", "").lower() for error in user_errors
                ]
                cap_exceeded = any(
                    "cap" in msg
                    or "capped" in msg
                    or "limit" in msg
                    or "exceeded" in msg
                    for msg in error_messages
                )
                # Return a special error indicator that can be checked by caller
                error_result = {
                    "error": True,
                    "user_errors": user_errors,
                    "cap_exceeded": cap_exceeded,
                }
                return error_result

            usage_record_data = data.get("appUsageRecord")
            if not usage_record_data:
                logger.error("No usage record data returned")
                return None

            # Store usage record and update billing cycle usage as best-effort.
            # A Shopify charge is the source of truth; if local tracking fails we
            # still mark the commission RECORDED and surface the bookkeeping error
            # in logs. We do NOT let bookkeeping failure corrupt commission state.
            try:
                await self._store_usage_record(
                    shop_id,
                    usage_record_data,
                    description,
                    amount,
                    currency,
                    idempotency_key,
                    commission_ids,
                    billing_period,
                )
            except Exception as e:
                logger.error(
                    f"Failed to store usage record/update billing cycle for shop {shop_id}: {e}. "
                    f"Shopify charge succeeded; local tracking is behind."
                )

            logger.info(
                f"✅ Recorded usage for shop {shop_id}: {usage_record_data['id']} "
                f"(usage tracked in billing cycle)"
            )

            return UsageRecord(
                id=usage_record_data["id"],
                subscription_line_item_id=subscription_line_item_id,
                description=description,
                price={"amount": float(amount), "currencyCode": currency},
                created_at=usage_record_data["createdAt"],
            )

        except Exception as e:
            logger.error(f"Error recording usage for shop {shop_id}: {e}")
            return None

    async def get_subscription_status(
        self, shop_domain: str, access_token: str, subscription_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get subscription status and usage information.

        Args:
            shop_domain: Shop domain
            access_token: Shop access token
            subscription_id: Subscription ID

        Returns:
            Subscription status data or None if failed
        """
        try:
            # GraphQL query for subscription status
            query = """
            query getSubscription($id: ID!) {
                node(id: $id) {
                    ... on AppSubscription {
                        id
                        name
                        status
                        lineItems {
                            id
                            plan {
                                pricingDetails {
                                    __typename
                                    ... on AppUsagePricing {
                                        terms
                                        cappedAmount {
                                            amount
                                            currencyCode
                                        }
                                        balanceUsed {
                                            amount
                                            currencyCode
                                        }
                                    }
                                }
                            }
                        }
                        createdAt
                    }
                }
            }
            """

            # Prepare variables
            variables = {"id": subscription_id}

            # Make GraphQL request
            response = await self._make_graphql_request(
                shop_domain, access_token, query, variables
            )

            if response.get("errors"):
                logger.error(f"GraphQL errors: {response['errors']}")
                return None

            data = response.get("data", {}).get("node")
            if not data:
                logger.error("No subscription data returned")
                return None

            return data

        except Exception as e:
            logger.error(f"Error getting subscription status: {e}")
            return None

    async def _make_graphql_request(
        self, shop_domain: str, access_token: str, query: str, variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make a GraphQL request to Shopify"""
        url = self.base_url.format(
            shop_domain=shop_domain, api_version=self._get_api_version()
        )

        headers = {
            "X-Shopify-Access-Token": access_token,
            "Content-Type": "application/json",
        }

        payload = {"query": query, "variables": variables}

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

    async def _store_usage_record(
        self,
        shop_id: str,
        usage_record_data: Dict[str, Any],
        description: str,
        amount: Decimal,
        currency: str,
        idempotency_key: str = None,
        commission_ids: List[str] = None,
        billing_period: Dict[str, str] = None,
    ) -> None:
        """Store usage record in database statelessly (best-effort cycle update if legacy cycle exists)."""
        try:
            # Get shop subscription
            shop_subscription = await self.billing_repository.get_shop_subscription(
                shop_id
            )
            if not shop_subscription:
                logger.debug(f"No shop subscription found for shop {shop_id}")
                return

            # Best-effort update of active legacy billing cycle if one exists
            current_cycle = await self.billing_repository.get_current_billing_cycle(
                shop_subscription.id
            )
            if not current_cycle:
                logger.debug(
                    f"No active billing cycle found for shop {shop_id} (stateless billing)"
                )
                return

            await self.billing_repository.update_billing_cycle_usage(
                current_cycle.id,
                amount,
                {
                    "usage_record_id": usage_record_data["id"],
                    "description": description,
                    "recorded_at": usage_record_data["createdAt"],
                    "type": "usage_based",
                    "idempotency_key": idempotency_key,
                    "commission_ids": commission_ids or [],
                    "billing_period": billing_period or {},
                },
            )
            logger.info(
                f"✅ Stored usage record: +${amount} for shop {shop_id} "
                f"(Shopify record: {usage_record_data['id']})"
            )
        except Exception as e:
            logger.error(f"Error in _store_usage_record: {e}")
