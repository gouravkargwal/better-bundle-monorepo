#!/usr/bin/env python3
"""
Delete everything BetterBundle knows about one shop.

This is the counterpart to `delete_store_data.py`. That one deletes products
and orders from the merchant's live Shopify store; this one only touches our
own database and never calls Shopify.

Use it to re-run onboarding from scratch: purge the shop, then press "Start
Free" again and the whole pipeline — collection, normalization, embeddings,
enrichment, priors, co-purchase mining — runs as it would for a new merchant.

Two things are deliberately left alone:

  `sessions`            the Shopify OAuth token. Deleting it would force a
                        full app reinstall to get a new one, which is almost
                        never what you want. Pass --forget-install to include
                        it if you really are testing the install flow.

  `subscription_plans`  global pricing configuration, not shop data. Wiping it
                        would break onboarding for every shop
                        (`No default subscription plan found`).

Usage:
    python -m app.scripts.delete_shop_data --shop my-store.myshopify.com
    python -m app.scripts.delete_shop_data --shop my-store.myshopify.com --dry-run
    python -m app.scripts.delete_shop_data --shop my-store.myshopify.com --keep-shop
"""

import argparse
import asyncio
import os
import sys
from typing import List, Optional, Tuple

python_worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, python_worker_dir)

from sqlalchemy import text  # noqa: E402

from app.core.database.session import get_transaction_context  # noqa: E402
from app.core.logging import get_logger  # noqa: E402

logger = get_logger(__name__)


# Deletion order matters: almost every foreign key to `shops` is NO ACTION
# rather than CASCADE, so deleting the parent first fails on a constraint
# violation. Children first, parents last.
#
# Each entry is (table, WHERE clause). The clause is parameterised on
# :shop_id — never interpolated, because a shop domain is user input.
DELETE_ORDER: List[Tuple[str, str]] = [
    # ---- recommendation engine outputs -----------------------------------
    #      Embeddings are cheap to rebuild (local CPU, no API), so they always
    #      go. product_enrichments is the one artifact that cost real money,
    #      which is why --keep-enrichment can exclude it below.
    ("product_edges", "shop_id = :shop_id"),
    ("product_vectors", "shop_id = :shop_id"),
    ("product_enrichments", "shop_id = :shop_id"),
    # ---- billing (commission_records CASCADEs from shops, but billing_cycles
    #      hangs off shop_subscriptions and has no shop_id of its own) ------
    ("commission_records", "shop_id = :shop_id"),
    (
        "billing_cycles",
        "shop_subscription_id IN "
        "(SELECT id FROM shop_subscriptions WHERE shop_id = :shop_id)",
    ),
    ("shop_subscriptions", "shop_id = :shop_id"),
    # ---- attribution and measurement -------------------------------------
    ("purchase_attributions", "shop_id = :shop_id"),
    ("offer_impressions", "shop_id = :shop_id"),
    ("user_identity_links", "shop_id = :shop_id"),
    ("user_sessions", "shop_id = :shop_id"),
    ("suspension_audit_log", "shop_id = :shop_id"),
    # ---- normalized Shopify data -----------------------------------------
    #      line_item_data keys on order_data.id, so it must precede orders.
    (
        "line_item_data",
        "order_id IN (SELECT id FROM order_data WHERE shop_id = :shop_id)",
    ),
    ("order_data", "shop_id = :shop_id"),
    ("product_data", "shop_id = :shop_id"),
    ("customer_data", "shop_id = :shop_id"),
    ("collection_data", "shop_id = :shop_id"),
    # ---- raw webhook/collection payloads ---------------------------------
    ("raw_orders", "shop_id = :shop_id"),
    ("raw_products", "shop_id = :shop_id"),
    ("raw_customers", "shop_id = :shop_id"),
    ("raw_collections", "shop_id = :shop_id"),
]


async def resolve_shop(shop_domain: str) -> Optional[str]:
    async with get_transaction_context() as session:
        row = (
            await session.execute(
                text("SELECT id FROM shops WHERE shop_domain = :d"),
                {"d": shop_domain},
            )
        ).first()
    return row.id if row else None


# The LLM enrichment cache. Keyed on (shop_id, product_id, text_hash,
# model_version), so it is only reusable while the product ids stay the same —
# i.e. after a shop-reset, but not after reseeding Shopify, which mints new ids.
PAID_TABLES = {"product_enrichments"}


