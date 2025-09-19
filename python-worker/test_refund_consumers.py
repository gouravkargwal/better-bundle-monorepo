#!/usr/bin/env python3
"""
Test script to verify refund consumers are working correctly
"""

import asyncio
import json
from datetime import datetime
from decimal import Decimal

from app.core.database import get_database
from app.core.logging import get_logger

logger = get_logger(__name__)


async def test_refund_consumers():
    """Test if refund consumers are processing data correctly"""

    db = await get_database()

    # Check if we have any refund data
    refund_data_count = await db.refunddata.count()
    refund_line_items_count = await db.refundlineitemdata.count()
    refund_adjustments_count = await db.refundattributionadjustment.count()

    print(f"📊 Refund Data Summary:")
    print(f"  - RefundData records: {refund_data_count}")
    print(f"  - RefundLineItemData records: {refund_line_items_count}")
    print(f"  - RefundAttributionAdjustment records: {refund_adjustments_count}")

    if refund_data_count > 0:
        # Get latest refund data
        latest_refund = await db.refunddata.find_first(order={"createdAt": "desc"})

        print(f"\n🔍 Latest Refund Data:")
        print(f"  - Shop ID: {latest_refund.shopId}")
        print(f"  - Order ID: {latest_refund.orderId}")
        print(f"  - Refund ID: {latest_refund.refundId}")
        print(f"  - Total Amount: ${latest_refund.totalRefundAmount}")
        print(f"  - Note: {latest_refund.note}")
        print(f"  - Restock: {latest_refund.restock}")
        print(f"  - Created: {latest_refund.createdAt}")

        # Check line items
        line_items = await db.refundlineitemdata.find_many(
            where={"refundId": latest_refund.id}
        )

        print(f"\n📦 Refund Line Items ({len(line_items)}):")
        for li in line_items:
            print(f"  - Product: {li.productId}, Variant: {li.variantId}")
            print(f"    Quantity: {li.quantity}, Unit Price: ${li.unitPrice}")
            print(f"    Refund Amount: ${li.refundAmount}")

        # Check attribution adjustments
        adjustments = await db.refundattributionadjustment.find_many(
            where={"refundId": latest_refund.id}
        )

        print(f"\n💰 Refund Attribution Adjustments ({len(adjustments)}):")
        for adj in adjustments:
            print(f"  - Per Extension Refund: {adj.perExtensionRefund}")
            print(f"  - Total Refund Amount: ${adj.totalRefundAmount}")
            print(f"  - Computed At: {adj.computedAt}")

    else:
        print("❌ No refund data found. Try creating a refund first.")

    # Check raw order data for refunds (simplified query)
    raw_orders_with_refunds = await db.raworder.find_many()

    print(f"\n📋 Raw Orders with Refunds: {len(raw_orders_with_refunds)}")
    for raw_order in raw_orders_with_refunds[:3]:  # Show first 3
        payload = raw_order.payload if isinstance(raw_order.payload, dict) else {}
        refunds = payload.get("refunds", [])
        print(f"  - Order {raw_order.shopifyId}: {len(refunds)} refunds")
        for refund in refunds[:2]:  # Show first 2 refunds
            print(f"    - Refund {refund.get('id')}: ${refund.get('amount', 0)}")


if __name__ == "__main__":
    asyncio.run(test_refund_consumers())
