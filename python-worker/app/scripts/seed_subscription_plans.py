"""
Seed script for the default subscription plan.

Creates a single flat-rate plan at $299/mo with a 50% promotional discount.
Run this once per environment (dev/staging/prod).

Usage:
    python -m app.scripts.seed_subscription_plans [--env dev|prod]
"""

import asyncio
import logging
from decimal import Decimal
from datetime import datetime, UTC
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add the python-worker directory to Python path
python_worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, python_worker_dir)

# Determine environment from --env flag (default: dev)
import argparse

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--env", default="dev", choices=["dev", "prod"])
args, _ = parser.parse_known_args()

# Load the correct .env file based on --env flag
python_worker_path = Path(python_worker_dir)
root_dir = python_worker_path.parent

if args.env == "prod":
    env_files = [
        root_dir / ".env.prod",
        python_worker_path / ".env.prod",
    ]
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

# Build DATABASE_URL from env vars or use DATABASE_URL directly
env_db_url = os.environ.get("DATABASE_URL", "")
if env_db_url:
    DATABASE_URL = env_db_url.replace("postgresql://", "postgresql+asyncpg://")
else:
    DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/betterbundle"

os.environ["DATABASE_URL"] = DATABASE_URL

# Import after path setup and env loading
from app.core.database import get_session_context
from app.core.database.models import (
    SubscriptionPlan,
    SubscriptionPlanType,
)
from app.core.config.settings import settings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

PLAN_NAME = "Flat Fee Standard"


async def seed_subscription_plans(session: AsyncSession) -> None:
    """Seed the default subscription plan"""
    try:
        logger.info("🌱 Starting subscription plan seeding...")

        # Check if plan already exists
        result = await session.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.name == PLAN_NAME)
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.info(f"✅ Plan already exists: {existing.name} (ID: {existing.id})")
            return

        plan = SubscriptionPlan(
            name=PLAN_NAME,
            description="Standard flat-fee plan with promotional discount",
            plan_type=SubscriptionPlanType.FLAT_RATE,
            monthly_fee=Decimal("299.00"),
            discount_percentage=Decimal("50.00"),
            trial_days=14,
            is_active=True,
            is_default=True,
            plan_metadata='{"features": ["shopify_subscription", "bundle_attribution", "analytics"]}',
            effective_from=datetime.now(UTC),
        )

        session.add(plan)
        await session.flush()
        logger.info(
            f"✅ Created plan: {plan.name} (ID: {plan.id}) — "
            f"${plan.monthly_fee}/mo with {plan.discount_percentage}% discount"
        )

        await session.commit()
        logger.info("🎉 Successfully seeded subscription plan!")

    except Exception as e:
        await session.rollback()
        logger.error(f"❌ Error seeding subscription plan: {e}")
        raise


async def main():
    """Main function to run the seeding script"""

    # Log database URL (without password) for debugging
    db_url = settings.database.DATABASE_URL
    if db_url:
        try:
            from urllib.parse import urlparse, urlunparse

            parsed = urlparse(db_url)
            if parsed.password:
                masked_netloc = parsed.netloc.replace(parsed.password, "***")
                safe_url = urlunparse(parsed._replace(netloc=masked_netloc))
                logger.info(f"🔌 Connecting to database: {safe_url}")
            else:
                logger.info(f"🔌 Connecting to database: {db_url}")
        except Exception:
            logger.info("🔌 Connecting to database: [URL configured]")
    else:
        logger.warning("⚠️  DATABASE_URL not set, using default connection")

    async with get_session_context() as session:
        await seed_subscription_plans(session)

    logger.info("✅ Seeding completed successfully!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
