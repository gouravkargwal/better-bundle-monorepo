#!/usr/bin/env python3
"""
Debug script to investigate purchase exclusion issues
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the parent directory to the path so we can import app modules
parent_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(parent_dir))

from app.core.database.session import get_transaction_context
from app.core.database.models.order_data import OrderData, LineItemData
from app.core.database.models.shop import Shop
from app.recommandations.purchase_history import PurchaseHistoryService
from sqlalchemy import select, and_
from app.core.logging import get_logger

logger = get_logger(__name__)


async def debug_purchase_exclusions(shop_id: str, user_id: str):
    """Debug purchase exclusions for a specific user"""

    print(
        f"🔍 Debugging purchase exclusions for shop_id: {shop_id}, user_id: {user_id}"
    )

    async with get_transaction_context() as session:
        # 1. Check if shop exists
        shop_result = await session.execute(select(Shop).where(Shop.id == shop_id))
        shop = shop_result.scalar_one_or_none()

        if not shop:
            print(f"❌ Shop {shop_id} not found")
            return

        print(f"✅ Shop found: {shop.shop_domain}")

        # 2. Check if there are any orders for this user
        orders_result = await session.execute(
            select(OrderData)
            .where(and_(OrderData.shop_id == shop_id, OrderData.customer_id == user_id))
            .order_by(OrderData.order_date.desc())
        )
        orders = orders_result.scalars().all()

        print(f"📦 Found {len(orders)} orders for user {user_id}")

        if orders:
            print("\n📋 Order Details:")
            for i, order in enumerate(orders[:5]):  # Show first 5 orders
                print(f"  {i+1}. Order ID: {order.order_id}")
                print(f"     Date: {order.order_date}")
                print(f"     Total: ${order.total_amount}")
                print(f"     Status: {'Cancelled' if order.cancelled_at else 'Active'}")
                print(f"     Test: {order.test}")
                print(f"     Refunded: ${order.total_refunded_amount or 0}")

                # Get line items for this order
                line_items_result = await session.execute(
                    select(LineItemData).where(LineItemData.order_id == order.id)
                )
                line_items = line_items_result.scalars().all()

                print(f"     Line Items: {len(line_items)}")
                for item in line_items[:3]:  # Show first 3 line items
                    print(
                        f"       - Product: {item.product_id} | Qty: {item.quantity} | Price: ${item.price}"
                    )
                if len(line_items) > 3:
                    print(f"       ... and {len(line_items) - 3} more items")
                print()
        else:
            print("❌ No orders found for this user")

            # Check if there are any orders at all for this shop
            all_orders_result = await session.execute(
                select(OrderData).where(OrderData.shop_id == shop_id)
            )
            all_orders = all_orders_result.scalars().all()
            print(f"📊 Total orders in shop: {len(all_orders)}")

            if all_orders:
                print("🔍 Sample orders in shop:")
                for i, order in enumerate(all_orders[:3]):
                    print(
                        f"  {i+1}. Customer: {order.customer_id} | Order: {order.order_id} | Date: {order.order_date}"
                    )

        # 3. Test the purchase history service
        print(f"\n🧪 Testing PurchaseHistoryService...")

        try:
            purchased_products = await PurchaseHistoryService.get_purchased_product_ids(
                session=session,
                shop_id=shop_id,
                customer_id=user_id,
                exclude_refunded=True,
                exclude_cancelled=True,
            )
            print(
                f"✅ PurchaseHistoryService returned {len(purchased_products)} products"
            )

            if purchased_products:
                print("📦 Purchased products:")
                for product_id in purchased_products[:10]:  # Show first 10
                    print(f"  - {product_id}")
                if len(purchased_products) > 10:
                    print(f"  ... and {len(purchased_products) - 10} more")
            else:
                print("❌ No purchased products found")

        except Exception as e:
            print(f"❌ Error in PurchaseHistoryService: {e}")
            import traceback

            traceback.print_exc()


async def main():
    """Main function"""
    import argparse

    parser = argparse.ArgumentParser(description="Debug purchase exclusions")
    parser.add_argument("--shop-id", required=True, help="Shop ID")
    parser.add_argument("--user-id", required=True, help="User ID")

    args = parser.parse_args()

    await debug_purchase_exclusions(args.shop_id, args.user_id)


if __name__ == "__main__":
    asyncio.run(main())
