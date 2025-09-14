"""
Attribution Service for tracking recommendation attribution
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from prisma import Prisma
from prisma.models import AttributionEvent
import logging

logger = logging.getLogger(__name__)


class AttributionService:
    def __init__(self, db: Prisma):
        self.db = db

    async def store_attribution_data(
        self,
        customer_id: str,
        session_id: str,
        product_id: str,
        position: int,
        event_type: str,
        event_data: Dict[str, Any],
        shop_id: str,
    ) -> Optional[AttributionEvent]:
        """
        Store attribution data when a customer interacts with a recommendation

        Args:
            customer_id: Shopify customer ID
            session_id: Recommendation session ID
            product_id: Product ID that was recommended
            position: Position of the recommendation
            event_type: Type of event (product_viewed, add_to_cart, etc.)
            event_data: Additional event data
            shop_id: Shop ID

        Returns:
            Created AttributionEvent record or None if failed
        """
        try:
            attribution_data = await self.db.attributionevent.create(
                data={
                    "customer_id": customer_id,
                    "session_id": session_id,
                    "product_id": product_id,
                    "position": position,
                    "event_type": event_type,
                    "event_data": event_data,
                    "shop_id": shop_id,
                }
            )

            logger.info(
                f"Stored attribution data for customer {customer_id}, "
                f"session {session_id}, product {product_id}"
            )

            return attribution_data

        except Exception as e:
            logger.error(f"Failed to store attribution data: {e}")
            return None

    async def get_attribution_for_customer(
        self, customer_id: str, shop_id: str, limit: int = 50
    ) -> list[AttributionEvent]:
        """
        Get attribution data for a specific customer

        Args:
            customer_id: Shopify customer ID
            shop_id: Shop ID
            limit: Maximum number of records to return

        Returns:
            List of AttributionEvent records
        """
        try:
            attribution_records = await self.db.attributionevent.find_many(
                where={
                    "customer_id": customer_id,
                    "shop_id": shop_id,
                },
                order_by={"created_at": "desc"},
                take=limit,
            )

            return attribution_records

        except Exception as e:
            logger.error(
                f"Failed to get attribution data for customer {customer_id}: {e}"
            )
            return []

    async def get_attribution_for_session(
        self, session_id: str, shop_id: str
    ) -> list[AttributionEvent]:
        """
        Get all attribution data for a specific recommendation session

        Args:
            session_id: Recommendation session ID
            shop_id: Shop ID

        Returns:
            List of AttributionEvent records
        """
        try:
            attribution_records = await self.db.attributionevent.find_many(
                where={
                    "session_id": session_id,
                    "shop_id": shop_id,
                },
                order_by={"created_at": "asc"},
            )

            return attribution_records

        except Exception as e:
            logger.error(
                f"Failed to get attribution data for session {session_id}: {e}"
            )
            return []

    async def link_attribution_to_order(
        self, order_id: str, customer_id: str, shop_id: str
    ) -> bool:
        """
        Link attribution data to an order when checkout completes

        Args:
            order_id: Shopify order ID
            customer_id: Shopify customer ID
            shop_id: Shop ID

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get recent attribution data for this customer
            attribution_records = await self.get_attribution_for_customer(
                customer_id, shop_id, limit=10
            )

            if not attribution_records:
                logger.info(f"No attribution data found for customer {customer_id}")
                return True

            # Update attribution records with order ID
            for record in attribution_records:
                await self.db.attributionevent.update(
                    where={"id": record.id},
                    data={"order_id": order_id, "linked_at": datetime.utcnow()},
                )

            logger.info(
                f"Linked {len(attribution_records)} attribution records to order {order_id}"
            )

            return True

        except Exception as e:
            logger.error(f"Failed to link attribution to order {order_id}: {e}")
            return False
