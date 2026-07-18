"""
Seed script for default subscription plans and pricing tiers.

This script creates the default subscription plan and pricing tiers
that will be used by shops when they sign up.
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
    # Ensure asyncpg driver is used
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
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def seed_subscription_plans(session: AsyncSession) -> None:
    """Seed default subscription plans and pricing tiers"""

    try:
        logger.info("🌱 Starting subscription plans seeding...")

        # 1. Check if subscription plan already exists
        from sqlalchemy import select

        existing_plan_query = select(SubscriptionPlan).where(
            SubscriptionPlan.name == "Flat Rate Standard"
        )
        existing_plan_result = await session.execute(existing_plan_query)
        existing_plan = existing_plan_result.scalar_one_or_none()

        if existing_plan:
            logger.info(
                f"✅ Subscription plan already exists: {existing_plan.name} (ID: {existing_plan.id})"
            )
            default_plan = existing_plan
        else:
            # Create default subscription plan
            default_plan = SubscriptionPlan(
                name="Flat Rate Standard",
                description="Standard flat-fee subscription plan with monthly pricing",
                plan_type=SubscriptionPlanType.FLAT_RATE,
                monthly_fee=Decimal("29.00"),
                trial_days=14,
                is_active=True,
                is_default=True,
                plan_metadata='{"features": ["shopify_subscription", "bundle_attribution", "analytics"]}',
                effective_from=datetime.now(UTC),
            )

            session.add(default_plan)
            await session.flush()  # Get the ID

            logger.info(
                f"✅ Created subscription plan: {default_plan.name} (ID: {default_plan.id})"
            )

        await session.commit()
        logger.info("🎉 Successfully seeded subscription plans and pricing tiers!")

    except Exception as e:
        await session.rollback()
        logger.error(f"❌ Error seeding subscription plans: {e}")
        raise


async def main():
    """Main function to run the seeding script"""

    # Log database URL (without password) for debugging
    db_url = settings.database.DATABASE_URL
    if db_url:
        # Mask password in URL for logging
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
            logger.info(f"🔌 Connecting to database: [URL configured]")
    else:
        logger.warning("⚠️  DATABASE_URL not set, using default connection")

    # Use the project's database connection method
    async with get_session_context() as session:
        await seed_subscription_plans(session)

    logger.info("✅ Seeding completed successfully!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
