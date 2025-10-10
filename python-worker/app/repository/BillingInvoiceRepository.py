"""
Billing Invoice Repository

Repository for BillingInvoice table operations.
Handles CRUD operations for Shopify billing invoices.
"""

import logging
from typing import Optional, List, Dict, Any
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database.models import BillingInvoice, ShopSubscription
from app.core.database.models.enums import InvoiceStatus

logger = logging.getLogger(__name__)


class BillingInvoiceRepository:
    """Repository for BillingInvoice operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_from_webhook(
        self, shop_subscription_id: str, webhook_data: Dict[str, Any]
    ) -> Optional[BillingInvoice]:
        """Create a new billing invoice from Shopify webhook data."""
        try:
            # Extract data from webhook
            shopify_invoice_id = webhook_data.get("id")
            invoice_number = webhook_data.get("invoice_number")
            amount_due = webhook_data.get("amount_due", 0)
            amount_paid = webhook_data.get("amount_paid", 0)
            total_amount = webhook_data.get("total", 0)
            currency = webhook_data.get("currency", "USD")

            # Parse dates
            invoice_date = webhook_data.get("created_at")
            due_date = webhook_data.get("due_date")
            paid_at = webhook_data.get("paid_at")

            # Determine status
            status = self._determine_status(webhook_data)

            # Create invoice
            invoice = BillingInvoice(
                shop_subscription_id=shop_subscription_id,
                shopify_invoice_id=str(shopify_invoice_id),
                invoice_number=invoice_number,
                amount_due=amount_due,
                amount_paid=amount_paid,
                total_amount=total_amount,
                currency=currency,
                invoice_date=invoice_date,
                due_date=due_date,
                paid_at=paid_at,
                status=status,
                description=webhook_data.get("description"),
                line_items=webhook_data.get("line_items", []),
                shopify_response=webhook_data,
                payment_method=webhook_data.get("payment_method"),
                payment_reference=webhook_data.get("payment_reference"),
            )

            self.session.add(invoice)
            await self.session.commit()
            await self.session.refresh(invoice)

            logger.info(
                f"Created billing invoice {shopify_invoice_id} for subscription {shop_subscription_id}"
            )
            return invoice

        except Exception as e:
            logger.error(f"Error creating billing invoice: {e}")
            await self.session.rollback()
            return None

    async def get_by_shopify_id(
        self, shopify_invoice_id: str
    ) -> Optional[BillingInvoice]:
        """Get billing invoice by Shopify invoice ID."""
        try:
            query = select(BillingInvoice).where(
                BillingInvoice.shopify_invoice_id == shopify_invoice_id
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting billing invoice by Shopify ID: {e}")
            return None

    async def get_by_subscription(
        self, shop_subscription_id: str, limit: int = 100, offset: int = 0
    ) -> List[BillingInvoice]:
        """Get billing invoices for a subscription with pagination."""
        try:
            query = (
                select(BillingInvoice)
                .where(BillingInvoice.shop_subscription_id == shop_subscription_id)
                .order_by(BillingInvoice.invoice_date.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting billing invoices by subscription: {e}")
            return []

    async def update_from_webhook(
        self, shopify_invoice_id: str, webhook_data: Dict[str, Any]
    ) -> Optional[BillingInvoice]:
        """Update existing billing invoice from webhook data."""
        try:
            invoice = await self.get_by_shopify_id(shopify_invoice_id)
            if not invoice:
                return None

            # Update fields
            invoice.amount_due = webhook_data.get("amount_due", invoice.amount_due)
            invoice.amount_paid = webhook_data.get("amount_paid", invoice.amount_paid)
            invoice.total_amount = webhook_data.get("total", invoice.total_amount)
            invoice.status = self._determine_status(webhook_data)
            invoice.paid_at = webhook_data.get("paid_at", invoice.paid_at)
            invoice.payment_method = webhook_data.get(
                "payment_method", invoice.payment_method
            )
            invoice.payment_reference = webhook_data.get(
                "payment_reference", invoice.payment_reference
            )
            invoice.shopify_response = webhook_data

            await self.session.commit()
            await self.session.refresh(invoice)

            logger.info(f"Updated billing invoice {shopify_invoice_id}")
            return invoice

        except Exception as e:
            logger.error(f"Error updating billing invoice: {e}")
            await self.session.rollback()
            return None

    async def get_by_shop(
        self, shop_id: str, limit: int = 100, offset: int = 0
    ) -> List[BillingInvoice]:
        """Get billing invoices for a shop with pagination."""
        try:
            query = (
                select(BillingInvoice)
                .join(ShopSubscription)
                .where(ShopSubscription.shop_id == shop_id)
                .order_by(BillingInvoice.invoice_date.desc())
                .limit(limit)
                .offset(offset)
            )
            result = await self.session.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error getting billing invoices by shop: {e}")
            return []

    def _determine_status(self, webhook_data: Dict[str, Any]) -> InvoiceStatus:
        """Determine invoice status from webhook data."""
        # Check if paid
        if webhook_data.get("paid_at"):
            return InvoiceStatus.PAID

        # Check if cancelled
        if webhook_data.get("cancelled_at"):
            return InvoiceStatus.CANCELLED

        # Check if refunded
        if webhook_data.get("refunded_at"):
            return InvoiceStatus.REFUNDED

        # Check if overdue
        due_date = webhook_data.get("due_date")
        if due_date:
            from datetime import datetime, timezone

            if datetime.now(timezone.utc) > due_date:
                return InvoiceStatus.OVERDUE

        # Default to pending
        return InvoiceStatus.PENDING
