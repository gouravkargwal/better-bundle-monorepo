#!/usr/bin/env python3
"""
Redis Monitor for Gorse Training Completion
Monitors Redis keys to detect when Gorse training completes
"""

import redis
import time
import json
from datetime import datetime


def monitor_gorse_training():
    """Monitor Redis for Gorse training completion indicators"""

    # Connect to Redis
    r = redis.Redis(host="localhost", port=6379, decode_responses=True)

    print("🔍 Monitoring Redis for Gorse training activity...")
    print("=" * 60)

    # Get initial state
    initial_keys = {
        "item_neighbors": len(r.keys("item_neighbors_digest/*")),
        "global_meta": len(r.keys("global_meta/*")),
        "popular_items": 1 if r.exists("popular_items") else 0,
        "latest_items": 1 if r.exists("latest_items") else 0,
    }

    print(f"📊 Initial Redis State:")
    print(f"   - Item neighbors: {initial_keys['item_neighbors']}")
    print(f"   - Global metadata: {initial_keys['global_meta']}")
    print(f"   - Popular items: {initial_keys['popular_items']}")
    print(f"   - Latest items: {initial_keys['latest_items']}")
    print()

    last_check = time.time()
    check_interval = 5  # Check every 5 seconds

    try:
        while True:
            current_time = time.time()

            if current_time - last_check >= check_interval:
                # Check current state
                current_keys = {
                    "item_neighbors": len(r.keys("item_neighbors_digest/*")),
                    "global_meta": len(r.keys("global_meta/*")),
                    "popular_items": 1 if r.exists("popular_items") else 0,
                    "latest_items": 1 if r.exists("latest_items") else 0,
                }

                # Check for changes
                changes = []
                for key_type in current_keys:
                    if current_keys[key_type] != initial_keys[key_type]:
                        change = current_keys[key_type] - initial_keys[key_type]
                        if change > 0:
                            changes.append(f"➕ {key_type}: +{change}")
                        else:
                            changes.append(f"➖ {key_type}: {change}")

                if changes:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"[{timestamp}] 🚀 Training Progress Detected:")
                    for change in changes:
                        print(f"   {change}")

                    # Update initial state
                    initial_keys = current_keys.copy()

                    # Check if training might be complete
                    if (
                        current_keys["item_neighbors"] > 0
                        and current_keys["global_meta"] > 0
                    ):
                        print(f"   🎯 Training appears to be progressing!")

                        # Check specific Gorse keys
                        gorse_keys = r.keys("item_neighbors_digest/*")
                        if gorse_keys:
                            print(
                                f"   📋 Sample item neighbors: {len(gorse_keys)} keys"
                            )
                            sample_keys = gorse_keys[:3]
                            for key in sample_keys:
                                print(f"      - {key}")

                last_check = current_time

            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped by user")
        print("=" * 60)
        print("📊 Final Redis State:")
        final_keys = {
            "item_neighbors": len(r.keys("item_neighbors_digest/*")),
            "global_meta": len(r.keys("global_meta/*")),
            "popular_items": 1 if r.exists("popular_items") else 0,
            "latest_items": 1 if r.exists("latest_items") else 0,
        }
        for key_type, count in final_keys.items():
            print(f"   - {key_type}: {count}")


if __name__ == "__main__":
    monitor_gorse_training()
