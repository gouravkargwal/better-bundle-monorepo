#!/usr/bin/env python3
"""
Test script to check refund data structure
"""

import asyncio
from app.core.database import get_database


async def test_refund_structure():
    """Test refund data structure"""

    db = await get_database()

    # Get the order with refunds
    order = await db.raworder.find_first(where={"shopifyId": "6081157628043"})

    if order and order.payload:
        payload = order.payload if isinstance(order.payload, dict) else {}
        refunds = payload.get("refunds", [])

        print(f"🔍 Refund Data Structure:")
        print(f"  - Refunds count: {len(refunds)}")

        for i, refund in enumerate(refunds):
            print(f"\n  - Refund {i}:")
            print(f"    - Keys: {list(refund.keys())}")
            print(f"    - ID: {refund.get('id')}")
            print(f"    - Order ID: {refund.get('order_id')}")
            print(f"    - Amount: {refund.get('amount')}")
            print(f"    - Created: {refund.get('created_at')}")
            print(f"    - Note: {refund.get('note')}")
            print(f"    - Restock: {refund.get('restock')}")

            # Check refund_line_items
            if "refund_line_items" in refund:
                line_items = refund["refund_line_items"]
                print(f"    - Line items count: {len(line_items)}")

                for j, item in enumerate(line_items[:2]):  # Show first 2
                    print(
                        f"      - Item {j}: {item.get('id')} - ${item.get('subtotal')}"
                    )
            else:
                print(f"    - No refund_line_items")

            # Check transactions
            if "transactions" in refund:
                transactions = refund["transactions"]
                print(f"    - Transactions count: {len(transactions)}")

                for j, txn in enumerate(transactions[:2]):  # Show first 2
                    print(f"      - Transaction {j}: ${txn.get('amount')}")
            else:
                print(f"    - No transactions")


if __name__ == "__main__":
    asyncio.run(test_refund_structure())
