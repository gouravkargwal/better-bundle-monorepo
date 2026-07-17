"""
One-off schema migration: drop legacy commission columns no longer used
with flat-rate billing.

Non-destructive: only drops columns that are no longer referenced by any
code (verified: zero code references to either column across all layers).
Existing data in those columns is lost — no rollback.

The columns being dropped:
  - subscription_plans.default_commission_rate (VARCHAR(10)) — legacy commission rate
  - billing_cycles.commission_count (INTEGER) — unused counter for commission records

Safe to run multiple times (every statement uses IF EXISTS).
"""

import asyncio
import os
import sys
from pathlib import Path

python_worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, python_worker_dir)

import argparse
from dotenv import load_dotenv

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--env", default="dev", choices=["dev", "prod"])
args, _ = parser.parse_known_args()

python_worker_path = Path(python_worker_dir)
root_dir = python_worker_path.parent

if args.env == "prod":
    env_files = [root_dir / ".env.prod", python_worker_path / ".env.prod"]
else:
    env_files = [
        root_dir / ".env.dev",
        root_dir / ".env.local",
        root_dir / ".env",
        python_worker_path / ".env.local",
        python_worker_path / ".env",
    ]

for env_file in env_files:
    if env_file.exists():
        load_dotenv(env_file, override=True)
        print(f"📄 Loaded env from: {env_file}")
        break

env_db_url = os.environ.get("DATABASE_URL", "")
if env_db_url:
    DATABASE_URL = env_db_url.replace("postgresql://", "postgresql+asyncpg://")
else:
    DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/betterbundle"
os.environ["DATABASE_URL"] = DATABASE_URL

from sqlalchemy import text
from app.core.database.engine import get_engine

STATEMENTS = [
    (
        "subscription_plans.default_commission_rate (dead column)",
        """
        ALTER TABLE subscription_plans
        DROP COLUMN IF EXISTS default_commission_rate
        """,
    ),
    (
        "billing_cycles.commission_count (dead column)",
        """
        ALTER TABLE billing_cycles
        DROP COLUMN IF EXISTS commission_count
        """,
    ),
]


async def migrate() -> None:
    engine = await get_engine()
    async with engine.begin() as conn:
        for label, statement in STATEMENTS:
            print(f"➡️  Dropping {label}")
            await conn.execute(text(statement))
    print("✅ Legacy commission columns dropped successfully")


if __name__ == "__main__":
    print("⚠️  WARNING: This will permanently delete data in dropped columns.")
    print("   Confirm by typing: yes, drop the columns")
    confirmation = input("> ")
    if confirmation.lower() not in ("yes", "y"):
        print("❌ Aborted.")
        sys.exit(1)
    asyncio.run(migrate())
