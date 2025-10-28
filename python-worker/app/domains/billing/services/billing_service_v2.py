"""
Billing Service V2

Updated billing service to work with the new redesigned billing system.
Uses new subscription and billing cycle models instead of old billing_plans.
"""

import logging
from datetime import datetime, timedelta
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
        """Process purchase attribution and handle billing based on subscription status - TRANSACTION SAFE."""
        try:
            shop_id = purchase_event.shop_id
            logger.info(
                f"🛒 Processing purchase {purchase_event.order_id} for shop {shop_id}"
            )

            # ✅ IDEMPOTENCY: Check if purchase already processed
            if await self._is_purchase_already_processed(purchase_event):
                logger.info(
                    f"Purchase {purchase_event.order_id} already processed, skipping"
                )
                return await self._get_existing_attribution_result(purchase_event)

            # ✅ TRANSACTION: Wrap all operations in a single transaction
            try:
                # 1. Calculate attribution
                attribution_result = await self._calculate_attribution(purchase_event)

                # Skip processing if no revenue to attribute
                if attribution_result.total_attributed_revenue <= 0:
                    logger.info(
                        f"⏭️ Skipping billing processing for purchase {purchase_event.order_id}: "
                        f"no revenue to attribute (${attribution_result.total_attributed_revenue})"
                    )
                    return attribution_result

                # 2. Get subscription and check trial completion
                shop_subscription = await self.billing_repository.get_shop_subscription(
                    shop_id
                )
                await self._check_trial_completion(shop_id, shop_subscription)

                # 3. Handle billing based on subscription status
                await self._process_billing_by_status(
                    shop_id, shop_subscription, attribution_result, purchase_event
                )

                # ✅ ATOMIC: Commit all changes together
                await self.session.commit()
                logger.info(
                    f"✅ Successfully processed purchase {purchase_event.order_id}"
                )

                return attribution_result

            except Exception as e:
                # ✅ ROLLBACK: Ensure data consistency on any failure
                await self.session.rollback()
                logger.error(
                    f"❌ Transaction rolled back for purchase {purchase_event.order_id}: {e}"
                )
                raise

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

            # ✅ Trial completion is now handled in commission service
            # No need to update trial revenue separately - it's calculated dynamically

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

        # Calculate actual revenue from commission records
        actual_revenue = (
            await self.purchase_attribution_repository.get_total_revenue_by_shop(
                shop_id
            )
        )

        logger.info(
            f"📊 Trial progress: ${actual_revenue}/${trial.threshold_amount} (${trial.commission_saved} saved)"
        )

        if trial.is_threshold_reached(actual_revenue):
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
        """Complete trial and wait for user to setup billing with their chosen cap - TRANSACTION SAFE"""
        try:
            # ✅ ATOMIC: Use the repository's atomic trial completion method
            await self.billing_repository.check_trial_completion(
                shop_subscription.id,
                Decimal("0"),  # Will be calculated dynamically in the repository
            )

            logger.info(
                f"✅ Trial completed for shop {shop_id}. "
                f"Awaiting user to setup billing with cap."
            )

            # ✅ NO MANUAL COMMIT: Let the main transaction handle it

        except Exception as e:
            logger.error(f"❌ Error completing trial: {e}")
            raise

    async def _is_purchase_already_processed(
        self, purchase_event: PurchaseEvent
    ) -> bool:
        """Check if purchase has already been processed to prevent duplicate processing.

        Returns True if the order has been processed AND no new line items were added
        since the last attribution calculation.
        """
        try:
            from sqlalchemy import select, func
            from app.core.database.models.purchase_attribution import (
                PurchaseAttribution,
            )
            from app.core.database.models.order_data import LineItemData

            # Check if attribution record exists
            query = select(PurchaseAttribution).where(
                PurchaseAttribution.order_id == str(purchase_event.order_id),
                PurchaseAttribution.shop_id == purchase_event.shop_id,
            )
            result = await self.session.execute(query)
            existing_attribution = result.scalar_one_or_none()

            if not existing_attribution:
                return False  # No attribution record, need to process

            logger.info(
                f"🔍 Checking for new line items in order {purchase_event.order_id}:"
            )
            logger.info(
                f"   - Existing attribution created_at: {existing_attribution.created_at}"
            )

            # ✅ FIX: LineItemData.order_id is a FK to OrderData.id (UUID), not Shopify order ID
            # First, get the OrderData record to find its UUID
            from app.core.database.models.order_data import OrderData

            order_query = select(OrderData.id).where(
                OrderData.order_id == existing_attribution.order_id
            )
            order_result = await self.session.execute(order_query)
            order_record_id = order_result.scalar_one_or_none()

            if not order_record_id:
                logger.warning(
                    f"❌ Order record not found for order_id {existing_attribution.order_id}"
                )
                return False  # If no order record, process it

            logger.info(f"✅ Found order record ID: {order_record_id}")

            # Check if new line items were added since last attribution
            # Get the count of line items that were created after the attribution
            line_items_query = select(func.count(LineItemData.id)).where(
                LineItemData.order_id == order_record_id,
                LineItemData.created_at > existing_attribution.created_at,
            )
            line_items_result = await self.session.execute(line_items_query)
            new_line_items_count = line_items_result.scalar() or 0

            # Also get details of all line items for debugging
            all_items_query = (
                select(LineItemData.id, LineItemData.title, LineItemData.created_at)
                .where(LineItemData.order_id == order_record_id)
                .order_by(LineItemData.created_at.asc())
            )
            all_items_result = await self.session.execute(all_items_query)
            all_items = all_items_result.fetchall()

            logger.info(f"   - Total line items in order: {len(all_items)}")
            for idx, (item_id, title, item_created_at) in enumerate(all_items, 1):
                is_new = item_created_at > existing_attribution.created_at
                logger.info(
                    f"   - Item {idx}: {title[:50]} | created_at={item_created_at} | "
                    f"is_new={is_new}"
                )

            if new_line_items_count > 0:
                logger.info(
                    f"🔄 Order {purchase_event.order_id} has {new_line_items_count} new line items "
                    f"since last attribution, re-processing"
                )
                return False  # New line items added, need to re-process

            logger.info(
                f"⏭️ Order {purchase_event.order_id} already processed with no new line items, skipping"
            )
            return True  # No new line items, skip processing

        except Exception as e:
            logger.error(f"Error checking if purchase already processed: {e}")
            return False

    async def _has_post_purchase_line_items(
        self, order_id: int, order_created_at: datetime
    ) -> bool:
        """Check if order has line items added after the original order creation (post-purchase additions).

        Returns True if any line items were created more than 5 seconds after order creation.
        The 5-second buffer accounts for normal Shopify order processing time.
        """
        try:
            from sqlalchemy import select, func
            from app.core.database.models.order_data import LineItemData

            logger.info(
                f"🔍 Checking for post-purchase line items in order {order_id}, "
                f"order_created_at={order_created_at}"
            )

            # ✅ FIX: LineItemData.order_id is a FK to OrderData.id (UUID), not Shopify order ID
            # First, get the OrderData record to find its UUID
            from app.core.database.models.order_data import OrderData

            order_query = select(OrderData.id).where(
                OrderData.order_id == str(order_id)
            )
            order_result = await self.session.execute(order_query)
            order_record_id = order_result.scalar_one_or_none()

            if not order_record_id:
                logger.warning(f"❌ Order record not found for order_id {order_id}")
                return False

            logger.info(f"✅ Found order record ID: {order_record_id}")

            # Now get ALL line items using the order record's UUID
            all_line_items_query = (
                select(LineItemData.id, LineItemData.title, LineItemData.created_at)
                .where(LineItemData.order_id == order_record_id)
                .order_by(LineItemData.created_at.asc())
            )

            all_items_result = await self.session.execute(all_line_items_query)
            all_line_items = all_items_result.fetchall()

            logger.info(
                f"📦 Order {order_id} has {len(all_line_items)} total line items:"
            )
            for idx, (item_id, product_title, item_created_at) in enumerate(
                all_line_items, 1
            ):
                time_diff = (item_created_at - order_created_at).total_seconds()
                logger.info(
                    f"   {idx}. {product_title[:50]} | "
                    f"created_at={item_created_at} | "
                    f"time_diff={time_diff:.1f}s"
                )

            # Count line items created after order creation (with 5-second buffer)
            cutoff_time = order_created_at + timedelta(seconds=5)
            logger.info(f"🕒 Cutoff time for post-purchase detection: {cutoff_time}")

            line_items_query = select(func.count(LineItemData.id)).where(
                LineItemData.order_id == str(order_id),
                LineItemData.created_at > cutoff_time,
            )
            result = await self.session.execute(line_items_query)
            post_purchase_count = result.scalar() or 0

            if post_purchase_count > 0:
                logger.info(
                    f"✅ Order {order_id} has {post_purchase_count} post-purchase line items "
                    f"(created >{cutoff_time})"
                )
                return True
            else:
                logger.info(
                    f"❌ Order {order_id} has NO post-purchase line items "
                    f"(all items created before {cutoff_time})"
                )

            return False

        except Exception as e:
            logger.error(f"❌ Error checking for post-purchase line items: {e}")
            import traceback

            logger.error(traceback.format_exc())
            # Default to False (use created_at) if check fails
            return False

    async def _has_post_purchase_interactions(
        self,
        shop_id: str,
        customer_id: str,
        session_id: str,
        order_created_at: datetime,
        order_updated_at: datetime,
    ) -> bool:
        """Check if there are Apollo post-purchase interactions after order creation.

        This checks for recommendation clicks/add-to-cart events that occurred after
        the initial order was created, indicating post-purchase additions.

        Returns True if there are interactions after order_created_at.
        """
        try:
            from sqlalchemy import select, func, and_, or_
            from app.core.database.models.user_interaction import UserInteraction
            from app.domains.analytics.models.interaction import InteractionType

            logger.info(
                f"🔍 Checking for post-purchase interactions between "
                f"{order_created_at} and {order_updated_at}"
            )

            # Look for Apollo interactions that indicate post-purchase recommendations
            post_purchase_interaction_types = [
                InteractionType.RECOMMENDATION_CLICKED.value,
                InteractionType.RECOMMENDATION_ADD_TO_CART.value,
                InteractionType.RECOMMENDATION_VIEWED.value,
            ]

            # Query for interactions that occurred AFTER the initial order creation
            # but BEFORE or AT the order update time
            query = select(func.count(UserInteraction.id)).where(
                and_(
                    UserInteraction.shop_id == shop_id,
                    UserInteraction.customer_id == customer_id,
                    UserInteraction.interaction_type.in_(
                        post_purchase_interaction_types
                    ),
                    UserInteraction.extension_type == "apollo",
                    UserInteraction.created_at > order_created_at,
                    UserInteraction.created_at <= order_updated_at,
                )
            )

            result = await self.session.execute(query)
            interaction_count = result.scalar() or 0

            if interaction_count > 0:
                logger.info(
                    f"✅ Found {interaction_count} post-purchase Apollo interactions "
                    f"between {order_created_at} and {order_updated_at}"
                )
                return True
            else:
                logger.info(
                    f"❌ No post-purchase Apollo interactions found "
                    f"between {order_created_at} and {order_updated_at}"
                )
                return False

        except Exception as e:
            logger.error(f"❌ Error checking for post-purchase interactions: {e}")
            import traceback

            logger.error(traceback.format_exc())
            # Default to False (use created_at) if check fails
            return False

    async def _get_existing_attribution_result(
        self, purchase_event: PurchaseEvent
    ) -> AttributionResult:
        """Get existing attribution result for already processed purchase."""
        try:
            from sqlalchemy import select
            from app.core.database.models.purchase_attribution import (
                PurchaseAttribution,
            )
            from app.domains.billing.models.attribution_models import (
                AttributionType,
                AttributionStatus,
                AttributionBreakdown,
            )

            query = select(PurchaseAttribution).where(
                PurchaseAttribution.order_id == str(purchase_event.order_id),
                PurchaseAttribution.shop_id == purchase_event.shop_id,
            )
            result = await self.session.execute(query)
            existing = result.scalar_one_or_none()

            if existing:
                # Convert existing attribution to AttributionResult
                attribution_breakdown = []
                if existing.attribution_weights:
                    for weight_data in existing.attribution_weights:
                        attribution_breakdown.append(
                            AttributionBreakdown(
                                extension_type=weight_data.get("extension_type"),
                                attributed_amount=Decimal(
                                    str(weight_data.get("attributed_amount", 0))
                                ),
                                attribution_weight=weight_data.get("weight", 0.0),
                                attribution_type=AttributionType.CROSS_EXTENSION,
                                interaction_id=weight_data.get("interaction_id"),
                                metadata=weight_data.get("metadata", {}),
                            )
                        )

                return AttributionResult(
                    order_id=int(purchase_event.order_id),
                    shop_id=purchase_event.shop_id,
                    customer_id=purchase_event.customer_id,
                    session_id=existing.session_id,
                    total_attributed_revenue=existing.total_revenue,
                    attribution_breakdown=attribution_breakdown,
                    attribution_type=AttributionType.CROSS_EXTENSION,
                    status=AttributionStatus.CALCULATED,
                    calculated_at=existing.created_at,
                    metadata=existing.attribution_metadata or {},
                )
            else:
                # Fallback - create empty result
                return AttributionResult(
                    order_id=int(purchase_event.order_id),
                    shop_id=purchase_event.shop_id,
                    customer_id=purchase_event.customer_id,
                    session_id=None,
                    total_attributed_revenue=Decimal("0.00"),
                    attribution_breakdown=[],
                    attribution_type=AttributionType.DIRECT_CLICK,
                    status=AttributionStatus.PENDING,
                    calculated_at=now_utc(),
                    metadata={},
                )
        except Exception as e:
            logger.error(f"Error getting existing attribution result: {e}")
            return AttributionResult(
                order_id=int(purchase_event.order_id),
                shop_id=purchase_event.shop_id,
                customer_id=purchase_event.customer_id,
                session_id=None,
                total_attributed_revenue=Decimal("0.00"),
                attribution_breakdown=[],
                attribution_type=AttributionType.DIRECT_CLICK,
                status=AttributionStatus.PENDING,
                calculated_at=now_utc(),
                metadata={},
            )

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
        # ✅ FIX: For post-purchase additions, check if line items were added after order creation
        # Use updated_at only if there are actual post-purchase line item additions
        purchase_time = purchase_event.created_at

        logger.info(f"🔍 Attribution calculation for order {purchase_event.order_id}:")
        logger.info(f"   - created_at: {purchase_event.created_at}")
        logger.info(f"   - updated_at: {purchase_event.updated_at}")
        logger.info(f"   - has updated_at: {purchase_event.updated_at is not None}")

        if purchase_event.updated_at:
            time_diff = (
                purchase_event.updated_at - purchase_event.created_at
            ).total_seconds()
            logger.info(
                f"   - time difference (updated - created): {time_diff:.1f} seconds"
            )

            # Check if there are post-purchase interactions (Apollo recommendations)
            logger.info(
                f"🔍 Checking if order {purchase_event.order_id} has post-purchase interactions..."
            )
            has_post_purchase_interactions = await self._has_post_purchase_interactions(
                purchase_event.shop_id,
                purchase_event.customer_id,
                purchase_event.session_id,
                purchase_event.created_at,
                purchase_event.updated_at,
            )

            if has_post_purchase_interactions:
                logger.info(
                    f"✅ Order {purchase_event.order_id} HAS post-purchase interactions, "
                    f"using updated_at ({purchase_event.updated_at}) for attribution"
                )
                purchase_time = purchase_event.updated_at
            else:
                logger.info(
                    f"❌ Order {purchase_event.order_id} has NO post-purchase interactions, "
                    f"using created_at ({purchase_event.created_at}) for attribution"
                )
        else:
            logger.info(
                f"ℹ️ Order {purchase_event.order_id} has no updated_at, "
                f"using created_at ({purchase_event.created_at}) for attribution"
            )

        logger.info(f"🎯 Final purchase_time for attribution: {purchase_time}")

        context = AttributionContext(
            shop_id=purchase_event.shop_id,
            customer_id=purchase_event.customer_id,
            session_id=purchase_event.session_id,
            order_id=purchase_event.order_id,
            purchase_amount=purchase_event.total_amount,
            purchase_products=purchase_event.products,
            purchase_time=purchase_time,
        )

        attribution_result = await self.attribution_engine.calculate_attribution(
            context
        )
        logger.info(
            f"💰 Attributed revenue: ${attribution_result.total_attributed_revenue} (purchase_time: {purchase_time})"
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
