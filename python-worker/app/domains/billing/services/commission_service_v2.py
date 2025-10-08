"""
Commission Service V2

Updated commission service to work with the new redesigned billing system.
Uses billing_cycles instead of calculating cycles on-the-fly.
"""

import logging
import asyncio
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.models import (
    CommissionRecord,
    ShopSubscription,
    BillingCycle,
    PurchaseAttribution,
)
from app.shared.helpers import now_utc
from app.core.database.models.enums import (
    BillingPhase,
    CommissionStatus,
    ChargeType,
    SubscriptionStatus,
)
from ..repositories.billing_repository_v2 import BillingRepositoryV2
from app.repository.CommissionRepository import CommissionRepository
from app.repository.PurchaseAttributionRepository import PurchaseAttributionRepository

logger = logging.getLogger(__name__)


class CommissionServiceV2:
    """Updated service for managing commission records with new billing system"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.billing_repository = BillingRepositoryV2(session)
        self.commission_repository = CommissionRepository(session)
        self.purchase_attribution_repository = PurchaseAttributionRepository(session)

    # ============= CREATION =============

    async def create_commission_record(
        self,
        purchase_attribution_id: str,
        shop_id: str,
    ) -> Optional[CommissionRecord]:
        """Create commission record for a purchase attribution."""
        try:
            # Check if already exists
            existing = await self._get_existing_commission(purchase_attribution_id)
            if existing:
                return existing

            # Get required data
            purchase_attr = await self._get_purchase_attribution(
                purchase_attribution_id
            )
            if not purchase_attr:
                return None

            shop_subscription = await self.billing_repository.get_shop_subscription(
                shop_id
            )
            if not shop_subscription:
                logger.error(f"❌ No subscription for shop {shop_id}")
                return None

            # Calculate commission
            commission_data = self._calculate_commission(purchase_attr)

            # Create commission based on subscription status
            commission = await self._create_commission_by_status(
                shop_id,
                purchase_attribution_id,
                shop_subscription,
                commission_data,
                purchase_attr,
            )

            if commission:
                await self.commission_repository.commit()
                logger.info(
                    f"✅ Created commission: ${commission.commission_earned} ({commission.billing_phase.value})"
                )

            return commission

        except Exception as e:
            logger.error(f"❌ Error creating commission: {e}")
            await self.commission_repository.rollback()
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
        """Create commission record for trial phase."""
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

            # Get trial accumulated revenue
            trial_accumulated = await self._get_trial_accumulated_revenue(shop_id)

            # Create commission record
            commission = self._build_trial_commission(
                shop_id,
                purchase_attribution_id,
                purchase_attr,
                attributed_revenue,
                commission_earned,
                commission_rate,
                trial_accumulated,
                shop_subscription,
            )

            await self.commission_repository.save(commission)

            # Update trial revenue
            await self.billing_repository.update_trial_revenue(
                shop_subscription.id, attributed_revenue
            )

            return commission

        except Exception as e:
            logger.error(f"❌ Error creating trial commission: {e}")
            return None

    async def _get_trial_accumulated_revenue(self, shop_id: str) -> Decimal:
        """Get total trial revenue for shop."""
        try:
            return await self.purchase_attribution_repository.get_total_revenue_by_shop(
                shop_id
            )
        except Exception as e:
            logger.error(f"Error getting trial accumulated revenue: {e}")
            return Decimal("0")

    def _build_trial_commission(
        self,
        shop_id: str,
        purchase_attribution_id: str,
        purchase_attr: PurchaseAttribution,
        attributed_revenue: Decimal,
        commission_earned: Decimal,
        commission_rate: Decimal,
        trial_accumulated: Decimal,
        shop_subscription: ShopSubscription,
    ) -> CommissionRecord:
        """Build trial commission record."""
        return CommissionRecord(
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
        """Create commission record for paid phase."""
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

            # Check cap and calculate charges
            charge_data = self._calculate_charge_amounts(
                commission_earned, current_cycle.remaining_cap
            )

            # Create commission record
            commission = self._build_paid_commission(
                shop_id,
                purchase_attribution_id,
                purchase_attr,
                attributed_revenue,
                commission_earned,
                commission_rate,
                charge_data,
                current_cycle,
                shop_subscription,
            )

            await self.commission_repository.save(commission)

            # Update billing cycle usage
            await self.billing_repository.update_billing_cycle_usage(
                current_cycle.id, charge_data["actual_charge"]
            )

            return commission

        except Exception as e:
            logger.error(f"❌ Error creating paid commission: {e}")
            return None

    def _calculate_charge_amounts(
        self, commission_earned: Decimal, remaining_capacity: Decimal
    ) -> Dict[str, Decimal]:
        """Calculate charge amounts based on cap."""
        if remaining_capacity <= 0:
            return {
                "actual_charge": Decimal("0"),
                "overflow": commission_earned,
                "charge_type": ChargeType.REJECTED,
            }

        actual_charge = min(commission_earned, remaining_capacity)
        overflow = commission_earned - actual_charge

        charge_type = ChargeType.PARTIAL if overflow > 0 else ChargeType.FULL

        if overflow > 0:
            logger.warning(
                f"⚠️ Partial charge due to cap: ${actual_charge} charged, ${overflow} overflow"
            )

        return {
            "actual_charge": actual_charge,
            "overflow": overflow,
            "charge_type": charge_type,
        }

    def _build_paid_commission(
        self,
        shop_id: str,
        purchase_attribution_id: str,
        purchase_attr: PurchaseAttribution,
        attributed_revenue: Decimal,
        commission_earned: Decimal,
        commission_rate: Decimal,
        charge_data: Dict[str, Decimal],
        current_cycle: BillingCycle,
        shop_subscription: ShopSubscription,
    ) -> CommissionRecord:
        """Build paid commission record."""
        return CommissionRecord(
            shop_id=shop_id,
            purchase_attribution_id=purchase_attribution_id,
            billing_cycle_id=current_cycle.id,
            order_id=str(purchase_attr.order_id),
            order_date=purchase_attr.purchase_at,
            attributed_revenue=attributed_revenue,
            commission_rate=commission_rate,
            commission_earned=commission_earned,
            commission_charged=charge_data["actual_charge"],
            commission_overflow=charge_data["overflow"],
            billing_cycle_start=current_cycle.start_date,
            billing_cycle_end=current_cycle.end_date,
            cycle_usage_before=current_cycle.usage_amount,
            cycle_usage_after=current_cycle.usage_amount + charge_data["actual_charge"],
            capped_amount=current_cycle.current_cap_amount,
            trial_accumulated=Decimal("0"),  # Not in trial
            billing_phase=BillingPhase.PAID,
            status=CommissionStatus.PENDING,
            charge_type=charge_data["charge_type"],
            currency=(
                shop_subscription.pricing_tier.currency
                if shop_subscription.pricing_tier
                else "USD"
            ),
        )

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

            await self.commission_repository.save(commission)

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
            commission = await self.commission_repository.get_by_id(commission_id)

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
                await self.commission_repository.rollback()
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

            await self.commission_repository.commit()

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
            await self.commission_repository.rollback()
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
            # Use repository method for basic query
            commissions = await self.commission_repository.get_by_shop(shop_id, limit)

            # Apply additional filters if needed
            if billing_phase:
                commissions = [
                    c for c in commissions if c.billing_phase == billing_phase
                ]

            if status:
                commissions = [c for c in commissions if c.status == status]

            return commissions

        except Exception as e:
            logger.error(f"❌ Error getting commissions: {e}")
            return []

    async def get_pending_commissions(self, limit: int = 100) -> List[CommissionRecord]:
        """Get all pending commissions that need to be recorded to Shopify"""
        try:
            # Get all commissions and filter for pending ones
            all_commissions = await self.commission_repository.get_all(
                limit * 10
            )  # Get more to filter

            pending_commissions = [
                c
                for c in all_commissions
                if (
                    c.status == CommissionStatus.PENDING
                    and c.billing_phase == BillingPhase.PAID
                    and c.shopify_usage_record_id is None
                )
            ]

            # Sort by created_at and limit
            pending_commissions.sort(key=lambda x: x.created_at)
            return pending_commissions[:limit]

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

    # ============= TRIAL THRESHOLD CHECK =============

    async def handle_trial_threshold_check(self, shop_id: str) -> Dict[str, Any]:
        """
        Check if trial threshold has been reached for a shop.

        Args:
            shop_id: Shop ID to check

        Returns:
            Dictionary with threshold status information
        """
        try:
            # Get shop subscription
            shop_subscription = await self.billing_repository.get_shop_subscription(
                shop_id
            )
            if not shop_subscription:
                return {
                    "threshold_reached": False,
                    "total_trial_revenue": 0,
                    "trial_threshold": 0,
                    "error": "No subscription found",
                }

            # Get trial information
            trial = await self.billing_repository.get_subscription_trial(
                shop_subscription.id
            )
            if not trial:
                return {
                    "threshold_reached": False,
                    "total_trial_revenue": 0,
                    "trial_threshold": 0,
                    "error": "No trial found",
                }

            # Get current trial revenue from purchase attributions
            revenue_query = select(
                func.coalesce(func.sum(PurchaseAttribution.total_revenue), 0)
            ).where(PurchaseAttribution.shop_id == shop_id)

            revenue_result = await self.session.execute(revenue_query)
            total_trial_revenue = Decimal(str(revenue_result.scalar_one()))

            # Check if threshold reached
            threshold_reached = total_trial_revenue >= trial.threshold_amount

            return {
                "threshold_reached": threshold_reached,
                "total_trial_revenue": float(total_trial_revenue),
                "trial_threshold": float(trial.threshold_amount),
                "remaining_revenue": float(
                    max(Decimal("0"), trial.threshold_amount - total_trial_revenue)
                ),
                "trial_status": trial.status.value,
            }

        except Exception as e:
            logger.error(f"❌ Error checking trial threshold: {e}")
            return {
                "threshold_reached": False,
                "total_trial_revenue": 0,
                "trial_threshold": 0,
                "error": str(e),
            }

    # ============= HELPER METHODS =============

    async def _get_existing_commission(
        self, purchase_attribution_id: str
    ) -> Optional[CommissionRecord]:
        """Get existing commission if it exists."""
        try:
            existing = await self.commission_repository.get_by_purchase_attribution_id(
                purchase_attribution_id
            )

            if existing:
                logger.info(
                    f"✅ Commission already exists for purchase {purchase_attribution_id}"
                )

            return existing
        except Exception as e:
            logger.error(f"Error getting existing commission: {e}")
            return None

    async def _get_purchase_attribution(
        self, purchase_attribution_id: str
    ) -> Optional[PurchaseAttribution]:
        """Get purchase attribution by ID."""
        try:
            purchase_attr = await self.purchase_attribution_repository.get_by_id(
                purchase_attribution_id
            )

            if not purchase_attr:
                logger.error(
                    f"❌ Purchase attribution {purchase_attribution_id} not found"
                )

            return purchase_attr
        except Exception as e:
            logger.error(f"Error getting purchase attribution: {e}")
            return None

    def _calculate_commission(
        self, purchase_attr: PurchaseAttribution
    ) -> Dict[str, Decimal]:
        """Calculate commission data."""
        attributed_revenue = Decimal(str(purchase_attr.total_revenue))
        commission_rate = Decimal("0.03")  # 3%
        commission_earned = attributed_revenue * commission_rate

        return {
            "attributed_revenue": attributed_revenue,
            "commission_rate": commission_rate,
            "commission_earned": commission_earned,
        }

    async def _create_commission_by_status(
        self,
        shop_id: str,
        purchase_attribution_id: str,
        shop_subscription: ShopSubscription,
        commission_data: Dict[str, Decimal],
        purchase_attr: PurchaseAttribution,
    ) -> Optional[CommissionRecord]:
        """Create commission based on subscription status."""
        if shop_subscription.status == SubscriptionStatus.TRIAL:
            return await self._create_trial_commission(
                shop_id,
                purchase_attribution_id,
                shop_subscription,
                commission_data["attributed_revenue"],
                commission_data["commission_earned"],
                commission_data["commission_rate"],
                purchase_attr,
            )
        elif shop_subscription.status == SubscriptionStatus.ACTIVE:
            return await self._create_paid_commission(
                shop_id,
                purchase_attribution_id,
                shop_subscription,
                commission_data["attributed_revenue"],
                commission_data["commission_earned"],
                commission_data["commission_rate"],
                purchase_attr,
            )
        else:
            logger.warning(
                f"⚠️ Shop {shop_id} status is {shop_subscription.status.value}, not processing commission"
            )
            return None
