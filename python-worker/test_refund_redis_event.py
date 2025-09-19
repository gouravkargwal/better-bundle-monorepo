#!/usr/bin/env python3
"""
Test script to trigger a sample refund Redis event
This simulates the exact format that comes from the refund webhook
"""

import asyncio
import redis.asyncio as redis
from datetime import datetime


async def trigger_sample_refund_event():
    """Trigger a sample refund event to test the consumer"""

    # Connect to Redis
    redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)

    try:
        # Sample refund message data (exact same data from webhook logs)
        refund_message = {
            "event_type": "refund_created",
            "shop_id": "cmfnmj5sn0000v3gaipwx948o",  # Exact shop ID from logs
            "shopify_id": "6081126858891",  # Exact order ID from logs
            "raw_record_id": "cmfpqbxih0010v3e5b2ihp8al",  # Exact raw record ID from logs
            "timestamp": "2025-09-19T05:13:59.871Z",  # Exact timestamp from logs
        }

        print("🚀 Triggering sample refund event...")
        print(f"📋 Message data: {refund_message}")

        # Publish to the refund normalization stream
        stream_name = "betterbundle:refund-normalization-jobs"

        # Convert to Redis Stream format (dictionary)
        stream_data = {key: str(value) for key, value in refund_message.items()}

        print(f"📡 Publishing to stream: {stream_name}")
        print(f"📡 Stream data: {stream_data}")

        # Add message to stream
        message_id = await redis_client.xadd(stream_name, stream_data)

        print(f"✅ Successfully published refund event!")
        print(f"📋 Message ID: {message_id}")
        print(f"📋 Stream: {stream_name}")
        print(f"📋 Shop ID: {refund_message['shop_id']}")
        print(f"📋 Order ID: {refund_message['shopify_id']}")
        print(f"📋 Raw Record ID: {refund_message['raw_record_id']}")

        return message_id

    except Exception as e:
        print(f"❌ Error triggering refund event: {e}")
        raise
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    print("🧪 Testing Refund Redis Event Trigger")
    print("=" * 50)

    asyncio.run(trigger_sample_refund_event())

    print("\n✅ Test completed!")
    print(
        "🔍 Check your Python worker logs to see if the consumer processes this event"
    )