def tables_to_delete(keep_enrichment: bool) -> List[Tuple[str, str]]:
    if not keep_enrichment:
        return DELETE_ORDER
    return [(t, w) for t, w in DELETE_ORDER if t not in PAID_TABLES]


async def count_rows(
    shop_id: str, keep_enrichment: bool = False
) -> List[Tuple[str, int]]:
    """What would be deleted, without deleting it."""
    counts = []
    async with get_transaction_context() as session:
        for table, where in tables_to_delete(keep_enrichment):
            n = (
                await session.execute(
                    text(f"SELECT COUNT(*) FROM {table} WHERE {where}"),
                    {"shop_id": shop_id},
                )
            ).scalar_one()
            counts.append((table, int(n)))
    return counts


async def delete_shop_data(
    shop_domain: str,
    keep_shop: bool = False,
    forget_install: bool = False,
    keep_enrichment: bool = False,
) -> bool:
    shop_id = await resolve_shop(shop_domain)
    if not shop_id:
        logger.error(f"No shop found for domain {shop_domain}")
        return False

    logger.info(f"Deleting BetterBundle data for {shop_domain} (id={shop_id})")

    total = 0
    # One transaction: a half-deleted shop is worse than an untouched one,
    # because the pipeline would then run against a mix of old and new data.
    async with get_transaction_context() as session:
        for table, where in tables_to_delete(keep_enrichment):
            result = await session.execute(
                text(f"DELETE FROM {table} WHERE {where}"),
                {"shop_id": shop_id},
            )
            deleted = result.rowcount or 0
            total += deleted
            if deleted:
                logger.info(f"  {table}: {deleted}")

        if keep_enrichment:
            logger.info(
                "  product_enrichments: kept (already paid for; valid while "
                "product ids are unchanged)"
            )

        if forget_install:
            result = await session.execute(
                text("DELETE FROM sessions WHERE shop = :d"), {"d": shop_domain}
            )
            n = result.rowcount or 0
            total += n
            logger.info(f"  sessions: {n} (app will need reinstalling)")

        if keep_shop:
            # Reset the flags onboarding checks, so "Start Free" is offered
            # again without discarding the access token on the shops row.
            await session.execute(
                text(
                    "UPDATE shops SET onboarding_completed = false, "
                    "setup_guide_visited = false, last_analysis_at = NULL, "
                    "suspended_at = NULL, suspension_reason = NULL, "
                    "service_impact = NULL, updated_at = NOW() "
                    "WHERE id = :shop_id"
                ),
                {"shop_id": shop_id},
            )
            logger.info("  shops: kept, onboarding flags reset")
        else:
            result = await session.execute(
                text("DELETE FROM shops WHERE id = :shop_id"), {"shop_id": shop_id}
            )
            total += result.rowcount or 0
            logger.info("  shops: 1")

    logger.info(f"✅ Deleted {total} rows for {shop_domain}")
    return True


async def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete BetterBundle's data for one shop (not Shopify's)."
    )
    parser.add_argument("--shop", required=True, help="Shop domain")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be deleted and exit",
    )
    parser.add_argument(
        "--keep-shop",
        action="store_true",
        help="Keep the shops row and its access token; only reset onboarding",
    )
    parser.add_argument(
        "--keep-enrichment",
        action="store_true",
        help="Keep the LLM enrichment cache, so re-running costs no API calls",
    )
    parser.add_argument(
        "--forget-install",
        action="store_true",
        help="Also delete the Shopify OAuth session (forces an app reinstall)",
    )
    args = parser.parse_args()

    shop_id = await resolve_shop(args.shop)
    if not shop_id:
        logger.error(f"No shop found for domain {args.shop}")
        return 1

    if args.dry_run:
        rows = await count_rows(shop_id, keep_enrichment=args.keep_enrichment)
        logger.info(f"Dry run for {args.shop} (id={shop_id}):")
        for table, n in rows:
            if n:
                logger.info(f"  {table}: {n}")
        logger.info(f"  TOTAL: {sum(n for _, n in rows)} rows")
        logger.info("Nothing was deleted.")
        return 0

    ok = await delete_shop_data(
        args.shop,
        keep_shop=args.keep_shop,
        forget_install=args.forget_install,
        keep_enrichment=args.keep_enrichment,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
