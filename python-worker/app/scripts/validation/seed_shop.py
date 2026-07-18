"""
Seed a fake shop record to trigger the feature computation pipeline.

After running this, the pipeline will detect the new shop and start
processing any data you've seeded (products, customers, orders).

Run:
  uv run python-worker/app/scripts/validation/seed_shop.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from app.core.database.session import get_session_context
from app.core.database.models.shop import Shop

SHOP_ID = "validation_test_shop"
SHOP_DOMAIN = "validation-test-shop.myshopify.com"


async def seed_shop():
    print("=" * 50)
    print("Seeding shop record")
    print("=" * 50)

    async with get_session_context() as session:
        existing = await session.get(Shop, SHOP_ID)
        if existing:
            print(f"✅ Shop already exists (id={SHOP_ID}, domain={SHOP_DOMAIN})")
            return

        shop = Shop(
            id=SHOP_ID,
            shop_domain=SHOP_DOMAIN,
            access_token="test-token",
            plan_type="Free",
            currency_code="USD",
            money_format="${{amount}}",
            is_active=True,
            onboarding_completed=True,
        )
        session.add(shop)
        await session.commit()
        print(f"✅ Shop created (id={SHOP_ID}, domain={SHOP_DOMAIN})")

    print()
    print("Next: fill in data then run the validation pipeline.")


if __name__ == "__main__":
    asyncio.run(seed_shop())
