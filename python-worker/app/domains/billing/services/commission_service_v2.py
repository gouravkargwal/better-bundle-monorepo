import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

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
from ..services.shopify_usage_billing_service_v2 import ShopifyUsageBillingServiceV2
from app.repository.CommissionRepository import CommissionRepository
from app.repository.PurchaseAttributionRepository import PurchaseAttributionRepository
from app.core.messaging.event_publisher import EventPublisher
from app.core.config.kafka_settings import kafka_settings
from app.core.database.session import get_transaction_context
from app.core.database.models.shop_subscription import ShopSubscription
from app.core.exceptions import CapError, TransientError, PermanentError
from sqlalchemy import update, and_

logger = logging.getLogger(__name__)


class CommissionServiceV2:
    """Updated service for managing commission records with unified subscription system"""

    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session
        self.billing_repository = BillingRepositoryV2(session) if session else None
        self.commission_repository = CommissionRepository(session) if session else None
        self.purchase_attribution_repository = (
            PurchaseAttributionRepository(session) if session else None
        )

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

            try:
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

            except IntegrityError:
                await self.session.rollback()
                logger.info(
                    f"🔁 Duplicate commission race for attribution {purchase_attribution_id}; "
                    f"returning existing row"
                )
                return await self.commission_repository.get_by_purchase_attribution_id(
                    purchase_attribution_id
                )

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

    def _classify_shopify_user_error(self, user_errors: list) -> PermanentError:
        """Classify a Shopify userError.

        Until a live test call gives the exact cap-exceeded signal, treat every
        user error as permanent. Do not guess from docs or message text.
        """
        if not user_errors:
            return PermanentError("Shopify returned userErrors with no entries")

        first = user_errors[0]
        message = (first.get("message") or "").strip()
        code = first.get("code")
        detail = f"code={code!r}, message={message!r}" if message or code else str(first)

        return PermanentError(f"Shopify user error: {detail}")

    async def charge_commission_to_shopify(self, commission_id: str) -> None:
        """Charge a single commission to Shopify using two short DB transactions
        with the Shopify call in between.

        Phase 1 — read commission in a short transaction.
        Phase 2 — call Shopify outside any transaction.
        Phase 3 — write outcome in a short transaction with SELECT FOR UPDATE.

        Returns None on success. Raises CapError, TransientError, or
        PermanentError on failure.
        """
        # Phase 1 — read in a short transaction
        async with get_transaction_context() as session:
            repo = CommissionRepository(session)
            commission = await repo.get_by_id(commission_id)
            if commission is None:
                logger.warning("Commission not found", commission_id=commission_id)
                return
            if commission.status != CommissionStatus.PENDING:
                return

            shop_id = commission.shop_id
            earned = commission.commission_earned
            order_id = commission.order_id
            currency = commission.currency

            billing_repo = BillingRepositoryV2(session)
            shop = await billing_repo.get_shop(shop_id)
            if not shop:
                raise PermanentError(f"Shop {shop_id} not found")

            shop_subscription = await billing_repo.get_shop_subscription(shop_id)
            if not shop_subscription:
                raise PermanentError(
                    f"Shop subscription not found for shop {shop_id}"
                )

            if not shop_subscription.shopify_line_item_id:
                raise PermanentError(
                    f"No Shopify line item ID for shop {shop_id}"
                )

            shop_domain = shop.shop_domain
            access_token = shop.access_token
            line_item_id = shop_subscription.shopify_line_item_id

        # Phase 2 — Shopify call, no transaction
        try:
            billing_repo = BillingRepositoryV2(None) if self.billing_repository is None else self.billing_repository
            billing_service = ShopifyUsageBillingServiceV2(
                session=None, billing_repository=billing_repo
            )
            usage_record = await billing_service.record_usage(
                shop_id=shop_id,
                shop_domain=shop_domain,
                access_token=access_token,
                subscription_line_item_id=line_item_id,
                description=f"Better Bundle - Order {order_id}",
                amount=earned,
                currency=currency,
                idempotency_key=f"commission-{commission_id}",
                commission_ids=[commission_id],
            )

            if isinstance(usage_record, dict) and usage_record.get("error"):
                raise self._classify_shopify_user_error(
                    usage_record.get("user_errors", [])
                )

            if not usage_record:
                raise PermanentError("Shopify returned no usage record")

            outcome = "RECORDED"
            usage_record_id = usage_record.id
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                raise TransientError(f"Shopify 5xx: {e}") from e
            raise PermanentError(f"Shopify HTTP error: {e}") from e
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            raise TransientError(f"Shopify connection error: {e}") from e
        except PermanentError:
            outcome = "FAILED"
            logger.error("Permanent Shopify charge failure", exc_info=True)
        except CapError:
            outcome = "CAPPED"

        # Phase 3 — write in a short transaction with SELECT FOR UPDATE
        async with get_transaction_context() as session:
            repo = CommissionRepository(session)
            commission = await repo.get_for_update(commission_id, session)
            if commission.status != CommissionStatus.PENDING:
                return

            if outcome == "RECORDED":
                commission.shopify_usage_record_id = usage_record_id
                commission.status = CommissionStatus.RECORDED
                commission.commission_charged = earned
                commission.commission_overflow = Decimal("0")
                commission.charge_type = ChargeType.FULL
                commission.shopify_recorded_at = now_utc()
            elif outcome == "CAPPED":
                commission.status = CommissionStatus.CAPPED
                await session.execute(
                    update(ShopSubscription)
                    .where(
                        ShopSubscription.shop_id == shop_id,
                        ShopSubscription.paused.is_(False),
                    )
                    .values(paused=True, paused_at=func.now())
                )
            elif outcome == "FAILED":
                commission.status = CommissionStatus.FAILED

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
