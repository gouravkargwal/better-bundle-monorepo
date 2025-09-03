#!/usr/bin/env python3
"""
Test script to verify the complete data processing pipeline
"""

import asyncio
import time
from app.core.redis_client import streams_manager
from app.core.config import settings
from app.services.data_processor import data_processor
from app.services.features_consumer import features_consumer
from app.services.ml_training_consumer import ml_training_consumer
from app.core.logger import get_logger

logger = get_logger("pipeline-test")


async def test_complete_pipeline():
    """Test the complete data processing pipeline"""
    try:
        logger.info("Starting pipeline test...")

        # Initialize Redis streams
        await streams_manager.initialize()
        logger.info("Redis streams initialized")

        # Test data collection event
        test_event = {
            "job_id": f"test_job_{int(time.time())}",
            "shop_id": "test_shop_123",
            "shop_domain": "test.myshopify.com",
            "access_token": "test_token",
            "job_type": "complete",
            "days_back": 30,
        }

        logger.info("Publishing test data collection event...")
        await streams_manager.publish_event(
            stream_name=settings.DATA_JOB_STREAM, event_data=test_event
        )
        logger.info("Test event published successfully")

        # Wait a bit for processing
        await asyncio.sleep(5)

        # Check if features computation event was published
        logger.info("Checking for features computation events...")
        features_events = await streams_manager.read_events(
            stream_name=settings.FEATURES_COMPUTED_STREAM,
            consumer_group=settings.DATA_PROCESSOR_GROUP,
            consumer_name="test-consumer",
            count=10,
            block_ms=1000,
        )

        if features_events:
            logger.info(f"Found {len(features_events)} features computation events")
            for event in features_events:
                logger.info(f"Event: {event}")
        else:
            logger.info("No features computation events found")

        # Check if ML training event was published
        logger.info("Checking for ML training events...")
        ml_events = await streams_manager.read_events(
            stream_name=settings.ML_TRAINING_STREAM,
            consumer_group=settings.DATA_PROCESSOR_GROUP,
            consumer_name="test-consumer",
            count=10,
            block_ms=1000,
        )

        if ml_events:
            logger.info(f"Found {len(ml_events)} ML training events")
            for event in ml_events:
                logger.info(f"Event: {event}")
        else:
            logger.info("No ML training events found")

        logger.info("Pipeline test completed")

    except Exception as e:
        logger.error(f"Pipeline test failed: {e}")
        raise


async def main():
    """Main test function"""
    try:
        await test_complete_pipeline()
    except Exception as e:
        logger.error(f"Test failed: {e}")
        return 1
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
