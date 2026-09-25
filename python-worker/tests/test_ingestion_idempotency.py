"""Ingestion must be idempotent, because delivery is at-least-once.

Shopify fires orders/paid and orders/updated for a single purchase, and the
ingestion backstop republishes orders it believes are missing — so the same
resource routinely arrives several times at once. Storage used to read first
and insert if absent, so every concurrent collection saw "not there" and
inserted.

The duplicate rows wedged the resource permanently: normalisation reads with
`scalar_one_or_none()`, which raises "Multiple rows were found" as soon as
there is more than one, so the order never reached `order_data`. The backstop
then saw it missing and republished it, producing another duplicate. A sweep
built to repair missing data was manufacturing the corruption instead.

These tests run against a live Postgres (the dev container).
"""

import asyncio
import uuid

import pytest
from sqlalchemy import text

from app.core.database.session import get_transaction_context
from app.domains.shopify.services.data_storage import ShopifyDataStorageService

RAW_TABLES = ("raw_orders", "raw_products", "raw_customers", "raw_collections")


@pytest.mark.asyncio
async def test_raw_tables_have_the_unique_constraint():
    """Without it, concurrent inserts cannot be settled at all.

    Application-level checks cannot win a race; only the database can.
    """
    async with get_transaction_context() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT conrelid::regclass::text AS tbl
                    FROM pg_constraint
                    WHERE contype = 'u'
                      AND conname LIKE 'uq_raw_%_shop_shopify_id'
                    """
                )
            )
        ).all()

    constrained = {r.tbl for r in rows}
    missing = set(RAW_TABLES) - constrained
    assert not missing, f"raw tables without a uniqueness guarantee: {missing}"


@pytest.mark.asyncio
async def test_no_duplicate_raw_rows_exist():
    """A standing check on real data, not just on new writes."""
    for table in RAW_TABLES:
        async with get_transaction_context() as session:
            dupes = (
                await session.execute(
                    text(
                        f"""
                        SELECT COALESCE(SUM(c - 1), 0)
                        FROM (
                          SELECT COUNT(*) c FROM {table}
                          GROUP BY shop_id, shopify_id
                          HAVING COUNT(*) > 1
                        ) x
                        """
                    )
                )
            ).scalar()
        assert dupes == 0, f"{table} holds {dupes} duplicate row(s)"


@pytest.mark.asyncio
async def test_concurrent_collection_of_one_order_stores_one_row():
    """The actual regression: three collections at once, one row.

    Mirrors what the logs showed — orders/paid, orders/updated and a backstop
    republish all landing on the same order inside one second.
    """
    shop_id = None
    order_gid = f"gid://shopify/Order/{uuid.uuid4().int % 10**13}"

    async with get_transaction_context() as session:
        shop_id = (
            await session.execute(text("SELECT id FROM shops LIMIT 1"))
        ).scalar()

    if not shop_id:
        pytest.skip("no shop in the database to attach test rows to")

    def order_payload(updated_at: str):
        return {
            "id": order_gid,
            "updatedAt": updated_at,
            "createdAt": "2026-09-25T00:00:00Z",
            "name": "#TEST",
        }

    try:
        service = ShopifyDataStorageService()
        await asyncio.gather(
            service.store_orders_data(
                [order_payload("2026-09-25T01:00:00Z")], shop_id
            ),
            service.store_orders_data(
                [order_payload("2026-09-25T02:00:00Z")], shop_id
            ),
            service.store_orders_data(
                [order_payload("2026-09-25T03:00:00Z")], shop_id
            ),
        )

        async with get_transaction_context() as session:
            count = (
                await session.execute(
                    text(
                        "SELECT COUNT(*) FROM raw_orders "
                        "WHERE shop_id = :shop_id AND shopify_id = :gid"
                    ),
                    {"shop_id": shop_id, "gid": order_gid},
                )
            ).scalar()

        assert count == 1, (
            f"three concurrent collections produced {count} rows; "
            "normalisation will raise 'Multiple rows were found' on this order"
        )

        # And the survivor must be the newest payload, not whichever commit
        # happened to land last.
        async with get_transaction_context() as session:
            latest = (
                await session.execute(
                    text(
                        "SELECT shopify_updated_at FROM raw_orders "
                        "WHERE shop_id = :shop_id AND shopify_id = :gid"
                    ),
                    {"shop_id": shop_id, "gid": order_gid},
                )
            ).scalar()
        assert latest.hour == 3, (
            f"kept the {latest.hour}:00 copy; an older payload must never "
            "overwrite a newer one"
        )
    finally:
        async with get_transaction_context() as session:
            await session.execute(
                text("DELETE FROM raw_orders WHERE shopify_id = :gid"),
                {"gid": order_gid},
            )
            await session.commit()
