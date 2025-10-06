"""
Billing Service - Pattern 1: Trial WITHOUT Upfront Consent

Flow:
1. Install → Track usage internally (no Shopify subscription yet)
2. $200 threshold → Suspend + Create Shopify subscription
3. User approves → Resume services + Record future usage with Shopify
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .attribution_engine import AttributionEngine, AttributionContext
from .shopify_usage_billing_service import ShopifyUsageBillingService
from ..repositories.billing_repository import BillingRepository
from ..models.attribution_models import AttributionResult, PurchaseEvent
from app.core.database.models import Shop, BillingPlan, BillingEvent

logger = logging.getLogger(__name__)

# Constants
TRIAL_THRESHOLD_USD = 200.0
PAID_CAPPED_AMOUNT_USD = 1000.0  # Monthly cap after trial


class BillingService:
    """Pattern 1: Trial without upfront consent"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.billing_repository = BillingRepository(session)
        self.attribution_engine = AttributionEngine(session)
        self.shopify_billing = ShopifyUsageBillingService(
            session, self.billing_repository
        )

    # ============= MAIN ENTRY POINT =============

    async def process_purchase_attribution(
        self, purchase_event: PurchaseEvent
    ) -> AttributionResult:
        """
        Main entry point for ALL purchases.
        Handles both trial and post-trial usage.
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

            # 2. Get billing plan with row lock
            billing_plan = await self._get_billing_plan_locked(shop_id)

            if not billing_plan:
                logger.warning(f"⚠️ No billing plan for shop {shop_id}")
                return attribution_result

            # 3. Route based on billing state
            if self._is_in_trial(billing_plan):
                # TRIAL PHASE: Track internally
                await self._handle_trial_purchase(
                    shop_id, billing_plan, attributed_revenue, purchase_event
                )
            elif self._has_active_subscription(billing_plan):
                # POST-TRIAL: Record with Shopify
                await self._handle_subscription_purchase(
                    shop_id, billing_plan, attributed_revenue, purchase_event
                )
            elif self._is_awaiting_approval(billing_plan):
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

            # 4. Store analytics
            await self._store_attribution_analytics(
                shop_id, purchase_event, attribution_result
            )

            return attribution_result

        except Exception as e:
            logger.error(f"❌ Error processing attribution: {e}", exc_info=True)
            raise

    # ============= TRIAL PHASE (Internal Tracking) =============

    def _is_in_trial(self, billing_plan: BillingPlan) -> bool:
        """Check if shop is in active trial"""
        return (
            billing_plan.is_trial_active
            and billing_plan.subscription_id is None
            and billing_plan.subscription_status in ["none", None]
        )

    async def _get_billing_plan_locked(self, shop_id: str) -> Optional[BillingPlan]:
        """Get billing plan with row lock to prevent race conditions"""
        stmt = (
            select(BillingPlan)
            .where(BillingPlan.shop_id == shop_id)
            .with_for_update()  # 🔒 Critical: Prevents concurrent updates
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _handle_trial_purchase(
        self,
        shop_id: str,
        billing_plan: BillingPlan,
        attributed_revenue: Decimal,
        purchase_event: PurchaseEvent,
    ) -> None:
        """
        Handle purchase during trial phase.
        Track internally, check threshold, suspend if needed.
        """
        try:
            # Read current values
            old_revenue = billing_plan.trial_revenue or Decimal("0")
            new_revenue = old_revenue + attributed_revenue

            # Use trial threshold from billing plan (already in shop currency)
            trial_threshold = Decimal(str(billing_plan.trial_threshold or 0))

            # Update counters
            billing_plan.trial_revenue = new_revenue
            billing_plan.trial_usage_records_count = (
                billing_plan.trial_usage_records_count or 0
            ) + 1
            billing_plan.updated_at = datetime.utcnow()

            logger.info(
                f"📊 Trial revenue updated: ${old_revenue} → ${new_revenue} "
                f"(threshold: ${trial_threshold})"
            )

            # Create billing event for tracking
            event = BillingEvent(
                shop_id=shop_id,
                plan_id=billing_plan.id,  # ✅ FIX: Add required plan_id
                type="trial_usage_recorded",
                occurred_at=datetime.utcnow(),
                processed_at=datetime.utcnow(),  # ✅ FIX: Add required processed_at
                data={
                    "order_id": purchase_event.order_id,
                    "attributed_revenue": float(attributed_revenue),
                    "cumulative_revenue": float(new_revenue),
                    "threshold": float(trial_threshold),
                    "usage_count": billing_plan.trial_usage_records_count,
                },
                billing_metadata={
                    "phase": "trial",
                    "internal_tracking": True,
                },
            )
            self.session.add(event)

            # ✅ CHECK THRESHOLD
            if new_revenue >= trial_threshold:
                logger.warning(
                    f"🎯 Trial threshold reached for shop {shop_id}! "
                    f"${new_revenue} >= ${trial_threshold}"
                )
                await self._trigger_trial_completion(shop_id, billing_plan, new_revenue)

            await self.session.commit()

        except Exception as e:
            await self.session.rollback()
            logger.error(f"❌ Error handling trial purchase: {e}")
            raise

    async def _trigger_trial_completion(
        self, shop_id: str, billing_plan: BillingPlan, final_revenue: Decimal
    ) -> None:
        """
        Trial threshold reached - suspend services and require subscription.

        This does NOT create Shopify subscription yet - that happens when
        user clicks "Setup Billing" in frontend.
        """
        try:
            logger.info(f"🛑 Completing trial for shop {shop_id}")

            # 1. Mark trial as completed
            billing_plan.is_trial_active = False
            billing_plan.trial_completed_at = datetime.utcnow()
            billing_plan.status = "suspended"
            billing_plan.requires_subscription_approval = True

            # Update configuration
            config = billing_plan.configuration or {}
            config.update(
                {
                    "trial_active": False,
                    "trial_completed_at": datetime.utcnow().isoformat(),
                    "trial_final_revenue": float(final_revenue),
                    "subscription_required": True,
                    "services_suspended": True,
                }
            )
            billing_plan.configuration = config

            # 2. Suspend shop services
            shop_stmt = (
                update(Shop)
                .where(Shop.id == shop_id)
                .values(
                    is_active=False,
                    suspended_at=datetime.utcnow(),
                    suspension_reason="trial_completed_subscription_required",
                    service_impact="suspended",
                    updated_at=datetime.utcnow(),
                )
            )
            await self.session.execute(shop_stmt)

            # 3. Create event
            event = BillingEvent(
                shop_id=shop_id,
                plan_id=billing_plan.id,  # ✅ FIX: Add required plan_id
                type="trial_completed",
                occurred_at=datetime.utcnow(),
                processed_at=datetime.utcnow(),  # ✅ FIX: Add required processed_at
                data={
                    "final_revenue": float(final_revenue),
                    "threshold": TRIAL_THRESHOLD_USD,
                    "completed_at": datetime.utcnow().isoformat(),
                    "services_suspended": True,
                    "requires_subscription": True,
                },
                billing_metadata={
                    "phase": "trial_completion",
                    "next_action": "create_subscription",
                },
            )
            self.session.add(event)

            await self.session.commit()

            logger.info(
                f"✅ Trial completed for shop {shop_id}. "
                f"Services suspended. User must approve subscription."
            )

        except Exception as e:
            await self.session.rollback()
            logger.error(f"❌ Error completing trial: {e}")
            raise

    # ============= POST-TRIAL PHASE (Shopify Tracking) =============

    def _has_active_subscription(self, billing_plan: BillingPlan) -> bool:
        """Check if shop has active Shopify subscription"""
        return (
            billing_plan.subscription_id is not None
            and billing_plan.subscription_status == "ACTIVE"
        )

    def _is_awaiting_approval(self, billing_plan: BillingPlan) -> bool:
        """Check if subscription is pending approval"""
        return (
            billing_plan.subscription_id is not None
            and billing_plan.subscription_status == "PENDING"
        )

    async def _handle_subscription_purchase(
        self,
        shop_id: str,
        billing_plan: BillingPlan,
        attributed_revenue: Decimal,
        purchase_event: PurchaseEvent,
    ) -> None:
        """
        Handle purchase after subscription is active.
        Record usage with Shopify API (source of truth).
        """
        try:
            # Get shop details
            shop_stmt = select(Shop).where(Shop.id == shop_id)
            shop_result = await self.session.execute(shop_stmt)
            shop = shop_result.scalar_one_or_none()

            if not shop:
                logger.error(f"❌ Shop not found: {shop_id}")
                return

            # Calculate fee (3% of attributed revenue)
            fee_amount = attributed_revenue * Decimal("0.03")
            currency = shop.currency_code or "USD"

            # Get subscription line item ID
            line_item_id = billing_plan.subscription_line_item_id

            if not line_item_id:
                logger.error(f"❌ No subscription line item ID for shop {shop_id}")
                return

            # ✅ RECORD WITH SHOPIFY (Source of Truth)
            logger.info(
                f"📤 Recording usage with Shopify: ${fee_amount} "
                f"(from ${attributed_revenue} revenue)"
            )

            usage_record = await self.shopify_billing.record_usage(
                shop_id=shop_id,
                shop_domain=shop.shop_domain,
                access_token=shop.access_token,
                subscription_line_item_id=line_item_id,
                description=f"Better Bundle - Order {purchase_event.order_id}",
                amount=fee_amount,
                currency=currency,
            )

            if usage_record:
                logger.info(f"✅ Usage recorded with Shopify: {usage_record.id}")

                # Store event for analytics
                event = BillingEvent(
                    shop_id=shop_id,
                    plan_id=billing_plan.id,  # ✅ FIX: Add required plan_id
                    type="usage_recorded",
                    occurred_at=datetime.utcnow(),
                    processed_at=datetime.utcnow(),  # ✅ FIX: Add required processed_at
                    data={
                        "order_id": purchase_event.order_id,
                        "attributed_revenue": float(attributed_revenue),
                        "fee_amount": float(fee_amount),
                        "shopify_usage_record_id": usage_record.id,
                        "currency": currency,
                    },
                    metadata={
                        "phase": "post_trial",
                        "shopify_tracking": True,
                    },
                )
                self.session.add(event)
                await self.session.commit()
            else:
                logger.error(
                    f"❌ Failed to record usage with Shopify for shop {shop_id}"
                )

        except Exception as e:
            logger.error(f"❌ Error handling subscription purchase: {e}")
            # Don't raise - we don't want to block order processing
            # if Shopify API has issues

    # ============= SUBSCRIPTION CREATION =============

    async def create_subscription_for_shop(self, shop_id: str) -> Dict[str, any]:
        """
        Create Shopify subscription after trial completion.
        Called from frontend when user clicks "Setup Billing".
        """
        try:
            logger.info(f"🔄 Creating subscription for shop {shop_id}")

            # Get shop and billing plan
            shop_stmt = select(Shop).where(Shop.id == shop_id)
            shop_result = await self.session.execute(shop_stmt)
            shop = shop_result.scalar_one_or_none()

            if not shop:
                return {"success": False, "error": "Shop not found"}

            billing_plan_stmt = select(BillingPlan).where(
                BillingPlan.shop_id == shop_id
            )
            plan_result = await self.session.execute(billing_plan_stmt)
            billing_plan = plan_result.scalar_one_or_none()

            if not billing_plan:
                return {"success": False, "error": "Billing plan not found"}

            # Check if already has subscription
            if billing_plan.subscription_id:
                return {
                    "success": False,
                    "error": "Subscription already exists",
                    "subscription_id": billing_plan.subscription_id,
                }

            # Create Shopify subscription
            currency = shop.currency_code or "USD"
            subscription = await self.shopify_billing.create_usage_subscription(
                shop_id=shop_id,
                shop_domain=shop.shop_domain,
                access_token=shop.access_token,
                currency=currency,
                capped_amount=PAID_CAPPED_AMOUNT_USD,
            )

            if not subscription:
                return {
                    "success": False,
                    "error": "Failed to create Shopify subscription",
                }

            # Update billing plan
            billing_plan.subscription_id = subscription.id
            billing_plan.subscription_status = "PENDING"
            billing_plan.subscription_line_item_id = subscription.line_items[0]["id"]
            billing_plan.subscription_confirmation_url = subscription.confirmation_url
            billing_plan.requires_subscription_approval = True

            config = billing_plan.configuration or {}
            config.update(
                {
                    "subscription_id": subscription.id,
                    "subscription_status": "PENDING",
                    "subscription_created_at": datetime.utcnow().isoformat(),
                    "capped_amount": PAID_CAPPED_AMOUNT_USD,
                }
            )
            billing_plan.configuration = config

            # Create event
            event = BillingEvent(
                shop_id=shop_id,
                plan_id=billing_plan.id,  # ✅ FIX: Add required plan_id
                type="subscription_created",
                occurred_at=datetime.utcnow(),
                processed_at=datetime.utcnow(),  # ✅ FIX: Add required processed_at
                data={
                    "subscription_id": subscription.id,
                    "status": "PENDING",
                    "capped_amount": PAID_CAPPED_AMOUNT_USD,
                    "currency": currency,
                },
                billing_metadata={
                    "phase": "subscription_creation",
                },
            )
            self.session.add(event)

            await self.session.commit()

            logger.info(
                f"✅ Subscription created: {subscription.id} "
                f"(status: PENDING, awaiting approval)"
            )

            return {
                "success": True,
                "subscription_id": subscription.id,
                "confirmation_url": subscription.confirmation_url,
                "status": "PENDING",
            }

        except Exception as e:
            await self.session.rollback()
            logger.error(f"❌ Error creating subscription: {e}")
            return {"success": False, "error": str(e)}

    # ============= SUBSCRIPTION ACTIVATION =============

    async def activate_subscription(self, shop_id: str, subscription_id: str) -> bool:
        """
        Activate subscription after merchant approval.
        Called by webhook handler.
        """
        try:
            logger.info(
                f"✅ Activating subscription {subscription_id} for shop {shop_id}"
            )

            # Update billing plan
            billing_plan_stmt = select(BillingPlan).where(
                BillingPlan.shop_id == shop_id,
                BillingPlan.subscription_id == subscription_id,
            )
            result = await self.session.execute(billing_plan_stmt)
            billing_plan = result.scalar_one_or_none()

            if not billing_plan:
                logger.error(f"❌ Billing plan not found for subscription")
                return False

            # Update status
            billing_plan.subscription_status = "ACTIVE"
            billing_plan.status = "active"
            billing_plan.requires_subscription_approval = False

            config = billing_plan.configuration or {}
            config.update(
                {
                    "subscription_status": "ACTIVE",
                    "subscription_activated_at": datetime.utcnow().isoformat(),
                    "services_suspended": False,
                }
            )
            billing_plan.configuration = config

            # Reactivate shop
            shop_stmt = (
                update(Shop)
                .where(Shop.id == shop_id)
                .values(
                    is_active=True,
                    suspended_at=None,
                    suspension_reason=None,
                    service_impact=None,
                    updated_at=datetime.utcnow(),
                )
            )
            await self.session.execute(shop_stmt)

            # Create event
            event = BillingEvent(
                shop_id=shop_id,
                plan_id=billing_plan.id,  # ✅ FIX: Add required plan_id
                type="subscription_activated",
                occurred_at=datetime.utcnow(),
                processed_at=datetime.utcnow(),  # ✅ FIX: Add required processed_at
                data={
                    "subscription_id": subscription_id,
                    "status": "ACTIVE",
                    "services_resumed": True,
                },
                billing_metadata={
                    "phase": "subscription_activation",
                },
            )
            self.session.add(event)

            await self.session.commit()

            logger.info(
                f"✅ Subscription activated. Services resumed for shop {shop_id}"
            )

            return True

        except Exception as e:
            await self.session.rollback()
            logger.error(f"❌ Error activating subscription: {e}")
            return False

    # ============= HELPER METHODS =============

    async def _store_attribution_analytics(
        self,
        shop_id: str,
        purchase_event: PurchaseEvent,
        attribution_result: AttributionResult,
    ) -> None:
        """Store attribution result for analytics"""
        # Implementation depends on your analytics tables
        pass
