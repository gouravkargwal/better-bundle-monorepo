"""
Kafka-based Shopify Usage consumer
Handles Shopify usage record creation, retries, and reprocessing rejected commissions
"""

import asyncio
from typing import Dict, Any
from decimal import Decimal
from datetime import datetime, timedelta

from app.core.kafka.consumer import KafkaConsumer
from app.core.config.kafka_settings import kafka_settings
from app.core.logging import get_logger
from app.core.database.session import get_transaction_context
from app.domains.billing.repositories.billing_repository_v2 import BillingRepositoryV2
from app.domains.billing.services.commission_service_v2 import CommissionServiceV2
from app.domains.billing.services.shopify_usage_billing_service_v2 import (
    ShopifyUsageBillingServiceV2,
)
from app.repository.CommissionRepository import CommissionRepository
from app.core.database.models.enums import (
    CommissionStatus,
    ChargeType,
    SubscriptionStatus,
)
from app.shared.helpers import now_utc
from app.core.redis_client import get_redis_client

from sqlalchemy import select, and_
from app.core.database.models.commission import CommissionRecord
from app.core.database.models.scheduler_job_execution import SchedulerJobExecution
from sqlalchemy import update
from app.core.database.models.shop_subscription import ShopSubscription

logger = get_logger(__name__)


# =====================================================================
# Standalone reconciler — callable from both the background loop and API
# =====================================================================


async def reconcile_stuck_recording_commissions() -> int:
    """
    Reconcile commissions stuck in RECORDING status.

    When commission_service_v2 sets a commission to RECORDING and then calls
    Shopify's appUsageRecordCreate, if the process crashes after Shopify succeeds
    but before updating the commission to RECORDED, the commission stays in RECORDING.

    This function:
    1. Finds commissions stuck in RECORDING for > 5 minutes
    2. If they have shopify_usage_record_id -> sets to RECORDED (Shopify succeeded)
    3. If they don't -> resets to PENDING for retry

    Returns the number of commissions reconciled.
    """
    try:
        cutoff_time = datetime.utcnow() - timedelta(minutes=5)

        async with get_transaction_context() as session:
            query = select(CommissionRecord).where(
                and_(
                    CommissionRecord.status == CommissionStatus.RECORDING,
                    CommissionRecord.updated_at < cutoff_time,
                )
            )
            result = await session.execute(query)
            stuck_commissions = result.scalars().all()

            if not stuck_commissions:
                return 0

            reconciled = 0
            for commission in stuck_commissions:
                if commission.shopify_usage_record_id:
                    # Shopify succeeded but we crashed before marking RECORDED
                    commission.status = CommissionStatus.RECORDED
                    logger.info(
                        f"Reconciled commission {commission.id}: "
                        f"had shopify_usage_record_id, marking RECORDED"
                    )
                else:
                    # Process likely crashed before Shopify call or Shopify returned error
                    # Reset to PENDING for retry on next event
                    commission.status = CommissionStatus.PENDING
                    commission.error_count = (commission.error_count or 0) + 1
                    commission.last_error = "Stuck in RECORDING - reset to PENDING for retry"
                    commission.last_error_at = now_utc()
                    logger.warning(
                        f"Reconciled commission {commission.id}: "
                        f"no usage record, reset to PENDING for retry"
                    )
                commission.updated_at = now_utc()
                reconciled += 1

            await session.flush()

            if reconciled > 0:
                logger.info(f"Reconciled {reconciled} stuck RECORDING commissions")

            return reconciled

    except Exception as e:
        logger.error(f"Error reconciling stuck RECORDING commissions: {e}")
        return 0


# =====================================================================
# Kafka consumer class
# =====================================================================


