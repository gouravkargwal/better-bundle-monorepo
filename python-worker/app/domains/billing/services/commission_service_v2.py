"""
Commission Service V2

Updated commission service to work with the new redesigned billing system.
Uses unified subscription model instead of separate trial/shopify tables.
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
    SubscriptionType,
    SubscriptionStatus,
)
from ..repositories.billing_repository_v2 import BillingRepositoryV2
from app.repository.CommissionRepository import CommissionRepository
from app.repository.PurchaseAttributionRepository import PurchaseAttributionRepository

logger = logging.getLogger(__name__)


class CommissionServiceV2:
    """Updated service for managing commission records with unified subscription system"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.billing_repository = BillingRepositoryV2(session)
        self.commission_repository = CommissionRepository(session)
        self.purchase_attribution_repository = PurchaseAttributionRepository(session)

    # ============= MAIN CREATION =============

    async def create_commission_record(
        self,
        purchase_attribution_id: str,
        shop_id: str,
    ) -> Optional[CommissionRecord]:
        """Create commission record for a purchase attribution."""
        try:
            existing = await self.commission_repository.get_by_purchase_attribution_id(
                purchase_attribution_id
            )
            if existing:
                return existing
            purchase_attr = await self.purchase_attribution_repository.get_by_id(
                purchase_attribution_id
            )
            shop_subscription = await self.billing_repository.get_shop_subscription(
                shop_id
            )
            logger.info(
                f"💰 Purchase attribution: {purchase_attr}---------------------->"
            )
            logger.info(
                f"💰 Shop subscription: {shop_subscription}---------------------->"
            )
            effective_commission_rate = shop_subscription.effective_commission_rate
            logger.info(
                f"💰 Effective commission rate: {effective_commission_rate}---------------------->"
            )
            total_revenue = purchase_attr.total_revenue
            logger.info(f"💰 Total revenue: {total_revenue}---------------------->")
            commission_data = self._calculate_commission(
                total_revenue, effective_commission_rate
            )
            if commission_data["attributed_revenue"] <= 0:
                logger.info(
                    f"⏭️ Skipping commission creation for attribution {purchase_attribution_id}: "
                    f"no revenue to attribute (${commission_data['attributed_revenue']})"
                )
                return None

            commission = await self._create_commission_by_type(
                shop_id,
                purchase_attribution_id,
                shop_subscription,
                commission_data,
                purchase_attr,
            )

            if commission:
                await self.commission_repository.commit()
                logger.info(
                    f"✅ Created commission: ${commission.commission_earned} "
                    f"({commission.billing_phase.value}, {commission.charge_type.value})"
                )

                # ✅ Publish Kafka event for async Shopify usage recording (PAID commissions only)
                if (
                    commission.billing_phase == BillingPhase.PAID
                    and commission.commission_charged > 0
                    and commission.status == CommissionStatus.PENDING
                ):
                    try:
                        from app.core.messaging.event_publisher import EventPublisher
                        from app.core.config.kafka_settings import kafka_settings

                        event_publisher = EventPublisher(kafka_settings.model_dump())
                        await event_publisher.initialize()

                        await event_publisher.publish_shopify_usage_event(
                            {
                                "event_type": "record_usage",
                                "shop_id": shop_id,
                                "commission_id": commission.id,
                            }
                        )

                        logger.info(
                            f"📤 Published Shopify usage recording event for commission {commission.id}"
                        )
                    except Exception as e:
                        logger.error(
                            f"❌ Failed to publish Shopify usage event for commission {commission.id}: {e}",
                            exc_info=True,
                        )
                        # Don't fail the entire flow - can retry later

            return commission

        except Exception as e:
            logger.error(f"❌ Error creating commission: {e}")
            await self.commission_repository.rollback()
            return None

    # ============= TRIAL COMMISSION =============

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
            # Get current trial revenue from commission records
            current_trial_revenue = (
                await self.billing_repository.calculate_trial_revenue(shop_id)
            )

            # Create commission record
            commission = self._build_trial_commission(
                shop_id,
                purchase_attribution_id,
                purchase_attr,
                attributed_revenue,
                commission_earned,
                commission_rate,
                current_trial_revenue,
                shop_subscription,
            )

            await self.commission_repository.save(commission)

            # Check trial completion using repository method
            await self.billing_repository.check_trial_completion(
                shop_id, current_trial_revenue + attributed_revenue
            )

            return commission

        except Exception as e:
            logger.error(f"❌ Error creating trial commission: {e}")
            return None

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
            capped_amount=shop_subscription.effective_trial_threshold,
            trial_accumulated=trial_accumulated,
            billing_phase=BillingPhase.TRIAL,
            status=CommissionStatus.TRIAL_PENDING,
            charge_type=ChargeType.TRIAL,
            currency=shop_subscription.currency,
        )

    # ============= PAID COMMISSION =============

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

            # Suspend shop if cap is completely reached
            if charge_data["charge_type"] == ChargeType.REJECTED:
                await self._suspend_shop_for_cap_reached(shop_id)

            return commission

        except Exception as e:
            logger.error(f"❌ Error creating paid commission: {e}")
            return None

    def _calculate_charge_amounts(
        self, commission_earned: Decimal, remaining_capacity: Decimal
    ) -> Dict[str, Any]:
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
        charge_data: Dict[str, Any],
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
            currency=shop_subscription.currency,
        )

    async def _suspend_shop_for_cap_reached(self, shop_id: str) -> None:
        """Suspend shop subscription when monthly cap is reached - ATOMIC"""
        try:
            from app.core.database.models.shop_subscription import ShopSubscription
            from app.core.database.models.enums import SubscriptionStatus
            from sqlalchemy import update, and_

            # Get active subscription for this shop
            shop_subscription = await self.billing_repository.get_shop_subscription(
                shop_id
            )
            if not shop_subscription:
                logger.error(f"❌ No active subscription found for shop {shop_id}")
                return

            # Only suspend if subscription is currently ACTIVE
            subscription_update = (
                update(ShopSubscription)
                .where(
                    and_(
                        ShopSubscription.id == shop_subscription.id,
                        ShopSubscription.status
                        == SubscriptionStatus.ACTIVE,  # Only suspend if currently active
                    )
                )
                .values(
                    status=SubscriptionStatus.SUSPENDED,
                    updated_at=now_utc(),
                )
            )

            result = await self.session.execute(subscription_update)

            if result.rowcount > 0:
                logger.warning(
                    f"🛑 Shop subscription {shop_subscription.id} suspended due to monthly cap reached for shop {shop_id}"
                )
            else:
                logger.debug(
                    f"Shop subscription {shop_subscription.id} was already suspended or not found"
                )

        except Exception as e:
            logger.error(
                f"❌ Error suspending shop subscription for shop {shop_id}: {e}"
            )
            raise

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

            # Get subscription for Shopify integration info
            shop_subscription = (
                await self.billing_repository.get_shop_subscription_by_id(
                    billing_cycle.shop_subscription_id
                )
            )
            if not shop_subscription:
                logger.error(f"❌ Shop subscription not found")
                return {"success": False, "error": "subscription_not_found"}

            # Check if we have charge amount
            if commission.commission_charged <= 0:
                logger.warning(f"⚠️ Commission has no charge amount: {commission_id}")
                return {"success": False, "error": "no_charge_amount"}

            # Check if we have Shopify line item ID
            if not shop_subscription.shopify_line_item_id:
                logger.error(f"❌ No Shopify line item ID found")
                return {"success": False, "error": "no_shopify_line_item"}

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

            cap_exceeded_error = False
            for attempt in range(1, max_retries + 1):
                usage_record_result = await shopify_billing_service.record_usage(
                    shop_id=shop.id,
                    shop_domain=shop.shop_domain,
                    access_token=shop.access_token,
                    subscription_line_item_id=shop_subscription.shopify_line_item_id,
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

                # Check if Shopify returned an error (cap exceeded or other)
                if isinstance(usage_record_result, dict) and usage_record_result.get(
                    "error"
                ):
                    if usage_record_result.get("cap_exceeded"):
                        # Cap exceeded - don't retry, handle it immediately
                        cap_exceeded_error = True
                        last_error_message = "Capped amount exceeded"
                        logger.error(
                            f"❌ Shopify rejected usage record due to cap exceeded: {usage_record_result.get('user_errors')}"
                        )
                        break
                    else:
                        # Other user error - log and retry
                        last_error_message = f"Shopify user errors: {usage_record_result.get('user_errors')}"
                        logger.warning(
                            f"Shopify returned user errors (attempt {attempt}/{max_retries}): {last_error_message}"
                        )
                        if attempt < max_retries:
                            sleep_seconds = backoff_base_seconds * (2 ** (attempt - 1))
                            await asyncio.sleep(sleep_seconds)
                        continue
                elif usage_record_result:
                    # Success - got a UsageRecord
                    usage_record = usage_record_result
                    break
                else:
                    # No result (None) - retry
                    last_error_message = "Failed to create Shopify usage record"
                    if attempt < max_retries:
                        sleep_seconds = backoff_base_seconds * (2 ** (attempt - 1))
                        logger.warning(
                            f"Retry {attempt}/{max_retries} after failure recording to Shopify; sleeping {sleep_seconds:.2f}s"
                        )
                        await asyncio.sleep(sleep_seconds)

            # Handle cap exceeded error from Shopify
            if cap_exceeded_error:
                # Mark commission as REJECTED and update overflow
                commission.commission_overflow = (
                    commission.commission_overflow + commission.commission_charged
                )
                commission.commission_charged = Decimal("0")
                commission.charge_type = ChargeType.REJECTED
                commission.status = CommissionStatus.REJECTED
                commission.updated_at = now_utc()

                await self.commission_repository.commit()

                # Suspend subscription since we can't accumulate negative
                await self._suspend_shop_for_cap_reached(commission.shop_id)

                logger.warning(
                    f"🛑 Commission {commission_id} rejected by Shopify due to cap exceeded. "
                    f"Shop subscription suspended for shop {commission.shop_id}"
                )

                return {
                    "success": False,
                    "error": "cap_exceeded",
                    "error_message": "Capped amount exceeded - Shopify rejected usage record",
                    "commission_rejected": True,
                }

            # Check if we still don't have a usage record (other errors)
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
            all_commissions = await self.commission_repository.get_all(limit * 10)

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

    # ============= HELPER METHODS =============

    def _calculate_commission(
        self, total_revenue: Decimal, effective_commission_rate: Decimal
    ) -> Dict[str, Decimal]:
        """Calculate commission data using subscription's pricing tier."""

        commission_earned = total_revenue * effective_commission_rate

        return {
            "attributed_revenue": total_revenue,
            "commission_rate": effective_commission_rate,
            "commission_earned": commission_earned,
        }

    async def _create_commission_by_type(
        self,
        shop_id: str,
        purchase_attribution_id: str,
        shop_subscription: ShopSubscription,
        commission_data: Dict[str, Decimal],
        purchase_attr: PurchaseAttribution,
    ) -> Optional[CommissionRecord]:
        """Create commission based on subscription type and status."""

        if (
            shop_subscription.subscription_type == SubscriptionType.TRIAL
            and shop_subscription.status == SubscriptionStatus.TRIAL
        ):
            return await self._create_trial_commission(
                shop_id,
                purchase_attribution_id,
                shop_subscription,
                commission_data["attributed_revenue"],
                commission_data["commission_earned"],
                commission_data["commission_rate"],
                purchase_attr,
            )
        elif (
            shop_subscription.subscription_type == SubscriptionType.PAID
            and shop_subscription.status == SubscriptionStatus.ACTIVE
        ):
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
                f"⚠️ Shop {shop_id} type: {shop_subscription.subscription_type.value}, "
                f"status: {shop_subscription.status.value} - not processing commission"
            )
            return None
