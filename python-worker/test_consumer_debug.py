#!/usr/bin/env python3
"""
Test script to debug consumer issues
"""

import asyncio
from app.core.database import get_database


async def test_consumer_debug():
    """Test consumer database operations"""

    db = await get_database()

    # Check if we can find the order that was created
    print("🔍 Looking for order 6081157628043...")

    try:
        # Look for the order that was created in the webhook
        order = await db.raworder.find_first(where={"shopifyId": "6081157628043"})

        if order:
            print(f"✅ Found order: {order.id}")
            print(f"  - Shop ID: {order.shopId}")
            print(f"  - Shopify ID: {order.shopifyId}")
            print(f"  - Created: {getattr(order, 'createdAt', 'N/A')}")

            # Check payload structure
            if order.payload:
                payload = order.payload if isinstance(order.payload, dict) else {}
                print(f"  - Payload keys: {list(payload.keys())}")

                if "refunds" in payload:
                    refunds = payload["refunds"]
                    print(f"  - Refunds count: {len(refunds)}")

                    for i, refund in enumerate(refunds):
                        print(
                            f"    - Refund {i}: ID={refund.get('id')}, Amount={refund.get('amount', 'N/A')}"
                        )
                else:
                    print("  - No refunds in payload")
            else:
                print("  - No payload data")
        else:
            print("❌ Order not found")

            # List recent orders
            recent_orders = await db.raworder.find_many(
                order={"createdAt": "desc"}, take=5
            )

            print(f"\n📋 Recent orders ({len(recent_orders)}):")
            for order in recent_orders:
                print(f"  - {order.shopifyId} (created: {order.createdAt})")

    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_consumer_debug())
