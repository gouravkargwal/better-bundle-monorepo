#!/usr/bin/env python3
"""
Test script to manually test refund consumer processing
"""

import asyncio
from app.consumers.refund_normalization_consumer import RefundNormalizationConsumer
from app.core.logging import get_logger

logger = get_logger(__name__)

async def test_consumer_manual():
    """Test refund consumer manually"""
    
    # Create consumer instance
    consumer = RefundNormalizationConsumer()
    
    # Create test message
    test_message = {
        "event_type": "refund_created",
        "shop_id": "cmfnmj5sn0000v3gaipwx948o",
        "shopify_id": "6081157628043",
        "refund_id": "912070443147",
        "timestamp": "2025-09-19T04:39:46.208Z",
        "refund_amount": 58.1,
        "refund_note": "",
        "refund_restock": True
    }
    
    print(f"🧪 Testing refund consumer with message:")
    print(f"  - Shop ID: {test_message['shop_id']}")
    print(f"  - Order ID: {test_message['shopify_id']}")
    print(f"  - Refund ID: {test_message['refund_id']}")
    
    try:
        # Process the message
        await consumer._process_single_message(test_message)
        print("✅ Consumer processing completed")
    except Exception as e:
        print(f"❌ Consumer processing failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_consumer_manual())
