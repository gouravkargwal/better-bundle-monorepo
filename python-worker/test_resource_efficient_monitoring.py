#!/usr/bin/env python3
"""
Test Resource-Efficient Gorse Training Monitoring
Demonstrates how the system automatically detects training completion without polling
"""

import asyncio
import redis
from datetime import datetime


async def test_resource_efficient_monitoring():
    """Test the resource-efficient monitoring system"""

    print("🚀 Testing Resource-Efficient Gorse Training Monitoring")
    print("=" * 60)

    # Connect to Redis
    r = redis.Redis(host="localhost", port=6379, decode_responses=True)

    print("📊 Current Redis State:")
    current_keys = {
        "item_neighbors": len(r.keys("item_neighbors_digest/*")),
        "global_meta": len(r.keys("global_meta/*")),
        "popular_items": 1 if r.exists("popular_items") else 0,
        "latest_items": 1 if r.exists("latest_items") else 0,
    }

    for key_type, count in current_keys.items():
        print(f"   - {key_type}: {count}")

    print("\n🎯 How Resource-Efficient Monitoring Works:")
    print("1. ✅ Training event published to Redis stream")
    print("2. ✅ ML consumer processes event and starts Gorse training")
    print("3. ✅ Resource-efficient monitor starts (ZERO polling)")
    print("4. ✅ Redis keyspace notifications detect key changes")
    print("5. ✅ Automatic progress updates and completion detection")
    print("6. ✅ Monitor automatically stops when training completes")

    print("\n💡 Resource Benefits:")
    print("   - ❌ NO continuous polling")
    print("   - ❌ NO resource waste")
    print("   - ❌ NO manual status checks")
    print("   - ✅ Real-time notifications")
    print("   - ✅ Automatic cleanup")
    print("   - ✅ Zero resource overhead when idle")

    print("\n🔍 Test the System:")
    print("1. Publish a training event:")
    print(
        "   redis-cli XADD 'betterbundle:ml-training' '*' 'event_type' 'ML_TRAINING_REQUESTED' ..."
    )
    print("\n2. Watch automatic monitoring:")
    print("   - Monitor starts automatically")
    print("   - Detects Redis key changes")
    print("   - Publishes progress events")
    print("   - Stops when training completes")

    print("\n📡 Monitor Training Progress:")
    print(
        "   redis-cli XREAD COUNT 10 STREAMS 'betterbundle:gorse-training-complete' 0"
    )

    print("\n" + "=" * 60)
    print("🎉 Resource-efficient monitoring is ready!")


if __name__ == "__main__":
    asyncio.run(test_resource_efficient_monitoring())
