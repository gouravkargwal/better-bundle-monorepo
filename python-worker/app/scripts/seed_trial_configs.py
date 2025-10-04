#!/usr/bin/env python3
"""
Trial Configuration Seeder
Seeds trial configurations for different currencies
"""

import asyncio
import sys
import os
from decimal import Decimal

# Add the python-worker directory to Python path
python_worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, python_worker_dir)

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert

from app.core.database import get_session_factory
from app.core.database.models import TrialConfig

# Trial configuration data
TRIAL_CONFIG_DATA = [
    # Major Markets - Higher thresholds
    {
        "currency_code": "USD",
        "currency_symbol": "$",
        "trial_threshold_usd": 200.00,
        "market_tier": "major",
        "market_description": "US Market",
    },
    {
        "currency_code": "EUR",
        "currency_symbol": "€",
        "trial_threshold_usd": 180.00,
        "market_tier": "major",
        "market_description": "European Market",
    },
    {
        "currency_code": "GBP",
        "currency_symbol": "£",
        "trial_threshold_usd": 160.00,
        "market_tier": "major",
        "market_description": "UK Market",
    },
    {
        "currency_code": "CAD",
        "currency_symbol": "C$",
        "trial_threshold_usd": 200.00,
        "market_tier": "major",
        "market_description": "Canadian Market",
    },
    {
        "currency_code": "AUD",
        "currency_symbol": "A$",
        "trial_threshold_usd": 200.00,
        "market_tier": "major",
        "market_description": "Australian Market",
    },
    {
        "currency_code": "JPY",
        "currency_symbol": "¥",
        "trial_threshold_usd": 200.00,
        "market_tier": "major",
        "market_description": "Japanese Market",
    },
    {
        "currency_code": "CHF",
        "currency_symbol": "CHF",
        "trial_threshold_usd": 180.00,
        "market_tier": "major",
        "market_description": "Swiss Market",
    },
    {
        "currency_code": "SEK",
        "currency_symbol": "kr",
        "trial_threshold_usd": 200.00,
        "market_tier": "major",
        "market_description": "Swedish Market",
    },
    {
        "currency_code": "NOK",
        "currency_symbol": "kr",
        "trial_threshold_usd": 200.00,
        "market_tier": "major",
        "market_description": "Norwegian Market",
    },
    {
        "currency_code": "DKK",
        "currency_symbol": "kr",
        "trial_threshold_usd": 200.00,
        "market_tier": "major",
        "market_description": "Danish Market",
    },
    # Emerging Markets - Moderate thresholds
    {
        "currency_code": "INR",
        "currency_symbol": "₹",
        "trial_threshold_usd": 100.00,
        "market_tier": "emerging",
        "market_description": "Indian Market",
    },
    {
        "currency_code": "BRL",
        "currency_symbol": "R$",
        "trial_threshold_usd": 200.00,
        "market_tier": "emerging",
        "market_description": "Brazilian Market",
    },
    {
        "currency_code": "MXN",
        "currency_symbol": "$",
        "trial_threshold_usd": 200.00,
        "market_tier": "emerging",
        "market_description": "Mexican Market",
    },
    {
        "currency_code": "KRW",
        "currency_symbol": "₩",
        "trial_threshold_usd": 200.00,
        "market_tier": "emerging",
        "market_description": "Korean Market",
    },
    {
        "currency_code": "CNY",
        "currency_symbol": "¥",
        "trial_threshold_usd": 200.00,
        "market_tier": "emerging",
        "market_description": "Chinese Market",
    },
    {
        "currency_code": "PLN",
        "currency_symbol": "zł",
        "trial_threshold_usd": 200.00,
        "market_tier": "emerging",
        "market_description": "Polish Market",
    },
    {
        "currency_code": "CZK",
        "currency_symbol": "Kč",
        "trial_threshold_usd": 200.00,
        "market_tier": "emerging",
        "market_description": "Czech Market",
    },
    {
        "currency_code": "HUF",
        "currency_symbol": "Ft",
        "trial_threshold_usd": 200.00,
        "market_tier": "emerging",
        "market_description": "Hungarian Market",
    },
    {
        "currency_code": "ZAR",
        "currency_symbol": "R",
        "trial_threshold_usd": 200.00,
        "market_tier": "emerging",
        "market_description": "South African Market",
    },
    {
        "currency_code": "TRY",
        "currency_symbol": "₺",
        "trial_threshold_usd": 200.00,
        "market_tier": "emerging",
        "market_description": "Turkish Market",
    },
    # Developing Markets - Lower thresholds
    {
        "currency_code": "VND",
        "currency_symbol": "₫",
        "trial_threshold_usd": 50.00,
        "market_tier": "developing",
        "market_description": "Vietnamese Market",
    },
    {
        "currency_code": "IDR",
        "currency_symbol": "Rp",
        "trial_threshold_usd": 50.00,
        "market_tier": "developing",
        "market_description": "Indonesian Market",
    },
    {
        "currency_code": "PHP",
        "currency_symbol": "₱",
        "trial_threshold_usd": 50.00,
        "market_tier": "developing",
        "market_description": "Philippine Market",
    },
    {
        "currency_code": "THB",
        "currency_symbol": "฿",
        "trial_threshold_usd": 50.00,
        "market_tier": "developing",
        "market_description": "Thai Market",
    },
    {
        "currency_code": "MYR",
        "currency_symbol": "RM",
        "trial_threshold_usd": 200.00,
        "market_tier": "developing",
        "market_description": "Malaysian Market",
    },
    {
        "currency_code": "SGD",
        "currency_symbol": "S$",
        "trial_threshold_usd": 200.00,
        "market_tier": "developing",
        "market_description": "Singapore Market",
    },
    {
        "currency_code": "BDT",
        "currency_symbol": "৳",
        "trial_threshold_usd": 50.00,
        "market_tier": "developing",
        "market_description": "Bangladeshi Market",
    },
    {
        "currency_code": "PKR",
        "currency_symbol": "₨",
        "trial_threshold_usd": 50.00,
        "market_tier": "developing",
        "market_description": "Pakistani Market",
    },
    {
        "currency_code": "LKR",
        "currency_symbol": "₨",
        "trial_threshold_usd": 50.00,
        "market_tier": "developing",
        "market_description": "Sri Lankan Market",
    },
    {
        "currency_code": "NPR",
        "currency_symbol": "₨",
        "trial_threshold_usd": 50.00,
        "market_tier": "developing",
        "market_description": "Nepalese Market",
    },
]


