"""shops.settings: merchant surface toggles + exclusions

Revision ID: 8f3a9c1e2b4d
Revises: ce4b52bddb76
Create Date: 2026-09-08 18:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '8f3a9c1e2b4d'
down_revision: Union[str, None] = 'ce4b52bddb76'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Merchant controls from the admin Settings page. Shape:
    #   {
    #     "surfaces": { "mercury": true, "apollo": true, "thank_you": true,
    #                   "phoenix": true, "venus": true },
    #     "excluded_product_ids": ["gid://shopify/Product/123", ...]
    #   }
    # Absent/missing keys mean "use the default" (all surfaces on, no
    # exclusions), so a shop that never opens Settings behaves exactly as
    # before this column existed.
    op.add_column(
        'shops',
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('shops', 'settings')