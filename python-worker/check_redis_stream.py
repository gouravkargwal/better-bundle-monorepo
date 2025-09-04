#!/usr/bin/env python3
"""
Script to check Redis stream contents
"""
import asyncio
import sys
import os
import json

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

from app.core.redis_client import get_redis_client
from app.shared.constants.redis import FEATURES_COMPUTED_STREAM
from app.core.logging import get_logger

logger = get_logger(__name__)


async def check_stream():
    """Check the Redis stream contents"""
    try:
        redis = await get_redis_client()

        # Get stream info
        stream_info = await redis.xinfo_stream(FEATURES_COMPUTED_STREAM)
        print(f"📊 Stream: {FEATURES_COMPUTED_STREAM}")
        print(f"📈 Length: {stream_info.get('length', 0)}")
        print(f"🔢 Groups: {stream_info.get('groups', 0)}")
        print(f"👥 Consumers: {stream_info.get('first-entry', 'None')}")

        # Get recent entries
        entries = await redis.xrevrange(FEATURES_COMPUTED_STREAM, count=5)
        print(f"\n📋 Recent entries (last 5):")

        for entry_id, fields in entries:
            print(f"\n🆔 Entry ID: {entry_id}")
            for key, value in fields.items():
                if key == "metadata":
                    try:
                        metadata = json.loads(value)
                        print(f"   {key}: {json.dumps(metadata, indent=2)}")
                    except:
                        print(f"   {key}: {value}")
                else:
                    print(f"   {key}: {value}")

        # Check consumer groups
        try:
            groups = await redis.xinfo_groups(FEATURES_COMPUTED_STREAM)
            print(f"\n👥 Consumer Groups:")
            for group in groups:
                print(f"   Group: {group['name']}")
                print(f"   Consumers: {group['consumers']}")
                print(f"   Pending: {group['pending']}")
        except Exception as e:
            print(f"   No consumer groups found: {e}")

    except Exception as e:
        logger.error(f"Error checking stream: {str(e)}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(check_stream())
