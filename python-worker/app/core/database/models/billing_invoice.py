"""
Billing Invoice Model

Stores Shopify billing invoices received via webhooks.
Tracks invoice details, amounts, and payment status.
"""

from decimal import Decimal
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Numeric,
    Boolean,
    ForeignKey,
    Index,
    Enum as SQLEnum,
    Text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, JSON
from sqlalchemy.orm import relationship
from .base import BaseModel
from .enums import InvoiceStatus
from .shop_subscription import ShopSubscription


class BillingInvoice(BaseModel):
    """
    Billing Invoice

    Stores Shopify billing invoices received via webhooks.
    Links to shop subscriptions and tracks payment status.
    """

    __tablename__ = "billing_invoices"

    # Foreign keys
    shop_subscription_id = Column(
        String(255),
        ForeignKey("shop_subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Shopify invoice details
    shopify_invoice_id = Column(String(255), nullable=False, unique=True, index=True)
    invoice_number = Column(String(100), nullable=True, index=True)

    # Invoice amounts
    amount_due = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    amount_paid = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    total_amount = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    currency = Column(String(3), nullable=False, default="USD", index=True)

    # Invoice dates
    invoice_date = Column(TIMESTAMP(timezone=True), nullable=False, index=True)
    due_date = Column(TIMESTAMP(timezone=True), nullable=True, index=True)
    paid_at = Column(TIMESTAMP(timezone=True), nullable=True, index=True)

    # Invoice status
    status = Column(
        SQLEnum(InvoiceStatus, name="invoice_status_enum"),
        nullable=False,
        default=InvoiceStatus.PENDING,
        index=True,
    )

    # Invoice metadata
    description = Column(Text, nullable=True)
    line_items = Column(JSON, nullable=True)  # Store line items as JSON
    shopify_response = Column(JSON, nullable=True)  # Store full Shopify response

    # Payment tracking
    payment_method = Column(String(100), nullable=True)
    payment_reference = Column(String(255), nullable=True)

    # Relationships
    shop_subscription = relationship(
        "ShopSubscription", back_populates="billing_invoices"
    )

    # Indexes
    __table_args__ = (
        Index("ix_billing_invoice_subscription", "shop_subscription_id"),
        Index("ix_billing_invoice_shopify_id", "shopify_invoice_id"),
        Index("ix_billing_invoice_status", "status"),
        Index("ix_billing_invoice_date", "invoice_date"),
        Index("ix_billing_invoice_due_date", "due_date"),
        Index("ix_billing_invoice_paid_at", "paid_at"),
        Index("ix_billing_invoice_currency", "currency"),
    )

    def __repr__(self) -> str:
        return f"<BillingInvoice(shopify_id={self.shopify_invoice_id}, amount={self.total_amount}, status={self.status.value})>"

    @property
    def is_paid(self) -> bool:
        """Check if invoice is paid"""
        return self.status == InvoiceStatus.PAID

    @property
    def is_overdue(self) -> bool:
        """Check if invoice is overdue"""
        if not self.due_date:
            return False
        return (
            self.status in [InvoiceStatus.PENDING, InvoiceStatus.OVERDUE]
            and datetime.now(self.due_date.tzinfo) > self.due_date
        )

    @property
    def outstanding_amount(self) -> Decimal:
        """Get outstanding amount (total - paid)"""
        return self.total_amount - self.amount_paid
