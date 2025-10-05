"""
Shopify Usage-Based Billing Service

This service handles integration with Shopify's Usage-Based Subscriptions API
for creating subscriptions, recording usage, and managing billing.
"""

import logging
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import httpx
from prisma import Prisma

from ..repositories.billing_repository import BillingRepository, BillingPeriod

logger = logging.getLogger(__name__)

# Currency symbols mapping
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


class ShopifyUsageBillingService:
    """Service for managing Shopify usage-based billing"""

    def __init__(self, prisma: Prisma, billing_repository: BillingRepository):
        self.prisma = prisma
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
                        updatedAt
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

            # Store subscription in database
            await self._store_subscription(shop_id, subscription_data)

            logger.info(
                f"Created usage subscription for shop {shop_id}: {subscription_data['id']}"
            )

            return UsageSubscription(
                id=subscription_data["id"],
                name=subscription_data["name"],
                status=subscription_data["status"],
                line_items=subscription_data["lineItems"],
                created_at=subscription_data["createdAt"],
                updated_at=subscription_data["updatedAt"],
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

        Returns:
            Created usage record or None if failed
        """
        try:
            # GraphQL mutation for recording usage
            mutation = """
            mutation appUsageRecordCreate($subscriptionLineItemId: ID!, $description: String!, $price: MoneyInput!) {
                appUsageRecordCreate(
                    subscriptionLineItemId: $subscriptionLineItemId,
                    description: $description,
                    price: $price
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
                logger.error(f"User errors: {data['userErrors']}")
                return None

            usage_record_data = data.get("appUsageRecord")
            if not usage_record_data:
                logger.error("No usage record data returned")
                return None

            # Store usage record in database
            await self._store_usage_record(
                shop_id, usage_record_data, description, amount, currency
            )

            logger.info(f"Recorded usage for shop {shop_id}: {usage_record_data['id']}")

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
                        updatedAt
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

    async def _store_subscription(
        self, shop_id: str, subscription_data: Dict[str, Any]
    ) -> None:
        """Store subscription data in database"""
        try:
            # Store subscription in billing plan
            await self.prisma.billingplan.update_many(
                where={"shopId": shop_id, "status": "active"},
                data={
                    "configuration": {
                        "subscription_id": subscription_data["id"],
                        "subscription_status": subscription_data["status"],
                        "line_items": subscription_data["lineItems"],
                        "usage_based": True,
                        "capped_amount": subscription_data["lineItems"][0]["plan"][
                            "pricingDetails"
                        ]["cappedAmount"]["amount"],
                        "currency": subscription_data["lineItems"][0]["plan"][
                            "pricingDetails"
                        ]["cappedAmount"]["currencyCode"],
                    }
                },
            )

            logger.info(f"Stored subscription data for shop {shop_id}")
        except Exception as e:
            logger.error(f"Error storing subscription data: {e}")

    async def _store_usage_record(
        self,
        shop_id: str,
        usage_record_data: Dict[str, Any],
        description: str,
        amount: Decimal,
        currency: str,
    ) -> None:
        """Store usage record in database"""
        try:
            # Create billing invoice for usage record
            await self.prisma.billinginvoice.create(
                {
                    "data": {
                        "shopId": shop_id,
                        "planId": None,  # Usage-based doesn't have a plan ID
                        "invoiceNumber": f"USAGE-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{shop_id[:5]}",
                        "amount": amount,
                        "currency": currency,
                        "status": "pending",
                        "period": {
                            "start_date": datetime.utcnow().isoformat(),
                            "end_date": datetime.utcnow().isoformat(),
                            "cycle": "usage",
                        },
                        "metadata": {
                            "usage_record_id": usage_record_data["id"],
                            "description": description,
                            "recorded_at": usage_record_data["createdAt"],
                            "type": "usage_based",
                        },
                    }
                }
            )

            logger.info(f"Stored usage record for shop {shop_id}")
        except Exception as e:
            logger.error(f"Error storing usage record: {e}")

    async def process_monthly_usage_billing(
        self, shop_id: str, billing_result: Dict[str, Any]
    ) -> Optional[UsageRecord]:
        """
        Process monthly usage billing for a shop.

        Args:
            shop_id: Shop ID
            billing_result: Billing calculation result

        Returns:
            Created usage record or None if failed
        """
        try:
            # Get shop information
            shop = await self.prisma.shop.find_unique(
                where={"id": shop_id},
                select={"domain": True, "accessToken": True, "currencyCode": True},
            )

            if not shop:
                logger.error(f"Shop {shop_id} not found")
                return None

            if not shop.accessToken:
                logger.error(f"No access token for shop {shop_id}")
                return None

            # Get subscription information
            billing_plan = await self.prisma.billingplan.find_first(
                where={"shopId": shop_id, "status": "active"}
            )

            if not billing_plan or not billing_plan.configuration:
                logger.error(f"No active billing plan found for shop {shop_id}")
                return None

            subscription_id = billing_plan.configuration.get("subscription_id")
            line_items = billing_plan.configuration.get("line_items", [])

            if not subscription_id or not line_items:
                logger.error(f"No subscription data found for shop {shop_id}")
                return None

            # Get the first line item ID
            line_item_id = line_items[0]["id"]

            # Calculate usage amount (3% of attributed revenue)
            attributed_revenue = Decimal(
                str(billing_result["metrics"]["attributed_revenue"])
            )
            usage_amount = attributed_revenue * Decimal("0.03")

            # Skip if no revenue to bill
            if usage_amount <= 0:
                logger.info(f"No usage to bill for shop {shop_id}")
                return None

            # Create usage description
            currency = shop.currencyCode or "USD"
            currency_symbol = self._get_currency_symbol(currency)
            description = (
                f"Better Bundle - {billing_result['period']['start_date'][:7]} "
                f"({currency_symbol}{attributed_revenue:.2f} attributed revenue)"
            )

            # Record usage
            usage_record = await self.record_usage(
                shop_id=shop_id,
                shop_domain=shop.domain,
                access_token=shop.accessToken,
                subscription_line_item_id=line_item_id,
                description=description,
                amount=usage_amount,
                currency=currency,
            )

            if usage_record:
                logger.info(
                    f"Recorded usage for shop {shop_id}: {currency_symbol}{usage_amount} "
                    f"({currency_symbol}{attributed_revenue} attributed revenue)"
                )
                return usage_record
            else:
                logger.error(f"Failed to record usage for shop {shop_id}")
                return None

        except Exception as e:
            logger.error(
                f"Error processing monthly usage billing for shop {shop_id}: {e}"
            )
            return None
