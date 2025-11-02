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

# Currency symbols mapping (same as original)
CURRENCY_SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "CAD": "C$",
    "AUD": "A$",
    "JPY": "¥",
    "CHF": "CHF",
    "SEK": "kr",
    "NOK": "kr",
    "DKK": "kr",
    "PLN": "zł",
    "CZK": "Kč",
    "HUF": "Ft",
    "BGN": "лв",
    "RON": "lei",
    "HRK": "kn",
    "RSD": "дин",
    "MKD": "ден",
    "BAM": "КМ",
    "ALL": "L",
    "ISK": "kr",
    "UAH": "₴",
    "RUB": "₽",
    "BYN": "Br",
    "KZT": "₸",
    "GEL": "₾",
    "AMD": "֏",
    "AZN": "₼",
    "KGS": "с",
    "TJS": "SM",
    "TMT": "T",
    "UZS": "so'm",
    "MNT": "₮",
    "KHR": "៛",
    "LAK": "₭",
    "VND": "₫",
    "THB": "฿",
    "MYR": "RM",
    "SGD": "S$",
    "IDR": "Rp",
    "PHP": "₱",
    "INR": "₹",
    "PKR": "₨",
    "BDT": "৳",
    "LKR": "₨",
    "NPR": "₨",
    "BTN": "Nu",
    "MVR": "ރ",
    "AFN": "؋",
    "IRR": "﷼",
    "IQD": "ع.د",
    "JOD": "د.ا",
    "KWD": "د.ك",
    "LBP": "ل.ل",
    "OMR": "ر.ع",
    "QAR": "ر.ق",
    "SAR": "ر.س",
    "SYP": "ل.س",
    "AED": "د.إ",
    "YER": "﷼",
    "ILS": "₪",
    "JMD": "J$",
    "BBD": "Bds$",
    "BZD": "BZ$",
    "XCD": "EC$",
    "KYD": "CI$",
    "TTD": "TT$",
    "AWG": "ƒ",
    "BSD": "B$",
    "BMD": "BD$",
    "BND": "B$",
    "FJD": "FJ$",
    "GYD": "G$",
    "LRD": "L$",
    "SBD": "SI$",
    "SRD": "Sr$",
    "TVD": "TV$",
    "VES": "Bs.S",
    "ARS": "$",
    "BOB": "Bs",
    "BRL": "R$",
    "CLP": "$",
    "COP": "$",
    "CRC": "₡",
    "CUP": "$",
    "DOP": "RD$",
    "GTQ": "Q",
    "HNL": "L",
    "MXN": "$",
    "NIO": "C$",
    "PAB": "B/.",
    "PEN": "S/",
    "PYG": "₲",
    "UYU": "$U",
    "VEF": "Bs",
    "ZAR": "R",
    "BWP": "P",
    "LSL": "L",
    "NAD": "N$",
    "SZL": "L",
    "ZMW": "ZK",
    "ZWL": "Z$",
    "AOA": "Kz",
    "CDF": "FC",
    "GMD": "D",
    "GNF": "FG",
    "KES": "KSh",
    "MAD": "د.م.",
    "MGA": "Ar",
    "MUR": "₨",
    "NGN": "₦",
    "RWF": "RF",
    "SLL": "Le",
    "SOS": "S",
    "TZS": "TSh",
    "UGX": "USh",
    "XAF": "FCFA",
    "XOF": "CFA",
}


@dataclass
class UsageSubscription:
    """Shopify usage-based subscription data"""

    id: str
    name: str
    status: str
    line_items: List[Dict[str, Any]]
    created_at: str
    updated_at: str


@dataclass
class UsageRecord:
    """Shopify usage record data"""

    id: str
    subscription_line_item_id: str
    description: str
    price: Dict[str, Any]
    created_at: str


