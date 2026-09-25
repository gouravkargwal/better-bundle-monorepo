"""per-shop holdout percent, so the rate can step down once lift is measurable

A shop starts with a large control arm to reach a measured lift quickly, then
steps down to a monitoring rate. NULL means "still learning" and resolves to
the learning default in code, so existing shops need no backfill.

Revision ID: d58a1c3e7b94
Revises: c47e9b2a8d15
Create Date: 2026-09-25 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d58a1c3e7b94"
down_revision: Union[str, None] = "c47e9b2a8d15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shops", sa.Column("holdout_percent", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("shops", "holdout_percent")
