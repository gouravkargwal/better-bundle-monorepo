"""
Migration Script: Add Unique Constraint on billing_cycles(shop_subscription_id, cycle_number)

Ensures no duplicate cycle numbers exist within a single subscription by:
1. Deduplicating any existing rows (keeping the most recent one by id)
2. Adding a UNIQUE constraint with a descriptive PostgreSQL constraint name

NOTE: This uses the existing pattern from add_flat_fee_columns.py for idempotency.

Usage:
    # As part of application startup (called automatically)
    python -c "from app.scripts.add_billing_cycles_unique_constraint import run_migration; import asyncio; asyncio.run(run_migration())"

    # Standalone
    python -m app.scripts.add_billing_cycles_unique_constraint
"""

import asyncio
import sys
from pathlib import Path

# Ensure the python-worker directory is on sys.path for standalone runs
_python_worker_dir = str(Path(__file__).resolve().parent.parent.parent)
if _python_worker_dir not in sys.path:
    sys.path.insert(0, _python_worker_dir)

from sqlalchemy import text
from app.core.database.engine import get_engine
from app.core.logging import get_logger

logger = get_logger(__name__)

# SQL statements — deduplicate first, then add constraint idempotently
MIGRATION_SQL: list[str] = [
    # Deduplicate: keep the row with the highest id per (shop_subscription_id, cycle_number)
    """
    DELETE FROM billing_cycles a USING billing_cycles b
    WHERE a.id < b.id
      AND a.shop_subscription_id = b.shop_subscription_id
      AND a.cycle_number = b.cycle_number;
    """,
    # Add unique constraint (safe to run multiple times — IF NOT EXISTS style via DO block)
    """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'uq_billing_cycles_subscription_cycle'
        ) THEN
            ALTER TABLE billing_cycles
            ADD CONSTRAINT uq_billing_cycles_subscription_cycle
            UNIQUE (shop_subscription_id, cycle_number);
        END IF;
    END $$;
    """,
]


async def run_migration() -> bool:
    """Execute the billing_cycles unique constraint migration.

    Returns True on success (or if constraint already exists), False on failure.
    """
    try:
        engine = await get_engine()
        async with engine.begin() as conn:
            for statement in MIGRATION_SQL:
                logger.info(f"Executing: {statement.strip()[:80]}...")
                await conn.execute(text(statement))
        logger.info(
            "✅ billing_cycles unique constraint migration completed successfully"
        )
        return True
    except Exception as e:
        logger.error(f"❌ billing_cycles unique constraint migration failed: {e}")
        return False


async def dry_run() -> None:
    """Log the SQL statements that would be executed, without running them."""
    logger.info("=== DRY RUN: billing_cycles unique constraint migration ===")
    for statement in MIGRATION_SQL:
        logger.info(f"  {statement.strip()}")
    logger.info("=== End dry run ===")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Add unique constraint on billing_cycles(shop_subscription_id, cycle_number)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print SQL statements without executing",
    )
    args = parser.parse_args()

    if args.dry_run:
        asyncio.run(dry_run())
    else:
        print("🚀 Running billing_cycles unique constraint migration...")
        success = asyncio.run(run_migration())
        if success:
            print("✅ Migration completed successfully")
        else:
            print("❌ Migration failed")
            sys.exit(1)
