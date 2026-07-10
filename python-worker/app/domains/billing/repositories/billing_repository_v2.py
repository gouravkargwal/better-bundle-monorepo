"""
Billing Repository V2

Single source of billing state. subscription_type has been removed —
SubscriptionStatus alone drives all business logic:

  TRIAL → ACTIVE → SUSPENDED / CANCELLED / EXPIRED

PENDING_APPROVAL has been removed. Merchants stay in TRIAL until the
APP_SUBSCRIPTIONS_UPDATE webhook confirms ACTIVE. The UI checks the
confirmation_url field to determine if billing setup has been initiated.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from sqlalchemy import select, and_, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

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
)
from app.core.database.models.enums import BillingPhase

logger = logging.getLogger(__name__)


@dataclass
class BillingPeriod:
    start_date: datetime
    end_date: datetime
    cycle: str  # 'monthly'


class BillingRepositoryV2:
    """Repository for billing-related database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ============= SHOP =============

    async def get_shop(self, shop_id: str) -> Optional[Shop]:
        try:
            result = await self.session.execute(
                select(Shop).where(Shop.id == shop_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting shop {shop_id}: {e}")
            return None

    # ============= SUBSCRIPTION PLAN =============

    async def get_default_subscription_plan(self) -> Optional[SubscriptionPlan]:
        try:
            result = await self.session.execute(
                select(SubscriptionPlan)
                .where(
                    and_(
                        SubscriptionPlan.is_active == True,
                        SubscriptionPlan.is_default == True,
                    )
                )
                .order_by(SubscriptionPlan.created_at.desc())
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting default subscription plan: {e}")
            return None

    async def get_subscription_plan_by_id(self, plan_id: str) -> Optional[SubscriptionPlan]:
        try:
            result = await self.session.execute(
                select(SubscriptionPlan).where(SubscriptionPlan.id == plan_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting subscription plan {plan_id}: {e}")
            return None

    # ============= PRICING TIER =============

    async def get_pricing_tier(self, pricing_tier_id: str) -> Optional[PricingTier]:
        try:
            result = await self.session.execute(
                select(PricingTier).where(PricingTier.id == pricing_tier_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting pricing tier {pricing_tier_id}: {e}")
            return None

    async def get_pricing_tier_for_plan_and_currency(
        self, plan_id: str, currency: str
    ) -> Optional[PricingTier]:
        try:
            result = await self.session.execute(
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
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting pricing tier for plan {plan_id}, currency {currency}: {e}")
            return None

    async def get_pricing_tier_for_country(
        self, country_code: str, plan_id: str
    ) -> Optional[PricingTier]:
        currency_map = {
            "US": "USD", "CA": "CAD", "GB": "GBP", "DE": "EUR", "FR": "EUR",
            "IN": "INR", "JP": "JPY", "AU": "AUD", "BR": "BRL", "MX": "MXN",
            "KR": "KRW", "CN": "CNY", "CH": "CHF", "SE": "SEK", "NO": "NOK",
            "DK": "DKK", "PL": "PLN", "CZ": "CZK", "HU": "HUF", "ZA": "ZAR",
            "TR": "TRY", "VN": "VND", "ID": "IDR", "PH": "PHP", "TH": "THB",
            "MY": "MYR", "SG": "SGD", "BD": "BDT", "PK": "PKR", "LK": "LKR",
            "NP": "NPR",
        }
        currency = currency_map.get(country_code, "USD")
        return await self.get_pricing_tier_for_plan_and_currency(plan_id, currency)

    # ============= SHOP SUBSCRIPTION =============

    async def get_shop_subscription(self, shop_id: str) -> Optional[ShopSubscription]:
        """Get the active subscription for a shop (any non-CANCELLED status)."""
        try:
            result = await self.session.execute(
                select(ShopSubscription)
                .options(
                    selectinload(ShopSubscription.pricing_tier),
                    joinedload(ShopSubscription.shop),
                )
                .where(
                    and_(
                        ShopSubscription.shop_id == shop_id,
                        ShopSubscription.is_active == True,
                    )
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting shop subscription for shop {shop_id}: {e}")
            return None

    async def get_shop_subscription_by_id(self, subscription_id: str) -> Optional[ShopSubscription]:
        try:
            result = await self.session.execute(
                select(ShopSubscription)
                .where(ShopSubscription.id == subscription_id)
                .options(
                    selectinload(ShopSubscription.subscription_plan),
                    selectinload(ShopSubscription.pricing_tier),
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting subscription {subscription_id}: {e}")
            return None

    async def create_trial_subscription(
        self,
        shop_id: str,
        subscription_plan_id: str,
        pricing_tier_id: str,
        trial_threshold_override: Optional[Decimal] = None,
    ) -> Optional[ShopSubscription]:
        """Create a new trial subscription. status=TRIAL is all that's needed."""
        try:
            subscription = ShopSubscription(
                shop_id=shop_id,
                status=SubscriptionStatus.TRIAL,
                subscription_plan_id=subscription_plan_id,
                pricing_tier_id=pricing_tier_id,
                trial_threshold_override=trial_threshold_override,
                trial_revenue=Decimal("0.00"),
                started_at=now_utc(),
                is_active=True,
            )
            self.session.add(subscription)
            await self.session.flush()
            logger.info(f"Created trial subscription {subscription.id} for shop {shop_id}")
            return subscription
        except Exception as e:
            logger.error(f"Error creating trial subscription: {e}")
            raise  # Let the caller's transaction handle rollback

    async def update_shop_subscription_status(
        self, subscription_id: str, status: SubscriptionStatus
    ) -> bool:
        result = await self.session.execute(
            update(ShopSubscription)
            .where(ShopSubscription.id == subscription_id)
            .values(status=status, updated_at=now_utc())
        )
        return result.rowcount > 0

    async def complete_trial_subscription(
        self, shop_id: str, additional_revenue: Decimal
    ) -> bool:
        """
        Atomically add revenue to trial_revenue. When threshold is reached,
        the merchant stays in TRIAL status — the UI checks trial_revenue vs
        threshold to prompt billing setup.

        Returns True if the trial threshold was crossed, False otherwise.
        """
        try:
            subscription = await self.get_shop_subscription(shop_id)
            if not subscription:
                return False

            if subscription.status != SubscriptionStatus.TRIAL:
                logger.debug(f"Subscription {subscription.id} is not in TRIAL status, skipping")
                return False

            # Atomically increment trial_revenue
            new_revenue = subscription.trial_revenue + additional_revenue
            threshold = subscription.effective_trial_threshold

            if new_revenue < threshold:
                # Update revenue but don't complete trial yet
                await self.session.execute(
                    update(ShopSubscription)
                    .where(ShopSubscription.id == subscription.id)
                    .values(
                        trial_revenue=new_revenue,
                        updated_at=now_utc(),
                    )
                )
                await self.session.flush()
                return False

            # Threshold reached — update revenue and completed_at, stay in TRIAL.
            # PENDING_APPROVAL no longer exists. The merchant stays in TRIAL
            # until they set up billing and Shopify confirms with ACTIVE.
            result = await self.session.execute(
                update(ShopSubscription)
                .where(
                    and_(
                        ShopSubscription.id == subscription.id,
                        ShopSubscription.status == SubscriptionStatus.TRIAL,
                    )
                )
                .values(
                    trial_revenue=new_revenue,
                    completed_at=now_utc(),
                    updated_at=now_utc(),
                )
            )

            if result.rowcount == 0:
                logger.debug(f"Trial {subscription.id} was already completed by another process")
                return True

            logger.info(
                f"✅ Trial threshold reached for shop {shop_id}. "
                f"Revenue: {new_revenue} >= {threshold}. Awaiting billing setup."
            )
            await self.session.flush()
            return True

        except Exception as e:
            logger.error(f"Error completing trial subscription: {e}")
            raise

    async def check_trial_completion(self, shop_id: str, additional_revenue: Decimal) -> bool:
        """Check and complete trial if threshold is reached. Idempotent."""
        try:
            subscription = await self.get_shop_subscription(shop_id)
            if not subscription or subscription.status != SubscriptionStatus.TRIAL:
                return False
            return await self.complete_trial_subscription(shop_id, additional_revenue)
        except Exception as e:
            logger.error(f"Error checking trial completion: {e}")
            return False

    async def create_paid_subscription(
        self,
        shop_id: str,
        shopify_subscription_id: str,
        shopify_line_item_id: Optional[str] = None,
        confirmation_url: Optional[str] = None,
    ) -> Optional[ShopSubscription]:
        """
        Activate a subscription from TRIAL to ACTIVE.
        The subscription must be in TRIAL status with a confirmation_url set
        (meaning billing setup was initiated).
        """
        try:
            result = await self.session.execute(
                update(ShopSubscription)
                .where(
                    and_(
                        ShopSubscription.shop_id == shop_id,
                        ShopSubscription.status == SubscriptionStatus.TRIAL,
                        ShopSubscription.is_active == True,
                    )
                )
                .values(
                    status=SubscriptionStatus.ACTIVE,
                    shopify_subscription_id=shopify_subscription_id,
                    shopify_line_item_id=shopify_line_item_id,
                    confirmation_url=confirmation_url,
                    updated_at=now_utc(),
                )
                .returning(ShopSubscription)
            )
            subscription = result.scalar_one_or_none()
            if subscription:
                await self.session.flush()
                logger.info(f"Activated subscription for shop {shop_id}")
            return subscription
        except Exception as e:
            logger.error(f"Error activating subscription: {e}")
            raise

    # ============= BILLING CYCLE =============

    async def get_current_billing_cycle(self, shop_subscription_id: str) -> Optional[BillingCycle]:
        """Get the single active billing cycle for a subscription."""
        try:
            result = await self.session.execute(
                select(BillingCycle)
                .where(
                    and_(
                        BillingCycle.shop_subscription_id == shop_subscription_id,
                        BillingCycle.status == BillingCycleStatus.ACTIVE,
                    )
                )
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting current billing cycle: {e}")
            return None

    async def get_billing_cycle_by_id(self, cycle_id: str) -> Optional[BillingCycle]:
        try:
            result = await self.session.execute(
                select(BillingCycle).where(BillingCycle.id == cycle_id)
            )
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
        """Atomically increment billing cycle usage (no race conditions)."""
        try:
            result = await self.session.execute(
                update(BillingCycle)
                .where(BillingCycle.id == cycle_id)
                .values(
                    usage_amount=BillingCycle.usage_amount + additional_usage,
                    commission_count=BillingCycle.commission_count + 1,
                    updated_at=now_utc(),
                )
            )
            if result.rowcount == 0:
                logger.error(f"Billing cycle {cycle_id} not found for usage update")
                return False
            await self.session.flush()
            return True
        except Exception as e:
            logger.error(f"Error updating billing cycle usage: {e}")
            return False

    # ============= COMMISSION =============

    async def get_commissions_for_cycle(
        self, billing_cycle_id: str, limit: int = 100
    ) -> List[CommissionRecord]:
        try:
            result = await self.session.execute(
                select(CommissionRecord)
                .where(CommissionRecord.billing_cycle_id == billing_cycle_id)
                .order_by(CommissionRecord.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting commissions for cycle: {e}")
            return []

    async def calculate_trial_revenue(self, shop_id: str) -> Decimal:
        """
        Get trial revenue from shop_subscriptions.trial_revenue (single source of truth).
        Falls back to summing commission_records if needed.
        """
        try:
            subscription = await self.get_shop_subscription(shop_id)
            if subscription and subscription.trial_revenue is not None:
                return subscription.trial_revenue

            # Fallback: sum from commission_records
            result = await self.session.execute(
                select(func.coalesce(func.sum(CommissionRecord.attributed_revenue), 0))
                .where(
                    and_(
                        CommissionRecord.shop_id == shop_id,
                        CommissionRecord.billing_phase == BillingPhase.TRIAL,
                        CommissionRecord.deleted_at == None,
                    )
                )
            )
            return Decimal(str(result.scalar_one()))
        except Exception as e:
            logger.error(f"Error calculating trial revenue: {e}")
            return Decimal("0")

    async def get_shops_for_billing(self) -> List[str]:
        """Get shop IDs with an active paid subscription."""
        try:
            result = await self.session.execute(
                select(ShopSubscription.shop_id).where(
                    and_(
                        ShopSubscription.is_active == True,
                        ShopSubscription.status == SubscriptionStatus.ACTIVE,
                    )
                )
            )
            shop_ids = [row[0] for row in result.fetchall()]
            logger.info(f"Found {len(shop_ids)} shops for billing processing")
            return shop_ids
        except Exception as e:
            logger.error(f"Error getting shops for billing: {e}")
            return []

    async def get_subscription_trial(self, shop_id: str) -> Optional[ShopSubscription]:
        """Return the active TRIAL subscription for a shop."""
        try:
            result = await self.session.execute(
                select(ShopSubscription)
                .where(
                    and_(
                        ShopSubscription.shop_id == shop_id,
                        ShopSubscription.status == SubscriptionStatus.TRIAL,
                        ShopSubscription.is_active == True,
                    )
                )
                .limit(1)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching active trial for shop {shop_id}: {e}")
            return None

    async def get_subscription_trial_by_id(self, subscription_id: str) -> Optional[ShopSubscription]:
        """Return a subscription by its primary ID."""
        try:
            result = await self.session.execute(
                select(ShopSubscription)
                .where(ShopSubscription.id == subscription_id)
                .limit(1)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error fetching subscription {subscription_id}: {e}")
            return None

    async def create_shopify_subscription(
        self,
        shop_subscription_id: str,
        shopify_subscription_id: str,
        shopify_line_item_id: Optional[str] = None,
        confirmation_url: Optional[str] = None,
    ) -> bool:
        """Store Shopify subscription info on an existing subscription record."""
        try:
            result = await self.session.execute(
                update(ShopSubscription)
                .where(ShopSubscription.id == shop_subscription_id)
                .values(
                    shopify_subscription_id=shopify_subscription_id,
                    shopify_line_item_id=shopify_line_item_id,
                    confirmation_url=confirmation_url,
                    updated_at=now_utc(),
                )
            )
            await self.session.flush()
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error storing Shopify subscription: {e}")
            return False
