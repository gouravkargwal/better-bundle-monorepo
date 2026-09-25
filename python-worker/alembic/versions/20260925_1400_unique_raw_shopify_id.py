"""make raw ingestion idempotent: unique (shop_id, shopify_id)

The same resource legitimately arrives several times at once — a purchase fires
orders/paid and orders/updated together, and the ingestion backstop republishes
orders it thinks are missing. Storage read first and inserted if absent, so
concurrent collections all saw "not there" and all inserted.

The duplicate rows then wedged the resource permanently: normalisation reads
with `scalar_one_or_none()`, which raises "Multiple rows were found" once there
is more than one. The order never reached `order_data`, so the backstop saw it
missing and republished it, collecting it again and adding another duplicate.

A race is only settleable in the database, hence this constraint. Existing
duplicates are collapsed to the most recently extracted row first, otherwise
the constraint cannot be created.

Revision ID: c47e9b2a8d15
Revises: b31f7c4d9a02
Create Date: 2026-09-25 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c47e9b2a8d15"
down_revision: Union[str, None] = "b31f7c4d9a02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RAW_TABLES = ("raw_orders", "raw_products", "raw_customers", "raw_collections")


def upgrade() -> None:
    for table in RAW_TABLES:
        # Keep the freshest row per (shop_id, shopify_id); drop the rest.
        # `extracted_at DESC` rather than `created_at`: the newest fetch holds
        # the most current payload, which is what normalisation should read.
        op.execute(
            f"""
            DELETE FROM {table} a
            USING {table} b
            WHERE a.shop_id = b.shop_id
              AND a.shopify_id = b.shopify_id
              AND a.shopify_id IS NOT NULL
              AND (
                    a.extracted_at < b.extracted_at
                 OR (a.extracted_at = b.extracted_at AND a.id < b.id)
              )
            """
        )
        op.create_unique_constraint(
            f"uq_{table}_shop_shopify_id", table, ["shop_id", "shopify_id"]
        )


def downgrade() -> None:
    for table in RAW_TABLES:
        op.drop_constraint(f"uq_{table}_shop_shopify_id", table, type_="unique")
