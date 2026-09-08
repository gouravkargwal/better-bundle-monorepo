"""
Billing Repository V2 for database operations

Updated repository to work with the unified subscription model.
Simplified to work with single table approach while keeping essential configuration.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from sqlalchemy import select, and_, or_, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.shared.helpers import now_utc
from app.core.database.models import (
    Shop,
    SubscriptionPlan,
    ShopSubscription,
    BillingCycle,
    CommissionRecord,
    SubscriptionStatus,
    BillingCycleStatus,
    SubscriptionType,
)
from app.core.database.models.enums import BillingPhase

logger = logging.getLogger(__name__)


@dataclass
class BillingPeriod:
    """Billing period data"""

    start_date: datetime
    end_date: datetime
    cycle: str  # 'monthly', 'quarterly', 'annually'


class BillingRepositoryV2:
    """
    Repository for billing-related database operations.
    Updated for the unified subscription model.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # ============= SHOP OPERATIONS =============

    async def get_shop(self, shop_id: str) -> Optional[Shop]:
        """Get shop by ID"""
        try:
            query = select(Shop).where(Shop.id == shop_id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting shop {shop_id}: {e}")
            return None

    # ============= SUBSCRIPTION PLAN OPERATIONS =============

    async def get_default_subscription_plan(self) -> Optional[SubscriptionPlan]:
        """Get the default subscription plan"""
        try:
            query = (
                select(SubscriptionPlan)
                .where(
                    and_(
                        SubscriptionPlan.is_active == True,
                        SubscriptionPlan.is_default == True,
                    )
                )
                .order_by(SubscriptionPlan.created_at.desc())
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting default subscription plan: {e}")
            return None

    async def get_subscription_plan_by_id(
        self, plan_id: str
    ) -> Optional[SubscriptionPlan]:
        """Get subscription plan by ID"""
        try:
            query = select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting subscription plan {plan_id}: {e}")
            return None

    # ============= UNIFIED SHOP SUBSCRIPTION OPERATIONS =============

    async def create_trial_subscription(
        self,
        shop_id: str,
        subscription_plan_id: str,
    ) -> Optional[ShopSubscription]:
        """Create a new trial subscription"""
        try:
            subscription = ShopSubscription(
                shop_id=shop_id,
                subscription_type=SubscriptionType.TRIAL,
                status=SubscriptionStatus.ACTIVE,
                subscription_plan_id=subscription_plan_id,
                started_at=now_utc(),
                is_active=True,
            )

            self.session.add(subscription)
            await self.session.flush()

            logger.info(
                f"Created trial subscription {subscription.id} for shop {shop_id}"
            )
            return subscription

        except Exception as e:
            logger.error(f"Error creating trial subscription: {e}")
            await self.session.rollback()
            return None

    async def create_paid_subscription(
        self,
        shop_id: str,
        subscription_plan_id: str,
        shopify_subscription_id: str,
        shopify_line_item_id: Optional[str] = None,
        confirmation_url: Optional[str] = None,
    ) -> Optional[ShopSubscription]:
        """Create a new paid subscription and complete trial atomically"""
        try:
            # 1. Complete the trial subscription
            await self.session.execute(
                update(ShopSubscription)
                .where(
                    and_(
                        ShopSubscription.shop_id == shop_id,
                        ShopSubscription.subscription_type == SubscriptionType.TRIAL,
                        ShopSubscription.is_active == True,
                    )
                )
                .values(
                    status=SubscriptionStatus.COMPLETED,
                    completed_at=now_utc(),
                    is_active=False,  # Deactivate trial
                    updated_at=now_utc(),
                )
            )

            # 2. Create paid subscription
            paid_subscription = ShopSubscription(
                shop_id=shop_id,
                subscription_type=SubscriptionType.PAID,
                status=SubscriptionStatus.ACTIVE,
                subscription_plan_id=subscription_plan_id,
                shopify_subscription_id=shopify_subscription_id,
                shopify_line_item_id=shopify_line_item_id,
                confirmation_url=confirmation_url,
                started_at=now_utc(),
                is_active=True,
            )

            self.session.add(paid_subscription)
            await self.session.flush()

            logger.info(
                f"Created paid subscription {paid_subscription.id} for shop {shop_id}"
            )
            return paid_subscription

        except Exception as e:
            logger.error(f"Error creating paid subscription: {e}")
            await self.session.rollback()
            return None

    async def get_shop_subscription(self, shop_id: str) -> ShopSubscription:
        """Get shop subscription with all required relationships loaded."""
        try:
            query = (
                select(ShopSubscription)
                .options(
                    selectinload(ShopSubscription.subscription_plan),
                    joinedload(ShopSubscription.shop),  # if needed
                )
                .where(ShopSubscription.shop_id == shop_id)
                .where(ShopSubscription.is_active == True)
            )
            result = await self.session.execute(query)
            return result.scalar_one()
        except Exception as e:
            logger.error(f"Error getting shop subscription for shop {shop_id}: {e}")
            return None

    async def get_shop_subscription_by_id(
        self, subscription_id: str
    ) -> Optional[ShopSubscription]:
        """Get shop subscription by ID"""
        query = (
            select(ShopSubscription)
            .where(ShopSubscription.id == subscription_id)
            .options(
                selectinload(ShopSubscription.subscription_plan),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_shop_subscription_status(
        self, subscription_id: str, status: SubscriptionStatus
    ) -> bool:
        """Update shop subscription status"""
        query = (
            update(ShopSubscription)
            .where(ShopSubscription.id == subscription_id)
            .values(status=status, updated_at=now_utc())
        )
        result = await self.session.execute(query)
        return result.rowcount > 0

    # ============= BILLING CYCLE OPERATIONS =============
    # (Keep existing billing cycle methods unchanged)

    async def get_billing_cycle_by_id(self, cycle_id: str) -> Optional[BillingCycle]:
        """Get billing cycle by ID"""
        try:
            query = select(BillingCycle).where(BillingCycle.id == cycle_id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting billing cycle by ID {cycle_id}: {e}")
            return None

    async def get_current_billing_cycle(
        self, shop_subscription_id: str
    ) -> Optional[BillingCycle]:
        """Get current active billing cycle for a subscription"""
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
            logger.error(f"Error getting current billing cycle: {e}")
            return None

    async def update_billing_cycle_usage(
        self,
        cycle_id: str,
        additional_usage: Decimal,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update billing cycle usage amount - ATOMIC"""
        try:
            # ✅ ATOMIC: Use database-level increment to prevent race conditions
            cycle_update = (
                update(BillingCycle)
                .where(BillingCycle.id == cycle_id)
                .values(
                    usage_amount=BillingCycle.usage_amount + additional_usage,
                    commission_count=BillingCycle.commission_count + 1,
                    updated_at=now_utc(),
                )
            )

            result = await self.session.execute(cycle_update)

            if result.rowcount == 0:
                logger.error(f"Billing cycle {cycle_id} not found for usage update")
                return False

            await self.session.flush()
            return True
        except Exception as e:
            logger.error(f"Error updating billing cycle usage: {e}")
            return False

    # ============= TRIAL COMPLETION BY REVENUE =============
    #
    # The trial ends when the app has driven `effective_trial_threshold` of
    # attributed revenue. There is deliberately no elapsed-time gate: a shop
    # that has not yet been sold $1,000 of attributed revenue has not received
    # what it was promised, so charging it after N days would contradict the
    # offer.

    async def calculate_trial_revenue(self, shop_id: str) -> Decimal:
        """Total attributed revenue accumulated during the trial phase."""
        try:
            query = select(
                func.coalesce(func.sum(CommissionRecord.attributed_revenue), 0)
            ).where(
                and_(
                    CommissionRecord.shop_id == shop_id,
                    # Only TRIAL-phase rows: counting paid ones too would make
                    # the threshold appear to be re-crossed on every order.
                    CommissionRecord.billing_phase == BillingPhase.TRIAL,
                )
            )
            result = await self.session.execute(query)
            return Decimal(str(result.scalar_one()))
        except Exception as e:
            logger.error(f"Error calculating trial revenue: {e}")
            return Decimal("0")

    async def check_trial_completion(
        self, shop_id: str, actual_revenue: Decimal
    ) -> bool:
        """Complete the trial if attributed revenue has reached the threshold."""
        try:
            subscription = await self.get_shop_subscription(shop_id)
            if not subscription:
                return False

            if subscription.subscription_type != SubscriptionType.TRIAL:
                return True  # Already past the trial.

            if subscription.status != SubscriptionStatus.TRIAL:
                return True  # Already completed.

            return await self.complete_trial_subscription(shop_id, actual_revenue)
        except Exception as e:
            logger.error(f"Error checking trial completion: {e}")
            return False

    async def complete_trial_subscription(
        self, shop_id: str, actual_revenue: Decimal
    ) -> bool:
        """Mark the trial complete once the revenue threshold is crossed."""
        try:
            result = await self.session.execute(
                select(ShopSubscription)
                .where(
                    and_(
                        ShopSubscription.shop_id == shop_id,
                        ShopSubscription.subscription_type == SubscriptionType.TRIAL,
                        ShopSubscription.status == SubscriptionStatus.TRIAL,
                        ShopSubscription.is_active == True,
                    )
                )
                # Was selectinload(pricing_tier); the terms now live on the plan.
                .options(selectinload(ShopSubscription.subscription_plan))
            )
            subscription = result.scalar_one_or_none()
            if not subscription:
                logger.debug(f"No active trial found for shop {shop_id}")
                return False

            threshold = subscription.effective_trial_threshold
            if actual_revenue < threshold:
                logger.debug(
                    f"Trial threshold not reached: {actual_revenue} < {threshold}"
                )
                return False

            # Guarded on status so two concurrent orders cannot both complete it.
            update_result = await self.session.execute(
                update(ShopSubscription)
                .where(
                    and_(
                        ShopSubscription.id == subscription.id,
                        ShopSubscription.status == SubscriptionStatus.TRIAL,
                    )
                )
                .values(
                    status=SubscriptionStatus.TRIAL_COMPLETED,
                    completed_at=now_utc(),
                    updated_at=now_utc(),
                )
            )

            if update_result.rowcount == 0:
                logger.debug(f"Trial {subscription.id} already completed elsewhere")
                return True

            # The shop keeps serving recommendations — it is not suspended here.
            # It simply owes a billing setup before anything can be charged.
            logger.info(
                f"✅ Trial completed for shop {shop_id}: "
                f"attributed revenue {actual_revenue} >= threshold {threshold}"
            )
            await self.session.flush()
            return True

        except Exception as e:
            logger.error(f"Error completing trial subscription: {e}")
            return False

    async def create_billing_cycle_for_subscription(
        self,
        shop_subscription_id: str,
        cycle_number: int = 1,
        period_fee: Optional[Decimal] = None,
    ) -> Optional[BillingCycle]:
        """Create a new billing cycle for a flat fee subscription"""
        try:
            billing_cycle = BillingCycle(
                shop_subscription_id=shop_subscription_id,
                cycle_number=cycle_number,
                start_date=now_utc(),
                end_date=now_utc() + timedelta(days=30),
                period_fee=period_fee,
                status=BillingCycleStatus.ACTIVE,
                activated_at=now_utc(),
            )

            self.session.add(billing_cycle)
            await self.session.flush()

            logger.info(
                f"Created billing cycle #{cycle_number} for subscription {shop_subscription_id}"
            )
            return billing_cycle

        except Exception as e:
            logger.error(f"Error creating billing cycle: {e}")
            return None

    async def get_active_billing_cycle_for_subscription(
        self, shop_subscription_id: str
    ) -> Optional[BillingCycle]:
        """Get active billing cycle for a subscription"""
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
                .limit(1)
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting active billing cycle: {e}")
            return None

    # ============= BILLING PERIODS & OVERFLOW (Keep unchanged) =============

    async def get_shops_for_billing(self) -> List[str]:
        """Get list of shop IDs that need billing processing"""
        try:
            query = select(ShopSubscription.shop_id).where(
                and_(
                    ShopSubscription.is_active == True,
                    ShopSubscription.status.in_(
                        [
                            SubscriptionStatus.ACTIVE,
                        ]
                    ),
                )
            )
            result = await self.session.execute(query)
            shop_ids = [row[0] for row in result.fetchall()]

            logger.info(f"Found {len(shop_ids)} shops for billing processing")
            return shop_ids

        except Exception as e:
            logger.error(f"Error getting shops for billing: {e}")
            return []

    async def get_subscription_trial(self, shop_id: str) -> Optional[ShopSubscription]:
        """
        Return the currently active TRIAL subscription for a shop.
        """
        try:
            query = (
                select(ShopSubscription)
                .where(
                    and_(
                        ShopSubscription.shop_id == shop_id,
                        ShopSubscription.subscription_type == SubscriptionType.TRIAL,
                        ShopSubscription.is_active.is_(True),
                        ShopSubscription.status == SubscriptionStatus.ACTIVE,
                    )
                )
                .limit(1)
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching active trial for shop {shop_id}: {e}")
            return None

    async def get_subscription_trial_by_id(
        self, subscription_id: str
    ) -> Optional[ShopSubscription]:
        """
        Return the TRIAL subscription by its subscription primary ID.
        """
        try:
            query = (
                select(ShopSubscription)
                .where(ShopSubscription.id == subscription_id)
                .limit(1)
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching trial by id {subscription_id}: {e}")
            return None
