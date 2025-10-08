"""
Billing Cycle Manager Service

Handles billing cycle creation, rollover, and cap adjustments.
Manages the lifecycle of billing cycles for shop subscriptions.
"""

import logging
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database.models import (
    ShopSubscription,
    BillingCycle,
    BillingCycleAdjustment,
    SubscriptionStatus,
    BillingCycleStatus,
    AdjustmentReason,
)
from app.shared.helpers import now_utc

logger = logging.getLogger(__name__)


class BillingCycleManager:
    """Service for managing billing cycles"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ============= CYCLE CREATION =============

    async def create_initial_cycle(
        self, shop_subscription_id: str, cap_amount: Decimal
    ) -> Optional[BillingCycle]:
        """
        Create the first billing cycle when subscription becomes active.

        Args:
            shop_subscription_id: Shop subscription ID
            cap_amount: Initial cap amount for the cycle

        Returns:
            Created billing cycle or None if failed
        """
        try:
            logger.info(
                f"🔄 Creating initial billing cycle for subscription {shop_subscription_id}"
            )

            # Get shop subscription
            subscription = await self._get_shop_subscription(shop_subscription_id)
            if not subscription:
                logger.error(f"❌ Shop subscription {shop_subscription_id} not found")
                return None

            # Create first billing cycle
            cycle = BillingCycle(
                shop_subscription_id=shop_subscription_id,
                cycle_number=1,
                start_date=now_utc(),
                end_date=now_utc() + timedelta(days=30),
                initial_cap_amount=cap_amount,
                current_cap_amount=cap_amount,
                usage_amount=Decimal("0.00"),
                commission_count=0,
                status=BillingCycleStatus.ACTIVE,
                activated_at=now_utc(),
                cycle_metadata={
                    "created_by": "billing_cycle_manager",
                    "cycle_type": "initial",
                    "cap_source": "pricing_tier",
                },
            )

            self.session.add(cycle)
            await self.session.flush()

            logger.info(
                f"✅ Created initial billing cycle {cycle.id} "
                f"(cap: ${cap_amount}, period: {cycle.start_date} to {cycle.end_date})"
            )

            return cycle

        except Exception as e:
            logger.error(f"❌ Error creating initial cycle: {e}")
            await self.session.rollback()
            return None

    async def create_next_cycle(
        self, shop_subscription_id: str, previous_cycle: BillingCycle
    ) -> Optional[BillingCycle]:
        """
        Create the next billing cycle after the previous one ends.

        Args:
            shop_subscription_id: Shop subscription ID
            previous_cycle: The previous billing cycle

        Returns:
            Created billing cycle or None if failed
        """
        try:
            logger.info(
                f"🔄 Creating next billing cycle for subscription {shop_subscription_id}"
            )

            # Calculate next cycle dates
            next_cycle_start = previous_cycle.end_date
            next_cycle_end = next_cycle_start + timedelta(days=30)

            # Use current cap from previous cycle (may have been adjusted)
            next_cap_amount = previous_cycle.current_cap_amount

            # Create next billing cycle
            cycle = BillingCycle(
                shop_subscription_id=shop_subscription_id,
                cycle_number=previous_cycle.cycle_number + 1,
                start_date=next_cycle_start,
                end_date=next_cycle_end,
                initial_cap_amount=next_cap_amount,
                current_cap_amount=next_cap_amount,
                usage_amount=Decimal("0.00"),
                commission_count=0,
                status=BillingCycleStatus.ACTIVE,
                activated_at=now_utc(),
                cycle_metadata={
                    "created_by": "billing_cycle_manager",
                    "cycle_type": "recurring",
                    "previous_cycle_id": str(previous_cycle.id),
                    "cap_source": "previous_cycle",
                },
            )

            self.session.add(cycle)
            await self.session.flush()

            logger.info(
                f"✅ Created next billing cycle {cycle.id} "
                f"(cycle #{cycle.cycle_number}, cap: ${next_cap_amount})"
            )

            return cycle

        except Exception as e:
            logger.error(f"❌ Error creating next cycle: {e}")
            await self.session.rollback()
            return None

    # ============= CYCLE ROLLOVER =============

    async def rollover_expired_cycles(self) -> Dict[str, Any]:
        """
        Find and rollover expired billing cycles.
        Called by scheduled job.

        Returns:
            Dictionary with rollover results
        """
        try:
            logger.info("🔄 Starting billing cycle rollover...")

            # Find expired active cycles
            expired_cycles = await self._get_expired_cycles()

            if not expired_cycles:
                logger.info("✅ No expired cycles found")
                return {
                    "success": True,
                    "processed_cycles": 0,
                    "created_cycles": 0,
                    "errors": [],
                }

            processed_cycles = 0
            created_cycles = 0
            errors = []

            for cycle in expired_cycles:
                try:
                    # Close the expired cycle
                    await self._close_cycle(cycle)
                    processed_cycles += 1

                    # Create next cycle if subscription is still active
                    if await self._should_create_next_cycle(cycle.shop_subscription_id):
                        next_cycle = await self.create_next_cycle(
                            cycle.shop_subscription_id, cycle
                        )
                        if next_cycle:
                            created_cycles += 1
                            logger.info(
                                f"✅ Created next cycle {next_cycle.id} for subscription {cycle.shop_subscription_id}"
                            )
                        else:
                            errors.append(
                                f"Failed to create next cycle for subscription {cycle.shop_subscription_id}"
                            )
                    else:
                        logger.info(
                            f"ℹ️ Skipping next cycle creation for subscription {cycle.shop_subscription_id} (subscription inactive)"
                        )

                except Exception as e:
                    error_msg = f"Error processing cycle {cycle.id}: {e}"
                    logger.error(f"❌ {error_msg}")
                    errors.append(error_msg)

            await self.session.commit()

            logger.info(
                f"✅ Rollover completed: {processed_cycles} cycles processed, "
                f"{created_cycles} new cycles created"
            )

            return {
                "success": True,
                "processed_cycles": processed_cycles,
                "created_cycles": created_cycles,
                "errors": errors,
            }

        except Exception as e:
            logger.error(f"❌ Error during rollover: {e}")
            await self.session.rollback()
            return {
                "success": False,
                "processed_cycles": 0,
                "created_cycles": 0,
                "errors": [str(e)],
            }

    # ============= CAP ADJUSTMENTS =============

    async def increase_cap(
        self,
        billing_cycle_id: str,
        new_cap_amount: Decimal,
        adjusted_by: str,
        reason: AdjustmentReason = AdjustmentReason.CAP_INCREASE,
        reason_description: Optional[str] = None,
    ) -> Optional[BillingCycleAdjustment]:
        """
        Increase the cap for a billing cycle.
        Creates audit trail and updates cycle.

        Args:
            billing_cycle_id: Billing cycle ID
            new_cap_amount: New cap amount
            adjusted_by: Who made the adjustment
            reason: Reason for adjustment
            reason_description: Optional description

        Returns:
            Created adjustment record or None if failed
        """
        try:
            logger.info(
                f"📈 Increasing cap for cycle {billing_cycle_id} to ${new_cap_amount}"
            )

            # Get billing cycle
            cycle = await self._get_billing_cycle(billing_cycle_id)
            if not cycle:
                logger.error(f"❌ Billing cycle {billing_cycle_id} not found")
                return None

            # Validate new cap amount
            if new_cap_amount <= cycle.current_cap_amount:
                logger.error(
                    f"❌ New cap amount ${new_cap_amount} must be greater than current ${cycle.current_cap_amount}"
                )
                return None

            # Calculate adjustment amount
            adjustment_amount = new_cap_amount - cycle.current_cap_amount

            # Create adjustment record
            adjustment = BillingCycleAdjustment(
                billing_cycle_id=billing_cycle_id,
                old_cap_amount=cycle.current_cap_amount,
                new_cap_amount=new_cap_amount,
                adjustment_amount=adjustment_amount,
                adjustment_reason=reason,
                reason_description=reason_description,
                adjusted_by=adjusted_by,
                adjusted_by_type="user",
                adjusted_at=now_utc(),
                adjustment_metadata={
                    "previous_usage_percentage": float(cycle.usage_percentage),
                    "new_usage_percentage": float(
                        (cycle.usage_amount / new_cap_amount) * 100
                    ),
                },
            )

            self.session.add(adjustment)

            # Update cycle cap
            cycle.current_cap_amount = new_cap_amount
            cycle.cycle_metadata = {
                **(cycle.cycle_metadata or {}),
                "last_cap_adjustment": {
                    "adjusted_at": now_utc().isoformat(),
                    "adjusted_by": adjusted_by,
                    "new_cap": float(new_cap_amount),
                },
            }

            await self.session.flush()

            logger.info(
                f"✅ Cap increased for cycle {billing_cycle_id}: "
                f"${cycle.current_cap_amount - adjustment_amount} → ${new_cap_amount} "
                f"(+${adjustment_amount})"
            )

            return adjustment

        except Exception as e:
            logger.error(f"❌ Error increasing cap: {e}")
            await self.session.rollback()
            return None

    # ============= QUERY METHODS =============

    async def get_current_cycle(
        self, shop_subscription_id: str
    ) -> Optional[BillingCycle]:
        """Get the current active billing cycle for a subscription"""
        try:
            query = (
                select(BillingCycle)
                .where(
                    and_(
                        BillingCycle.shop_subscription_id == shop_subscription_id,
                        BillingCycle.status == BillingCycleStatus.ACTIVE,
                    )
                )
                .order_by(BillingCycle.cycle_number.desc())
            )

            result = await self.session.execute(query)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"❌ Error getting current cycle: {e}")
            return None

    async def get_cycle_history(
        self, shop_subscription_id: str, limit: int = 10
    ) -> List[BillingCycle]:
        """Get billing cycle history for a subscription"""
        try:
            query = (
                select(BillingCycle)
                .where(BillingCycle.shop_subscription_id == shop_subscription_id)
                .order_by(BillingCycle.cycle_number.desc())
                .limit(limit)
            )

            result = await self.session.execute(query)
            return list(result.scalars().all())

        except Exception as e:
            logger.error(f"❌ Error getting cycle history: {e}")
            return []

    # ============= PRIVATE HELPERS =============

    async def _get_shop_subscription(
        self, shop_subscription_id: str
    ) -> Optional[ShopSubscription]:
        """Get shop subscription by ID"""
        try:
            query = select(ShopSubscription).where(
                ShopSubscription.id == shop_subscription_id
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"❌ Error getting shop subscription: {e}")
            return None

    async def _get_billing_cycle(self, billing_cycle_id: str) -> Optional[BillingCycle]:
        """Get billing cycle by ID"""
        try:
            query = select(BillingCycle).where(BillingCycle.id == billing_cycle_id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"❌ Error getting billing cycle: {e}")
            return None

    async def _get_expired_cycles(self) -> List[BillingCycle]:
        """Get all expired active cycles"""
        try:
            now = now_utc()
            query = (
                select(BillingCycle)
                .where(
                    and_(
                        BillingCycle.status == BillingCycleStatus.ACTIVE,
                        BillingCycle.end_date <= now,
                    )
                )
                .options(selectinload(BillingCycle.shop_subscription))
            )

            result = await self.session.execute(query)
            return list(result.scalars().all())

        except Exception as e:
            logger.error(f"❌ Error getting expired cycles: {e}")
            return []

    async def _close_cycle(self, cycle: BillingCycle) -> None:
        """Close a billing cycle"""
        try:
            cycle.status = BillingCycleStatus.COMPLETED
            cycle.completed_at = now_utc()

            logger.info(
                f"✅ Closed billing cycle {cycle.id} "
                f"(usage: ${cycle.usage_amount} / ${cycle.current_cap_amount})"
            )

        except Exception as e:
            logger.error(f"❌ Error closing cycle: {e}")
            raise

    async def _should_create_next_cycle(self, shop_subscription_id: str) -> bool:
        """Check if we should create the next cycle for a subscription"""
        try:
            subscription = await self._get_shop_subscription(shop_subscription_id)
            if not subscription:
                return False

            # Only create next cycle if subscription is active
            return (
                subscription.is_active
                and subscription.status == SubscriptionStatus.ACTIVE
            )

        except Exception as e:
            logger.error(f"❌ Error checking if should create next cycle: {e}")
            return False

    # ============= OVERFLOW HANDLING =============

    async def create_next_cycle_with_overflow(
        self, shop_subscription_id: str, previous_cycle: BillingCycle
    ) -> Optional[BillingCycle]:
        """
        Create next cycle and handle overflow from previous cycle.

        Args:
            shop_subscription_id: Shop subscription ID
            previous_cycle: The completed cycle to get overflow from

        Returns:
            New billing cycle with overflow adjustments or None if failed
        """
        try:
            from ..repositories.billing_repository_v2 import BillingRepositoryV2

            billing_repo = BillingRepositoryV2(self.session)

            # Get total overflow from previous cycle
            total_overflow = await billing_repo.get_cycle_overflow_amount(
                previous_cycle.id
            )

            logger.info(
                f"📊 Previous cycle {previous_cycle.id} had ${total_overflow} overflow"
            )

            # Create next cycle
            next_cycle = BillingCycle(
                shop_subscription_id=shop_subscription_id,
                cycle_number=previous_cycle.cycle_number + 1,
                start_date=previous_cycle.end_date,
                end_date=previous_cycle.end_date + timedelta(days=30),
                initial_cap_amount=previous_cycle.current_cap_amount,
                current_cap_amount=previous_cycle.current_cap_amount,
                usage_amount=Decimal("0"),
                commission_count=0,
                status=BillingCycleStatus.ACTIVE,
            )

            self.session.add(next_cycle)
            await self.session.flush()

            # If there's overflow, create an adjustment to increase cap
            if total_overflow > 0:
                await self._create_overflow_adjustment(next_cycle, total_overflow)
                logger.info(
                    f"✅ Created next cycle {next_cycle.id} with ${total_overflow} overflow adjustment"
                )
            else:
                logger.info(f"✅ Created next cycle {next_cycle.id} with no overflow")

            return next_cycle

        except Exception as e:
            logger.error(f"❌ Error creating next cycle with overflow: {e}")
            return None

    async def _create_overflow_adjustment(
        self, cycle: BillingCycle, overflow_amount: Decimal
    ) -> None:
        """
        Create cap adjustment for overflow from previous cycle.

        Args:
            cycle: The billing cycle to adjust
            overflow_amount: Amount of overflow to add to cap
        """
        try:
            old_cap = cycle.current_cap_amount
            new_cap = old_cap + overflow_amount

            # Create adjustment record
            adjustment = BillingCycleAdjustment(
                billing_cycle_id=cycle.id,
                old_cap_amount=old_cap,
                new_cap_amount=new_cap,
                adjustment_amount=overflow_amount,
                adjustment_reason=AdjustmentReason.CAP_INCREASE,
                reason_description=f"Overflow from previous cycle: ${overflow_amount}",
                adjusted_by="system",
                adjusted_by_type="system",
                adjusted_at=now_utc(),
            )

            # Update cycle cap
            cycle.current_cap_amount = new_cap

            self.session.add(adjustment)
            await self.session.flush()

            logger.info(
                f"✅ Created overflow adjustment: cap increased from ${old_cap} to ${new_cap}"
            )

        except Exception as e:
            logger.error(f"❌ Error creating overflow adjustment: {e}")
            raise
