"""restore refund_data for recommendation signal

Refund ingestion and normalization were never removed; only storage was, in
c6f6af7. This recreates the table the normalizer writes to. Deliberately does
not restore `refund_attributions` — refunds adjust recommendations, not billing.

Revision ID: b31f7c4d9a02
Revises: 077a48cbc2e3
Create Date: 2026-09-25 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b31f7c4d9a02"
down_revision: Union[str, None] = "077a48cbc2e3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "refund_data",
        sa.Column(
            "id",
            sa.String(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("shop_id", sa.String(), nullable=False),
        # Internal order_data.id, so refunds join to line items directly.
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("refund_id", sa.String(), nullable=False),
        sa.Column("refunded_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("total_refund_amount", sa.Float(), nullable=False),
        sa.Column(
            "currency_code", sa.String(), nullable=False, server_default="USD"
        ),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("restock", sa.Boolean(), server_default=sa.false()),
        sa.Column("refund_line_items", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('UTC', CURRENT_TIMESTAMP)"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("timezone('UTC', CURRENT_TIMESTAMP)"),
        ),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_refund_data_order_id", "refund_data", ["order_id"])
    op.create_index("ix_refund_data_refund_id", "refund_data", ["refund_id"])
    op.create_index("ix_refund_data_shop_id", "refund_data", ["shop_id"])
    op.create_index(
        "idx_refund_data_shop_order", "refund_data", ["shop_id", "order_id"]
    )
    op.create_index("idx_refund_data_refunded_at", "refund_data", ["refunded_at"])
    op.create_index(
        "ux_refund_data_shop_refund",
        "refund_data",
        ["shop_id", "refund_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("refund_data")
