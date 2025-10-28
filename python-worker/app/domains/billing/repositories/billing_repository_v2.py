"""
Billing Repository V2 for database operations

Updated repository to work with the new redesigned billing system.
Uses SQLAlchemy models instead of Prisma.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from sqlalchemy import select, and_, or_, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.shared.helpers import now_utc
from app.core.database.models import (
    Shop,
    SubscriptionPlan,
    PricingTier,
    ShopSubscription,
    SubscriptionTrial,
    BillingCycle,
    BillingCycleAdjustment,
    ShopifySubscription,
    CommissionRecord,
    # BillingInvoice,  # REMOVED: Using Shopify's billing system
    SubscriptionStatus,
    BillingCycleStatus,
    TrialStatus,
    ShopifySubscriptionStatus,
)

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
    Updated for the new redesigned billing system.
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

    # ============= PRICING TIER OPERATIONS =============

    async def get_pricing_tier_for_plan_and_currency(
        self, plan_id: str, currency: str
    ) -> Optional[PricingTier]:
        """Get pricing tier for a plan and currency"""
        try:
            query = (
                select(PricingTier)
                .where(
                    and_(
                        PricingTier.subscription_plan_id == plan_id,
                        PricingTier.currency == currency,
                        PricingTier.is_active == True,
                    )
                )
                .order_by(PricingTier.is_default.desc(), PricingTier.created_at.desc())
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(
                f"Error getting pricing tier for plan {plan_id} and currency {currency}: {e}"
            )
            return None

    async def get_default_pricing_tier_for_plan(
        self, plan_id: str
    ) -> Optional[PricingTier]:
        """Get default pricing tier for a plan"""
        try:
            query = (
                select(PricingTier)
                .where(
                    and_(
                        PricingTier.subscription_plan_id == plan_id,
                        PricingTier.is_default == True,
                        PricingTier.is_active == True,
                    )
                )
                .order_by(PricingTier.created_at.desc())
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting default pricing tier for plan {plan_id}: {e}")
            return None

    async def get_pricing_tier(self, pricing_tier_id: str) -> Optional[PricingTier]:
        """Get pricing tier by ID"""
        try:
            query = select(PricingTier).where(PricingTier.id == pricing_tier_id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting pricing tier {pricing_tier_id}: {e}")
            return None

    # ============= SHOP SUBSCRIPTION OPERATIONS =============

    async def create_shop_subscription(
        self,
        shop_id: str,
        subscription_plan_id: str,
        pricing_tier_id: str,
        start_date: Optional[datetime] = None,
    ) -> Optional[ShopSubscription]:
        """Create a new shop subscription"""
        try:
            if start_date is None:
                start_date = now_utc()

            subscription = ShopSubscription(
                shop_id=shop_id,
                subscription_plan_id=subscription_plan_id,
                pricing_tier_id=pricing_tier_id,
                status=SubscriptionStatus.TRIAL,
                start_date=start_date,
                is_active=True,
                auto_renew=True,
            )

            self.session.add(subscription)
            await self.session.flush()

            logger.info(
                f"Created shop subscription {subscription.id} for shop {shop_id}"
            )
            return subscription

        except Exception as e:
            logger.error(f"Error creating shop subscription: {e}")
            await self.session.rollback()
            return None

    async def get_shop_subscription(self, shop_id: str) -> Optional[ShopSubscription]:
        """Get active shop subscription for a shop"""
        try:
            query = (
                select(ShopSubscription)
                .where(
                    and_(
                        ShopSubscription.shop_id == shop_id,
                        ShopSubscription.is_active == True,
                    )
                )
                .options(
                    selectinload(ShopSubscription.subscription_plan),
                    selectinload(ShopSubscription.pricing_tier),
                    selectinload(ShopSubscription.subscription_trial),
                    selectinload(ShopSubscription.shopify_subscription),
                )
                .order_by(ShopSubscription.created_at.desc())
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting shop subscription for shop {shop_id}: {e}")
            return None

    async def get_shop_subscription_by_id(
        self, subscription_id: str
    ) -> Optional[ShopSubscription]:
        """Get shop subscription by ID"""
        try:
            query = (
                select(ShopSubscription)
                .where(ShopSubscription.id == subscription_id)
                .options(
                    selectinload(ShopSubscription.subscription_plan),
                    selectinload(ShopSubscription.pricing_tier),
                    selectinload(ShopSubscription.subscription_trial),
                    selectinload(ShopSubscription.shopify_subscription),
                )
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting shop subscription {subscription_id}: {e}")
            return None

    async def update_shop_subscription_status(
        self, subscription_id: str, status: SubscriptionStatus
    ) -> bool:
        """Update shop subscription status"""
        try:
            query = (
                update(ShopSubscription)
                .where(ShopSubscription.id == subscription_id)
                .values(status=status, updated_at=now_utc())
            )
            result = await self.session.execute(query)
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating shop subscription status: {e}")
            return False

    # ============= SUBSCRIPTION TRIAL OPERATIONS =============

    async def create_subscription_trial(
        self,
        shop_subscription_id: str,
        threshold_amount: Decimal,
        trial_duration_days: Optional[str] = None,
    ) -> Optional[SubscriptionTrial]:
        """Create a subscription trial"""
        try:
            trial = SubscriptionTrial(
                shop_subscription_id=shop_subscription_id,
                threshold_amount=threshold_amount,
                trial_duration_days=trial_duration_days,
                status=TrialStatus.ACTIVE,
                started_at=now_utc(),
            )

            self.session.add(trial)
            await self.session.flush()

            logger.info(
                f"Created subscription trial {trial.id} for subscription {shop_subscription_id}"
            )
            return trial

        except Exception as e:
            logger.error(f"Error creating subscription trial: {e}")
            await self.session.rollback()
            return None

    async def get_subscription_trial(
        self, shop_subscription_id: str
    ) -> Optional[SubscriptionTrial]:
        """Get subscription trial for a shop subscription"""
        try:
            query = select(SubscriptionTrial).where(
                SubscriptionTrial.shop_subscription_id == shop_subscription_id
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting subscription trial: {e}")
            return None

    async def check_trial_completion(
        self, shop_subscription_id: str, actual_revenue: Decimal
    ) -> bool:
        """Check if trial should be completed based on actual revenue - IDEMPOTENT"""
        try:
            trial = await self.get_subscription_trial(shop_subscription_id)
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
                from app.core.database.models.shop import Shop

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

                # Update shop subscription status
                shop_subscription = await self.get_shop_subscription_by_id(
                    shop_subscription_id
                )
                if shop_subscription:
                    shop_subscription.status = SubscriptionStatus.TRIAL_COMPLETED

                    # ✅ SUSPEND SHOP: When trial is completed, suspend the shop
                    shop_update = (
                        update(Shop)
                        .where(
                            Shop.id == shop_subscription.shop_id,
                            Shop.is_active == True,  # Only suspend if currently active
                        )
                        .values(
                            is_active=False,
                            suspended_at=now_utc(),
                            suspension_reason="trial_completed",
                            service_impact="suspended",
                            updated_at=now_utc(),
                        )
                    )

                    shop_result = await self.session.execute(shop_update)

                    if shop_result.rowcount > 0:
                        logger.info(
                            f"✅ Trial completed for shop {shop_subscription.shop_id}. "
                            f"Shop suspended - awaiting user to setup billing with cap."
                        )
                    else:
                        logger.warning(
                            f"⚠️ Trial completed but shop {shop_subscription.shop_id} was already suspended"
                        )

            await self.session.flush()
            return True

        except Exception as e:
            logger.error(f"Error checking trial completion: {e}")
            return False

    # ============= BILLING CYCLE OPERATIONS =============

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

    async def get_billing_cycle_by_id(self, cycle_id: str) -> Optional[BillingCycle]:
        """Get billing cycle by ID"""
        try:
            query = select(BillingCycle).where(BillingCycle.id == cycle_id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting billing cycle {cycle_id}: {e}")
            return None

    async def update_billing_cycle_usage(
        self,
        cycle_id: str,
        additional_usage: Decimal,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update billing cycle usage amount - ATOMIC"""
        try:
            from sqlalchemy import update

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

            # Update metadata separately if provided (less critical)
            if metadata:
                cycle = await self.get_billing_cycle_by_id(cycle_id)
                if cycle:
                    if not cycle.usage_metadata:
                        cycle.usage_metadata = {}
                    cycle.usage_metadata.update(metadata)

            await self.session.flush()
            return True
        except Exception as e:
            logger.error(f"Error updating billing cycle usage: {e}")
            return False

    # ============= SHOPIFY SUBSCRIPTION OPERATIONS =============

    async def create_shopify_subscription(
        self,
        shop_subscription_id: str,
        shopify_subscription_id: str,
        shopify_line_item_id: Optional[str] = None,
        confirmation_url: Optional[str] = None,
    ) -> Optional[ShopifySubscription]:
        """Create a Shopify subscription record"""
        try:
            shopify_sub = ShopifySubscription(
                shop_subscription_id=shop_subscription_id,
                shopify_subscription_id=shopify_subscription_id,
                shopify_line_item_id=shopify_line_item_id,
                confirmation_url=confirmation_url,
                status=ShopifySubscriptionStatus.PENDING,
                created_at=now_utc(),
            )

            self.session.add(shopify_sub)
            await self.session.flush()

            logger.info(f"Created Shopify subscription {shopify_sub.id}")
            return shopify_sub

        except Exception as e:
            logger.error(f"Error creating Shopify subscription: {e}")
            await self.session.rollback()
            return None

    async def get_shopify_subscription(
        self, shop_subscription_id: str
    ) -> Optional[ShopifySubscription]:
        """Get Shopify subscription for a shop subscription"""
        try:
            query = select(ShopifySubscription).where(
                ShopifySubscription.shop_subscription_id == shop_subscription_id
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting Shopify subscription: {e}")
            return None

    async def update_shopify_subscription_status(
        self, shopify_subscription_id: str, status: ShopifySubscriptionStatus
    ) -> bool:
        """Update Shopify subscription status"""
        try:
            query = (
                update(ShopifySubscription)
                .where(
                    ShopifySubscription.shopify_subscription_id
                    == shopify_subscription_id
                )
                .values(status=status, updated_at=now_utc())
            )
            result = await self.session.execute(query)
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating Shopify subscription status: {e}")
            return False

    # ============= COMMISSION OPERATIONS =============

    async def get_commissions_for_cycle(
        self, billing_cycle_id: str, limit: int = 100
    ) -> List[CommissionRecord]:
        """Get commission records for a billing cycle"""
        try:
            query = (
                select(CommissionRecord)
                .where(CommissionRecord.billing_cycle_id == billing_cycle_id)
                .order_by(CommissionRecord.created_at.desc())
                .limit(limit)
            )
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting commissions for cycle: {e}")
            return []

    # ============= BILLING PERIODS =============

    async def get_billing_periods_for_shop(
        self, shop_id: str, cycle: str = "monthly"
    ) -> List[BillingPeriod]:
        """Get billing periods that need processing for a shop"""
        try:
            periods = []

            if cycle == "monthly":
                # Get last 3 months
                for i in range(3):
                    period_start = now_utc().replace(day=1) - timedelta(days=30 * i)
                    period_end = period_start + timedelta(days=30)
                    periods.append(
                        BillingPeriod(
                            start_date=period_start,
                            end_date=period_end,
                            cycle="monthly",
                        )
                    )

            return periods

        except Exception as e:
            logger.error(f"Error getting billing periods for shop {shop_id}: {e}")
            return []

    async def get_shops_for_billing(self) -> List[str]:
        """Get list of shop IDs that need billing processing"""
        try:
            # Get shops with active subscriptions
            query = select(ShopSubscription.shop_id).where(
                and_(
                    ShopSubscription.is_active == True,
                    ShopSubscription.status.in_(
                        [
                            SubscriptionStatus.ACTIVE,
                            SubscriptionStatus.TRIAL,
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

    # ============= OVERFLOW HANDLING =============

    async def get_cycle_overflow_summary(self, cycle_id: str) -> Dict[str, Any]:
        """Get overflow summary for a billing cycle"""
        try:
            from app.core.database.models import CommissionRecord
            from sqlalchemy import func, case

            query = select(
                func.count(CommissionRecord.id).label("total_commissions"),
                func.coalesce(func.sum(CommissionRecord.commission_earned), 0).label(
                    "total_earned"
                ),
                func.coalesce(func.sum(CommissionRecord.commission_charged), 0).label(
                    "total_charged"
                ),
                func.coalesce(func.sum(CommissionRecord.commission_overflow), 0).label(
                    "total_overflow"
                ),
                func.count(
                    case(
                        (CommissionRecord.commission_overflow > 0, CommissionRecord.id),
                        else_=None,
                    )
                ).label("overflow_commissions"),
            ).where(CommissionRecord.billing_cycle_id == cycle_id)

            result = await self.session.execute(query)
            stats = result.one()

            return {
                "total_commissions": stats.total_commissions,
                "total_earned": float(stats.total_earned or 0),
                "total_charged": float(stats.total_charged or 0),
                "total_overflow": float(stats.total_overflow or 0),
                "overflow_commissions": stats.overflow_commissions,
                "charge_rate": (
                    float(stats.total_charged / stats.total_earned * 100)
                    if stats.total_earned and stats.total_earned > 0
                    else 0
                ),
            }

        except Exception as e:
            logger.error(f"Error getting cycle overflow summary: {e}")
            return {
                "total_commissions": 0,
                "total_earned": 0,
                "total_charged": 0,
                "total_overflow": 0,
                "overflow_commissions": 0,
                "charge_rate": 0,
            }

    async def get_cycle_overflow_amount(self, cycle_id: str) -> Decimal:
        """Get total overflow amount for a billing cycle"""
        try:
            from app.core.database.models import CommissionRecord
            from sqlalchemy import func

            query = select(
                func.coalesce(func.sum(CommissionRecord.commission_overflow), 0)
            ).where(CommissionRecord.billing_cycle_id == cycle_id)

            result = await self.session.execute(query)
            overflow_amount = result.scalar_one() or Decimal("0")

            return overflow_amount

        except Exception as e:
            logger.error(f"Error getting cycle overflow amount: {e}")
            return Decimal("0")
