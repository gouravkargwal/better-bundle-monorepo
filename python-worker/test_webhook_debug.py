#!/usr/bin/env python3
"""
Test script to debug webhook issues
"""

import asyncio
from app.core.database import get_database

async def test_webhook_debug():
    """Test webhook database operations"""
    
    db = await get_database()
    
    # Test database connection
    print("🔍 Testing database connection...")
    try:
        shop_count = await db.shop.count()
        print(f"✅ Database connected - {shop_count} shops found")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return
    
    # Test RawOrder operations
    print("\n🔍 Testing RawOrder operations...")
    try:
        raw_order_count = await db.raworder.count()
        print(f"✅ RawOrder table accessible - {raw_order_count} records")
        
        # Test creating a minimal record
        test_shop = await db.shop.find_first()
        if test_shop:
            print(f"✅ Found test shop: {test_shop.id}")
            
            # Test if we can create a minimal RawOrder
            try:
                test_order = await db.raworder.create({
                    "data": {
                        "shopId": test_shop.id,
                        "payload": {
                            "refunds": [{"id": "test_refund", "amount": "10.00"}],
                            "id": "test_order",
                            "created_at": "2024-01-01T00:00:00Z",
                            "line_items": [],
                            "total_price": "0.00",
                            "currency": "USD"
                        },
                        "shopifyId": "test_order_123",
                        "shopifyCreatedAt": "2024-01-01T00:00:00Z",
                        "source": "webhook",
                        "format": "rest",
                        "receivedAt": "2024-01-01T00:00:00Z"
                    }
                })
                print(f"✅ Test RawOrder created: {test_order.id}")
                
                # Clean up
                await db.raworder.delete(where={"id": test_order.id})
                print("✅ Test RawOrder cleaned up")
                
            except Exception as e:
                print(f"❌ RawOrder creation failed: {e}")
        else:
            print("❌ No shops found for testing")
            
    except Exception as e:
        print(f"❌ RawOrder operations failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_webhook_debug())
