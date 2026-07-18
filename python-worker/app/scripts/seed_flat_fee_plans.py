"""
Seed script for flat fee subscription plans and pricing tiers.

This script creates flat-fee subscription plans (Basic, Pro, Enterprise)
with time-based trials and per-currency pricing tiers.

Run with: python -m app.scripts.seed_flat_fee_plans [--env dev|prod]
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

# Load the correct .env file
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
        print(f" Loaded env from: {env_file}")
        break

# Build DATABASE_URL
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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def seed_flat_fee_plans(session: AsyncSession) -> None:
    """Seed flat fee subscription plans and pricing tiers"""

    try:
        logger.info("🌱 Starting flat fee plans seeding...")

        # ===================== PLAN 1: BASIC =====================
        basic_plan_name = "Flat Fee Basic"
        existing_basic = await session.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.name == basic_plan_name)
        )
        basic_plan = existing_basic.scalar_one_or_none()

        if not basic_plan:
            basic_plan = SubscriptionPlan(
                name=basic_plan_name,
                description="Perfect for small stores getting started with product bundles",
                plan_type=SubscriptionPlanType.FLAT_RATE,
                monthly_fee=Decimal("29.00"),
                trial_days=14,
                is_active=True,
                is_default=True,
                plan_metadata='{"features": ["bundle_attribution", "analytics_dashboard", "email_support", "up_to_1000_orders"]}',
                effective_from=datetime.now(UTC),
            )
            session.add(basic_plan)
            await session.flush()
            logger.info(f"✅ Created plan: {basic_plan.name} (ID: {basic_plan.id})")
        else:
            logger.info(f" Plan already exists: {basic_plan.name}")

        # ===================== PLAN 2: PRO =====================
        pro_plan_name = "Flat Fee Pro"
        existing_pro = await session.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.name == pro_plan_name)
        )
        pro_plan = existing_pro.scalar_one_or_none()

        if not pro_plan:
            pro_plan = SubscriptionPlan(
                name=pro_plan_name,
                description="For growing stores that need advanced recommendations",
                plan_type=SubscriptionPlanType.FLAT_RATE,
                monthly_fee=Decimal("99.00"),
                trial_days=14,
                is_active=True,
                is_default=False,
                plan_metadata='{"features": ["bundle_attribution", "advanced_analytics", "priority_support", "up_to_10000_orders", "custom_branding"]}',
                effective_from=datetime.now(UTC),
            )
            session.add(pro_plan)
            await session.flush()
            logger.info(f"✅ Created plan: {pro_plan.name} (ID: {pro_plan.id})")
        else:
            logger.info(f" Plan already exists: {pro_plan.name}")

        # ===================== PLAN 3: ENTERPRISE =====================
        ent_plan_name = "Flat Fee Enterprise"
        existing_ent = await session.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.name == ent_plan_name)
        )
        ent_plan = existing_ent.scalar_one_or_none()

        if not ent_plan:
            ent_plan = SubscriptionPlan(
                name=ent_plan_name,
                description="For high-volume stores needing unlimited everything",
                plan_type=SubscriptionPlanType.FLAT_RATE,
                monthly_fee=Decimal("299.00"),
                trial_days=14,
                is_active=True,
                is_default=False,
                plan_metadata='{"features": ["bundle_attribution", "premium_analytics", "dedicated_support", "unlimited_orders", "custom_integrations", "SLA_guarantee"]}',
                effective_from=datetime.now(UTC),
            )
            session.add(ent_plan)
            await session.flush()
            logger.info(f"✅ Created plan: {ent_plan.name} (ID: {ent_plan.id})")
        else:
            logger.info(f" Plan already exists: {ent_plan.name}")

        await session.commit()
        logger.info("🎉 Flat fee plans seeding complete: 3 plans created/verified")

    except Exception as e:
        await session.rollback()
        logger.error(f" Error seeding flat fee plans: {e}")
        raise


async def main():
    """Main function to run the seeding script"""
    logging.basicConfig(level=logging.INFO)

    async with get_session_context() as session:
        await seed_flat_fee_plans(session)

    logger.info(" Flat fee seeding completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
