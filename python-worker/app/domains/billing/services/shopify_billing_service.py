"""
Shopify Billing Service

This service handles integration with Shopify's Billing API for creating charges,
processing payments, and handling billing webhooks.
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
    "LRD": "L$",
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
    "ZAR": "R",
}


@dataclass
class ShopifyCharge:
    """Shopify billing charge data"""

    id: str
    shop_id: str
    amount: Decimal
    currency: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]


@dataclass
class ShopifyBillingWebhook:
    """Shopify billing webhook data"""

    shop_id: str
    charge_id: str
    status: str
    amount: Decimal
    currency: str
    occurred_at: datetime
    metadata: Dict[str, Any]


class ShopifyBillingService:
    """
    Service for integrating with Shopify's Billing API.
    """

    def __init__(self, prisma: Prisma):
        self.prisma = prisma
        self.billing_repository = BillingRepository(prisma)

    def _get_currency_symbol(self, currency_code: str) -> str:
        """Get currency symbol for display"""
        return CURRENCY_SYMBOLS.get(currency_code, currency_code)

    async def create_billing_charge(
        self,
        shop_id: str,
        shop_domain: str,
        access_token: str,
        amount: Decimal,
        description: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ShopifyCharge:
        """
        Create a billing charge in Shopify.

        Args:
            shop_id: Shop ID
            shop_domain: Shop domain
            access_token: Shopify access token
            amount: Charge amount
            description: Charge description
            metadata: Additional metadata

        Returns:
            Created Shopify charge
        """
        try:
            logger.info(
                f"Creating Shopify billing charge for shop {shop_id}: ${amount}"
            )

            # Prepare charge data
            charge_data = {
                "recurring_application_charge": {
                    "name": description,
                    "price": str(amount),
                    "return_url": f"https://{shop_domain}/admin/apps/better-bundle/billing/success",
                    "test": self._is_test_environment(),
                    "trial_days": 0,
                    "capped_amount": str(amount),
                    "terms": "Pay-as-Performance billing based on attributed revenue",
                }
            }

            # Add metadata if provided
            if metadata:
                charge_data["recurring_application_charge"]["metadata"] = json.dumps(
                    metadata
                )

            # Make API request
            url = f"{self.base_url.format(shop_domain=shop_domain)}/recurring_application_charges.json"
            headers = {
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=charge_data, headers=headers)
                response.raise_for_status()

                charge_response = response.json()
                charge_info = charge_response["recurring_application_charge"]

                # Create ShopifyCharge object
                charge = ShopifyCharge(
                    id=str(charge_info["id"]),
                    shop_id=shop_id,
                    amount=Decimal(str(charge_info["price"])),
                    currency="USD",  # Shopify charges are typically in USD
                    description=charge_info["name"],
                    status=charge_info["status"],
                    created_at=datetime.fromisoformat(
                        charge_info["created_at"].replace("Z", "+00:00")
                    ),
                    updated_at=datetime.fromisoformat(
                        charge_info["updated_at"].replace("Z", "+00:00")
                    ),
                    metadata=json.loads(charge_info.get("metadata", "{}")),
                )

                # Store charge in database
                await self._store_shopify_charge(charge)

                logger.info(f"Created Shopify charge {charge.id} for shop {shop_id}")
                return charge

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error creating Shopify charge for shop {shop_id}: {e.response.status_code} - {e.response.text}"
            )
            raise Exception(f"Shopify API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"Error creating Shopify charge for shop {shop_id}: {e}")
            raise

    async def get_charge_status(
        self, shop_domain: str, access_token: str, charge_id: str
    ) -> Optional[ShopifyCharge]:
        """
        Get the status of a Shopify billing charge.

        Args:
            shop_domain: Shop domain
            access_token: Shopify access token
            charge_id: Charge ID

        Returns:
            Charge status or None if not found
        """
        try:
            url = f"{self.base_url.format(shop_domain=shop_domain)}/recurring_application_charges/{charge_id}.json"
            headers = {
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                charge_response = response.json()
                charge_info = charge_response["recurring_application_charge"]

                return ShopifyCharge(
                    id=str(charge_info["id"]),
                    shop_id="",  # Will be filled from database
                    amount=Decimal(str(charge_info["price"])),
                    currency="USD",
                    description=charge_info["name"],
                    status=charge_info["status"],
                    created_at=datetime.fromisoformat(
                        charge_info["created_at"].replace("Z", "+00:00")
                    ),
                    updated_at=datetime.fromisoformat(
                        charge_info["updated_at"].replace("Z", "+00:00")
                    ),
                    metadata=json.loads(charge_info.get("metadata", "{}")),
                )

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Shopify charge {charge_id} not found")
                return None
            logger.error(
                f"HTTP error getting Shopify charge {charge_id}: {e.response.status_code}"
            )
            raise
        except Exception as e:
            logger.error(f"Error getting Shopify charge {charge_id}: {e}")
            raise

    async def cancel_charge(
        self, shop_domain: str, access_token: str, charge_id: str
    ) -> bool:
        """
        Cancel a Shopify billing charge.

        Args:
            shop_domain: Shop domain
            access_token: Shopify access token
            charge_id: Charge ID

        Returns:
            True if cancelled successfully
        """
        try:
            url = f"{self.base_url.format(shop_domain=shop_domain)}/recurring_application_charges/{charge_id}.json"
            headers = {
                "X-Shopify-Access-Token": access_token,
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.delete(url, headers=headers)
                response.raise_for_status()

                logger.info(f"Cancelled Shopify charge {charge_id}")
                return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error cancelling Shopify charge {charge_id}: {e.response.status_code}"
            )
            return False
        except Exception as e:
            logger.error(f"Error cancelling Shopify charge {charge_id}: {e}")
            return False

    async def process_billing_webhook(self, webhook_data: Dict[str, Any]) -> bool:
        """
        Process a Shopify billing webhook.

        Args:
            webhook_data: Webhook payload from Shopify

        Returns:
            True if processed successfully
        """
        try:
            logger.info(f"Processing Shopify billing webhook: {webhook_data.get('id')}")

            # Parse webhook data
            webhook = self._parse_billing_webhook(webhook_data)

            # Update billing status based on webhook
            await self._update_billing_status(webhook)

            # Create billing event
            await self.billing_repository.create_billing_event(
                shop_id=webhook.shop_id,
                event_type=f"shopify_webhook_{webhook.status}",
                data={
                    "charge_id": webhook.charge_id,
                    "amount": float(webhook.amount),
                    "currency": webhook.currency,
                    "status": webhook.status,
                },
                metadata=webhook.metadata,
            )

            logger.info(
                f"Processed Shopify billing webhook for charge {webhook.charge_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error processing Shopify billing webhook: {e}")
            return False

    async def create_monthly_billing_charge(
        self, shop_id: str, billing_result: Dict[str, Any]
    ) -> Optional[ShopifyCharge]:
        """
        Create a monthly billing charge for a shop.

        Args:
            shop_id: Shop ID
            billing_result: Billing calculation result

        Returns:
            Created Shopify charge or None if failed
        """
        try:
            # Get shop information
            shop = await self.prisma.shop.find_unique(
                where={"id": shop_id}, select={"domain": True, "accessToken": True}
            )

            if not shop:
                logger.error(f"Shop {shop_id} not found")
                return None

            if not shop.accessToken:
                logger.error(f"No access token for shop {shop_id}")
                return None

            # Prepare charge details
            amount = Decimal(str(billing_result["calculation"]["final_fee"]))
            currency = billing_result["calculation"]["currency"]
            period = billing_result["period"]

            # Get currency symbol for description
            currency_symbol = self._get_currency_symbol(currency)

            description = (
                f"Better Bundle - {period['start_date'][:7]} "
                f"({currency_symbol}{billing_result['metrics']['attributed_revenue']:.2f} attributed revenue)"
            )

            metadata = {
                "billing_period": period,
                "attributed_revenue": billing_result["metrics"]["attributed_revenue"],
                "total_interactions": billing_result["metrics"]["total_interactions"],
                "conversion_rate": billing_result["metrics"]["conversion_rate"],
                "extension_breakdown": billing_result["breakdown"].get(
                    "extension_breakdown", {}
                ),
            }

            # Create the charge
            charge = await self.create_billing_charge(
                shop_id=shop_id,
                shop_domain=shop.domain,
                access_token=shop.accessToken,
                amount=amount,
                description=description,
                metadata=metadata,
            )

            # Create billing invoice
            await self._create_billing_invoice_from_charge(
                shop_id, charge, billing_result
            )

            return charge

        except Exception as e:
            logger.error(
                f"Error creating monthly billing charge for shop {shop_id}: {e}"
            )
            return None

    async def _store_shopify_charge(self, charge: ShopifyCharge) -> None:
        """Store Shopify charge in database."""
        try:
            # Store in a custom table or extend existing tables
            # For now, we'll store in billing events
            await self.billing_repository.create_billing_event(
                shop_id=charge.shop_id,
                event_type="shopify_charge_created",
                data={
                    "charge_id": charge.id,
                    "amount": float(charge.amount),
                    "currency": charge.currency,
                    "description": charge.description,
                    "status": charge.status,
                },
                metadata=charge.metadata,
            )
        except Exception as e:
            logger.error(f"Error storing Shopify charge {charge.id}: {e}")

    def _parse_billing_webhook(
        self, webhook_data: Dict[str, Any]
    ) -> ShopifyBillingWebhook:
        """Parse Shopify billing webhook data."""
        try:
            # Extract charge information from webhook
            charge_data = webhook_data.get("recurring_application_charge", {})

            return ShopifyBillingWebhook(
                shop_id=webhook_data.get("shop_id", ""),
                charge_id=str(charge_data.get("id", "")),
                status=charge_data.get("status", "unknown"),
                amount=Decimal(str(charge_data.get("price", 0))),
                currency="USD",
                occurred_at=datetime.utcnow(),
                metadata={
                    "webhook_id": webhook_data.get("id"),
                    "shop_domain": webhook_data.get("shop_domain"),
                    "charge_name": charge_data.get("name"),
                    "raw_data": webhook_data,
                },
            )
        except Exception as e:
            logger.error(f"Error parsing billing webhook: {e}")
            raise

    async def _update_billing_status(self, webhook: ShopifyBillingWebhook) -> None:
        """Update billing status based on webhook."""
        try:
            # Find the corresponding invoice
            invoices = await self.billing_repository.get_shop_invoices(webhook.shop_id)

            for invoice in invoices:
                # Check if this invoice corresponds to the webhook
                if self._invoice_matches_webhook(invoice, webhook):
                    # Update invoice status
                    payment_data = {
                        "payment_method": "shopify_billing",
                        "payment_reference": webhook.charge_id,
                    }

                    await self.billing_repository.update_invoice_status(
                        invoice.id, webhook.status, payment_data
                    )
                    break

        except Exception as e:
            logger.error(
                f"Error updating billing status for webhook {webhook.charge_id}: {e}"
            )

    def _invoice_matches_webhook(self, invoice, webhook: ShopifyBillingWebhook) -> bool:
        """Check if an invoice matches a webhook."""
        try:
            # Simple matching logic - can be enhanced
            invoice_amount = float(invoice.total)
            webhook_amount = float(webhook.amount)

            # Allow for small differences due to rounding
            return abs(invoice_amount - webhook_amount) < 0.01
        except Exception:
            return False

    async def _create_billing_invoice_from_charge(
        self, shop_id: str, charge: ShopifyCharge, billing_result: Dict[str, Any]
    ) -> None:
        """Create billing invoice from Shopify charge."""
        try:
            # Get billing plan
            billing_plan = await self.billing_repository.get_billing_plan(shop_id)
            if not billing_plan:
                logger.error(f"No billing plan found for shop {shop_id}")
                return

            # Create billing period
            period = BillingPeriod(
                start_date=datetime.fromisoformat(
                    billing_result["period"]["start_date"]
                ),
                end_date=datetime.fromisoformat(billing_result["period"]["end_date"]),
                cycle=billing_result["period"]["cycle"],
            )

            # Create invoice data
            invoice_data = {
                "subtotal": float(charge.amount),
                "taxes": 0.0,  # No taxes for now
                "discounts": 0.0,
                "total": float(charge.amount),
                "currency": charge.currency,
            }

            # Create the invoice
            await self.billing_repository.create_billing_invoice(
                shop_id=shop_id,
                plan_id=billing_plan.id,
                metrics_id="",  # Will be linked later
                period=period,
                invoice_data=invoice_data,
            )

        except Exception as e:
            logger.error(f"Error creating billing invoice from charge {charge.id}: {e}")

    def _is_test_environment(self) -> bool:
        """Check if we're in a test environment."""
        # This should be configured based on your environment
        import os

        return os.getenv("ENVIRONMENT", "production") == "test"

    async def get_shop_billing_status(self, shop_id: str) -> Dict[str, Any]:
        """
        Get billing status for a shop.

        Args:
            shop_id: Shop ID

        Returns:
            Billing status information
        """
        try:
            # Get recent invoices
            invoices = await self.billing_repository.get_shop_invoices(shop_id, limit=5)

            # Get billing plan
            billing_plan = await self.billing_repository.get_billing_plan(shop_id)

            return {
                "shop_id": shop_id,
                "billing_plan": {
                    "id": billing_plan.id if billing_plan else None,
                    "name": billing_plan.name if billing_plan else None,
                    "type": billing_plan.type if billing_plan else None,
                    "status": billing_plan.status if billing_plan else None,
                },
                "recent_invoices": [
                    {
                        "id": invoice.id,
                        "invoice_number": invoice.invoiceNumber,
                        "status": invoice.status,
                        "total": float(invoice.total),
                        "currency": invoice.currency,
                        "created_at": invoice.createdAt.isoformat(),
                    }
                    for invoice in invoices
                ],
            }

        except Exception as e:
            logger.error(f"Error getting billing status for shop {shop_id}: {e}")
            return {"error": str(e)}
