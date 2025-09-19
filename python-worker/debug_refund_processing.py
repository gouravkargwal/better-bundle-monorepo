#!/usr/bin/env python3
"""
Debug script to check refund processing status
"""

import asyncio
from app.core.database import get_database
from app.core.logging import get_logger

logger = get_logger(__name__)

async def debug_refund_processing():
    """Debug what's happening with refund processing"""
    
    db = await get_database()
    
    # Check if we have any refund data
    refund_data_count = await db.refunddata.count()
    refund_line_items_count = await db.refundlineitemdata.count()
    refund_adjustments_count = await db.refundattributionadjustment.count()
    
    print(f"📊 Refund Processing Status:")
    print(f"  - RefundData records: {refund_data_count}")
    print(f"  - RefundLineItemData records: {refund_line_items_count}")
    print(f"  - RefundAttributionAdjustment records: {refund_adjustments_count}")
    
    # Check RawOrder data for refunds
    raw_orders = await db.raworder.find_many(take=5)
    
    print(f"\n🔍 Recent RawOrder Data:")
    for order in raw_orders:
        payload = order.payload if isinstance(order.payload, dict) else {}
        refunds = payload.get("refunds", [])
        line_items = payload.get("line_items", [])
        
        print(f"  - Order {order.shopifyId}:")
        print(f"    - Refunds: {len(refunds)}")
        print(f"    - Line Items: {len(line_items)}")
        print(f"    - Has refunds: {'refunds' in payload}")
        print(f"    - Has line_items: {'line_items' in payload}")
        
        if refunds:
            for i, refund in enumerate(refunds[:2]):  # Show first 2 refunds
                print(f"      - Refund {i}: ID={refund.get('id')}, Amount={refund.get('amount', 'N/A')}")
    
    # Check if there are any orders with refunds but no processed refund data
    orders_with_refunds = []
    for order in raw_orders:
        if order.payload and isinstance(order.payload, dict):
            payload = order.payload
            if "refunds" in payload and payload["refunds"]:
                orders_with_refunds.append(order)
    
    print(f"\n📋 Orders with Refunds: {len(orders_with_refunds)}")
    for order in orders_with_refunds:
        print(f"  - Order {order.shopifyId}: {len(order.payload.get('refunds', []))} refunds")
        print(f"    - Created: {order.createdAt}")
        print(f"    - Updated: {order.updatedAt}")
        
        # Check if refunds have been processed
        refunds = order.payload.get('refunds', [])
        for refund in refunds:
            refund_id = refund.get('id')
            if refund_id:
                # Check if this refund has been processed
                processed_refund = await db.refunddata.find_first(
                    where={"refundId": str(refund_id)}
                )
                if processed_refund:
                    print(f"      ✅ Refund {refund_id} processed")
                else:
                    print(f"      ❌ Refund {refund_id} NOT processed")

if __name__ == "__main__":
    asyncio.run(debug_refund_processing())
