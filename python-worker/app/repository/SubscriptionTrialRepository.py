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

    async def check_completion(
        self, shop_subscription_id: str, actual_revenue: Decimal
    ) -> bool:
        """Check if trial should be completed based on actual revenue - IDEMPOTENT."""
        try:
            trial = await self.get_by_subscription_id(shop_subscription_id)
            if not trial:
                return False

            # ✅ IDEMPOTENCY: Check if trial can be completed
            if not trial.can_be_completed():
                logger.debug(
                    f"Trial {shop_subscription_id} cannot be completed (status: {trial.status}, completed_at: {trial.completed_at}), skipping"
                )
                return True

            # Check if threshold reached based on actual revenue
            if trial.is_threshold_reached(actual_revenue):
                # ✅ ATOMIC: Use database-level update to prevent race conditions
                from sqlalchemy import update

                # Update trial status atomically
                trial_update = (
                    update(SubscriptionTrial)
                    .where(
                        SubscriptionTrial.id == trial.id,
                        SubscriptionTrial.status
                        == TrialStatus.ACTIVE,  # ✅ Only update if still active
                    )
                    .values(status=TrialStatus.COMPLETED, completed_at=now_utc())
                )

                result = await self.session.execute(trial_update)

                # Check if the update actually happened (prevents race conditions)
                if result.rowcount == 0:
                    logger.debug(
                        f"Trial {shop_subscription_id} was already completed by another process"
                    )
                    return True

            await self.session.flush()
            return True
        except Exception as e:
            logger.error(f"Error checking trial completion: {e}")
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
