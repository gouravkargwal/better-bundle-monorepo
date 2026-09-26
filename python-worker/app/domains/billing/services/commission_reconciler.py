"""
Commission Reconciler

Handles two periodic sweeps for usage-based billing:
- Sweep 1: Detects Shopify cycle rollovers and resets CAPPED commissions.
- Sweep 2: Republishes stale PENDING commissions that lost their Kafka event.
"""

import asyncio
import logging
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional

from opentelemetry import trace
from opentelemetry.trace import StatusCode
from sqlalchemy import select, and_, update, func

from app.core.config.kafka_settings import kafka_settings
from app.core.database.models import ShopSubscription
from app.core.database.models.commission import CommissionRecord
from app.core.database.models.enums import CommissionStatus
from app.core.database.session import get_transaction_context
from app.core.metrics import (
    commission_reconciler_reset_capped_total,
    commission_reconciler_republished_pending_total,
    commission_reconciler_skipped_with_usage_record_total,
    reconciler_duration,
    reconciler_runs_total,
)
from app.core.single_run import claim
from app.domains.billing.services.shopify_usage_billing_service_v2 import (
    ShopifyUsageBillingServiceV2,
)
from app.core.messaging.event_publisher import EventPublisher

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

RECONCILE_INTERVAL_SECONDS = 3600
MAX_SHOPS_PER_SWEEP = 100


async def _get_shops_with_capped_commissions(limit: int = MAX_SHOPS_PER_SWEEP) -> List[Dict[str, Any]]:
    """Find distinct shops that have at least one CAPPED commission."""
    async with get_transaction_context() as session:
        query = (
            select(
                CommissionRecord.shop_id,
                ShopSubscription.shopify_subscription_id,
                ShopSubscription.shop_subscription_metadata,
            )
            .join(
                ShopSubscription,
                ShopSubscription.shop_id == CommissionRecord.shop_id,
            )
            .where(
                and_(
                    CommissionRecord.status == CommissionStatus.CAPPED,
                    ShopSubscription.shopify_subscription_id.is_not(None),
                )
            )
            .group_by(CommissionRecord.shop_id, ShopSubscription.shopify_subscription_id, ShopSubscription.shop_subscription_metadata)
            .limit(limit)
        )
        result = await session.execute(query)
        rows = result.all()
        return [
            {
                "shop_id": row.shop_id,
                "shopify_subscription_id": row.shopify_subscription_id,
                "metadata": dict(row.shop_subscription_metadata or {}),
            }
            for row in rows
        ]


async def _reset_capped_commissions(shop_id: str, cutoff_time) -> int:
    """Reset CAPPED commissions for a shop to PENDING if they were CAPPED before cutoff."""
    async with get_transaction_context() as session:
        result = await session.execute(
            update(CommissionRecord)
            .where(
                and_(
                    CommissionRecord.shop_id == shop_id,
                    CommissionRecord.status == CommissionStatus.CAPPED,
                    CommissionRecord.updated_at <= cutoff_time,
                )
            )
            .values(status=CommissionStatus.PENDING, updated_at=func.now())
        )
        return result.rowcount


async def _clear_paused(shop_id: str) -> None:
    """Clear the paused flag on a shop's subscription."""
    async with get_transaction_context() as session:
        await session.execute(
            update(ShopSubscription)
            .where(
                and_(
                    ShopSubscription.shop_id == shop_id,
                    ShopSubscription.paused.is_(True),
                )
            )
            .values(paused=False, paused_at=None)
        )


