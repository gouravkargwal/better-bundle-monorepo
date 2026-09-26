"""Add pause fields to ShopSubscription for commission reconciler.

Revision ID: 0002_commission_pause_fields
Revises: 0001_baseline
Create Date: 2026-09-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_commission_pause_fields"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "shop_subscriptions",
        sa.Column("paused", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "shop_subscriptions",
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("shop_subscriptions", "paused_at")
    op.drop_column("shop_subscriptions", "paused")
