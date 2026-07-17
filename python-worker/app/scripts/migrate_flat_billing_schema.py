"""
One-off schema migration for the flat-fee billing model.

Non-destructive: only adds new columns and relaxes a NOT NULL constraint that
no longer applies now that BetterBundle bills a single flat plan instead of
per-currency pricing tiers. No tables or columns are dropped — existing data
(commission_records, billing_cycles, billing_invoices, pricing_tiers) is left
in place, just unused going forward. The ORM no longer maps pricing_tier_id
at all, so it must be nullable at the DB level for new subscription rows to
insert successfully.

Safe to run multiple times (every statement is conditional).
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
        "subscription_plans.monthly_price",
        """
        ALTER TABLE subscription_plans
        ADD COLUMN IF NOT EXISTS monthly_price NUMERIC(10, 2) NOT NULL DEFAULT 99.00
        """,
    ),
    (
        "subscription_plans.trial_days",
        """
        ALTER TABLE subscription_plans
        ADD COLUMN IF NOT EXISTS trial_days INTEGER NOT NULL DEFAULT 14
        """,
    ),
    (
        "shop_subscriptions.pricing_tier_id nullable (column unmapped by ORM)",
        """
        ALTER TABLE shop_subscriptions
        ALTER COLUMN pricing_tier_id DROP NOT NULL
        """,
    ),
]


async def migrate() -> None:
    engine = await get_engine()
    async with engine.begin() as conn:
        for label, statement in STATEMENTS:
            print(f"➡️  {label}")
            await conn.execute(text(statement))
    print("✅ Flat billing schema migration complete")


if __name__ == "__main__":
    asyncio.run(migrate())