async def reconcile_commissions_once(
    limit: int = MAX_SHOPS_PER_SWEEP,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Execute one reconciliation pass across shops with CAPPED commissions."""
    start_time = time.perf_counter()
    with tracer.start_as_current_span("reconciler.commission.sweep") as span:
        span.set_attribute("dry_run", dry_run)
        try:
            # Sweep 1 — Cycle rollover
            candidates = await _get_shops_with_capped_commissions(limit)

            if not candidates:
                duration = time.perf_counter() - start_time
                reconciler_runs_total.add(1, {"reconciler": "commission", "status": "success"})
                reconciler_duration.record(duration, {"reconciler": "commission"})
                return {
                    "checked": 0,
                    "capped_reset": 0,
                    "pending_republished": 0,
                    "dry_run": dry_run,
                }

            logger.info(
                f"Commission reconciler checking {len(candidates)} shops with CAPPED commissions",
                extra={"reconciler": "commission", "checked": len(candidates)},
            )

            cutoff_time = func.now()
            capped_reset_total = 0
            pending_republished_total = 0
            skipped_with_usage_record_total = 0

            usage_service = ShopifyUsageBillingServiceV2(session=None, billing_repository=None)

            for candidate in candidates:
                shop_id = candidate["shop_id"]
                shopify_subscription_id = candidate["shopify_subscription_id"]
                metadata = candidate["metadata"]

                if not shopify_subscription_id:
                    logger.warning(f"Shop {shop_id} has CAPPED commissions but no Shopify subscription ID")
                    continue

                try:
                    # Need shop domain and access token — fetch from shop record
                    async with get_transaction_context() as session:
                        from app.core.database.models.shop import Shop
                        shop_result = await session.execute(
                            select(Shop.shop_domain, Shop.access_token).where(Shop.id == shop_id)
                        )
                        shop_row = shop_result.first()
                        if not shop_row or not shop_row.shop_domain or not shop_row.access_token:
                            logger.warning(f"Shop {shop_id} missing domain or token; skipping")
                            continue
                        shop_domain = shop_row.shop_domain
                        access_token = shop_row.access_token

                    status_data = await usage_service.get_subscription_status(
                        shop_domain=shop_domain,
                        access_token=access_token,
                        subscription_id=shopify_subscription_id,
                    )

                    if not status_data:
                        logger.warning(f"Could not fetch subscription status for shop {shop_id}")
                        continue

                    line_items = status_data.get("lineItems", [])
                    pricing = (
                        line_items[0].get("plan", {}).get("pricingDetails", {})
                        if line_items
                        else {}
                    )

                    if pricing.get("__typename") != "AppUsagePricing":
                        logger.warning(f"Subscription {shopify_subscription_id} for shop {shop_id} is not AppUsagePricing")
                        continue

                    current_period_end = pricing.get("cappedAmount", {}).get("amount")
                    last_seen_period_end = metadata.get("last_seen_period_end")

                    if last_seen_period_end is None:
                        if not dry_run:
                            async with get_transaction_context() as update_session:
                                sub_result = await update_session.execute(
                                    select(ShopSubscription).where(ShopSubscription.shop_id == shop_id).limit(1)
                                )
                                sub = sub_result.scalar_one_or_none()
                                if sub:
                                    sub_metadata = dict(sub.shop_subscription_metadata or {})
                                    sub_metadata["last_seen_period_end"] = current_period_end
                                    sub.shop_subscription_metadata = sub_metadata
                        logger.info(f"Recorded baseline period end for shop {shop_id}: {current_period_end}")
                        continue

                    # Compare as strings since they come from Shopify as strings
                    if str(current_period_end) > str(last_seen_period_end):
                        if not dry_run:
                            reset_count = await _reset_capped_commissions(shop_id, cutoff_time)
                            await _clear_paused(shop_id)
                            capped_reset_total += reset_count
                            logger.info(
                                f"Reset {reset_count} CAPPED commissions for shop {shop_id} "
                                f"(period: {last_seen_period_end} -> {current_period_end})"
                            )
                        else:
                            capped_reset_total += 1

                except Exception as e:
                    logger.error(
                        f"Error processing rollover for shop {shop_id}: {e}",
                        exc_info=True,
                    )

            # Sweep 2 — Stuck PENDING
            if not dry_run:
                async with get_transaction_context() as session:
                    query = (
                        select(CommissionRecord.shop_id, CommissionRecord.id)
                        .where(
                            and_(
                                CommissionRecord.status == CommissionStatus.PENDING,
                                CommissionRecord.updated_at < func.now() - func.text("interval '1 hour'"),
                            )
                        )
                    )
                    result = await session.execute(query)
                    rows = result.all()

                # Group by shop
                shop_pending: Dict[str, List[str]] = {}
                for row in rows:
                    shop_id = row.shop_id
                    comm_id = row.id
                    shop_pending.setdefault(shop_id, []).append(comm_id)

                for shop_id, comm_ids in shop_pending.items():
                    # Check which have shopify_usage_record_id set
                    async with get_transaction_context() as session:
                        comm_query = (
                            select(CommissionRecord.id, CommissionRecord.shopify_usage_record_id)
                            .where(
                                and_(
                                    CommissionRecord.id.in_(comm_ids),
                                    CommissionRecord.status == CommissionStatus.PENDING,
                                )
                            )
                        )
                        comm_result = await session.execute(comm_query)
                        comm_rows = comm_result.all()

                    to_republish = []
                    for row in comm_rows:
                        if row.shopify_usage_record_id is not None:
                            skipped_with_usage_record_total += 1
                        else:
                            to_republish.append(row.id)

                    if to_republish:
                        published = await _republish_pending_commissions_for_ids(
                            shop_id, to_republish
                        )
                        pending_republished_total += published

            if skipped_with_usage_record_total > 0:
                commission_reconciler_skipped_with_usage_record_total.add(
                    skipped_with_usage_record_total
                )

            duration = time.perf_counter() - start_time
            reconciler_runs_total.add(1, {"reconciler": "commission", "status": "success"})
            reconciler_duration.record(duration, {"reconciler": "commission"})

            if capped_reset_total > 0:
                commission_reconciler_reset_capped_total.add(capped_reset_total)
            if pending_republished_total > 0:
                commission_reconciler_republished_pending_total.add(pending_republished_total)

            logger.info(
                f"Commission reconciler completed: {capped_reset_total} capped reset, "
                f"{pending_republished_total} pending republished, "
                f"{skipped_with_usage_record_total} skipped (already recorded)",
                extra={
                    "reconciler": "commission",
                    "checked": len(candidates),
                    "capped_reset": capped_reset_total,
                    "pending_republished": pending_republished_total,
                    "skipped_with_usage_record": skipped_with_usage_record_total,
                    "duration_sec": duration,
                },
            )

            return {
                "checked": len(candidates),
                "capped_reset": capped_reset_total,
                "pending_republished": pending_republished_total,
                "dry_run": dry_run,
            }
        except Exception as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            duration = time.perf_counter() - start_time
            reconciler_runs_total.add(1, {"reconciler": "commission", "status": "error"})
            reconciler_duration.record(duration, {"reconciler": "commission"})
            raise


async def _republish_pending_commissions_for_ids(shop_id: str, comm_ids: List[str]) -> int:
    """Republish Kafka events for specific commission IDs."""
    publisher = EventPublisher(kafka_settings.model_dump())
    await publisher.initialize()
    published = 0
    try:
        for comm_id in comm_ids:
            try:
                await publisher.publish_shopify_usage_event(
                    {
                        "event_type": "record_usage",
                        "shop_id": shop_id,
                        "commission_id": comm_id,
                        "trigger": "reconciler_retry",
                    }
                )
                published += 1
            except Exception as e:
                logger.error(
                    f"Failed to republish usage event for commission {comm_id}: {e}"
                )
    finally:
        await publisher.close()
    return published


async def run_forever(interval: int = RECONCILE_INTERVAL_SECONDS) -> None:
    """Run commission reconciler loop forever."""
    logger.info(f"Commission reconciler started (every {interval}s)")
    while True:
        try:
            async with claim("commission_reconciler") as mine:
                if mine:
                    result = await reconcile_commissions_once()
                    if result.get("capped_reset", 0) > 0 or result.get("pending_republished", 0) > 0:
                        logger.info(f"Commission reconciler pass: {result}")
        except asyncio.CancelledError:
            logger.info("Commission reconciler stopped")
            raise
        except Exception as e:
            logger.error(f"Commission reconciler loop error: {e}", exc_info=True)
        await asyncio.sleep(interval)
