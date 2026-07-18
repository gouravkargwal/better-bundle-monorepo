"""
Migration Script: Fix Legacy Nullable Fields on billing_cycles

Originally, the SQLAlchemy model for billing_cycles defined the following
fields as nullable in the ORM layer but the database columns were created
with NOT NULL. This script alters those columns to allow NULL values,
bringing the DB schema in line with the model.

Columns affected (all on billing_cycles):
  - initial_cap_amount    NUMERIC(10,2)  — DROP NOT NULL
  - current_cap_amount    NUMERIC(10,2)  — DROP NOT NULL
  - usage_amount          NUMERIC(10,2)  — DROP NOT NULL
  - commission_count      INTEGER        — DROP NOT NULL

Usage:
    # As part of application startup (called automatically)
    python -c "from app.scripts.fix_legacy_nullable_fields import run_migration; import asyncio; asyncio.run(run_migration())"

    # Standalone
    python -m app.scripts.fix_legacy_nullable_fields
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

# Each ALTER COLUMN uses IF NOT EXISTS equivalent via a DO block for safety
MIGRATION_SQL: list[str] = [
    """
    DO $$
    BEGIN
        -- Check if the column is still NOT NULL before altering
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'billing_cycles'
              AND column_name = 'initial_cap_amount'
              AND is_nullable = 'NO'
        ) THEN
            ALTER TABLE billing_cycles ALTER COLUMN initial_cap_amount DROP NOT NULL;
        END IF;
    END $$;
    """,
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'billing_cycles'
              AND column_name = 'current_cap_amount'
              AND is_nullable = 'NO'
        ) THEN
            ALTER TABLE billing_cycles ALTER COLUMN current_cap_amount DROP NOT NULL;
        END IF;
    END $$;
    """,
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'billing_cycles'
              AND column_name = 'usage_amount'
              AND is_nullable = 'NO'
        ) THEN
            ALTER TABLE billing_cycles ALTER COLUMN usage_amount DROP NOT NULL;
        END IF;
    END $$;
    """,
    """
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'billing_cycles'
              AND column_name = 'commission_count'
              AND is_nullable = 'NO'
        ) THEN
            ALTER TABLE billing_cycles ALTER COLUMN commission_count DROP NOT NULL;
        END IF;
    END $$;
    """,
]


async def run_migration() -> bool:
    """Execute the legacy nullable fields migration.

    Returns True on success (or if columns are already nullable), False on failure.
    """
    try:
        engine = await get_engine()
        async with engine.begin() as conn:
            for statement in MIGRATION_SQL:
                logger.info("Executing: ALTER COLUMN DROP NOT NULL (if applicable)...")
                await conn.execute(text(statement))
        logger.info("✅ Legacy nullable fields migration completed successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Legacy nullable fields migration failed: {e}")
        return False


async def dry_run() -> None:
    """Log the SQL statements that would be executed, without running them."""
    logger.info("=== DRY RUN: Legacy nullable fields migration ===")
    for statement in MIGRATION_SQL:
        logger.info(f"  {statement.strip()}")
    logger.info("=== End dry run ===")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Fix legacy nullable fields on billing_cycles table"
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
        print("🚀 Running legacy nullable fields migration...")
        success = asyncio.run(run_migration())
        if success:
            print("✅ Migration completed successfully")
        else:
            print("❌ Migration failed")
            sys.exit(1)
