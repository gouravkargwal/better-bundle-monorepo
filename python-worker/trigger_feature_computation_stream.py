#!/usr/bin/env python3
"""
Script to trigger feature computation via Redis stream
"""
import asyncio
import sys
import os
import json
from datetime import datetime

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

from app.core.redis_client import streams_manager
from app.shared.constants.redis import FEATURES_COMPUTED_STREAM
from app.core.logging import get_logger
from app.shared.helpers import now_utc

logger = get_logger(__name__)


async def trigger_feature_computation_via_stream(shop_id: str, batch_size: int = 100):
    """Trigger feature computation by publishing to Redis stream"""
    try:
        logger.info(
            f"🚀 Publishing feature computation event to Redis stream for shop: {shop_id}"
        )

        # Initialize the streams manager
        await streams_manager.initialize()

        # Generate a unique job ID
        job_id = f"manual_feature_compute_{shop_id}_{now_utc().timestamp()}"

        # Prepare event metadata
        metadata = {
            "batch_size": batch_size,
            "trigger_source": "manual_script",
            "timestamp": now_utc().isoformat(),
            "processed_count": 0,  # Will be updated by the consumer
        }

        # Publish the event to the stream
        event_id = await streams_manager.publish_features_computed_event(
            job_id=job_id,
            shop_id=shop_id,
            features_ready=False,  # Features need to be computed
            metadata=metadata,
        )

        logger.info(f"✅ Successfully published feature computation event")
        logger.info(f"   Event ID: {event_id}")
        logger.info(f"   Job ID: {job_id}")
        logger.info(f"   Shop ID: {shop_id}")
        logger.info(f"   Stream: {FEATURES_COMPUTED_STREAM}")
        logger.info(f"   Batch Size: {batch_size}")

        return {
            "success": True,
            "event_id": event_id,
            "job_id": job_id,
            "shop_id": shop_id,
            "stream": FEATURES_COMPUTED_STREAM,
        }

    except Exception as e:
        logger.error(f"❌ Error publishing to Redis stream: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}


async def main():
    """Main function"""
    shop_id = "cmf4uf3tr0000v3rsmi68lnrj"
    batch_size = 100

    logger.info(
        f"🚀 Triggering feature computation via Redis stream for shop: {shop_id}"
    )
    logger.info(f"📊 Using batch size: {batch_size}")

    result = await trigger_feature_computation_via_stream(shop_id, batch_size)

    if result["success"]:
        print(f"\n✅ SUCCESS: Feature computation event published to Redis stream")
        print(f"📡 Event ID: {result['event_id']}")
        print(f"🆔 Job ID: {result['job_id']}")
        print(f"🏪 Shop ID: {result['shop_id']}")
        print(f"📊 Stream: {result['stream']}")
        print(
            f"\n💡 The feature computation consumer should pick up this event and process it."
        )
        print(f"   Check the consumer logs to see the processing progress.")
    else:
        print(f"\n❌ FAILED: Could not publish feature computation event")
        print(f"Error: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    asyncio.run(main())
