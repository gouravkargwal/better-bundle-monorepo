#!/usr/bin/env python3
"""
Redis Reset Script for Gorse
Flushes all data from Redis database
"""

import redis
import sys
from datetime import datetime

# Redis connection details
REDIS_CONFIG = {"host": "10.80.138.89", "port": 6379, "db": 0, "decode_responses": True}


def reset_redis_database():
    """Flush all data from Redis"""

    print("🔴 Starting Redis database reset...")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    try:
        # Connect to Redis
        print("🔌 Connecting to Redis...")
        r = redis.Redis(**REDIS_CONFIG)

        # Test connection
        r.ping()
        print("✅ Connected to Redis successfully!")

        # Get current database info
        info = r.info()
        print(f"📊 Redis Version: {info.get('redis_version', 'Unknown')}")
        print(f"📊 Connected Clients: {info.get('connected_clients', 'Unknown')}")
        print(f"📊 Used Memory: {info.get('used_memory_human', 'Unknown')}")

        # Count keys before flush
        key_count = r.dbsize()
        print(f"🔑 Keys before flush: {key_count}")

        if key_count > 0:
            print("\n🗑️  Flushing Redis database...")
            r.flushdb()
            print("✅ Database flushed successfully!")

            # Verify flush
            new_key_count = r.dbsize()
            print(f"🔑 Keys after flush: {new_key_count}")

            if new_key_count == 0:
                print("✅ Redis database is now completely empty!")
            else:
                print(f"⚠️  Some keys remain: {new_key_count}")
        else:
            print("✅ Redis database is already empty!")

        print("\n🎯 Redis reset complete!")
        print("=" * 60)

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    finally:
        if "r" in locals():
            r.close()
            print("🔌 Redis connection closed")


if __name__ == "__main__":
    reset_redis_database()
