"""add billing_invoices table

The BillingInvoice model was added to the codebase after the baseline migration
was created, and was never followed by an explicit migration. The dev database
therefore lacks the table even though the model and SQLAdmin view exist.

Revision ID: a1b2c3d4e5f6
Revises: d58a1c3e7b94
Create Date: 2026-09-25 17:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "d58a1c3e7b94"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CREATE_ENUM = (
    "CREATE TYPE IF NOT EXISTS invoice_status_enum AS ENUM ("
    "'draft', 'pending', 'paid', 'overdue', 'cancelled', 'refunded', 'failed'"
    ")"
)


def upgrade() -> None:
    op.execute(CREATE_ENUM)

    op.create_table(
        "billing_invoices",
        sa.Column("id", sa.String(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("timezone('UTC', CURRENT_TIMESTAMP)")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("timezone('UTC', CURRENT_TIMESTAMP)")),
        sa.Column("shop_subscription_id", sa.String(255), nullable=False),
        sa.Column("shopify_invoice_id", sa.String(255), nullable=False),
        sa.Column("invoice_number", sa.String(100), nullable=True),
        sa.Column("amount_due", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("amount_paid", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("total_amount", sa.Numeric(10, 2), nullable=False, server_default=sa.text("0.00")),
        sa.Column("currency", sa.String(3), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("invoice_date", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("due_date", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("paid_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.Enum('draft', 'pending', 'paid', 'overdue', 'cancelled', 'refunded', 'failed', name='invoice_status_enum', create_type=False), nullable=False, server_default=sa.text("'pending'::invoice_status_enum")),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("line_items", sa.JSON(), nullable=True),
        sa.Column("shopify_response", sa.JSON(), nullable=True),
        sa.Column("payment_method", sa.String(100), nullable=True),
        sa.Column("payment_reference", sa.String(255), nullable=True),
        sa.Column("failure_reason", sa.String(500), nullable=True),
        sa.ForeignKeyConstraint(["shop_subscription_id"], ["shop_subscriptions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_billing_invoice_subscription", "billing_invoices", ["shop_subscription_id"])
    op.create_index("ix_billing_invoice_shopify_id", "billing_invoices", ["shopify_invoice_id"], unique=True)
    op.create_index("ix_billing_invoice_status", "billing_invoices", ["status"])
    op.create_index("ix_billing_invoice_date", "billing_invoices", ["invoice_date"])
    op.create_index("ix_billing_invoice_due_date", "billing_invoices", ["due_date"])
    op.create_index("ix_billing_invoice_paid_at", "billing_invoices", ["paid_at"])
    op.create_index("ix_billing_invoice_currency", "billing_invoices", ["currency"])


def downgrade() -> None:
    op.drop_table("billing_invoices")
