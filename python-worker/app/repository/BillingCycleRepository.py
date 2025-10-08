"""
Billing Cycle Repository

Repository for BillingCycle table operations.
"""

import logging
from typing import Optional, List
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.models import BillingCycle
from app.core.database.models.enums import BillingCycleStatus

logger = logging.getLogger(__name__)


class BillingCycleRepository:
    """Repository for BillingCycle operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_current_by_subscription(
        self, shop_subscription_id: str
    ) -> Optional[BillingCycle]:
        """Get current active billing cycle for a subscription."""
        try:
            query = select(BillingCycle).where(
                and_(
                    BillingCycle.shop_subscription_id == shop_subscription_id,
                    BillingCycle.status == BillingCycleStatus.ACTIVE,
                )
            )

            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting current billing cycle: {e}")
            return None

    async def get_by_id(self, cycle_id: str) -> Optional[BillingCycle]:
        """Get billing cycle by ID."""
        try:
            query = select(BillingCycle).where(BillingCycle.id == cycle_id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting billing cycle by ID: {e}")
            return None

    async def get_by_subscription(
        self, shop_subscription_id: str, limit: int = 100
    ) -> List[BillingCycle]:
        """Get billing cycles for a subscription."""
        try:
            query = (
                select(BillingCycle)
                .where(BillingCycle.shop_subscription_id == shop_subscription_id)
                .order_by(BillingCycle.start_date.desc())
                .limit(limit)
            )

            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting billing cycles by subscription: {e}")
            return []

    async def create(self, cycle: BillingCycle) -> BillingCycle:
        """Create a new billing cycle."""
        try:
            self.session.add(cycle)
            await self.session.flush()
            return cycle
        except Exception as e:
            logger.error(f"Error creating billing cycle: {e}")
            raise

    async def update(self, cycle: BillingCycle) -> BillingCycle:
        """Update an existing billing cycle."""
        try:
            await self.session.flush()
            return cycle
        except Exception as e:
            logger.error(f"Error updating billing cycle: {e}")
            raise

    async def save(self, cycle: BillingCycle) -> BillingCycle:
        """Save a billing cycle (create or update)."""
        try:
            if cycle.id is None:
                self.session.add(cycle)
            await self.session.flush()
            return cycle
        except Exception as e:
            logger.error(f"Error saving billing cycle: {e}")
            raise

    async def commit(self) -> None:
        """Commit the current transaction."""
        try:
            await self.session.commit()
        except Exception as e:
            logger.error(f"Error committing billing cycle transaction: {e}")
            raise

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        try:
            await self.session.rollback()
        except Exception as e:
            logger.error(f"Error rolling back billing cycle transaction: {e}")
            raise
