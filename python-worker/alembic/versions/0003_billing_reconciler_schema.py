"""Add reconciled_at to BillingCycle and usage linkage fields to BillingInvoice.

Revision ID: 0003_billing_reconciler_schema
Revises: 0002_commission_pause_fields
Create Date: 2026-09-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = "0003_billing_reconciler_schema"
down_revision: Union[str, None] = "0002_commission_pause_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # BillingCycle: reconciled_at
    op.add_column(
        "billing_cycles",
        sa.Column(
            "reconciled_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_billing_cycles_reconciled_at",
        "billing_cycles",
        ["reconciled_at"],
    )

    # Partial index for reconciler: completed but unreconciled cycles
    op.create_index(
        "ix_billing_cycles_unreconciled",
        "billing_cycles",
        ["completed_at"],
        postgresql_where=text("reconciled_at IS NULL"),
    )

    # Unique constraint: one cycle per subscription per start_date
    op.create_index(
        "ix_billing_cycle_unique_subscription_start",
        "billing_cycles",
        ["shop_subscription_id", "start_date"],
        unique=True,
    )

    # BillingInvoice: shop_id, billing_cycle_id, usage_amount
    op.add_column(
        "billing_invoices",
        sa.Column(
            "shop_id",
            sa.String(255),
            sa.ForeignKey("shops.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_billing_invoices_shop_id",
        "billing_invoices",
        ["shop_id"],
    )

    op.add_column(
        "billing_invoices",
        sa.Column(
            "billing_cycle_id",
            sa.String(255),
            sa.ForeignKey("billing_cycles.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_billing_invoices_billing_cycle_id",
        "billing_invoices",
        ["billing_cycle_id"],
    )
    op.add_column(
        "billing_invoices",
        sa.Column(
            "usage_amount",
            sa.Numeric(10, 2),
            nullable=False,
            server_default=sa.text("0.00"),
        ),
    )


def downgrade() -> None:
    op.drop_column("billing_invoices", "usage_amount")
    op.drop_column("billing_invoices", "billing_cycle_id")
    op.drop_column("billing_invoices", "shop_id")

    op.drop_index("ix_billing_cycle_unique_subscription_start", table_name="billing_cycles")
    op.drop_index("ix_billing_cycles_unreconciled", table_name="billing_cycles")
    op.drop_index("ix_billing_cycles_reconciled_at", table_name="billing_cycles")
    op.drop_column("billing_cycles", "reconciled_at")
