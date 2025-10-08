"""
Subscription Trial Repository

Repository for SubscriptionTrial table operations.
"""

import logging
from decimal import Decimal
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.models import SubscriptionTrial
from app.core.database.models.enums import TrialStatus
from app.shared.helpers import now_utc

logger = logging.getLogger(__name__)


class SubscriptionTrialRepository:
    """Repository for SubscriptionTrial operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_subscription_id(
        self, shop_subscription_id: str
    ) -> Optional[SubscriptionTrial]:
        """Get subscription trial by shop subscription ID."""
        try:
            query = select(SubscriptionTrial).where(
                SubscriptionTrial.shop_subscription_id == shop_subscription_id
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting subscription trial: {e}")
            return None

    async def create(self, trial: SubscriptionTrial) -> SubscriptionTrial:
        """Create a new subscription trial."""
        try:
            self.session.add(trial)
            await self.session.flush()
            return trial
        except Exception as e:
            logger.error(f"Error creating subscription trial: {e}")
            raise

    async def update_revenue(
        self, shop_subscription_id: str, additional_revenue: Decimal
    ) -> bool:
        """Update trial accumulated revenue."""
        try:
            trial = await self.get_by_subscription_id(shop_subscription_id)
            if not trial:
                return False

            trial.accumulated_revenue += additional_revenue
            trial.updated_at = now_utc()

            # Check if threshold reached
            if trial.accumulated_revenue >= trial.threshold_amount:
                trial.status = TrialStatus.COMPLETED
                trial.completed_at = now_utc()

            await self.session.flush()
            return True
        except Exception as e:
            logger.error(f"Error updating trial revenue: {e}")
            return False

    async def update(self, trial: SubscriptionTrial) -> SubscriptionTrial:
        """Update an existing subscription trial."""
        try:
            await self.session.flush()
            return trial
        except Exception as e:
            logger.error(f"Error updating subscription trial: {e}")
            raise

    async def save(self, trial: SubscriptionTrial) -> SubscriptionTrial:
        """Save a subscription trial (create or update)."""
        try:
            if trial.id is None:
                self.session.add(trial)
            await self.session.flush()
            return trial
        except Exception as e:
            logger.error(f"Error saving subscription trial: {e}")
            raise

    async def commit(self) -> None:
        """Commit the current transaction."""
        try:
            await self.session.commit()
        except Exception as e:
            logger.error(f"Error committing subscription trial transaction: {e}")
            raise

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        try:
            await self.session.rollback()
        except Exception as e:
            logger.error(f"Error rolling back subscription trial transaction: {e}")
            raise
