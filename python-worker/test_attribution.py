#!/usr/bin/env python3
"""
Test script for attribution engine
"""
import asyncio
from app.domains.billing.services.attribution_engine import (
    AttributionEngine,
    AttributionContext,
)
from app.core.database.simple_db_client import get_database
from decimal import Decimal
from datetime import datetime


async def test_attribution():
    db = await get_database()
    try:
        print("🔍 Testing Attribution Engine...")

        engine = AttributionEngine(db)
        context = AttributionContext(
            order_id="6081172439179",
            shop_id="cmfnmj5sn0000v3gaipwx948o",
            customer_id="8619514265739",
            session_id="unified_1758208661161_niqxnclr5",
            purchase_amount=Decimal("68.56"),
            purchase_products=[{"id": "7894679355531", "price": 34.28}],
            purchase_time=datetime.utcnow(),
        )

        print("📊 Running attribution calculation...")
        result = await engine.calculate_attribution(context)

        print("✅ Attribution completed successfully!")
        print(f"📋 Order ID: {result.order_id}")
        print(f"💰 Total attributed revenue: ${result.total_attributed_revenue}")
        print(f"📊 Attribution breakdown: {len(result.attribution_breakdown)} items")

        if result.attribution_breakdown:
            print("\n🎯 Attribution breakdown details:")
            for i, breakdown in enumerate(result.attribution_breakdown, 1):
                print(
                    f"  {i}. {breakdown.extension_type}: ${breakdown.attributed_amount}"
                )

        print(f"\n🎉 Status: {result.status}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(test_attribution())
