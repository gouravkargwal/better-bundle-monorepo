#!/usr/bin/env python3
"""
Debug script to check what refund data is actually in the database
"""

import asyncio
from app.core.database import get_database


async def debug_refund_data():
    """Debug what refund data exists in the database"""

    db = await get_database()

    # Check RawOrder data
    print("🔍 RawOrder Data:")
    raw_orders = await db.raworder.find_many(take=5)

    for order in raw_orders:
        print(f"  - ID: {order.id}")
        print(f"    Shop ID: {order.shopId}")
        print(f"    Shopify ID: {order.shopifyId}")
        print(f"    Source: {order.source}")
        print(f"    Format: {order.format}")

        # Check payload structure
        if order.payload:
            payload = order.payload if isinstance(order.payload, dict) else {}
            print(f"    Payload keys: {list(payload.keys())}")

            if "refunds" in payload:
                refunds = payload["refunds"]
                print(f"    Refunds count: {len(refunds)}")
                for i, refund in enumerate(refunds[:2]):  # Show first 2
                    print(
                        f"      Refund {i}: ID={refund.get('id')}, Amount={refund.get('amount')}"
                    )

        print()

    # Check if any orders have refunds
    print("🔍 Orders with Refunds:")
    orders_with_refunds = []
    for order in raw_orders:
        if order.payload and isinstance(order.payload, dict):
            payload = order.payload
            if "refunds" in payload and payload["refunds"]:
                orders_with_refunds.append(order)

    print(f"Found {len(orders_with_refunds)} orders with refunds")

    for order in orders_with_refunds:
        print(f"  - Order {order.shopifyId} (Shop: {order.shopId})")
        payload = order.payload if isinstance(order.payload, dict) else {}
        refunds = payload.get("refunds", [])
        for refund in refunds:
            print(f"    - Refund {refund.get('id')}: ${refund.get('amount', 0)}")


if __name__ == "__main__":
    asyncio.run(debug_refund_data())
