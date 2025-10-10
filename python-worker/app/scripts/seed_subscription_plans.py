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

python_worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, python_worker_dir)

from app.core.database import get_session_context
from app.core.database.models import (
    SubscriptionPlan,
    PricingTier,
    SubscriptionPlanType,
)
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def seed_subscription_plans(session: AsyncSession) -> None:
    """Seed default subscription plans and pricing tiers"""

    try:
        logger.info("🌱 Starting subscription plans seeding...")

        # 1. Check if subscription plan already exists
        from sqlalchemy import select, and_

        existing_plan_query = select(SubscriptionPlan).where(
            SubscriptionPlan.name == "Usage-Based Standard"
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
                name="Usage-Based Standard",
                description="Standard usage-based billing plan with 3% commission rate",
                plan_type=SubscriptionPlanType.USAGE_BASED,
                is_active=True,
                is_default=True,
                default_commission_rate="0.03",
                plan_metadata='{"features": ["bundle_attribution", "commission_tracking", "usage_analytics"]}',
                effective_from=datetime.now(UTC),
            )

            session.add(default_plan)
            await session.flush()  # Get the ID

            logger.info(
                f"✅ Created subscription plan: {default_plan.name} (ID: {default_plan.id})"
            )

        # 2. Create pricing tiers for different currencies (consolidated from trial configs)
        pricing_tiers = [
            # Major Markets - Higher thresholds
            {
                "currency": "USD",
                "trial_threshold_amount": Decimal("200.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "US Market", "region": "US", "market_tier": "major", "currency_symbol": "$"}',
            },
            {
                "currency": "EUR",
                "trial_threshold_amount": Decimal("180.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "European Market", "region": "EU", "market_tier": "major", "currency_symbol": "€"}',
            },
            {
                "currency": "GBP",
                "trial_threshold_amount": Decimal("160.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "UK Market", "region": "UK", "market_tier": "major", "currency_symbol": "£"}',
            },
            {
                "currency": "CAD",
                "trial_threshold_amount": Decimal("200.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Canadian Market", "region": "CA", "market_tier": "major", "currency_symbol": "C$"}',
            },
            {
                "currency": "AUD",
                "trial_threshold_amount": Decimal("200.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Australian Market", "region": "AU", "market_tier": "major", "currency_symbol": "A$"}',
            },
            {
                "currency": "JPY",
                "trial_threshold_amount": Decimal("20000.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Japanese Market", "region": "JP", "market_tier": "major", "currency_symbol": "¥"}',
            },
            {
                "currency": "CHF",
                "trial_threshold_amount": Decimal("180.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Swiss Market", "region": "CH", "market_tier": "major", "currency_symbol": "CHF"}',
            },
            {
                "currency": "SEK",
                "trial_threshold_amount": Decimal("2000.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Swedish Market", "region": "SE", "market_tier": "major", "currency_symbol": "kr"}',
            },
            {
                "currency": "NOK",
                "trial_threshold_amount": Decimal("2000.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Norwegian Market", "region": "NO", "market_tier": "major", "currency_symbol": "kr"}',
            },
            {
                "currency": "DKK",
                "trial_threshold_amount": Decimal("1200.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Danish Market", "region": "DK", "market_tier": "major", "currency_symbol": "kr"}',
            },
            # Emerging Markets - Moderate thresholds
            {
                "currency": "INR",
                "trial_threshold_amount": Decimal("1000.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Indian Market", "region": "IN", "market_tier": "emerging", "currency_symbol": "₹"}',
            },
            {
                "currency": "BRL",
                "trial_threshold_amount": Decimal("1000.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Brazilian Market", "region": "BR", "market_tier": "emerging", "currency_symbol": "R$"}',
            },
            {
                "currency": "MXN",
                "trial_threshold_amount": Decimal("4000.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Mexican Market", "region": "MX", "market_tier": "emerging", "currency_symbol": "$"}',
            },
            {
                "currency": "KRW",
                "trial_threshold_amount": Decimal("260000.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Korean Market", "region": "KR", "market_tier": "emerging", "currency_symbol": "₩"}',
            },
            {
                "currency": "CNY",
                "trial_threshold_amount": Decimal("1400.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Chinese Market", "region": "CN", "market_tier": "emerging", "currency_symbol": "¥"}',
            },
            {
                "currency": "PLN",
                "trial_threshold_amount": Decimal("800.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Polish Market", "region": "PL", "market_tier": "emerging", "currency_symbol": "zł"}',
            },
            {
                "currency": "CZK",
                "trial_threshold_amount": Decimal("4400.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Czech Market", "region": "CZ", "market_tier": "emerging", "currency_symbol": "Kč"}',
            },
            {
                "currency": "HUF",
                "trial_threshold_amount": Decimal("70000.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Hungarian Market", "region": "HU", "market_tier": "emerging", "currency_symbol": "Ft"}',
            },
            {
                "currency": "ZAR",
                "trial_threshold_amount": Decimal("3600.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "South African Market", "region": "ZA", "market_tier": "emerging", "currency_symbol": "R"}',
            },
            {
                "currency": "TRY",
                "trial_threshold_amount": Decimal("1200.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Turkish Market", "region": "TR", "market_tier": "emerging", "currency_symbol": "₺"}',
            },
            # Developing Markets - Lower thresholds
            {
                "currency": "VND",
                "trial_threshold_amount": Decimal("120000.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Vietnamese Market", "region": "VN", "market_tier": "developing", "currency_symbol": "₫"}',
            },
            {
                "currency": "IDR",
                "trial_threshold_amount": Decimal("750000.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Indonesian Market", "region": "ID", "market_tier": "developing", "currency_symbol": "Rp"}',
            },
            {
                "currency": "PHP",
                "trial_threshold_amount": Decimal("2750.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Philippine Market", "region": "PH", "market_tier": "developing", "currency_symbol": "₱"}',
            },
            {
                "currency": "THB",
                "trial_threshold_amount": Decimal("1750.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Thai Market", "region": "TH", "market_tier": "developing", "currency_symbol": "฿"}',
            },
            {
                "currency": "MYR",
                "trial_threshold_amount": Decimal("900.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Malaysian Market", "region": "MY", "market_tier": "developing", "currency_symbol": "RM"}',
            },
            {
                "currency": "SGD",
                "trial_threshold_amount": Decimal("260.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Singapore Market", "region": "SG", "market_tier": "developing", "currency_symbol": "S$"}',
            },
            {
                "currency": "BDT",
                "trial_threshold_amount": Decimal("5500.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Bangladeshi Market", "region": "BD", "market_tier": "developing", "currency_symbol": "৳"}',
            },
            {
                "currency": "PKR",
                "trial_threshold_amount": Decimal("14000.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Pakistani Market", "region": "PK", "market_tier": "developing", "currency_symbol": "₨"}',
            },
            {
                "currency": "LKR",
                "trial_threshold_amount": Decimal("16000.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Sri Lankan Market", "region": "LK", "market_tier": "developing", "currency_symbol": "₨"}',
            },
            {
                "currency": "NPR",
                "trial_threshold_amount": Decimal("1300.00"),
                "commission_rate": Decimal("0.03"),
                "is_default": True,
                "tier_metadata": '{"description": "Nepalese Market", "region": "NP", "market_tier": "developing", "currency_symbol": "₨"}',
            },
        ]

        for tier_data in pricing_tiers:
            # Check if pricing tier already exists for this plan and currency
            existing_tier_query = select(PricingTier).where(
                and_(
                    PricingTier.subscription_plan_id == default_plan.id,
                    PricingTier.currency == tier_data["currency"],
                )
            )
            existing_tier_result = await session.execute(existing_tier_query)
            existing_tier = existing_tier_result.scalar_one_or_none()

            if existing_tier:
                logger.info(
                    f"✅ Pricing tier already exists: {tier_data['currency']} for plan {default_plan.name}"
                )
                continue

            pricing_tier = PricingTier(
                subscription_plan_id=default_plan.id,
                **tier_data,
                effective_from=datetime.now(UTC),
            )
            session.add(pricing_tier)

            logger.info(
                f"✅ Created pricing tier: {tier_data['currency']} "
                f"(threshold: ${tier_data['trial_threshold_amount']})"
                f"(commission rate: ${tier_data['commission_rate']})"
            )

        await session.commit()
        logger.info("🎉 Successfully seeded subscription plans and pricing tiers!")

    except Exception as e:
        await session.rollback()
        logger.error(f"❌ Error seeding subscription plans: {e}")
        raise


async def main():
    """Main function to run the seeding script"""

    # Use the project's database connection method
    async with get_session_context() as session:
        await seed_subscription_plans(session)

    logger.info("✅ Seeding completed successfully!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
