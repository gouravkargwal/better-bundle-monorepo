"""
Commission Service V2

Updated commission service to work with the new redesigned billing system.
Uses billing_cycles instead of calculating cycles on-the-fly.
"""

import logging
import asyncio
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy import select, func, and_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.models import (
    CommissionRecord,
    ShopSubscription,
    BillingCycle,
    SubscriptionTrial,
    Shop,
    PurchaseAttribution,
)
from app.shared.helpers import now_utc
from app.core.database.models.enums import (
    BillingPhase,
    CommissionStatus,
    ChargeType,
    SubscriptionStatus,
    BillingCycleStatus,
    TrialStatus,
)
from ..repositories.billing_repository_v2 import BillingRepositoryV2
from .billing_cycle_manager import BillingCycleManager

logger = logging.getLogger(__name__)


class CommissionServiceV2:
    """Updated service for managing commission records with new billing system"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.billing_repository = BillingRepositoryV2(session)
        self.cycle_manager = BillingCycleManager(session)

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
                    f"✅ Commission already exists for purchase {purchase_attribution_id} "
                    f"(id: {existing.id}, status: {existing.status.value})"
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

            # Get shop subscription
            shop_subscription = await self.billing_repository.get_shop_subscription(
                shop_id
            )
            if not shop_subscription:
                logger.error(f"❌ No active subscription for shop {shop_id}")
                return None

            # Get shop details
            shop = await self.billing_repository.get_shop(shop_id)
            if not shop:
                logger.error(f"❌ Shop {shop_id} not found")
                return None

            # Calculate commission using Decimals only
            attributed_revenue = Decimal(str(purchase_attr.total_revenue))
            commission_rate = Decimal("0.03")  # 3%
            commission_earned = attributed_revenue * commission_rate

            # Determine billing phase and create commission record
            if shop_subscription.status == SubscriptionStatus.TRIAL:
                # TRIAL PHASE
                commission = await self._create_trial_commission(
                    shop_id,
                    purchase_attribution_id,
                    shop_subscription,
                    attributed_revenue,
                    commission_earned,
                    commission_rate,
                    purchase_attr,
                )
            elif shop_subscription.status == SubscriptionStatus.ACTIVE:
                # PAID PHASE
                commission = await self._create_paid_commission(
                    shop_id,
                    purchase_attribution_id,
                    shop_subscription,
                    attributed_revenue,
                    commission_earned,
                    commission_rate,
                    purchase_attr,
                )
            else:
                logger.warning(
                    f"⚠️ Shop {shop_id} subscription status is {shop_subscription.status.value}, not processing commission"
                )
                return None

            if commission:
                await self.session.commit()
                logger.info(
                    f"✅ Created commission record: ${commission.commission_earned} (phase={commission.billing_phase.value})"
                )

            return commission

        except Exception as e:
            logger.error(f"❌ Error creating commission record: {e}")
            await self.session.rollback()
            return None

    async def _create_trial_commission(
        self,
        shop_id: str,
        purchase_attribution_id: str,
        shop_subscription: ShopSubscription,
        attributed_revenue: Decimal,
        commission_earned: Decimal,
        commission_rate: Decimal,
        purchase_attr: PurchaseAttribution,
    ) -> Optional[CommissionRecord]:
        """Create commission record for trial phase"""
        try:
            # Get trial info
            trial = await self.billing_repository.get_subscription_trial(
                shop_subscription.id
            )
            if not trial:
                logger.error(
                    f"❌ No trial found for subscription {shop_subscription.id}"
                )
                return None

            # Calculate trial accumulated revenue
            trial_revenue_query = select(
                func.coalesce(func.sum(PurchaseAttribution.total_revenue), 0)
            ).where(PurchaseAttribution.shop_id == shop_id)

            trial_revenue_result = await self.session.execute(trial_revenue_query)
            trial_accumulated = Decimal(str(trial_revenue_result.scalar_one()))

            # Create commission record
            commission = CommissionRecord(
                shop_id=shop_id,
                purchase_attribution_id=purchase_attribution_id,
                billing_cycle_id=None,  # No billing cycle during trial
                order_id=str(purchase_attr.order_id),
                order_date=purchase_attr.purchase_at,
                attributed_revenue=attributed_revenue,
                commission_rate=commission_rate,
                commission_earned=commission_earned,
                commission_charged=Decimal("0"),  # Not charged during trial
                commission_overflow=Decimal("0"),
                billing_cycle_start=None,
                billing_cycle_end=None,
                cycle_usage_before=Decimal("0"),
                cycle_usage_after=Decimal("0"),
                capped_amount=Decimal("0"),  # No cap during trial
                trial_accumulated=trial_accumulated,
                billing_phase=BillingPhase.TRIAL,
                status=CommissionStatus.TRIAL_PENDING,
                charge_type=ChargeType.TRIAL,
                currency=(
                    shop_subscription.pricing_tier.currency
                    if shop_subscription.pricing_tier
                    else "USD"
                ),
            )

            self.session.add(commission)
            await self.session.flush()

            # Update trial revenue
            await self.billing_repository.update_trial_revenue(
                shop_subscription.id, attributed_revenue
            )

            return commission

        except Exception as e:
            logger.error(f"❌ Error creating trial commission: {e}")
            return None

    async def _create_paid_commission(
        self,
        shop_id: str,
        purchase_attribution_id: str,
        shop_subscription: ShopSubscription,
        attributed_revenue: Decimal,
        commission_earned: Decimal,
        commission_rate: Decimal,
        purchase_attr: PurchaseAttribution,
    ) -> Optional[CommissionRecord]:
        """Create commission record for paid phase"""
        try:
            # Get current billing cycle
            current_cycle = await self.billing_repository.get_current_billing_cycle(
                shop_subscription.id
            )
            if not current_cycle:
                logger.error(
                    f"❌ No active billing cycle for subscription {shop_subscription.id}"
                )
                return None

            # Check if cap is reached
            remaining_capacity = current_cycle.remaining_cap
            if remaining_capacity <= 0:
                logger.warning(
                    f"⚠️ Cap reached for shop {shop_id}, commission will be rejected"
                )
                return await self._create_rejected_commission(
                    shop_id,
                    purchase_attribution_id,
                    current_cycle,
                    attributed_revenue,
                    commission_earned,
                    commission_rate,
                    purchase_attr,
                )

            # Calculate actual charge (handle partial charge if needed)
            actual_charge = min(commission_earned, remaining_capacity)
            overflow = commission_earned - actual_charge

            # Determine charge type
            if overflow > 0:
                charge_type = ChargeType.PARTIAL
                logger.warning(
                    f"⚠️ Partial charge due to cap: ${actual_charge} charged, ${overflow} overflow"
                )
            else:
                charge_type = ChargeType.FULL

            # Create commission record
            commission = CommissionRecord(
                shop_id=shop_id,
                purchase_attribution_id=purchase_attribution_id,
                billing_cycle_id=current_cycle.id,
                order_id=str(purchase_attr.order_id),
                order_date=purchase_attr.purchase_at,
                attributed_revenue=attributed_revenue,
                commission_rate=commission_rate,
                commission_earned=commission_earned,
                commission_charged=actual_charge,
                commission_overflow=overflow,
                billing_cycle_start=current_cycle.start_date,
                billing_cycle_end=current_cycle.end_date,
                cycle_usage_before=current_cycle.usage_amount,
                cycle_usage_after=current_cycle.usage_amount + actual_charge,
                capped_amount=current_cycle.current_cap_amount,
                trial_accumulated=Decimal("0"),  # Not in trial
                billing_phase=BillingPhase.PAID,
                status=CommissionStatus.PENDING,
                charge_type=charge_type,
                currency=(
                    shop_subscription.pricing_tier.currency
                    if shop_subscription.pricing_tier
                    else "USD"
                ),
            )

            self.session.add(commission)
            await self.session.flush()

            # Update billing cycle usage
            await self.billing_repository.update_billing_cycle_usage(
                current_cycle.id, actual_charge
            )

            return commission

        except Exception as e:
            logger.error(f"❌ Error creating paid commission: {e}")
            return None

    async def _create_rejected_commission(
        self,
        shop_id: str,
        purchase_attribution_id: str,
        current_cycle: BillingCycle,
        attributed_revenue: Decimal,
        commission_earned: Decimal,
        commission_rate: Decimal,
        purchase_attr: PurchaseAttribution,
    ) -> Optional[CommissionRecord]:
        """Create rejected commission when cap is reached"""
        try:
            commission = CommissionRecord(
                shop_id=shop_id,
                purchase_attribution_id=purchase_attribution_id,
                billing_plan_id=None,
                billing_cycle_id=current_cycle.id,
                order_id=str(purchase_attr.order_id),
                order_date=purchase_attr.purchase_at,
                attributed_revenue=attributed_revenue,
                commission_rate=commission_rate,
                commission_earned=commission_earned,
                commission_charged=Decimal("0"),
                commission_overflow=commission_earned,
                billing_cycle_start=current_cycle.start_date,
                billing_cycle_end=current_cycle.end_date,
                cycle_usage_before=current_cycle.usage_amount,
                cycle_usage_after=current_cycle.usage_amount,
                capped_amount=current_cycle.current_cap_amount,
                trial_accumulated=Decimal("0"),
                billing_phase=BillingPhase.PAID,
                status=CommissionStatus.REJECTED,
                charge_type=ChargeType.REJECTED,
                currency="USD",  # Default currency
                notes="Cap reached before this commission",
            )

            self.session.add(commission)
            await self.session.flush()

            return commission

        except Exception as e:
            logger.error(f"❌ Error creating rejected commission: {e}")
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
        commission = None
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

            # Get shop and billing cycle
            shop = await self.billing_repository.get_shop(commission.shop_id)
            if not shop:
                logger.error(f"❌ Shop not found")
                return {"success": False, "error": "shop_not_found"}

            # Get billing cycle
            billing_cycle = await self.billing_repository.get_billing_cycle_by_id(
                commission.billing_cycle_id
            )
            if not billing_cycle:
                logger.error(f"❌ Billing cycle not found")
                return {"success": False, "error": "billing_cycle_not_found"}

            # Check if cap already reached
            if commission.commission_charged <= 0:
                logger.warning(f"⚠️ Commission has no charge amount: {commission_id}")
                return {"success": False, "error": "no_charge_amount"}

            # Generate idempotency key
            idempotency_key = (
                f"{commission.shop_id}-{commission.id}-{commission.order_id}"
            )

            # Record to Shopify with retry and backoff
            logger.info(f"📤 Recording ${commission.commission_charged} to Shopify...")

            max_retries = 3
            backoff_base_seconds = 0.5
            usage_record = None
            last_error_message = None

            for attempt in range(1, max_retries + 1):
                usage_record = await shopify_billing_service.record_usage(
                    shop_id=shop.id,
                    shop_domain=shop.shop_domain,
                    access_token=shop.access_token,
                    subscription_line_item_id=billing_cycle.shop_subscription.shopify_subscription.shopify_line_item_id,
                    description=f"Better Bundle - Order {commission.order_id}",
                    amount=commission.commission_charged,
                    currency=commission.currency,
                    idempotency_key=idempotency_key,
                    commission_ids=[commission.id],
                    billing_period={
                        "start": (
                            commission.billing_cycle_start.isoformat()
                            if commission.billing_cycle_start
                            else None
                        ),
                        "end": (
                            commission.billing_cycle_end.isoformat()
                            if commission.billing_cycle_end
                            else None
                        ),
                    },
                )
                if usage_record:
                    break
                last_error_message = "Failed to create Shopify usage record"
                sleep_seconds = backoff_base_seconds * (2 ** (attempt - 1))
                logger.warning(
                    f"Retry {attempt}/{max_retries} after failure recording to Shopify; sleeping {sleep_seconds:.2f}s"
                )
                await asyncio.sleep(sleep_seconds)

            if not usage_record:
                logger.error("❌ Failed to record to Shopify after retries")
                await self.session.rollback()
                return {
                    "success": False,
                    "error": "shopify_api_failed",
                    "error_message": last_error_message,
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
                "idempotency_key": idempotency_key,
            }
            commission.status = CommissionStatus.RECORDED
            commission.updated_at = now_utc()

            await self.session.flush()
            await self.session.commit()

            logger.info(
                f"✅ Recorded commission to Shopify: {usage_record.id} (${commission.commission_charged} charged)"
            )

            return {
                "success": True,
                "shopify_usage_record_id": usage_record.id,
                "commission_charged": float(commission.commission_charged),
                "commission_overflow": float(commission.commission_overflow),
                "charge_type": commission.charge_type.value,
            }

        except Exception as e:
            logger.error(f"❌ Error recording to Shopify: {e}")
            await self.session.rollback()
            return {"success": False, "error": str(e)}

    # ============= QUERY METHODS =============

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

    # ============= STATISTICS =============

    async def get_commission_stats_for_cycle(
        self, billing_cycle_id: str
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
            ).where(CommissionRecord.billing_cycle_id == billing_cycle_id)

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
