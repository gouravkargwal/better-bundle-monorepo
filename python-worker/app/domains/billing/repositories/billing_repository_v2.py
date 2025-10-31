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
from sqlalchemy.orm import selectinload

from app.shared.helpers import now_utc
from app.core.database.models import (
    Shop,
    SubscriptionPlan,
    PricingTier,
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

    async def get_pricing_tier_for_country(
        self, country_code: str, plan_id: str
    ) -> Optional[PricingTier]:
        """Get appropriate pricing tier based on country code"""
        # Map country codes to currencies
        currency_map = {
            "US": "USD",
            "CA": "CAD",
            "GB": "GBP",
            "DE": "EUR",
            "FR": "EUR",
            "IN": "INR",
            "JP": "JPY",
            "AU": "AUD",
            "BR": "BRL",
            "MX": "MXN",
            "KR": "KRW",
            "CN": "CNY",
            "CH": "CHF",
            "SE": "SEK",
            "NO": "NOK",
            "DK": "DKK",
            "PL": "PLN",
            "CZ": "CZK",
            "HU": "HUF",
            "ZA": "ZAR",
            "TR": "TRY",
            "VN": "VND",
            "ID": "IDR",
            "PH": "PHP",
            "TH": "THB",
            "MY": "MYR",
            "SG": "SGD",
            "BD": "BDT",
            "PK": "PKR",
            "LK": "LKR",
            "NP": "NPR",
        }

        currency = currency_map.get(country_code, "USD")  # Default to USD
        return await self.get_pricing_tier_for_plan_and_currency(plan_id, currency)

    async def get_pricing_tier(self, pricing_tier_id: str) -> Optional[PricingTier]:
        """Get pricing tier by ID"""
        try:
            query = select(PricingTier).where(PricingTier.id == pricing_tier_id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting pricing tier {pricing_tier_id}: {e}")
            return None

    # ============= UNIFIED SHOP SUBSCRIPTION OPERATIONS =============

    async def create_trial_subscription(
        self,
        shop_id: str,
        subscription_plan_id: str,
        pricing_tier_id: str,
        trial_threshold_override: Optional[Decimal] = None,
    ) -> Optional[ShopSubscription]:
        """Create a new trial subscription"""
        try:
            subscription = ShopSubscription(
                shop_id=shop_id,
                subscription_type=SubscriptionType.TRIAL,
                status=SubscriptionStatus.ACTIVE,
                subscription_plan_id=subscription_plan_id,
                pricing_tier_id=pricing_tier_id,
                trial_threshold_override=trial_threshold_override,
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
        pricing_tier_id: str,
        user_chosen_cap_amount: Decimal,
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
                pricing_tier_id=pricing_tier_id,
                user_chosen_cap_amount=user_chosen_cap_amount,
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

    async def complete_trial_subscription(
        self, shop_id: str, actual_revenue: Decimal
    ) -> bool:
        """Complete trial subscription atomically"""
        try:
            # Get current trial subscription
            trial_subscription = await self.session.execute(
                select(ShopSubscription)
                .where(
                    and_(
                        ShopSubscription.shop_id == shop_id,
                        ShopSubscription.subscription_type == SubscriptionType.TRIAL,
                        ShopSubscription.status == SubscriptionStatus.ACTIVE,
                        ShopSubscription.is_active == True,
                    )
                )
                .options(selectinload(ShopSubscription.pricing_tier))
            )
            subscription = trial_subscription.scalar_one_or_none()

            if not subscription:
                logger.debug(f"No active trial found for shop {shop_id}")
                return False

            # Check if threshold reached
            threshold = subscription.effective_trial_threshold
            if actual_revenue < threshold:
                logger.debug(
                    f"Trial threshold not reached: {actual_revenue} < {threshold}"
                )
                return False

            # ✅ ATOMIC: Update trial subscription
            update_result = await self.session.execute(
                update(ShopSubscription)
                .where(
                    and_(
                        ShopSubscription.id == subscription.id,
                        ShopSubscription.status
                        == SubscriptionStatus.ACTIVE,  # Only update if still active
                    )
                )
                .values(
                    status=SubscriptionStatus.COMPLETED,
                    completed_at=now_utc(),
                    updated_at=now_utc(),
                )
            )

            # Check if update happened (race condition protection)
            if update_result.rowcount == 0:
                logger.debug(
                    f"Trial {subscription.id} was already completed by another process"
                )
                return True

            # ✅ SUSPEND SHOP: When trial is completed, suspend the shop
            await self.session.execute(
                update(Shop)
                .where(
                    and_(
                        Shop.id == shop_id,
                        Shop.is_active == True,  # Only suspend if currently active
                    )
                )
                .values(
                    is_active=False,
                    suspended_at=now_utc(),
                    suspension_reason="trial_completed",
                    service_impact="suspended",
                    updated_at=now_utc(),
                )
            )

            logger.info(
                f"✅ Trial completed for shop {shop_id}. "
                f"Revenue: {actual_revenue} >= {threshold} {subscription.currency}. "
                f"Shop suspended - awaiting user billing setup."
            )

            await self.session.flush()
            return True

        except Exception as e:
            logger.error(f"Error completing trial subscription: {e}")
            return False

    # ============= TRIAL OPERATIONS (SIMPLIFIED) =============

    async def check_trial_completion(
        self, shop_id: str, actual_revenue: Decimal
    ) -> bool:
        """Check if trial should be completed based on actual revenue - IDEMPOTENT"""
        try:
            subscription = await self.get_shop_subscription(shop_id)
            if not subscription:
                return False

            # ✅ GUARD: Only check for trial subscriptions
            if not subscription.is_trial:
                logger.debug(
                    f"Subscription {subscription.id} is not a trial, skipping completion check"
                )
                return True

            # ✅ GUARD: Check if already completed
            if subscription.status != SubscriptionStatus.ACTIVE:
                logger.debug(
                    f"Trial {subscription.id} already completed (status: {subscription.status})"
                )
                return True

            # Check and complete if threshold reached
            return await self.complete_trial_subscription(shop_id, actual_revenue)

        except Exception as e:
            logger.error(f"Error checking trial completion: {e}")
            return False

    # ============= BILLING CYCLE OPERATIONS =============
    # (Keep existing billing cycle methods unchanged)

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

    # ============= COMMISSION OPERATIONS =============
    # (Keep existing commission methods unchanged)

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

    async def calculate_trial_revenue(self, shop_id: str) -> Decimal:
        """Calculate total trial revenue from commission records"""
        try:
            # ✅ IMPORTANT: Only count revenue from TRIAL phase commissions
            # This prevents double-counting during recalculation
            query = select(
                func.coalesce(func.sum(CommissionRecord.attributed_revenue), 0)
            ).where(
                and_(
                    CommissionRecord.shop_id == shop_id,
                    CommissionRecord.billing_phase == BillingPhase.TRIAL,
                )
            )

            result = await self.session.execute(query)
            return Decimal(str(result.scalar_one()))

        except Exception as e:
            logger.error(f"Error calculating trial revenue: {e}")
            return Decimal("0")

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