class ShopifyUsageBillingServiceV2:
    """Updated service for managing Shopify usage-based billing with new system"""

    def __init__(self, session: AsyncSession, billing_repository: BillingRepositoryV2):
        self.session = session
        self.billing_repository = billing_repository
        self.base_url = "https://{shop_domain}/admin/api/2024-01/graphql.json"

    def _get_currency_symbol(self, currency_code: str) -> str:
        """Get currency symbol for display"""
        return CURRENCY_SYMBOLS.get(currency_code, currency_code)

    async def create_usage_subscription(
        self,
        shop_id: str,
        shop_domain: str,
        access_token: str,
        currency: str = "USD",
        capped_amount: float = 1000.0,
    ) -> Optional[UsageSubscription]:
        """
        Create a usage-based subscription for a shop.

        Args:
            shop_id: Shop ID
            shop_domain: Shop domain
            access_token: Shop access token
            currency: Store currency
            capped_amount: Maximum amount to charge per 30-day cycle

        Returns:
            Created subscription or None if failed
        """
        try:
            # GraphQL mutation for creating usage-based subscription
            mutation = """
            mutation appSubscriptionCreate($name: String!, $returnUrl: URL!, $lineItems: [AppSubscriptionLineItemInput!]!) {
                appSubscriptionCreate(
                    name: $name,
                    returnUrl: $returnUrl,
                    lineItems: $lineItems
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
            variables = {
                "name": "Better Bundle - Usage-Based Billing",
                "returnUrl": f"https://your-app.com/billing/return?shop={shop_domain}",
                "lineItems": [
                    {
                        "plan": {
                            "appUsagePricingDetails": {
                                "terms": f"3% of attributed revenue (max {self._get_currency_symbol(currency)}{capped_amount:.2f} per month)",
                                "cappedAmount": {
                                    "amount": capped_amount,
                                    "currencyCode": currency,
                                },
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

            # Store subscription in database using new system
            await self._store_shopify_subscription(shop_id, subscription_data)

            logger.info(
                f"Created usage subscription for shop {shop_id}: {subscription_data['id']}"
            )

            return UsageSubscription(
                id=subscription_data["id"],
                name=subscription_data["name"],
                status=subscription_data["status"],
                line_items=subscription_data["lineItems"],
                created_at=subscription_data["createdAt"],
                updated_at=subscription_data.get(
                    "updatedAt", subscription_data["createdAt"]
                ),  # Fallback to createdAt
            )

        except Exception as e:
            logger.error(f"Error creating usage subscription for shop {shop_id}: {e}")
            return None

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

            # ✅ CRITICAL: Store usage record AND update billing cycle usage
            # This must succeed before commission can be marked as RECORDED
            # If this fails, the exception will propagate and commission stays PENDING
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
                    f"❌ Failed to store usage record/update billing cycle: {e}. "
                    f"Commission will NOT be marked as RECORDED."
                )
                # Re-raise so caller knows usage tracking failed
                raise

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
        self, shop_id: str, subscription_data: Dict[str, Any]
    ) -> None:
        """Store Shopify subscription data in database using new system"""
        try:
            # Get shop subscription
            shop_subscription = await self.billing_repository.get_shop_subscription(
                shop_id
            )
            if not shop_subscription:
                logger.error(f"No shop subscription found for shop {shop_id}")
                return

            # Create Shopify subscription record
            shopify_sub = await self.billing_repository.create_shopify_subscription(
                shop_subscription_id=shop_subscription.id,
                shopify_subscription_id=subscription_data["id"],
                shopify_line_item_id=(
                    subscription_data["lineItems"][0]["id"]
                    if subscription_data["lineItems"]
                    else None
                ),
                confirmation_url=f"https://your-app.com/billing/return?shop={shop_id}",
            )

            if shopify_sub:
                # Update shop subscription status
                await self.billing_repository.update_shop_subscription_status(
                    shop_subscription.id, SubscriptionStatus.PENDING_APPROVAL
                )

                logger.info(f"Stored Shopify subscription data for shop {shop_id}")
            else:
                logger.error(
                    f"Failed to create Shopify subscription record for shop {shop_id}"
                )

        except Exception as e:
            logger.error(f"Error storing Shopify subscription data: {e}")

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
        """Store usage record in database using new system"""
        try:
            # Get shop subscription
            shop_subscription = await self.billing_repository.get_shop_subscription(
                shop_id
            )
            if not shop_subscription:
                logger.error(f"No shop subscription found for shop {shop_id}")
                return

            # Get current billing cycle
            current_cycle = await self.billing_repository.get_current_billing_cycle(
                shop_subscription.id
            )
            if not current_cycle:
                logger.error(f"No active billing cycle found for shop {shop_id}")
                return

            # ✅ CRITICAL: Update usage ONLY when Shopify successfully creates the usage record
            # This ensures:
            # 1. Usage accurately reflects what's actually charged to Shopify
            # 2. Failed recordings don't count as usage
            # 3. PENDING commissions don't increment usage until RECORDED

            # Check if commission was already counted (prevent double-counting on retries)
            # If commission_ids is provided, check if any were already counted
            from app.core.database.models.commission import CommissionRecord
            from sqlalchemy import select, and_
            from app.core.database.models.enums import CommissionStatus

            already_counted = False
            if commission_ids:
                # Check if any of these commissions are already RECORDED
                query = select(CommissionRecord).where(
                    and_(
                        CommissionRecord.id.in_(commission_ids),
                        CommissionRecord.status == CommissionStatus.RECORDED,
                        CommissionRecord.billing_cycle_id == current_cycle.id,
                    )
                )
                result = await self.billing_repository.session.execute(query)
                existing_recorded = result.scalars().first()
                if existing_recorded:
                    already_counted = True
                    logger.warning(
                        f"⚠️ Commission {existing_recorded.id} already RECORDED - skipping usage update to prevent double-counting"
                    )

            if not already_counted:
                # Update billing cycle usage - only for successfully recorded commissions
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
                    f"✅ Updated billing cycle usage: +${amount} for shop {shop_id} "
                    f"(cycle: {current_cycle.id}, Shopify record: {usage_record_data['id']})"
                )

                # ✅ CRITICAL: Check if cap is reached AFTER usage is updated
                # Refresh cycle to get updated usage_amount
                await self.billing_repository.session.refresh(current_cycle)

                # Check if cap is now reached
                if current_cycle.remaining_cap <= Decimal("0"):
                    logger.warning(
                        f"🛑 Cap reached after usage update: "
                        f"usage=${current_cycle.usage_amount}, cap=${current_cycle.current_cap_amount}"
                    )

                    # Suspend shop and subscription - create CommissionServiceV2 to use suspension method
                    from app.domains.billing.services.commission_service_v2 import (
                        CommissionServiceV2,
                    )
                    from app.repository.CommissionRepository import CommissionRepository
                    from app.repository.PurchaseAttributionRepository import (
                        PurchaseAttributionRepository,
                    )

                    commission_repo = CommissionRepository(
                        self.billing_repository.session
                    )
                    purchase_attr_repo = PurchaseAttributionRepository(
                        self.billing_repository.session
                    )
                    commission_service = CommissionServiceV2(
                        self.billing_repository.session
                    )
                    commission_service.billing_repository = self.billing_repository
                    commission_service.commission_repository = commission_repo
                    commission_service.purchase_attribution_repository = (
                        purchase_attr_repo
                    )

                    await commission_service._suspend_shop_for_cap_reached(shop_id)
            else:
                logger.info(
                    f"✅ Stored Shopify usage record {usage_record_data['id']} for shop {shop_id} "
                    f"(amount: {amount}) - Usage already counted"
                )
        except Exception as e:
            logger.error(f"Error storing usage record: {e}")
