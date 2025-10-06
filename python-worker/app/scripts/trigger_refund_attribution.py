#!/usr/bin/env python3
"""
Script to trigger refund attribution for orders that have refunds but weren't processed.

This script:
1. Finds orders with refunds in the raw data
2. Republishes them to trigger normalization
3. This should detect refunds and publish refund attribution events
"""

import asyncio
import sys
import os
from datetime import datetime
from typing import List, Dict, Any

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

from app.core.database.session import get_session_context
from app.core.messaging.event_publisher import EventPublisher
from app.core.config.kafka_settings import kafka_settings
from app.core.database.models.raw_data import RawOrder
from sqlalchemy import select, and_
from app.core.logging import get_logger

logger = get_logger(__name__)


async def find_orders_with_refunds(shop_id: str) -> List[Dict[str, Any]]:
    """Find orders that have refunds in their raw data."""
    orders_with_refunds = []

    async with get_session_context() as session:
        # Get all raw orders for the shop
        query = select(RawOrder).where(RawOrder.shop_id == shop_id)
        result = await session.execute(query)
        raw_orders = result.scalars().all()

        for raw_order in raw_orders:
            if not raw_order.payload:
                continue

            payload = raw_order.payload if isinstance(raw_order.payload, dict) else {}

            # Check if order has refunds - handle GraphQL edges format
            refunds_data = payload.get("refunds", {})
            if isinstance(refunds_data, dict):
                refunds = refunds_data.get("edges", [])
            else:
                refunds = refunds_data if isinstance(refunds_data, list) else []

            if refunds and len(refunds) > 0:
                orders_with_refunds.append(
                    {
                        "shop_id": raw_order.shop_id,
                        "order_id": raw_order.shopify_id,
                        "refund_count": len(refunds),
                        "refunds": refunds,
                        "raw_order_id": raw_order.id,
                    }
                )
                logger.info(
                    f"Found order {raw_order.shopify_id} with {len(refunds)} refunds"
                )

    return orders_with_refunds


async def trigger_order_reprocessing(shop_id: str, order_id: str):
    """Trigger order reprocessing to detect refunds and publish refund attribution events."""
    try:
        publisher = EventPublisher(kafka_settings.model_dump())
        await publisher.initialize()

        try:
            # Publish a data collection event for this specific order
            collection_event = {
                "event_type": "order_updated",  # This will trigger data collection
                "shop_id": shop_id,
                "shopify_id": order_id,
                "timestamp": datetime.utcnow().isoformat(),
                "trigger_source": "refund_attribution_script",
            }

            await publisher.publish_shopify_event(collection_event)
            logger.info(f"✅ Published data collection event for order {order_id}")

        finally:
            await publisher.close()

    except Exception as e:
        logger.error(f"Failed to trigger reprocessing for order {order_id}: {e}")
        raise


async def trigger_refund_attribution_events(orders_with_refunds: List[Dict[str, Any]]):
    """Directly trigger refund attribution events for orders with refunds."""
    try:
        publisher = EventPublisher(kafka_settings.model_dump())
        await publisher.initialize()

        try:
            for order_data in orders_with_refunds:
                shop_id = order_data["shop_id"]
                order_id = order_data["order_id"]
                refunds = order_data["refunds"]

                # Publish refund attribution events for each refund
                for refund in refunds:
                    # Handle GraphQL edges format: { "node": { "id": "...", ... } }
                    if isinstance(refund, dict):
                        if "node" in refund:
                            # GraphQL edges format
                            refund_node = refund["node"]
                            refund_id = str(refund_node.get("id", ""))
                        else:
                            # Direct refund object
                            refund_id = str(refund.get("id", ""))
                    else:
                        refund_id = str(refund)

                    if not refund_id or refund_id in ["edges", "page_info"]:
                        logger.warning(
                            f"Invalid refund ID found for refund in order {order_id}: {refund_id}"
                        )
                        continue

                    refund_event = {
                        "event_type": "refund_created",
                        "shop_id": shop_id,
                        "order_id": order_id,
                        "refund_id": refund_id,
                        "timestamp": datetime.utcnow().isoformat(),
                        "trigger_source": "refund_attribution_script",
                    }

                    await publisher.publish_refund_attribution_event(refund_event)
                    logger.info(
                        f"✅ Published refund attribution event for refund {refund_id} in order {order_id}"
                    )

        finally:
            await publisher.close()

    except Exception as e:
        logger.error(f"Failed to trigger refund attribution events: {e}")
        raise


async def main():
    """Main function to trigger refund attribution processing."""
    # Use the shop ID from your data
    shop_id = "cmgem0tut0000v3h2h38lsh1y"

    logger.info(f"🔍 Looking for orders with refunds in shop {shop_id}")

    # Find orders with refunds
    orders_with_refunds = await find_orders_with_refunds(shop_id)

    if not orders_with_refunds:
        logger.info("❌ No orders with refunds found")
        return

    logger.info(f"📦 Found {len(orders_with_refunds)} orders with refunds")

    # Option 1: Trigger order reprocessing (this will detect refunds during normalization)
    logger.info("🔄 Triggering order reprocessing to detect refunds...")
    for order_data in orders_with_refunds:
        await trigger_order_reprocessing(shop_id, order_data["order_id"])

    # Small delay to let the data collection process
    await asyncio.sleep(2)

    # Option 2: Directly trigger refund attribution events
    logger.info("💰 Directly triggering refund attribution events...")
    await trigger_refund_attribution_events(orders_with_refunds)

    logger.info("✅ Refund attribution processing triggered successfully!")
    logger.info(
        "📊 Check the logs to see if refund attribution events are being processed"
    )


if __name__ == "__main__":
    asyncio.run(main())
