"""
Commission Service

Handles creation, tracking, and management of commission records
for both trial and paid billing phases.
"""

import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database.models import (
    CommissionRecord,
)
from app.core.database.models import BillingPlan
from app.core.database.models import PurchaseAttribution
from app.core.database.models import Shop
from app.shared.helpers import now_utc
from app.core.database.models.enums import BillingPhase, CommissionStatus, ChargeType


logger = logging.getLogger(__name__)


class CommissionService:
    """Service for managing commission records"""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ============= CREATION =============

    async def create_commission_record(
        self,
        purchase_attribution_id: str,
        shop_id: str,
    ) -> Optional[CommissionRecord]:
        """
        Create a commission record from a purchase attribution.
        This is idempotent - won't create duplicate if already exists.
        Handles both trial and paid phases automatically.

        Args:
            purchase_attribution_id: Purchase attribution ID
            shop_id: Shop ID

        Returns:
            Created or existing commission record, or None if failed
        """
        try:
            # Check if commission already exists for this purchase (idempotency)
            existing_query = select(CommissionRecord).where(
                CommissionRecord.purchase_attribution_id == purchase_attribution_id
            )
            existing_result = await self.session.execute(existing_query)
            existing = existing_result.scalar_one_or_none()

            if existing:
                logger.info(
                    f"✅ Commission already exists for purchase {purchase_attribution_id}"
                )
                return existing

            # Get purchase attribution
            purchase_attr_query = select(PurchaseAttribution).where(
                PurchaseAttribution.id == purchase_attribution_id
            )
            purchase_attr_result = await self.session.execute(purchase_attr_query)
            purchase_attr = purchase_attr_result.scalar_one_or_none()

            if not purchase_attr:
                logger.error(
                    f"❌ Purchase attribution {purchase_attribution_id} not found"
                )
                return None

            # Get billing plan
            billing_plan = await self._get_active_billing_plan(shop_id)
            if not billing_plan:
                logger.error(f"❌ No active billing plan for shop {shop_id}")
                return None

            # Get shop details
            shop_query = select(Shop).where(Shop.id == shop_id)
            shop_result = await self.session.execute(shop_query)
            shop = shop_result.scalar_one_or_none()

            if not shop:
                logger.error(f"❌ Shop {shop_id} not found")
                return None

            # Calculate commission
            attributed_revenue = Decimal(str(purchase_attr.total_revenue))
            commission_rate = Decimal("0.03")  # 3%
            commission_earned = attributed_revenue * commission_rate

            # Get capped amount from billing plan
            config = billing_plan.configuration or {}
            capped_amount = Decimal(str(config.get("capped_amount", 1000)))

            # Determine billing phase and cycle
            if billing_plan.is_trial_active:
                # TRIAL PHASE
                billing_phase = BillingPhase.TRIAL
                status = CommissionStatus.TRIAL_PENDING
                charge_type = ChargeType.TRIAL

                # Calculate trial accumulated revenue
                trial_revenue_query = select(
                    func.coalesce(func.sum(PurchaseAttribution.total_revenue), 0)
                ).where(PurchaseAttribution.shop_id == shop_id)

                trial_revenue_result = await self.session.execute(trial_revenue_query)
                trial_accumulated = Decimal(str(trial_revenue_result.scalar_one()))

                # No billing cycle during trial
                billing_cycle_start = None
                billing_cycle_end = None
                cycle_usage_before = Decimal("0")
                cycle_usage_after = Decimal("0")

            else:
                # PAID PHASE
                billing_phase = BillingPhase.PAID
                status = CommissionStatus.PENDING
                charge_type = ChargeType.FULL  # Will be updated if partial

                trial_accumulated = Decimal("0")

                # Calculate billing cycle (30 days from trial completion)
                trial_completed_at = billing_plan.trial_completed_at
                if not trial_completed_at:
                    logger.error(
                        f"❌ Trial not completed for shop {shop_id} but not in trial mode"
                    )
                    return None

                # Find which billing cycle this purchase belongs to
                days_since_trial = (purchase_attr.purchase_at - trial_completed_at).days
                cycle_number = days_since_trial // 30
                billing_cycle_start = trial_completed_at + timedelta(
                    days=cycle_number * 30
                )
                billing_cycle_end = billing_cycle_start + timedelta(days=30)

                # Get current cycle usage BEFORE this commission
                cycle_usage_before = await self._get_cycle_usage(
                    shop_id, billing_cycle_start, billing_cycle_end
                )

                cycle_usage_after = cycle_usage_before + commission_earned

            # Create commission record
            commission = CommissionRecord(
                shop_id=shop_id,
                purchase_attribution_id=purchase_attribution_id,
                billing_plan_id=billing_plan.id,
                order_id=str(purchase_attr.order_id),
                order_date=purchase_attr.purchase_at,
                attributed_revenue=attributed_revenue,
                commission_rate=commission_rate,
                commission_earned=commission_earned,
                commission_charged=Decimal("0"),  # Not charged yet
                commission_overflow=Decimal("0"),
                billing_cycle_start=billing_cycle_start,
                billing_cycle_end=billing_cycle_end,
                cycle_usage_before=cycle_usage_before,
                cycle_usage_after=cycle_usage_after,
                capped_amount=capped_amount,
                trial_accumulated=trial_accumulated,
                billing_phase=billing_phase,
                status=status,
                charge_type=charge_type,
                currency=shop.currency_code or "USD",
            )

            self.session.add(commission)
            await self.session.flush()

            logger.info(
                f"✅ Created commission record: ${commission_earned} "
                f"(phase={billing_phase.value}, status={status.value})"
            )

            if billing_phase == BillingPhase.PAID:
                logger.info(
                    f"📊 Cycle usage: ${cycle_usage_after} / ${capped_amount} "
                    f"({(cycle_usage_after / capped_amount * 100):.1f}%)"
                )

            return commission

        except Exception as e:
            logger.error(f"❌ Error creating commission record: {e}")
            await self.session.rollback()
            return None

    # ============= SHOPIFY RECORDING =============

    async def record_commission_to_shopify(
        self, commission_id: str, shopify_billing_service
    ) -> Dict[str, Any]:
        """
        Record commission to Shopify as usage record.
        Handles cap checking, partial charges, and overflow.

        Args:
            commission_id: Commission record ID
            shopify_billing_service: Instance of ShopifyUsageBillingService

        Returns:
            Result dictionary with success status and details
        """
        try:
            # Get commission record
            commission_query = select(CommissionRecord).where(
                CommissionRecord.id == commission_id
            )
            commission_result = await self.session.execute(commission_query)
            commission = commission_result.scalar_one_or_none()

            if not commission:
                logger.error(f"❌ Commission {commission_id} not found")
                return {"success": False, "error": "commission_not_found"}

            # Check if already recorded
            if commission.shopify_usage_record_id:
                logger.info(f"✅ Commission already recorded to Shopify")
                return {
                    "success": True,
                    "already_recorded": True,
                    "shopify_usage_record_id": commission.shopify_usage_record_id,
                }

            # Check if this is trial phase
            if commission.billing_phase == BillingPhase.TRIAL:
                logger.warning(
                    f"⚠️ Cannot record trial commission to Shopify: {commission_id}"
                )
                return {"success": False, "error": "trial_phase_no_charge"}

            # Get shop and billing plan
            shop_query = select(Shop).where(Shop.id == commission.shop_id)
            shop_result = await self.session.execute(shop_query)
            shop = shop_result.scalar_one_or_none()

            billing_plan_query = select(BillingPlan).where(
                BillingPlan.id == commission.billing_plan_id
            )
            billing_plan_result = await self.session.execute(billing_plan_query)
            billing_plan = billing_plan_result.scalar_one_or_none()

            if not shop or not billing_plan:
                logger.error(f"❌ Shop or billing plan not found")
                return {"success": False, "error": "shop_or_plan_not_found"}

            # Check subscription status
            if (
                not billing_plan.subscription_id
                or billing_plan.subscription_status != "ACTIVE"
            ):
                logger.warning(
                    f"⚠️ No active subscription for shop {commission.shop_id}"
                )
                commission.status = CommissionStatus.REJECTED
                commission.notes = "No active subscription"
                await self.session.flush()
                return {"success": False, "error": "no_active_subscription"}

            # Calculate remaining capacity in current cycle
            remaining_capacity = (
                commission.capped_amount - commission.cycle_usage_before
            )

            # Check if cap already reached
            if remaining_capacity <= 0:
                logger.warning(
                    f"⚠️ Cap already reached! "
                    f"${commission.cycle_usage_before} >= ${commission.capped_amount}"
                )

                commission.status = CommissionStatus.CAPPED
                commission.charge_type = ChargeType.REJECTED
                commission.commission_overflow = commission.commission_earned
                commission.notes = "Cap reached before this commission"
                await self.session.flush()

                return {
                    "success": False,
                    "error": "cap_reached",
                    "cycle_usage": float(commission.cycle_usage_before),
                    "capped_amount": float(commission.capped_amount),
                    "overflow": float(commission.commission_earned),
                }

            # Calculate actual charge (handle partial charge if needed)
            actual_charge = min(commission.commission_earned, remaining_capacity)
            overflow = commission.commission_earned - actual_charge

            # Determine charge type
            if overflow > 0:
                charge_type = ChargeType.PARTIAL
                logger.warning(
                    f"⚠️ Partial charge due to cap: "
                    f"${actual_charge} charged, ${overflow} overflow"
                )
            else:
                charge_type = ChargeType.FULL

            # Record to Shopify
            logger.info(f"📤 Recording ${actual_charge} to Shopify...")

            usage_record = await shopify_billing_service.record_usage(
                shop_id=shop.id,
                shop_domain=shop.shop_domain,
                access_token=shop.access_token,
                subscription_line_item_id=billing_plan.subscription_line_item_id,
                description=f"Better Bundle - Order {commission.order_id}",
                amount=actual_charge,
                currency=commission.currency,
            )

            if not usage_record:
                logger.error(f"❌ Failed to record to Shopify")
                commission.status = CommissionStatus.FAILED
                commission.error_count += 1
                commission.last_error = "Failed to create Shopify usage record"
                commission.last_error_at = now_utc()
                await self.session.flush()

                return {
                    "success": False,
                    "error": "shopify_api_failed",
                    "error_count": commission.error_count,
                }

            # Update commission record with success
            commission.shopify_usage_record_id = usage_record.id
            commission.shopify_recorded_at = now_utc()
            commission.shopify_response = {
                "id": usage_record.id,
                "created_at": usage_record.created_at,
                "price": {
                    "amount": str(usage_record.price["amount"]),
                    "currency": usage_record.price["currencyCode"],
                },
            }
            commission.commission_charged = actual_charge
            commission.commission_overflow = overflow
            commission.charge_type = charge_type
            commission.status = CommissionStatus.RECORDED
            commission.updated_at = now_utc()

            await self.session.flush()

            logger.info(
                f"✅ Recorded commission to Shopify: {usage_record.id} "
                f"(${actual_charge} charged"
                + (f", ${overflow} overflow)" if overflow > 0 else ")")
            )

            # Check if we should warn about approaching cap
            new_cycle_usage = commission.cycle_usage_before + actual_charge
            usage_percentage = (new_cycle_usage / commission.capped_amount) * 100

            if usage_percentage >= 90:
                logger.warning(
                    f"⚠️ Usage at {usage_percentage:.1f}% of cap "
                    f"(${new_cycle_usage} / ${commission.capped_amount})"
                )

            return {
                "success": True,
                "shopify_usage_record_id": usage_record.id,
                "commission_charged": float(actual_charge),
                "commission_overflow": float(overflow),
                "charge_type": charge_type.value,
                "cycle_usage": float(new_cycle_usage),
                "capped_amount": float(commission.capped_amount),
                "usage_percentage": usage_percentage,
                "is_partial_charge": overflow > 0,
            }

        except Exception as e:
            logger.error(f"❌ Error recording to Shopify: {e}")

            # Update error tracking
            if commission:
                commission.status = CommissionStatus.FAILED
                commission.error_count += 1
                commission.last_error = str(e)
                commission.last_error_at = now_utc()
                await self.session.flush()

            return {"success": False, "error": str(e)}

    # ============= TRIAL MANAGEMENT =============

    async def handle_trial_threshold_check(self, shop_id: str) -> Dict[str, Any]:
        """
        Check if trial threshold has been reached.
        Returns trial status and whether threshold was just reached.

        Args:
            shop_id: Shop ID

        Returns:
            Dictionary with trial status information
        """
        try:
            # Get billing plan
            billing_plan = await self._get_active_billing_plan(shop_id)
            if not billing_plan or not billing_plan.is_trial_active:
                return {
                    "is_trial": False,
                    "threshold_reached": False,
                }

            # Calculate total trial revenue
            trial_revenue_query = select(
                func.coalesce(func.sum(PurchaseAttribution.total_revenue), 0)
            ).where(PurchaseAttribution.shop_id == shop_id)

            trial_revenue_result = await self.session.execute(trial_revenue_query)
            total_trial_revenue = Decimal(str(trial_revenue_result.scalar_one()))

            trial_threshold = Decimal(str(billing_plan.trial_threshold or 200))

            threshold_reached = total_trial_revenue >= trial_threshold

            # Calculate trial commissions (what merchant saved)
            trial_commissions_query = select(
                func.coalesce(func.sum(CommissionRecord.commission_earned), 0)
            ).where(
                and_(
                    CommissionRecord.shop_id == shop_id,
                    CommissionRecord.billing_phase == BillingPhase.TRIAL,
                )
            )

            trial_commissions_result = await self.session.execute(
                trial_commissions_query
            )
            total_commission_saved = Decimal(str(trial_commissions_result.scalar_one()))

            logger.info(
                f"📊 Trial status for {shop_id}: "
                f"${total_trial_revenue} / ${trial_threshold} "
                f"(saved ${total_commission_saved} in commissions)"
            )

            return {
                "is_trial": True,
                "threshold_reached": threshold_reached,
                "total_trial_revenue": float(total_trial_revenue),
                "trial_threshold": float(trial_threshold),
                "remaining_revenue": float(
                    max(0, trial_threshold - total_trial_revenue)
                ),
                "progress_percentage": float(
                    (total_trial_revenue / trial_threshold * 100)
                    if trial_threshold > 0
                    else 0
                ),
                "total_commission_saved": float(total_commission_saved),
            }

        except Exception as e:
            logger.error(f"❌ Error checking trial threshold: {e}")
            return {
                "is_trial": False,
                "threshold_reached": False,
                "error": str(e),
            }

    async def transition_trial_to_paid(
        self, shop_id: str, subscription_id: str
    ) -> Dict[str, Any]:
        """
        Transition all trial commissions to paid phase after subscription approval.
        Trial commissions remain as historical records but are marked as trial_completed.

        Args:
            shop_id: Shop ID
            subscription_id: Shopify subscription ID

        Returns:
            Result dictionary
        """
        try:
            # Get billing plan
            billing_plan = await self._get_active_billing_plan(shop_id)
            if not billing_plan:
                logger.error(f"❌ No billing plan found for shop {shop_id}")
                return {"success": False, "error": "no_billing_plan"}

            # Calculate first billing cycle (starts from trial completion)
            cycle_start = billing_plan.trial_completed_at or now_utc()
            cycle_end = cycle_start + timedelta(days=30)

            # Update all trial commissions to mark them as completed
            # They stay in the system for audit trail but won't be charged
            update_query = (
                update(CommissionRecord)
                .where(
                    and_(
                        CommissionRecord.shop_id == shop_id,
                        CommissionRecord.billing_phase == BillingPhase.TRIAL,
                        CommissionRecord.status == CommissionStatus.TRIAL_PENDING,
                    )
                )
                .values(
                    billing_phase=BillingPhase.PAID,
                    status=CommissionStatus.TRIAL_COMPLETED,
                    billing_cycle_start=cycle_start,
                    billing_cycle_end=cycle_end,
                    commission_charged=Decimal("0"),  # Still $0 - was during trial
                    notes="Earned during trial period - not charged",
                    updated_at=now_utc(),
                )
            )

            result = await self.session.execute(update_query)
            updated_count = result.rowcount

            await self.session.flush()

            logger.info(
                f"✅ Transitioned {updated_count} trial commissions to paid phase "
                f"for shop {shop_id}"
            )

            return {
                "success": True,
                "shop_id": shop_id,
                "subscription_id": subscription_id,
                "trial_commissions_transitioned": updated_count,
                "first_cycle_start": cycle_start.isoformat(),
                "first_cycle_end": cycle_end.isoformat(),
            }

        except Exception as e:
            logger.error(f"❌ Error transitioning trial to paid: {e}")
            await self.session.rollback()
            return {"success": False, "error": str(e)}

    # ============= QUERY METHODS =============

    async def get_commission_by_id(
        self, commission_id: str
    ) -> Optional[CommissionRecord]:
        """Get commission record by ID"""
        try:
            query = select(CommissionRecord).where(CommissionRecord.id == commission_id)
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"❌ Error getting commission: {e}")
            return None

    async def get_commissions_by_shop(
        self,
        shop_id: str,
        billing_phase: Optional[BillingPhase] = None,
        status: Optional[CommissionStatus] = None,
        limit: int = 100,
    ) -> List[CommissionRecord]:
        """Get commission records for a shop"""
        try:
            query = select(CommissionRecord).where(CommissionRecord.shop_id == shop_id)

            if billing_phase:
                query = query.where(CommissionRecord.billing_phase == billing_phase)

            if status:
                query = query.where(CommissionRecord.status == status)

            query = query.order_by(CommissionRecord.created_at.desc()).limit(limit)

            result = await self.session.execute(query)
            return list(result.scalars().all())

        except Exception as e:
            logger.error(f"❌ Error getting commissions: {e}")
            return []

    async def get_cycle_commissions(
        self, shop_id: str, cycle_start: datetime, cycle_end: datetime
    ) -> List[CommissionRecord]:
        """Get all commissions for a specific billing cycle"""
        try:
            query = (
                select(CommissionRecord)
                .where(
                    and_(
                        CommissionRecord.shop_id == shop_id,
                        CommissionRecord.billing_cycle_start == cycle_start,
                        CommissionRecord.billing_cycle_end == cycle_end,
                        CommissionRecord.status.in_(
                            [
                                CommissionStatus.RECORDED,
                                CommissionStatus.INVOICED,
                            ]
                        ),
                    )
                )
                .order_by(CommissionRecord.created_at.asc())
            )

            result = await self.session.execute(query)
            return list(result.scalars().all())

        except Exception as e:
            logger.error(f"❌ Error getting cycle commissions: {e}")
            return []

    async def get_pending_commissions(self, limit: int = 100) -> List[CommissionRecord]:
        """Get all pending commissions that need to be recorded to Shopify"""
        try:
            query = (
                select(CommissionRecord)
                .where(
                    and_(
                        CommissionRecord.status == CommissionStatus.PENDING,
                        CommissionRecord.billing_phase == BillingPhase.PAID,
                        CommissionRecord.shopify_usage_record_id.is_(None),
                    )
                )
                .order_by(CommissionRecord.created_at.asc())
                .limit(limit)
            )

            result = await self.session.execute(query)
            return list(result.scalars().all())

        except Exception as e:
            logger.error(f"❌ Error getting pending commissions: {e}")
            return []

    async def get_failed_commissions(
        self, max_retries: int = 3, limit: int = 100
    ) -> List[CommissionRecord]:
        """Get failed commissions that can be retried"""
        try:
            query = (
                select(CommissionRecord)
                .where(
                    and_(
                        CommissionRecord.status == CommissionStatus.FAILED,
                        CommissionRecord.error_count < max_retries,
                    )
                )
                .order_by(CommissionRecord.last_error_at.asc())
                .limit(limit)
            )

            result = await self.session.execute(query)
            return list(result.scalars().all())

        except Exception as e:
            logger.error(f"❌ Error getting failed commissions: {e}")
            return []

    # ============= STATISTICS =============

    async def get_commission_stats(
        self, shop_id: str, cycle_start: datetime, cycle_end: datetime
    ) -> Dict[str, Any]:
        """Get commission statistics for a billing cycle"""
        try:
            query = select(
                func.count(CommissionRecord.id).label("count"),
                func.coalesce(func.sum(CommissionRecord.commission_earned), 0).label(
                    "total_earned"
                ),
                func.coalesce(func.sum(CommissionRecord.commission_charged), 0).label(
                    "total_charged"
                ),
                func.coalesce(func.sum(CommissionRecord.commission_overflow), 0).label(
                    "total_overflow"
                ),
            ).where(
                and_(
                    CommissionRecord.shop_id == shop_id,
                    CommissionRecord.billing_cycle_start == cycle_start,
                    CommissionRecord.billing_cycle_end == cycle_end,
                )
            )

            result = await self.session.execute(query)
            stats = result.one()

            return {
                "count": stats.count,
                "total_earned": float(stats.total_earned),
                "total_charged": float(stats.total_charged),
                "total_overflow": float(stats.total_overflow),
                "charge_rate": (
                    float(stats.total_charged / stats.total_earned * 100)
                    if stats.total_earned > 0
                    else 0
                ),
            }

        except Exception as e:
            logger.error(f"❌ Error getting commission stats: {e}")
            return {
                "count": 0,
                "total_earned": 0,
                "total_charged": 0,
                "total_overflow": 0,
                "charge_rate": 0,
            }

    # ============= PRIVATE HELPERS =============

    async def _get_active_billing_plan(self, shop_id: str) -> Optional[BillingPlan]:
        """Get active billing plan for shop"""
        try:
            query = (
                select(BillingPlan)
                .where(
                    and_(
                        BillingPlan.shop_id == shop_id,
                        BillingPlan.status.in_(["active", "suspended"]),
                    )
                )
                .order_by(BillingPlan.created_at.desc())
            )

            result = await self.session.execute(query)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error(f"❌ Error getting billing plan: {e}")
            return None

    async def _get_cycle_usage(
        self, shop_id: str, cycle_start: datetime, cycle_end: datetime
    ) -> Decimal:
        """
        Get total usage (sum of charged commissions) for a billing cycle.
        Only counts successfully recorded commissions.
        """
        try:
            query = select(
                func.coalesce(func.sum(CommissionRecord.commission_charged), 0)
            ).where(
                and_(
                    CommissionRecord.shop_id == shop_id,
                    CommissionRecord.billing_cycle_start == cycle_start,
                    CommissionRecord.billing_cycle_end == cycle_end,
                    CommissionRecord.status.in_(
                        [
                            CommissionStatus.RECORDED,
                            CommissionStatus.INVOICED,
                        ]
                    ),
                )
            )

            result = await self.session.execute(query)
            return Decimal(str(result.scalar_one()))

        except Exception as e:
            logger.error(f"❌ Error getting cycle usage: {e}")
            return Decimal("0")
