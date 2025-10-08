"""
Billing Service V2

Updated billing service to work with the new redesigned billing system.
Uses new subscription and billing cycle models instead of old billing_plans.
"""

import logging
from decimal import Decimal
from typing import Optional, Dict, Any
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from .attribution_engine import AttributionEngine, AttributionContext
from .shopify_usage_billing_service_v2 import ShopifyUsageBillingServiceV2
from ..repositories.billing_repository_v2 import BillingRepositoryV2
from ..models.attribution_models import AttributionResult, PurchaseEvent
from app.core.database.models import (
    Shop,
    ShopSubscription,
    BillingCycle,
    CommissionRecord,
    SubscriptionStatus,
    BillingCycleStatus,
    TrialStatus,
    PurchaseAttribution,
)
from app.shared.helpers import now_utc
from app.domains.billing.services.commission_service_v2 import (
    CommissionServiceV2,
)

logger = logging.getLogger(__name__)


class BillingServiceV2:
    """Updated billing service using new subscription and billing cycle system"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.billing_repository = BillingRepositoryV2(session)
        self.attribution_engine = AttributionEngine(session)
        self.shopify_billing = ShopifyUsageBillingServiceV2(
            session, self.billing_repository
        )
        self.commission_service = CommissionServiceV2(session)

    # ============= MAIN ENTRY POINT =============

    async def process_purchase_attribution(
        self, purchase_event: PurchaseEvent
    ) -> AttributionResult:
        """Process purchase attribution and handle billing based on subscription status."""
        try:
            shop_id = purchase_event.shop_id
            logger.info(
                f"🛒 Processing purchase {purchase_event.order_id} for shop {shop_id}"
            )

            # 1. Calculate attribution
            attribution_result = await self._calculate_attribution(purchase_event)

            # 2. Get subscription and check trial completion
            shop_subscription = await self.billing_repository.get_shop_subscription(
                shop_id
            )
            await self._check_trial_completion(shop_id, shop_subscription)

            # 3. Handle billing based on subscription status
            await self._process_billing_by_status(
                shop_id, shop_subscription, attribution_result, purchase_event
            )

            return attribution_result

        except Exception as e:
            logger.error(f"❌ Error processing attribution: {e}", exc_info=True)
            raise

    async def _handle_trial_purchase(
        self,
        shop_id: str,
        shop_subscription: ShopSubscription,
        attributed_revenue: Decimal,
        purchase_event: PurchaseEvent,
    ) -> None:
        """Handle purchase during trial phase."""
        try:
            logger.info(f"🎯 Trial purchase: ${attributed_revenue} for shop {shop_id}")

            # Skip if no attribution ID
            if not self._has_attribution_id(purchase_event):
                return

            # Create trial commission
            await self._create_trial_commission(
                shop_id, shop_subscription, attributed_revenue, purchase_event
            )

            # Update trial revenue
            await self.billing_repository.update_trial_revenue(
                shop_subscription.id, attributed_revenue
            )

            # Log trial progress
            await self._log_trial_progress(shop_id, shop_subscription.id)

        except Exception as e:
            logger.error(f"❌ Error handling trial purchase: {e}")

    def _has_attribution_id(self, purchase_event: PurchaseEvent) -> bool:
        """Check if purchase event has attribution ID."""
        if (
            not hasattr(purchase_event, "attribution_id")
            or not purchase_event.attribution_id
        ):
            logger.info(
                f"No attribution_id on event for order {purchase_event.order_id} → skipping"
            )
            return False
        return True

    async def _create_trial_commission(
        self,
        shop_id: str,
        shop_subscription: ShopSubscription,
        attributed_revenue: Decimal,
        purchase_event: PurchaseEvent,
    ) -> None:
        """Create trial commission record."""
        trial = await self.billing_repository.get_subscription_trial(
            shop_subscription.id
        )
        if not trial:
            logger.error(f"❌ No trial found for subscription {shop_subscription.id}")
            return

        pricing_tier = await self.billing_repository.get_pricing_tier(
            shop_subscription.pricing_tier_id
        )
        commission_rate = (
            pricing_tier.commission_rate if pricing_tier else Decimal("0.03")
        )

        commission = await self.commission_service._create_trial_commission(
            shop_id=shop_id,
            purchase_attribution_id=purchase_event.attribution_id,
            shop_subscription=shop_subscription,
            attributed_revenue=attributed_revenue,
            commission_earned=Decimal("0"),
            commission_rate=commission_rate,
            purchase_attr=purchase_event,
        )

        if commission:
            logger.info(
                f"✅ Trial commission created: ${commission.commission_earned} (not charged during trial)"
            )

    async def _log_trial_progress(self, shop_id: str, subscription_id: str) -> None:
        """Log trial progress and check for completion."""
        trial = await self.billing_repository.get_subscription_trial(subscription_id)
        logger.info(
            f"📊 Trial progress: ${trial.accumulated_revenue}/${trial.threshold_amount} (${trial.commission_saved} saved)"
        )

        if trial.accumulated_revenue >= trial.threshold_amount:
            logger.info(
                f"🎉 Trial threshold reached for shop {shop_id}! Transitioning to paid phase..."
            )
            shop_subscription = await self.billing_repository.get_shop_subscription(
                shop_id
            )
            await self._complete_trial(shop_id, shop_subscription)

    async def _handle_subscription_purchase(
        self,
        shop_id: str,
        shop_subscription: ShopSubscription,
        attributed_revenue: Decimal,
        purchase_event: PurchaseEvent,
    ) -> None:
        """Handle purchase during paid phase with overflow tracking."""
        try:
            logger.info(f"💳 Paid purchase: ${attributed_revenue} for shop {shop_id}")

            # Skip if no attribution ID
            if not self._has_attribution_id(purchase_event):
                return

            # Create and record commission
            await self._create_and_record_commission(shop_id, purchase_event)

        except Exception as e:
            logger.error(f"❌ Error handling subscription purchase: {e}")

    async def _create_and_record_commission(
        self, shop_id: str, purchase_event: PurchaseEvent
    ) -> None:
        """Create commission record and record with Shopify."""
        commission = await self.commission_service.create_commission_record(
            purchase_attribution_id=purchase_event.attribution_id, shop_id=shop_id
        )

        if commission:
            logger.info(
                f"✅ Commission created: ${commission.commission_charged} charged, ${commission.commission_overflow} overflow (type: {commission.charge_type.value})"
            )

            # Record with Shopify (only the charged amount)
            if commission.commission_charged > 0:
                await self.commission_service.record_commission_to_shopify(
                    commission_id=commission.id,
                    shopify_billing_service=self.shopify_billing,
                )

    async def _complete_trial(
        self, shop_id: str, shop_subscription: ShopSubscription
    ) -> None:
        """Complete trial and wait for user to setup billing with their chosen cap"""
        try:
            # Update trial status
            trial = await self.billing_repository.get_subscription_trial(
                shop_subscription.id
            )
            if trial:
                trial.status = TrialStatus.COMPLETED
                trial.completed_at = now_utc()

            # ✅ FIX: Set to TRIAL_COMPLETED, not SUSPENDED or PENDING_APPROVAL
            shop_subscription.status = SubscriptionStatus.TRIAL_COMPLETED

            logger.info(
                f"✅ Trial completed for shop {shop_id}. "
                f"Awaiting user to setup billing with cap."
            )

            # Persist changes immediately so UI sees updated status
            await self.session.flush()
            await self.session.commit()

        except Exception as e:
            logger.error(f"❌ Error completing trial: {e}")

    async def _check_trial_completion(self, shop_id: str, shop_subscription) -> None:
        """
        Check if trial threshold is reached and complete trial if needed.

        Args:
            shop_id: Shop ID
            shop_subscription: Shop subscription object
        """
        if not shop_subscription:
            return

        try:
            # Get trial
            trial = await self.billing_repository.get_subscription_trial(
                shop_subscription.id
            )
            if not trial or trial.status != TrialStatus.ACTIVE or trial.completed_at:
                return

            # Get current trial revenue
            trial_revenue_query = select(
                func.coalesce(func.sum(PurchaseAttribution.total_revenue), 0)
            ).where(PurchaseAttribution.shop_id == shop_id)

            result = await self.session.execute(trial_revenue_query)
            current_revenue = Decimal(str(result.scalar_one()))

            # Complete trial if threshold reached
            if current_revenue >= trial.threshold_amount:
                logger.info(
                    f"🎉 Trial threshold reached: ${current_revenue} >= ${trial.threshold_amount}"
                )
                await self._complete_trial(shop_id, shop_subscription)
                await self.session.refresh(shop_subscription)

        except Exception as e:
            logger.warning(f"Could not check trial completion for shop {shop_id}: {e}")

    # ============= HELPER METHODS =============

    async def _calculate_attribution(
        self, purchase_event: PurchaseEvent
    ) -> AttributionResult:
        """Calculate attribution for a purchase."""
        context = AttributionContext(
            shop_id=purchase_event.shop_id,
            customer_id=purchase_event.customer_id,
            session_id=purchase_event.session_id,
            order_id=purchase_event.order_id,
            purchase_amount=purchase_event.total_amount,
            purchase_products=purchase_event.products,
            purchase_time=purchase_event.created_at,
        )

        attribution_result = await self.attribution_engine.calculate_attribution(
            context
        )
        logger.info(
            f"💰 Attributed revenue: ${attribution_result.total_attributed_revenue}"
        )
        return attribution_result

    async def _process_billing_by_status(
        self,
        shop_id: str,
        shop_subscription,
        attribution_result: AttributionResult,
        purchase_event: PurchaseEvent,
    ) -> None:
        """Process billing based on subscription status."""
        if not purchase_event.session_id:
            logger.info(
                f"No session_id for order {purchase_event.order_id} → skipping billing"
            )
            return

        if not shop_subscription:
            logger.warning(f"⚠️ No subscription found for shop {shop_id}")
            return

        attributed_revenue = attribution_result.total_attributed_revenue

        # Route based on subscription status
        if shop_subscription.status == SubscriptionStatus.TRIAL:
            await self._handle_trial_purchase(
                shop_id, shop_subscription, attributed_revenue, purchase_event
            )
        elif shop_subscription.status == SubscriptionStatus.ACTIVE:
            await self._handle_subscription_purchase(
                shop_id, shop_subscription, attributed_revenue, purchase_event
            )
        elif shop_subscription.status == SubscriptionStatus.TRIAL_COMPLETED:
            logger.info(f"⏳ Shop {shop_id} trial completed, awaiting billing setup")
        elif shop_subscription.status == SubscriptionStatus.PENDING_APPROVAL:
            logger.info(f"⏳ Shop {shop_id} awaiting subscription approval")
        else:
            logger.warning(
                f"🛑 Shop {shop_id} has no active billing (status: {shop_subscription.status.value})"
            )
