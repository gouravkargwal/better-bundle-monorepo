import asyncio
import json
import sys
import os
import time
from datetime import datetime

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

python_worker_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, python_worker_dir)

from app.core.config.kafka_settings import kafka_settings
from app.core.messaging.event_publisher import EventPublisher
from app.core.logging import get_logger

logger = get_logger(__name__)


# Shop configuration (choose one)
SHOP_DOMAIN = "vnsaid.myshopify.com"  # Use this for shop domain
SHOP_ID = "cmg9hni8y0000v39a53hdajb3"  # Or use this for shop ID (set SHOP_DOMAIN to None if using this)
ORDER_ID = "6101770043531"  # Shopify order ID to test


async def test_order_paid_event():
    """Test function to fire a single order paid event"""

    publisher = None

    try:
        # Initialize Kafka publisher
        logger.info("🚀 Initializing Kafka publisher...")
        publisher = EventPublisher(kafka_settings.model_dump())
        await publisher.initialize()
        logger.info("✅ Kafka publisher initialized")

        # Prepare event data (matching Remix webhook structure)
        event_data = {
            "event_type": "order_paid",
            "shopify_id": str(ORDER_ID),
            "timestamp": int(time.time() * 1000),
            "source": "test_script",
        }

        # Add shop identifier
        if SHOP_DOMAIN:
            event_data["shop_domain"] = SHOP_DOMAIN
        if SHOP_ID:
            event_data["shop_id"] = SHOP_ID

        # Add additional metadata

        # Log the event data
        logger.info("📋 Event data:")
        logger.info(json.dumps(event_data, indent=2))

        # Publish the event
        logger.info(f"🚀 Publishing order paid event for order {ORDER_ID}...")
        message_id = await publisher.publish_shopify_event(event_data)

        logger.info(f"✅ Order paid event published successfully!")
        logger.info(f"   Message ID: {message_id}")
        logger.info(f"   Order ID: {ORDER_ID}")
        logger.info(f"   Shop: {SHOP_DOMAIN or SHOP_ID}")

        return message_id

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise

    finally:
        # Clean up
        if publisher:
            await publisher.close()
            logger.info("🔌 Kafka publisher closed")


async def test_multiple_orders():
    """Test function to fire multiple order paid events"""

    # Configuration for multiple orders
    ORDERS = ["12345", "67890", "11111", "22222"]

    publisher = None

    try:
        # Initialize Kafka publisher
        logger.info("🚀 Initializing Kafka publisher...")
        publisher = EventPublisher(kafka_settings.model_dump())
        await publisher.initialize()
        logger.info("✅ Kafka publisher initialized")

        message_ids = []

        for i, order_id in enumerate(ORDERS):
            try:
                logger.info(
                    f"🚀 Publishing event {i+1}/{len(ORDERS)} for order {order_id}"
                )

                # Prepare event data
                event_data = {
                    "event_type": "order_paid",
                    "shopify_id": str(order_id),
                    "timestamp": int(time.time() * 1000),
                    "source": "test_script",
                    "batch_index": i + 1,
                    "total_orders": len(ORDERS),
                }

                # Add shop identifier
                if SHOP_DOMAIN:
                    event_data["shop_domain"] = SHOP_DOMAIN
                if SHOP_ID:
                    event_data["shop_id"] = SHOP_ID

                # Add additional metadata

                # Publish the event
                message_id = await publisher.publish_shopify_event(event_data)
                message_ids.append(message_id)

                logger.info(f"✅ Event {i+1} published: {message_id}")

                # Small delay between events
                if i < len(ORDERS) - 1:
                    await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(
                    f"❌ Failed to publish event {i+1} for order {order_id}: {e}"
                )
                continue

        logger.info(
            f"✅ Published {len(message_ids)}/{len(ORDERS)} events successfully"
        )
        for i, msg_id in enumerate(message_ids):
            logger.info(f"   Event {i+1}: {msg_id}")

        return message_ids

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise

    finally:
        # Clean up
        if publisher:
            await publisher.close()
            logger.info("🔌 Kafka publisher closed")


async def main():
    """Main function - choose which test to run"""

    print("🧪 Order Paid Event Test Script")
    print("=" * 50)

    # Choose test type
    test_type = "single"  # Change to "multiple" to test multiple orders

    if test_type == "single":
        print("Running single order test...")
        await test_order_paid_event()
    elif test_type == "multiple":
        print("Running multiple orders test...")
        await test_multiple_orders()
    else:
        print("❌ Invalid test type. Choose 'single' or 'multiple'")
        return

    print("✅ Test completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
