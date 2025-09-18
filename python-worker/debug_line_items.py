#!/usr/bin/env python3
"""
Debug script to check line items structure
"""
import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from app.core.database.simple_db_client import get_database


async def debug_line_items():
    """Debug line items structure"""
    try:
        db = await get_database()

        # Get a sample order
        order = await db.orderdata.find_first(
            where={"shopId": "cmfnmj5sn0000v3gaipwx948o", "customerId": "8619514265739"}
        )

        if not order:
            print("No order found")
            return

        print(f"Order ID: {order.orderId}")
        print(f"Customer: {order.customerId}")
        print(f"Line items type: {type(order.lineItems)}")
        print(f"Line items: {order.lineItems}")

        if order.lineItems:
            print(f"Number of line items: {len(order.lineItems)}")
            for i, item in enumerate(order.lineItems):
                print(f"  Line item {i+1}: {item}")
        else:
            print("No line items or line items is None")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_line_items())
