"""add paid flag to offer_impressions

Revision ID: 077a48cbc2e3
Revises: 47239f0cc303
Create Date: 2026-09-17 05:14:39.829326
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


revision: str = '077a48cbc2e3'
down_revision: Union[str, None] = '47239f0cc303'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('offer_impressions', sa.Column('paid', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.alter_column('offer_impressions', 'paid', server_default=None)


def downgrade() -> None:
    op.drop_column('offer_impressions', 'paid')
