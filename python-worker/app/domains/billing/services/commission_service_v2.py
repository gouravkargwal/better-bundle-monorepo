import logging
import asyncio
from datetime import datetime
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
from app.core.database.models.order_data import OrderData
from app.core.database.models.shop import Shop
from .fx import convert_to_usd
from ..repositories.billing_repository_v2 import BillingRepositoryV2
from app.repository.CommissionRepository import CommissionRepository
from app.repository.PurchaseAttributionRepository import PurchaseAttributionRepository
from app.core.messaging.event_publisher import EventPublisher
from app.core.config.kafka_settings import kafka_settings
from app.core.database.models.shop_subscription import ShopSubscription
from app.core.database.models.enums import SubscriptionStatus
from sqlalchemy import update, and_

logger = logging.getLogger(__name__)


class CommissionServiceV2:
    """Updated service for managing commission records with unified subscription system"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.billing_repository = BillingRepositoryV2(session)
        self.commission_repository = CommissionRepository(session)
        self.purchase_attribution_repository = PurchaseAttributionRepository(session)

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

            effective_commission_rate = shop_subscription.effective_commission_rate

            # Attributed revenue is measured in whatever the shopper paid in;
            # every amount from here down is USD, because that is what the
            # Shopify subscription is pinned to. Converting at this single choke
            # point covers the trial and paid paths alike.
            order_currency = await self._get_order_currency(
                shop_id, str(purchase_attr.order_id)
            )
            converted = await convert_to_usd(
                self.session,
                Decimal(str(purchase_attr.total_revenue)),
                order_currency,
            )
            if converted is None:
                logger.error(
                    f"❌ Cannot bill attribution {purchase_attribution_id}: no "
                    f"usable USD rate for {order_currency}. Commission not "
                    f"created — it will be picked up once rates refresh."
                )
                return None

            total_revenue = converted.amount
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
                # Record what priced this charge. Stored, not re-derived: a
                # later rate refresh must not restate an invoice the merchant
                # has already paid, and a billing dispute needs an answer.
                commission.source_currency = converted.source_currency
                commission.fx_rate = converted.rate

                await self.commission_repository.commit()
                logger.info(
                    f"✅ Created commission: ${commission.commission_earned} "
                    f"({commission.billing_phase.value}, {commission.charge_type.value})"
                )

                # ✅ Publish Kafka event for async Shopify usage recording (PAID commissions only)
                # Skip publishing if shop subscription is SUSPENDED — the rollover reconciler drains it on reactivation
                if (
                    commission.billing_phase == BillingPhase.PAID
                    and commission.commission_charged > 0
                    and commission.status == CommissionStatus.PENDING
                    and shop_subscription.status == SubscriptionStatus.ACTIVE
                ):
                    try:

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

    async def _get_order_currency(self, shop_id: str, order_id: str) -> Optional[str]:
        """The currency the attributed revenue is denominated in.

        Presentment, not shop currency: `offer_impressions.revenue_added` is the
        price the extension *displayed* to the shopper, which on a Markets store
        is their local currency rather than the merchant's. One order has one
        presentment currency, so this is consistent at the scope that matters.

        Falls back to the shop's own currency when the order cannot be found —
        better than assuming USD, which is what silently over-billed every
        non-USD merchant.
        """
        row = (
            await self.session.execute(
                select(
                    OrderData.presentment_currency_code,
                    OrderData.currency_code,
                ).where(
                    and_(
                        OrderData.shop_id == shop_id,
                        OrderData.order_id == order_id,
                    )
                )
            )
        ).first()

        if row:
            return row.presentment_currency_code or row.currency_code

        shop_currency = (
            await self.session.execute(
                select(Shop.currency_code).where(Shop.id == shop_id)
            )
        ).scalar_one_or_none()
        logger.warning(
            f"💱 Order {order_id} not found for currency lookup; falling back to "
            f"shop currency {shop_currency}"
        )
        return shop_currency

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
            # Create commission record statelessly
            commission = self._build_paid_commission(
                shop_id,
                purchase_attribution_id,
                purchase_attr,
                attributed_revenue,
                commission_earned,
                commission_rate,
                shop_subscription,
            )

            await self.commission_repository.save(commission)

            return commission

        except Exception as e:
            logger.error(f"❌ Error creating paid commission: {e}")
            return None

    def _build_paid_commission(
        self,
        shop_id: str,
        purchase_attribution_id: str,
        purchase_attr: PurchaseAttribution,
        attributed_revenue: Decimal,
        commission_earned: Decimal,
        commission_rate: Decimal,
        shop_subscription: ShopSubscription,
    ) -> CommissionRecord:
        """Build paid commission record statelessly (Shopify handles caps and cycles)."""
        return CommissionRecord(
            shop_id=shop_id,
            purchase_attribution_id=purchase_attribution_id,
            billing_cycle_id=None,
            order_id=str(purchase_attr.order_id),
            order_date=purchase_attr.purchase_at,
            attributed_revenue=attributed_revenue,
            commission_rate=commission_rate,
            commission_earned=commission_earned,
            commission_charged=commission_earned,
            commission_overflow=Decimal("0"),
            billing_cycle_start=None,
            billing_cycle_end=None,
            cycle_usage_before=Decimal("0"),
            cycle_usage_after=Decimal("0"),
            capped_amount=None,
            trial_accumulated=Decimal("0"),  # Not in trial
            billing_phase=BillingPhase.PAID,
            status=CommissionStatus.PENDING,
            charge_type=ChargeType.FULL,
            currency=shop_subscription.currency,
        )

    async def _suspend_shop_for_cap_reached(
        self, shop_id: str, balance_used: Optional[Decimal] = None
    ) -> None:
        """Suspend shop subscription when monthly cap is reached - ATOMIC"""
        try:

            # Get active subscription for this shop
            shop_subscription = await self.billing_repository.get_shop_subscription(
                shop_id
            )
            if not shop_subscription:
                logger.error(f"❌ No active subscription found for shop {shop_id}")
                return

            metadata = dict(shop_subscription.shop_subscription_metadata or {})
            if balance_used is not None:
                metadata["suspended_balance_used"] = float(balance_used)
            metadata["suspended_at"] = now_utc().isoformat()

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
                    shop_subscription_metadata=metadata,
                    updated_at=now_utc(),
                )
            )

            result = await self.session.execute(subscription_update)

            if result.rowcount > 0:
                logger.warning(
                    f"🛑 Shop subscription {shop_subscription.id} suspended due to monthly cap reached for shop {shop_id} "
                    f"(suspended_balance_used={metadata.get('suspended_balance_used')})"
                )
                # Write to suspension_audit_log
                try:
                    from app.core.database.models.suspension_audit_log import (
                        SuspensionAuditLog,
                    )
                    import json

                    audit_entry = SuspensionAuditLog(
                        shop_id=shop_id,
                        action="SUSPENDED",
                        reason=f"Monthly usage cap reached (Shopify balance: {metadata.get('suspended_balance_used')})",
                        triggered_by="system",
                        metadata_json=json.dumps(metadata),
                    )
                    self.session.add(audit_entry)
                except Exception as audit_err:
                    logger.warning(
                        f"Failed to write suspension audit log for shop {shop_id}: {audit_err}"
                    )

                # Invalidate Redis suspension cache
                try:
                    from app.core.redis_client import get_redis_client

                    redis = await get_redis_client()
                    await redis.delete(f"suspension:{shop_id}")
                except Exception as cache_err:
                    logger.debug(
                        f"Could not invalidate redis cache for {shop_id}: {cache_err}"
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

    async def record_commission_to_shopify(
        self, commission_id: str, shopify_billing_service
    ) -> Dict[str, Any]:
        commission = None
        try:
            # Get commission record
            commission = await self.commission_repository.get_by_id(commission_id)
            if not commission:
                logger.error(f"❌ Commission {commission_id} not found")
                return {"success": False, "error": "commission_not_found"}

            # Check if already recorded AND no overflow remains to be settled
            overflow_amount = Decimal(str(commission.commission_overflow or 0))
            if commission.shopify_usage_record_id and overflow_amount == Decimal("0"):
                logger.info(
                    f"✅ Commission already recorded to Shopify (no overflow remaining)"
                )
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

            # Get shop
            shop = await self.billing_repository.get_shop(commission.shop_id)
            if not shop:
                logger.error(f"❌ Shop not found")
                return {"success": False, "error": "shop_not_found"}

            # Get subscription directly from shop_subscriptions (stateless billing)
            shop_subscription = await self.billing_repository.get_shop_subscription(
                commission.shop_id
            )
            if not shop_subscription:
                logger.error(
                    f"❌ Shop subscription not found for shop {commission.shop_id}"
                )
                return {"success": False, "error": "subscription_not_found"}

            # Check if we have Shopify line item ID
            if not shop_subscription.shopify_line_item_id:
                logger.error(f"❌ No Shopify line item ID found")
                return {"success": False, "error": "no_shopify_line_item"}

            # Determine charge amount and idempotency key
            is_overflow_settlement = overflow_amount > Decimal("0")
            if is_overflow_settlement:
                amount_to_charge = overflow_amount
                idempotency_key = (
                    f"{commission.shop_id}-{commission.id}-{commission.order_id}-overflow"
                )
            else:
                amount_to_charge = commission.commission_charged
                idempotency_key = (
                    f"{commission.shop_id}-{commission.id}-{commission.order_id}"
                )

            # Check if we have positive charge amount
            if amount_to_charge <= Decimal("0"):
                logger.warning(f"⚠️ Commission has no charge amount: {commission_id}")
                return {"success": False, "error": "no_charge_amount"}

            # Record to Shopify with retry and backoff
            logger.info(
                f"📤 Recording ${amount_to_charge} to Shopify (overflow_settlement={is_overflow_settlement})..."
            )

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
                    description=(
                        f"Better Bundle - Order {commission.order_id} (Overflow)"
                        if is_overflow_settlement
                        else f"Better Bundle - Order {commission.order_id}"
                    ),
                    amount=amount_to_charge,
                    currency=commission.currency,
                    idempotency_key=idempotency_key,
                    commission_ids=[commission.id],
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
                # Query Shopify live status once to inspect remaining cap
                status_data = await shopify_billing_service.get_subscription_status(
                    shop_domain=shop.shop_domain,
                    access_token=shop.access_token,
                    subscription_id=shop_subscription.shopify_subscription_id,
                )
                line_items = (
                    status_data.get("lineItems", [])
                    if isinstance(status_data, dict)
                    else []
                )
                pricing = (
                    line_items[0].get("plan", {}).get("pricingDetails", {})
                    if line_items
                    else {}
                )
                capped_amount = Decimal(
                    str(pricing.get("cappedAmount", {}).get("amount", "0"))
                )
                balance_used = Decimal(
                    str(pricing.get("balanceUsed", {}).get("amount", "0"))
                )
                remaining = max(Decimal("0.00"), capped_amount - balance_used)

                partial_record = None
                if remaining > Decimal("0.00") and remaining < amount_to_charge:
                    logger.info(
                        f"Attempting partial charge of remaining ${remaining} on shop {shop.id}"
                    )
                    partial_key = f"{commission.shop_id}-{commission.id}-{commission.order_id}-partial"
                    partial_result = await shopify_billing_service.record_usage(
                        shop_id=shop.id,
                        shop_domain=shop.shop_domain,
                        access_token=shop.access_token,
                        subscription_line_item_id=shop_subscription.shopify_line_item_id,
                        description=f"Better Bundle - Order {commission.order_id} (Partial)",
                        amount=remaining,
                        currency=commission.currency,
                        idempotency_key=partial_key,
                        commission_ids=[commission.id],
                    )
                    if partial_result and not (
                        isinstance(partial_result, dict)
                        and partial_result.get("error")
                    ):
                        partial_record = partial_result

                existing_responses = (
                    list(commission.shopify_response)
                    if isinstance(commission.shopify_response, list)
                    else (
                        [commission.shopify_response]
                        if commission.shopify_response
                        else []
                    )
                )

                if partial_record:
                    # Partial charge succeeded
                    commission.commission_charged = (
                        (commission.commission_charged or Decimal("0")) + remaining
                        if is_overflow_settlement
                        else remaining
                    )
                    commission.commission_overflow = (
                        commission.commission_earned - commission.commission_charged
                    )
                    if not commission.shopify_usage_record_id:
                        commission.shopify_usage_record_id = partial_record.id
                        commission.shopify_recorded_at = now_utc()
                    existing_responses.append(
                        {
                            "id": partial_record.id,
                            "created_at": partial_record.created_at,
                            "price": {
                                "amount": str(remaining),
                                "currency": commission.currency,
                            },
                            "idempotency_key": partial_key,
                            "type": "partial",
                        }
                    )
                    commission.shopify_response = existing_responses
                    commission.charge_type = ChargeType.PARTIAL
                    balance_used = balance_used + remaining
                else:
                    # Nothing could be charged
                    if not is_overflow_settlement:
                        commission.commission_overflow = commission.commission_earned
                        commission.commission_charged = Decimal("0")
                    commission.charge_type = ChargeType.REJECTED

                # Keep status as PENDING so it can be replayed after rollover
                commission.status = CommissionStatus.PENDING
                commission.updated_at = now_utc()
                await self.commission_repository.commit()

                # Suspend shop with recorded live balance
                await self._suspend_shop_for_cap_reached(
                    commission.shop_id, balance_used=balance_used
                )

                logger.warning(
                    f"🛑 Commission {commission_id} exceeded cap. "
                    f"Charged: ${commission.commission_charged}, Overflow: ${commission.commission_overflow}. "
                    f"Shop {commission.shop_id} suspended with Shopify balance ${balance_used}."
                )

                return {
                    "success": False,
                    "error": "cap_exceeded",
                    "error_message": "Capped amount exceeded - Shopify rejected usage record",
                    "commission_pending": True,
                    "commission_charged": float(commission.commission_charged),
                    "commission_overflow": float(commission.commission_overflow),
                }

            # Check if we still don't have a usage record (other errors)
            if not usage_record:
                logger.error("❌ Failed to record to Shopify after retries")
                # Commission remains PENDING - don't update status
                await self.commission_repository.rollback()
                return {
                    "success": False,
                    "error": "shopify_api_failed",
                    "error_message": last_error_message,
                }

            existing_responses = (
                list(commission.shopify_response)
                if isinstance(commission.shopify_response, list)
                else (
                    [commission.shopify_response]
                    if commission.shopify_response
                    else []
                )
            )
            record_type = "overflow_settlement" if is_overflow_settlement else "full"
            existing_responses.append(
                {
                    "id": usage_record.id,
                    "created_at": usage_record.created_at,
                    "price": {
                        "amount": str(amount_to_charge),
                        "currency": usage_record.price["currencyCode"],
                    },
                    "idempotency_key": idempotency_key,
                    "type": record_type,
                }
            )
            commission.shopify_response = existing_responses

            if is_overflow_settlement:
                commission.commission_charged = (
                    commission.commission_charged or Decimal("0")
                ) + amount_to_charge
                commission.commission_overflow = Decimal("0")
            else:
                commission.shopify_usage_record_id = usage_record.id
                commission.shopify_recorded_at = now_utc()
                commission.commission_charged = amount_to_charge
                commission.commission_overflow = Decimal("0")

            commission.charge_type = ChargeType.FULL
            commission.status = CommissionStatus.RECORDED
            commission.updated_at = now_utc()

            await self.commission_repository.commit()

            logger.info(
                f"✅ Commission marked as RECORDED: {usage_record.id} "
                f"(${commission.commission_charged} total charged)"
            )

            return {
                "success": True,
                "shopify_usage_record_id": commission.shopify_usage_record_id,
                "commission_charged": float(commission.commission_charged),
                "commission_overflow": float(commission.commission_overflow),
                "charge_type": commission.charge_type.value,
            }

        except Exception as e:
            logger.error(f"❌ Error recording to Shopify: {e}")
            await self.commission_repository.rollback()
            return {"success": False, "error": str(e)}

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

    async def get_pending_commissions(
        self, shop_id: Optional[str] = None, limit: int = 100
    ) -> List[CommissionRecord]:
        """Get all pending commissions that need to be recorded to Shopify"""
        try:
            from sqlalchemy import or_

            conditions = [
                CommissionRecord.status == CommissionStatus.PENDING,
                CommissionRecord.billing_phase == BillingPhase.PAID,
                or_(
                    CommissionRecord.shopify_usage_record_id.is_(None),
                    CommissionRecord.commission_overflow > 0,
                ),
            ]
            if shop_id:
                conditions.append(CommissionRecord.shop_id == shop_id)

            query = (
                select(CommissionRecord)
                .where(and_(*conditions))
                .order_by(CommissionRecord.created_at.asc())
                .limit(limit)
            )
            result = await self.session.execute(query)
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"❌ Error getting pending commissions: {e}")
            return []

    async def get_commission_stats_for_period(
        self,
        shop_id: Optional[str] = None,
        billing_cycle_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get commission statistics for a period or billing cycle"""
        try:
            conditions = []
            if billing_cycle_id:
                conditions.append(CommissionRecord.billing_cycle_id == billing_cycle_id)
            if shop_id:
                conditions.append(CommissionRecord.shop_id == shop_id)
            if date_from:
                conditions.append(CommissionRecord.order_date >= date_from)
            if date_to:
                conditions.append(CommissionRecord.order_date <= date_to)

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
            )
            if conditions:
                query = query.where(and_(*conditions))

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

    async def get_commission_stats_for_cycle(
        self, billing_cycle_id: str
    ) -> Dict[str, Any]:
        """Backward compatibility wrapper for cycle stats"""
        return await self.get_commission_stats_for_period(
            billing_cycle_id=billing_cycle_id
        )

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
            and shop_subscription.status
            in (SubscriptionStatus.ACTIVE, SubscriptionStatus.SUSPENDED)
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