class ShopifyUsageKafkaConsumer:
    """Kafka consumer for Shopify usage record operations"""

    def __init__(self):
        self.consumer = KafkaConsumer(kafka_settings.model_dump())
        self._initialized = False

    async def initialize(self):
        """Initialize consumer"""
        try:
            await self.consumer.initialize(
                topics=["shopify-usage-events"], group_id="shopify-usage-processors"
            )

            self._initialized = True
            logger.info("Shopify Usage Kafka consumer initialized")

        except Exception as e:
            logger.error(f"Failed to initialize Shopify Usage consumer: {e}")
            raise

    async def start_consuming(self):
        """Start consuming messages"""
        if not self._initialized:
            await self.initialize()

        try:
            logger.info("Starting Shopify Usage consumer...")
            async for message in self.consumer.consume():
                try:
                    await self._handle_message(message)
                    await self.consumer.commit(message)
                except Exception as e:
                    logger.error(f"Error processing Shopify usage message: {e}")
                    # Don't break - continue processing other messages
                    continue
        except Exception as e:
            logger.error(f"Error in Shopify Usage consumer: {e}")
            raise

    async def start_reconciler(self, interval_seconds: int = 300):
        """
        Background loop that periodically reconciles commissions stuck in RECORDING status.

        Uses a distributed Redis lock to ensure only one instance of the reconciler
        runs across multiple replicas. If Redis is unavailable, runs anyway (best-effort).

        Args:
            interval_seconds: How often to run the reconciler (default 5 minutes).
        """
        loop_name = "reconcile_stuck_recording_commissions"
        logger.info(f"Starting background reconciler every {interval_seconds}s")

        while True:
            try:
                # Attempt to acquire a distributed lock via Redis
                lock_acquired = False
                try:
                    redis_client = await get_redis_client()
                    lock_key = f"lock:{loop_name}"
                    # SET NX with 60s expiry - if it exists, another instance holds the lock
                    lock_acquired = await redis_client.set(
                        lock_key, now_utc().isoformat(), nx=True, ex=60
                    )
                except Exception:
                    # Redis unavailable - run without lock (best-effort)
                    lock_acquired = True

                if lock_acquired:
                    reconciled = await reconcile_stuck_recording_commissions()
                    if reconciled > 0:
                        logger.info(f"Reconciled {reconciled} stuck commissions")

                await asyncio.sleep(interval_seconds)

            except asyncio.CancelledError:
                logger.info("Background reconciler cancelled")
                break
            except Exception as e:
                logger.error(f"Background reconciler error: {e}")
                await asyncio.sleep(interval_seconds)

    async def close(self):
        """Close consumer"""
        if self.consumer:
            await self.consumer.close()
        logger.info("Shopify Usage consumer closed")

    async def _handle_message(self, message: Dict[str, Any]):
        """Handle individual Shopify usage messages"""
        try:
            payload = message.get("value") or message
            if isinstance(payload, str):
                try:
                    import json

                    payload = json.loads(payload)
                except Exception:
                    pass

            event_type = payload.get("event_type")
            shop_id = payload.get("shop_id")

            if not event_type:
                logger.warning(f"No event_type in message: {payload}")
                return

            logger.info(
                f"Processing Shopify usage event: {event_type} for shop {shop_id}"
            )

            async with get_transaction_context() as session:
                billing_repo = BillingRepositoryV2(session)
                shopify_billing = ShopifyUsageBillingServiceV2(session, billing_repo)
                commission_service = CommissionServiceV2(session)

                # Route to appropriate handler
                if event_type == "record_usage":
                    await self._handle_record_usage(payload)
                elif event_type == "cap_increase":
                    await self._handle_cap_increase(
                        payload,
                        session,
                        billing_repo,
                        commission_service,
                        shopify_billing,
                    )
                elif event_type == "reprocess_rejected_commissions":
                    await self._handle_reprocess_rejected(
                        payload,
                        session,
                        billing_repo,
                        commission_service,
                        shopify_billing,
                    )
                else:
                    logger.warning(f"Unknown event type: {event_type}")

        except Exception as e:
            logger.error(f"Error handling Shopify usage message: {e}")
            raise

    async def _handle_record_usage(self, payload: Dict[str, Any]):
        """Handle usage record creation request"""
        try:
            commission_id = payload.get("commission_id")
            if not commission_id:
                logger.error("No commission_id in record_usage event")
                return

            async with get_transaction_context() as session:
                billing_repo = BillingRepositoryV2(session)
                shopify_billing = ShopifyUsageBillingServiceV2(session, billing_repo)
                commission_service = CommissionServiceV2(session)

                # Record commission to Shopify
                result = await commission_service.record_commission_to_shopify(
                    commission_id=commission_id,
                    shopify_billing_service=shopify_billing,
                )

                if result.get("success"):
                    logger.info(
                        f"Successfully recorded commission {commission_id} to Shopify"
                    )
                else:
                    logger.error(
                        f"Failed to record commission {commission_id}: {result.get('error')}"
                    )

        except Exception as e:
            logger.error(f"Error in _handle_record_usage: {e}")
            raise

    async def _handle_cap_increase(self, payload: Dict[str, Any]):
        """Handle cap increase event - reprocess rejected commissions"""
        try:
            shop_id = payload.get("shop_id")
            cycle_id = payload.get("billing_cycle_id")
            new_cap_amount = payload.get("new_cap_amount")

            if not shop_id or not cycle_id:
                logger.error(
                    "Missing shop_id or billing_cycle_id in cap_increase event"
                )
                return

            logger.info(
                f"Processing cap increase for shop {shop_id}, cycle {cycle_id}, new cap: {new_cap_amount}"
            )

            # Reprocess rejected commissions (this will handle reactivating subscription if needed)
            await self._reprocess_rejected_commissions(shop_id, cycle_id)

            # Also reactivate subscription if it was suspended
            async with get_transaction_context() as session:
                billing_repo = BillingRepositoryV2(session)
                shop_subscription = await billing_repo.get_shop_subscription(shop_id)

                if (
                    shop_subscription
                    and shop_subscription.status == SubscriptionStatus.SUSPENDED
                ):

                    await session.execute(
                        update(ShopSubscription)
                        .where(ShopSubscription.id == shop_subscription.id)
                        .where(ShopSubscription.status == SubscriptionStatus.SUSPENDED)
                        .values(
                            status=SubscriptionStatus.ACTIVE,
                            updated_at=now_utc(),
                        )
                    )

                    logger.info(
                        f"Reactivated subscription {shop_subscription.id} after cap increase"
                    )

        except Exception as e:
            logger.error(f"Error in _handle_cap_increase: {e}")
            raise

    async def _handle_reprocess_rejected(
        self,
        payload: Dict[str, Any],
        session,
        billing_repo: BillingRepositoryV2,
        commission_service: CommissionServiceV2,
        shopify_billing: ShopifyUsageBillingServiceV2,
    ):
        """Handle explicit reprocess rejected commissions request"""
        try:
            shop_id = payload.get("shop_id")
            cycle_id = payload.get("billing_cycle_id")

            if not shop_id or not cycle_id:
                logger.error(
                    "Missing shop_id or billing_cycle_id in reprocess_rejected_commissions event"
                )
                return

            logger.info(
                f"Processing reprocess_rejected_commissions event for shop {shop_id}, cycle {cycle_id}"
            )

            await self._reprocess_rejected_commissions(shop_id, cycle_id)

        except Exception as e:
            logger.error(f"Error in _handle_reprocess_rejected: {e}", exc_info=True)
            raise

    async def _reprocess_rejected_commissions(
        self,
        shop_id: str,
        cycle_id: str,
        session=None,
        billing_repo=None,
        commission_service=None,
        shopify_billing=None,
    ) -> None:
        """Reprocess rejected commissions for a billing cycle"""
        try:
            # Use provided session or create new one
            if session is None:
                async with get_transaction_context() as new_session:
                    if billing_repo is None:
                        billing_repo = BillingRepositoryV2(new_session)
                    if commission_service is None:
                        shopify_billing = ShopifyUsageBillingServiceV2(
                            new_session, billing_repo
                        )
                        commission_service = CommissionServiceV2(new_session)
                    await self._do_reprocess(
                        shop_id,
                        cycle_id,
                        new_session,
                        billing_repo,
                        commission_service,
                        shopify_billing,
                    )
            else:
                await self._do_reprocess(
                    shop_id,
                    cycle_id,
                    session,
                    billing_repo,
                    commission_service,
                    shopify_billing,
                )
        except Exception as e:
            logger.error(
                f"Error reprocessing rejected commissions: {e}", exc_info=True
            )
            raise

    async def _do_reprocess(
        self,
        shop_id: str,
        cycle_id: str,
        session,
        billing_repo,
        commission_service,
        shopify_billing,
    ) -> None:
        """
        Reprocess REJECTED and PENDING commissions in the current billing cycle.

        Reprocessing means:
        1. Re-evaluate charge amounts based on current cap and usage
        2. Re-record commissions to Shopify

        Current cycle is the active billing cycle (status=ACTIVE) for the shop's subscription.
        """
        try:
            # Get current billing cycle
            current_cycle = await billing_repo.get_billing_cycle_by_id(cycle_id)
            if not current_cycle:
                logger.error(f"Billing cycle {cycle_id} not found")
                return

            logger.info(
                f"Current billing cycle: {cycle_id} (cap: {current_cycle.current_cap_amount}, usage: {current_cycle.usage_amount})"
            )

            # Query for both REJECTED and PENDING commissions in PAID phase
            query = select(CommissionRecord).where(
                and_(
                    CommissionRecord.shop_id == shop_id,
                    CommissionRecord.billing_cycle_id == cycle_id,
                    CommissionRecord.billing_phase == "PAID",
                    (
                        (CommissionRecord.status == CommissionStatus.REJECTED)
                        | (CommissionRecord.status == CommissionStatus.PENDING)
                    ),
                )
            )

            result = await session.execute(query)
            commissions_to_reprocess = result.scalars().all()

            if not commissions_to_reprocess:
                logger.info(
                    f"No rejected/pending commissions to reprocess for cycle {cycle_id}"
                )
                return

            logger.info(
                f"Reprocessing {len(commissions_to_reprocess)} commissions (REJECTED + PENDING) for cycle {cycle_id}"
            )

            total_reprocessed = 0
            total_charged = Decimal("0")

            # Process each commission
            for commission in commissions_to_reprocess:
                # Refresh cycle to get current usage_amount before calculating remaining_cap
                await session.refresh(current_cycle)

                # Calculate remaining cap from actual current usage
                remaining_cap = Decimal(current_cycle.current_cap_amount) - Decimal(
                    current_cycle.usage_amount
                )

                # Re-evaluate charge amounts based on current cap
                amount_to_charge = Decimal(commission.commission_earned)

                # Use commission service's charge calculation logic
                charge_data = commission_service._calculate_charge_amounts(
                    amount_to_charge, remaining_cap
                )

                # Update commission record
                commission.commission_charged = charge_data["actual_charge"]
                commission.commission_overflow = charge_data["overflow"]
                commission.charge_type = charge_data["charge_type"]
                commission.status = (
                    CommissionStatus.PENDING
                )  # Reset to pending for re-recording
                commission.updated_at = now_utc()

                await session.flush()

                # Record to Shopify if there's a charge amount
                if commission.commission_charged > 0:
                    logger.info(
                        f"Re-recording commission {commission.id} to Shopify "
                        f"(charge: ${commission.commission_charged}, remaining_cap: ${remaining_cap})"
                    )

                    record_result = (
                        await commission_service.record_commission_to_shopify(
                            commission_id=commission.id,
                            shopify_billing_service=shopify_billing,
                        )
                    )

                    if record_result.get("success"):
                        # Usage is already updated by record_commission_to_shopify
                        total_charged += commission.commission_charged
                        total_reprocessed += 1
                        logger.info(
                            f"Successfully re-recorded commission {commission.id} to Shopify"
                        )
                    else:
                        # If Shopify recording failed, mark as REJECTED
                        commission.charge_type = ChargeType.REJECTED
                        commission.status = CommissionStatus.REJECTED
                        commission.commission_overflow = (
                            commission.commission_overflow
                            + commission.commission_charged
                        )
                        commission.commission_charged = Decimal("0")
                        logger.warning(
                            f"Failed to record commission {commission.id} to Shopify: {record_result.get('error')}"
                        )
                        await session.flush()
                else:
                    # No charge amount - mark as REJECTED if needed
                    if charge_data["overflow"] > 0:
                        commission.charge_type = ChargeType.REJECTED
                        commission.status = CommissionStatus.REJECTED
                        logger.info(
                            f"Commission {commission.id} still has no charge amount (overflow: ${charge_data['overflow']}), marking as REJECTED"
                        )
                        await session.flush()

                # Refresh cycle to get updated usage for next iteration
                await session.refresh(current_cycle)
                remaining_cap_after = Decimal(
                    current_cycle.current_cap_amount
                ) - Decimal(current_cycle.usage_amount)

                # Stop processing if no remaining cap
                if remaining_cap_after <= 0:
                    logger.info(
                        f"Remaining cap exhausted. Stopping reprocessing. "
                        f"{len(commissions_to_reprocess) - total_reprocessed - 1} commissions remaining."
                    )
                    break

            logger.info(
                f"Reprocessed {total_reprocessed} commissions, charged ${total_charged} for cycle {cycle_id} "
                f"(usage already tracked in billing cycle during recording)"
            )

        except Exception as e:
            logger.error(f"Error reprocessing commissions: {e}", exc_info=True)
            raise
