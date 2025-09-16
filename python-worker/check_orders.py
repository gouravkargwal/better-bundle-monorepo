#!/usr/bin/env python3
"""
Simple script to check what orders exist in the database
"""

import asyncio
import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))

from app.core.database import get_database
from app.core.logging import get_logger

logger = get_logger(__name__)


async def check_orders():
    """Check what orders exist in the database"""

    try:
        db = await get_database()

        # Get all shops first
        shops_query = 'SELECT id, "shopDomain" FROM "Shop" LIMIT 10'
        shops_result = await db.query_raw(shops_query)

        if not shops_result:
            logger.info("No shops found in database")
            return

        logger.info(f"Found {len(shops_result)} shops:")
        for shop in shops_result:
            logger.info(f"  - {shop['id']}: {shop['shopDomain']}")

        # Get orders for the first shop
        first_shop = shops_result[0]
        shop_id = first_shop["id"]

        logger.info(
            f"\nChecking orders for shop: {first_shop['shopDomain']} ({shop_id})"
        )

        # Get orders
        orders_query = """
        SELECT "orderId", "orderName", "totalAmount", "financialStatus", 
               "totalRefundedAmount", "orderDate", "customerEmail"
        FROM "OrderData" 
        WHERE "shopId" = $1 
        ORDER BY "orderDate" DESC 
        LIMIT 5
        """

        orders_result = await db.query_raw(orders_query, shop_id)

        if orders_result:
            logger.info(f"Found {len(orders_result)} orders:")
            for order in orders_result:
                logger.info(f"  - Order {order['orderId']} ({order['orderName']}):")
                logger.info(f"    Amount: ${order['totalAmount']}")
                logger.info(f"    Status: {order['financialStatus']}")
                logger.info(f"    Refunded: ${order['totalRefundedAmount'] or 0}")
                logger.info(f"    Date: {order['orderDate']}")
                logger.info(f"    Customer: {order['customerEmail'] or 'Guest'}")
                logger.info("")
        else:
            logger.info("No orders found for this shop")

        # Also check raw orders
        raw_orders_query = """
        SELECT "shopifyId", "shopifyCreatedAt", "shopifyUpdatedAt"
        FROM "RawOrder" 
        WHERE "shopId" = $1 
        ORDER BY "extractedAt" DESC 
        LIMIT 3
        """

        raw_orders_result = await db.query_raw(raw_orders_query, shop_id)

        if raw_orders_result:
            logger.info(f"Found {len(raw_orders_result)} raw orders:")
            for raw_order in raw_orders_result:
                logger.info(f"  - Raw Order {raw_order['shopifyId']}:")
                logger.info(f"    Created: {raw_order['shopifyCreatedAt']}")
                logger.info(f"    Updated: {raw_order['shopifyUpdatedAt']}")
        else:
            logger.info("No raw orders found for this shop")

    except Exception as e:
        logger.error(f"Error checking orders: {e}")
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")


if __name__ == "__main__":
    asyncio.run(check_orders())
