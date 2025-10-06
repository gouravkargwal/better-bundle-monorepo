#!/usr/bin/env python3
"""
Retrigger Attribution Processing Script

This script allows you to retrigger attribution processing for existing orders
to test the fixed interaction metadata handling.

Usage:
    python app/scripts/retrigger_attribution.py --shop-id <shop_id> --order-id <order_id>
    python app/scripts/retrigger_attribution.py --shop-id <shop_id> --all-orders
    python app/scripts/retrigger_attribution.py --shop-id <shop_id> --recent-orders --days 7
"""

import asyncio
import argparse
import sys
from datetime import datetime, timedelta
from typing import List, Optional
import logging

# Add the project root to the Python path
sys.path.append("/Users/gouravkargwal/Desktop/BetterBundle/python-worker")

from app.core.database.session import get_session_context
from app.core.database.models import OrderData, UserSession, UserInteraction
from app.domains.billing.services.billing_service import BillingService
from app.domains.billing.models.attribution_models import PurchaseEvent
from sqlalchemy import select, and_, desc
from decimal import Decimal

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AttributionRetriggerScript:
    """Script to retrigger attribution processing for existing orders"""

    def __init__(self):
        self.processed_count = 0
        self.error_count = 0

    async def retrigger_order_attribution(self, shop_id: str, order_id: str) -> bool:
        """
        Retrigger attribution for a specific order

        Args:
            shop_id: Shop ID
            order_id: Order ID

        Returns:
            True if successful, False otherwise
        """
        try:
            async with get_session_context() as session:
                # Get the order
                order_result = await session.execute(
                    select(OrderData).where(
                        and_(
                            OrderData.shop_id == shop_id, OrderData.order_id == order_id
                        )
                    )
                )
                order = order_result.scalar_one_or_none()

                if not order:
                    logger.error(f"Order {order_id} not found for shop {shop_id}")
                    return False

                logger.info(f"Found order {order_id} with total ${order.total_amount}")

                # Check if customer has interactions
                customer_interactions = await self._get_customer_interactions(
                    session, shop_id, order.customer_id
                )

                if not customer_interactions:
                    logger.warning(
                        f"No interactions found for customer {order.customer_id}"
                    )
                    return False

                logger.info(
                    f"Found {len(customer_interactions)} interactions for customer {order.customer_id}"
                )

                # Create purchase event using order's currency_code (shop's base currency)
                if not order.currency_code:
                    logger.error(f"Order {order_id} has no currency_code, skipping")
                    return False

                purchase_event = PurchaseEvent(
                    order_id=order_id,
                    customer_id=order.customer_id,
                    shop_id=shop_id,
                    session_id=None,  # Will be determined from interactions
                    total_amount=Decimal(str(order.total_amount)),
                    currency=order.currency_code,  # Shop's base currency for trial calculations
                    products=self._parse_order_products(order.line_items),
                    created_at=order.order_date or order.created_at,
                    metadata={
                        "source": "retrigger_script",
                        "original_order_date": (
                            order.order_date or order.created_at
                        ).isoformat(),
                        "shop_currency": order.currency_code,
                        "presentment_currency": order.presentment_currency_code,
                    },
                )

                # Process attribution
                billing_service = BillingService(session)
                attribution_result = await billing_service.process_purchase_attribution(
                    purchase_event
                )

                logger.info(
                    f"✅ Attribution processed for order {order_id}: ${attribution_result.total_attributed_revenue}"
                )
                logger.info(
                    f"📊 Attribution breakdown: {len(attribution_result.attribution_breakdown)} items"
                )

                for breakdown in attribution_result.attribution_breakdown:
                    logger.info(
                        f"  - {breakdown.extension_type.value}: ${breakdown.attributed_amount} (weight: {breakdown.attribution_weight})"
                    )

                return True

        except Exception as e:
            logger.error(f"Error processing order {order_id}: {e}")
            return False

    async def retrigger_recent_orders(self, shop_id: str, days: int = 7) -> None:
        """
        Retrigger attribution for recent orders

        Args:
            shop_id: Shop ID
            days: Number of days to look back
        """
        try:
            async with get_session_context() as session:
                # Get recent orders
                cutoff_date = datetime.utcnow() - timedelta(days=days)

                orders_result = await session.execute(
                    select(OrderData)
                    .where(
                        and_(
                            OrderData.shop_id == shop_id,
                            OrderData.created_at >= cutoff_date,
                        )
                    )
                    .order_by(desc(OrderData.created_at))
                )
                orders = orders_result.scalars().all()

                logger.info(f"Found {len(orders)} orders in the last {days} days")

                for order in orders:
                    logger.info(
                        f"Processing order {order.order_id} from {order.created_at}"
                    )

                    success = await self.retrigger_order_attribution(
                        shop_id, order.order_id
                    )
                    if success:
                        self.processed_count += 1
                    else:
                        self.error_count += 1

        except Exception as e:
            logger.error(f"Error processing recent orders: {e}")

    async def retrigger_all_orders(self, shop_id: str) -> None:
        """
        Retrigger attribution for all orders for a shop

        Args:
            shop_id: Shop ID
        """
        try:
            async with get_session_context() as session:
                # Get all orders
                orders_result = await session.execute(
                    select(OrderData)
                    .where(OrderData.shop_id == shop_id)
                    .order_by(desc(OrderData.created_at))
                )
                orders = orders_result.scalars().all()

                logger.info(f"Found {len(orders)} total orders for shop {shop_id}")

                for order in orders:
                    logger.info(
                        f"Processing order {order.order_id} from {order.created_at}"
                    )

                    success = await self.retrigger_order_attribution(
                        shop_id, order.order_id
                    )
                    if success:
                        self.processed_count += 1
                    else:
                        self.error_count += 1

        except Exception as e:
            logger.error(f"Error processing all orders: {e}")

    async def _get_customer_interactions(
        self, session, shop_id: str, customer_id: str
    ) -> List[dict]:
        """Get interactions for a customer"""
        try:
            interactions_result = await session.execute(
                select(UserInteraction)
                .where(
                    and_(
                        UserInteraction.shop_id == shop_id,
                        UserInteraction.customer_id == customer_id,
                    )
                )
                .order_by(desc(UserInteraction.created_at))
            )
            interactions = interactions_result.scalars().all()

            return [
                {
                    "id": i.id,
                    "shop_id": i.shop_id,
                    "customer_id": i.customer_id,
                    "session_id": i.session_id,
                    "interaction_type": i.interaction_type,
                    "extension_type": i.extension_type,
                    "created_at": i.created_at,
                    "metadata": i.interaction_metadata or {},
                }
                for i in interactions
            ]

        except Exception as e:
            logger.error(f"Error fetching customer interactions: {e}")
            return []

    def _parse_order_products(self, line_items) -> List[dict]:
        """Parse order line items into product list"""
        try:
            if not line_items:
                return []

            products = []
            for item in line_items:
                products.append(
                    {
                        "id": str(item.product_id or ""),
                        "price": float(item.price or 0),
                        "quantity": int(item.quantity or 1),
                        "title": item.title or "",
                    }
                )

            return products

        except Exception as e:
            logger.error(f"Error parsing order products: {e}")
            return []

    def print_summary(self):
        """Print processing summary"""
        logger.info("=" * 50)
        logger.info("ATTRIBUTION RETRIGGER SUMMARY")
        logger.info("=" * 50)
        logger.info(f"✅ Successfully processed: {self.processed_count}")
        logger.info(f"❌ Errors: {self.error_count}")
        logger.info(f"📊 Total: {self.processed_count + self.error_count}")
        logger.info("=" * 50)


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Retrigger attribution processing")
    parser.add_argument("--shop-id", required=True, help="Shop ID to process")
    parser.add_argument("--order-id", help="Specific order ID to process")
    parser.add_argument(
        "--all-orders", action="store_true", help="Process all orders for shop"
    )
    parser.add_argument(
        "--recent-orders", action="store_true", help="Process recent orders"
    )
    parser.add_argument(
        "--days", type=int, default=7, help="Days to look back for recent orders"
    )

    args = parser.parse_args()

    script = AttributionRetriggerScript()

    try:
        if args.order_id:
            logger.info(f"Retriggering attribution for order {args.order_id}")
            success = await script.retrigger_order_attribution(
                args.shop_id, args.order_id
            )
            if success:
                logger.info("✅ Order processed successfully")
            else:
                logger.error("❌ Order processing failed")
                sys.exit(1)

        elif args.all_orders:
            logger.info(
                f"Retriggering attribution for all orders in shop {args.shop_id}"
            )
            await script.retrigger_all_orders(args.shop_id)

        elif args.recent_orders:
            logger.info(
                f"Retriggering attribution for recent orders in shop {args.shop_id} (last {args.days} days)"
            )
            await script.retrigger_recent_orders(args.shop_id, args.days)

        else:
            logger.error("Please specify --order-id, --all-orders, or --recent-orders")
            sys.exit(1)

        script.print_summary()

    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
        script.print_summary()
        sys.exit(1)
    except Exception as e:
        logger.error(f"Script failed: {e}")
        script.print_summary()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