async def seed_trial_configs():
    """Seed trial configurations using SQLAlchemy"""
    session_factory = await get_session_factory()

    async with session_factory() as session:
        try:
            # Check if data exists
            result = await session.execute(select(TrialConfig))
            existing_configs = result.scalars().all()

            if existing_configs:
                print(
                    f"ℹ️ Trial configs already exist ({len(existing_configs)} records)"
                )
                return

            print("🌍 Seeding trial configurations...")

            # Insert all configs
            for config_data in TRIAL_CONFIG_DATA:
                trial_config = TrialConfig(
                    currency_code=config_data["currency_code"],
                    currency_symbol=config_data["currency_symbol"],
                    trial_threshold_usd=Decimal(
                        str(config_data["trial_threshold_usd"])
                    ),
                    market_tier=config_data["market_tier"],
                    market_description=config_data["market_description"],
                    is_active=True,
                )
                session.add(trial_config)

            await session.commit()
            print(f"✅ Seeded {len(TRIAL_CONFIG_DATA)} trial configurations")

        except Exception as e:
            print(f"❌ Error seeding trial configs: {e}")
            await session.rollback()
            raise


async def main():
    """Main function"""
    print("🚀 Starting trial configuration seeding...")

    try:
        await seed_trial_configs()
        print("✅ Seeding completed successfully!")
    except Exception as e:
        print(f"❌ Seeding failed: {e}")
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())
