"""
Migration Script: Create suspension_audit_log Table

Creates the suspension_audit_log table for tracking shop suspension
and reactivation events. Uses CREATE TABLE IF NOT EXISTS for idempotency.

This migration is called automatically during application startup.

Table Schema:
  - id            BIGSERIAL PRIMARY KEY
  - shop_id       VARCHAR NOT NULL, indexed
  - action        VARCHAR(50) NOT NULL  ('SUSPENDED' | 'REACTIVATED')
  - reason        TEXT, nullable
  - triggered_by  VARCHAR(50) NOT NULL DEFAULT 'system'
  - metadata_json TEXT, nullable
  - created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()

Usage:
    # As part of application startup (called automatically)
    python -c "from app.scripts.add_suspension_audit_log import run_migration; import asyncio; asyncio.run(run_migration())"

    # Standalone
    python -m app.scripts.add_suspension_audit_log
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


async def run_migration() -> bool:
    """Execute the suspension_audit_log table migration.

    Creates the table and indexes idempotently (IF NOT EXISTS).
    Returns True on success, False on failure.
    """
    try:
        engine = await get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS suspension_audit_log (
                        id BIGSERIAL PRIMARY KEY,
                        shop_id VARCHAR NOT NULL,
                        action VARCHAR(50) NOT NULL,
                        reason TEXT,
                        triggered_by VARCHAR(50) NOT NULL DEFAULT 'system',
                        metadata_json TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """))
            await conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_suspension_audit_log_shop_id
                        ON suspension_audit_log(shop_id);
                """))
            await conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_suspension_audit_log_created_at
                        ON suspension_audit_log(created_at);
                """))
        logger.info("✅ suspension_audit_log table migration completed successfully")
        return True
    except Exception as e:
        logger.error(f"❌ suspension_audit_log table migration failed: {e}")
        return False


async def dry_run() -> None:
    """Log the SQL statements that would be executed, without running them."""
    logger.info("=== DRY RUN: suspension_audit_log table migration ===")
    logger.info(
        "  CREATE TABLE IF NOT EXISTS suspension_audit_log ("
        "id BIGSERIAL PRIMARY KEY, "
        "shop_id VARCHAR NOT NULL, "
        "action VARCHAR(50) NOT NULL, "
        "reason TEXT, "
        "triggered_by VARCHAR(50) NOT NULL DEFAULT 'system', "
        "metadata_json TEXT, "
        "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
        ");"
    )
    logger.info(
        "  CREATE INDEX IF NOT EXISTS idx_suspension_audit_log_shop_id "
        "ON suspension_audit_log(shop_id);"
    )
    logger.info(
        "  CREATE INDEX IF NOT EXISTS idx_suspension_audit_log_created_at "
        "ON suspension_audit_log(created_at);"
    )
    logger.info("=== End dry run ===")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create suspension_audit_log table")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print SQL statements without executing",
    )
    args = parser.parse_args()

    if args.dry_run:
        asyncio.run(dry_run())
    else:
        print("🚀 Running suspension_audit_log table migration...")
        success = asyncio.run(run_migration())
        if success:
            print("✅ Migration completed successfully")
        else:
            print("❌ Migration failed")
            sys.exit(1)
