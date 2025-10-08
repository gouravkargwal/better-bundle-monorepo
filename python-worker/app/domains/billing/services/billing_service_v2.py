"""
Billing Service V2

Updated billing service to work with the new redesigned billing system.
Uses new subscription and billing cycle models instead of old billing_plans.
"""

import logging
from decimal import Decimal
from typing import Optional, Dict, Any
from sqlalchemy import select, and_
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
        """
        Main entry point for ALL purchases.
        Handles both trial and post-trial usage using new schema.
        """
        try:
            shop_id = purchase_event.shop_id

            logger.info(
                f"🛒 Processing purchase {purchase_event.order_id} for shop {shop_id}"
            )

            # 1. Calculate attribution
            context = AttributionContext(
                shop_id=shop_id,
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

            attributed_revenue = attribution_result.total_attributed_revenue

            logger.info(
                f"💰 Attributed revenue: ${attributed_revenue} "
                f"for order {purchase_event.order_id}"
            )

            # Ensure trial auto-completion runs even if we later skip billing
            shop_subscription = await self.billing_repository.get_shop_subscription(
                shop_id
            )
            logger.info(f"🔍 Shop subscription: {shop_subscription}")
            if shop_subscription:
                try:
                    trial = await self.billing_repository.get_subscription_trial(
                        shop_subscription.id
                    )
                    logger.info(f"🔍 Trial: {trial}")
                    # If trial already completed but subscription not updated, fix it
                    if (
                        trial
                        and trial.completed_at
                        and shop_subscription.status != SubscriptionStatus.SUSPENDED
                    ):
                        logger.info(
                            f"🔄 Trial completed but subscription not updated for shop {shop_id} → setting to suspended"
                        )
                        shop_subscription.status = SubscriptionStatus.SUSPENDED
                        await self.session.flush()
                        await self.session.commit()
                        logger.info("✅ Shop subscription moved to suspended")

                    if (
                        trial
                        and trial.accumulated_revenue >= trial.threshold_amount
                        and not trial.completed_at
                    ):
                        logger.info(
                            f"🎉 Trial threshold already met for shop {shop_id} → completing trial"
                        )
                        await self._complete_trial_and_create_cycle(
                            shop_id, shop_subscription
                        )
                except Exception as _e:
                    logger.warning(
                        f"Could not auto-complete trial check for shop {shop_id}: {_e}"
                    )

            # Short-circuit: if we didn't influence (no session), skip billing entirely
            if not purchase_event.session_id:
                logger.info(
                    f"No session_id for order {purchase_event.order_id} → skipping billing"
                )
                return attribution_result

            if not shop_subscription:
                logger.warning(f"⚠️ No subscription found for shop {shop_id}")
                return attribution_result

            # 3. Route based on subscription status
            if shop_subscription.status == SubscriptionStatus.TRIAL:
                # TRIAL PHASE: Track internally
                await self._handle_trial_purchase(
                    shop_id, shop_subscription, attributed_revenue, purchase_event
                )
            elif shop_subscription.status == SubscriptionStatus.ACTIVE:
                # POST-TRIAL: Record with Shopify
                await self._handle_subscription_purchase(
                    shop_id, shop_subscription, attributed_revenue, purchase_event
                )
            elif shop_subscription.status == SubscriptionStatus.PENDING_APPROVAL:
                # WAITING: Subscription pending, don't process
                logger.info(
                    f"⏳ Shop {shop_id} awaiting subscription approval, "
                    f"not recording usage"
                )
            else:
                # SUSPENDED: No trial, no subscription
                logger.warning(
                    f"🛑 Shop {shop_id} has no active billing, services suspended"
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
        """Handle purchase during trial phase"""
        try:
            logger.info(f"🎯 Trial purchase: ${attributed_revenue} for shop {shop_id}")

            # Guard: skip if attribution id is not present on the event
            if (
                not hasattr(purchase_event, "attribution_id")
                or not purchase_event.attribution_id
            ):
                logger.info(
                    f"No attribution_id on event for order {purchase_event.order_id} → skipping trial commission"
                )
                return

            # Get trial info
            trial = await self.billing_repository.get_subscription_trial(
                shop_subscription.id
            )
            if not trial:
                logger.error(
                    f"❌ No trial found for subscription {shop_subscription.id}"
                )
                return
            pricing_tier = await self.billing_repository.get_pricing_tier(
                shop_subscription.pricing_tier_id
            )
            commission_rate = (
                pricing_tier.commission_rate if pricing_tier else Decimal("0.03")
            )

            # Create commission record
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
                    f"✅ Trial commission created: ${commission.commission_earned} "
                    f"(not charged during trial)"
                )

            # ✅ ADD: Update trial revenue
            await self.billing_repository.update_trial_revenue(
                shop_subscription.id, attributed_revenue
            )

            # Get updated trial info
            updated_trial = await self.billing_repository.get_subscription_trial(
                shop_subscription.id
            )

            logger.info(
                f"📊 Trial progress: ${updated_trial.accumulated_revenue}/"
                f"${updated_trial.threshold_amount} "
                f"(${updated_trial.commission_saved} saved)"
            )

            # Check if trial threshold reached
            if updated_trial.accumulated_revenue >= updated_trial.threshold_amount:
                logger.info(
                    f"🎉 Trial threshold reached for shop {shop_id}! "
                    f"Transitioning to paid phase..."
                )

                # Complete trial and create first billing cycle
                await self._complete_trial_and_create_cycle(shop_id, shop_subscription)

        except Exception as e:
            logger.error(f"❌ Error handling trial purchase: {e}")

    async def _handle_subscription_purchase(
        self,
        shop_id: str,
        shop_subscription: ShopSubscription,
        attributed_revenue: Decimal,
        purchase_event: PurchaseEvent,
    ) -> None:
        """Handle purchase during paid phase with overflow tracking"""
        try:
            logger.info(f"💳 Paid purchase: ${attributed_revenue} for shop {shop_id}")

            # Guard: skip if attribution id is not present on the event
            if (
                not hasattr(purchase_event, "attribution_id")
                or not purchase_event.attribution_id
            ):
                logger.info(
                    f"No attribution_id on event for order {purchase_event.order_id} → skipping paid commission"
                )
                return

            # Create commission record via commission service (handles overflow logic)
            commission = await self.commission_service.create_commission_record(
                purchase_attribution_id=purchase_event.attribution_id, shop_id=shop_id
            )

            if commission:
                logger.info(
                    f"✅ Commission created: ${commission.commission_charged} charged, "
                    f"${commission.commission_overflow} overflow "
                    f"(type: {commission.charge_type.value})"
                )

                # Record with Shopify (only the charged amount)
                if commission.commission_charged > 0:
                    await self.commission_service.record_commission_to_shopify(
                        commission_id=commission.id,
                        shopify_billing_service=self.shopify_billing,
                    )

        except Exception as e:
            logger.error(f"❌ Error handling subscription purchase: {e}")

    async def _complete_trial_and_create_cycle(
        self, shop_id: str, shop_subscription: ShopSubscription
    ) -> None:
        """Complete trial and create first billing cycle"""
        try:
            # Update trial status
            trial = await self.billing_repository.get_subscription_trial(
                shop_subscription.id
            )
            if trial:
                trial.status = TrialStatus.COMPLETED
                trial.completed_at = now_utc()

            # Update subscription status
            shop_subscription.status = SubscriptionStatus.SUSPENDED

            logger.info(f"✅ Trial completed")

            # Persist changes immediately so UI sees updated status
            await self.session.flush()
            await self.session.commit()

        except Exception as e:
            logger.error(f"❌ Error completing trial: {e}")
