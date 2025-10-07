"""
Purchase History Service - Fetches user purchase history for exclusion from recommendations
"""

from typing import List, Optional, Set
from datetime import datetime, timedelta

from app.shared.helpers import now_utc
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.database.models.order_data import OrderData, LineItemData

logger = get_logger(__name__)


class PurchaseHistoryService:
    """Service to fetch user purchase history for recommendation exclusions"""

    @staticmethod
    async def get_purchased_product_ids(
        session: AsyncSession,
        shop_id: str,
        customer_id: str,
        exclude_refunded: bool = True,
        exclude_cancelled: bool = True,
        days_lookback: Optional[int] = None,
    ) -> List[str]:
        """
        Get list of product IDs that a customer has purchased.

        Args:
            session: Database session
            shop_id: Shop ID
            customer_id: Customer ID
            exclude_refunded: Whether to exclude fully refunded orders (default: True)
            exclude_cancelled: Whether to exclude cancelled orders (default: True)
            days_lookback: Only look back N days (None = all time)

        Returns:
            List of product IDs the customer has purchased
        """
        try:
            # Build the query
            query_filters = [
                OrderData.shop_id == shop_id,
                OrderData.customer_id == customer_id,
            ]

            # Exclude cancelled orders if requested
            if exclude_cancelled:
                query_filters.append(OrderData.cancelled_at.is_(None))

            # Exclude test orders
            query_filters.append(OrderData.test == False)

            # Only look back N days if specified
            if days_lookback:
                cutoff_date = now_utc() - timedelta(days=days_lookback)
                query_filters.append(OrderData.order_date >= cutoff_date)

            # Query orders with their line items
            result = await session.execute(
                select(OrderData)
                .where(and_(*query_filters))
                .order_by(OrderData.order_date.desc())
            )
            orders = result.scalars().all()

            if not orders:
                logger.debug(f"No orders found for customer {customer_id}")
                return []

            # Extract product IDs from line items
            purchased_product_ids: Set[str] = set()

            for order in orders:
                # Skip fully refunded orders if requested
                if exclude_refunded and order.total_refunded_amount:
                    if order.total_refunded_amount >= order.total_amount:
                        logger.debug(f"Skipping fully refunded order {order.order_id}")
                        continue

                # Get line items for this order
                line_items_result = await session.execute(
                    select(LineItemData).where(LineItemData.order_id == order.id)
                )
                line_items = line_items_result.scalars().all()

                # Extract product IDs
                for line_item in line_items:
                    if line_item.product_id:
                        purchased_product_ids.add(line_item.product_id)

            logger.info(
                f"Found {len(purchased_product_ids)} purchased products for customer {customer_id} "
                f"from {len(orders)} orders"
            )

            return list(purchased_product_ids)

        except Exception as e:
            logger.error(
                f"Error fetching purchase history for customer {customer_id}: {e}"
            )
            return []

    @staticmethod
    async def get_recently_purchased_product_ids(
        session: AsyncSession,
        shop_id: str,
        customer_id: str,
        days: int = 90,
    ) -> List[str]:
        """
        Get product IDs purchased in the last N days.
        Useful for consumables/repurchasable items - exclude recent purchases
        but allow older ones to appear in recommendations.

        Args:
            session: Database session
            shop_id: Shop ID
            customer_id: Customer ID
            days: Number of days to look back (default: 90)

        Returns:
            List of recently purchased product IDs
        """
        return await PurchaseHistoryService.get_purchased_product_ids(
            session=session,
            shop_id=shop_id,
            customer_id=customer_id,
            exclude_refunded=True,
            exclude_cancelled=True,
            days_lookback=days,
        )

    @staticmethod
    async def should_exclude_product(
        session: AsyncSession,
        shop_id: str,
        customer_id: str,
        product_id: str,
        product_type: Optional[str] = None,
    ) -> bool:
        """
        Determine if a product should be excluded from recommendations.
        Uses intelligent logic based on product type.

        Args:
            session: Database session
            shop_id: Shop ID
            customer_id: Customer ID
            product_id: Product ID to check
            product_type: Product type (e.g., "consumable", "durable")

        Returns:
            True if product should be excluded, False otherwise
        """
        # Define repurchasable/consumable product types
        REPURCHASABLE_TYPES = {
            "consumable",
            "food",
            "beverage",
            "beauty",
            "cosmetics",
            "supplement",
            "subscription",
            "pet food",
            "cleaning",
        }

        # If product is repurchasable, only exclude recent purchases (last 60 days)
        if product_type and any(
            ptype in product_type.lower() for ptype in REPURCHASABLE_TYPES
        ):
            recent_purchases = (
                await PurchaseHistoryService.get_recently_purchased_product_ids(
                    session=session,
                    shop_id=shop_id,
                    customer_id=customer_id,
                    days=60,  # 60 days for consumables
                )
            )
            return product_id in recent_purchases

        # For durable goods, exclude all-time purchases
        all_purchases = await PurchaseHistoryService.get_purchased_product_ids(
            session=session,
            shop_id=shop_id,
            customer_id=customer_id,
        )
        return product_id in all_purchases
