#!/usr/bin/env python3
"""
Debug script to check consumer status
"""
import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.consumers.consumer_manager import ConsumerManager
from app.consumers.refund_normalization_consumer import RefundNormalizationConsumer
from app.consumers.refund_attribution_consumer import RefundAttributionConsumer


async def debug_consumer_status():
    print("🔍 Debugging consumer status...")

    # Create consumer manager
    manager = ConsumerManager()

    # Create refund consumers
    refund_norm_consumer = RefundNormalizationConsumer()
    refund_attr_consumer = RefundAttributionConsumer()

    # Register consumers
    manager.register_consumers(
        refund_normalization_consumer=refund_norm_consumer,
        refund_attribution_consumer=refund_attr_consumer,
    )

    print(f"📋 Registered consumers: {list(manager.consumers.keys())}")
    print(f"🏃 Is running: {manager.is_running}")

    # Try to start consumers
    try:
        print("🚀 Starting consumer manager...")
        await manager.start()
        print(f"✅ Consumer manager started: {manager.is_running}")

        # Check individual consumer status
        for name, consumer in manager.consumers.items():
            print(f"  - {name}: {consumer.status.value}")

    except Exception as e:
        print(f"❌ Error starting consumers: {e}")
        import traceback

        traceback.print_exc()

    # Clean up
    try:
        await manager.stop_all_consumers()
        print("🛑 Consumer manager stopped")
    except Exception as e:
        print(f"⚠️ Error stopping consumers: {e}")


if __name__ == "__main__":
    asyncio.run(debug_consumer_status())
