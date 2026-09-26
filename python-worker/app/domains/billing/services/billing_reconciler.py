"""
Billing Reconciler

Compares Shopify invoice usage charges against intended commission charges
per billing cycle. Runs once per day under a distributed advisory lock.

Sweep 0 — complete stale cycles:
  Mark any BillingCycle with end_date < now() and status != COMPLETED as
  COMPLETED with completed_at = end_date.

Sweep 1 — reconcile:
  For each BillingCycle where:
    - status = COMPLETED
    - completed_at < now() - 24h
    - reconciled_at IS NULL
    - has at least one BillingInvoice with status = PAID

  Sum commission_charged for CommissionRecord where:
    - shop_id = cycle.shop_subscription.shop_id
    - order_date >= cycle.start_date
    - order_date < cycle.end_date
    - status = RECORDED

  Sum usage_amount from BillingInvoice where billing_cycle_id = cycle.id
    and status = PAID.

  Compare with tolerance +/-$0.01. Log mismatches and emit
  `betterbundle.reconciler.billing.mismatch_total`. No auto-correct.
"""

import asyncio
import logging
import time
from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from opentelemetry import trace
from opentelemetry.trace import StatusCode
from sqlalchemy import select, and_, update, func

from app.core.database.models import ShopSubscription, BillingInvoice, BillingCycle
from app.core.database.models.commission import CommissionRecord
from app.core.database.models.enums import (
    BillingCycleStatus,
    CommissionStatus,
    InvoiceStatus,
)
from app.core.database.session import get_transaction_context
from app.core.metrics import (
    reconciler_duration,
    reconciler_runs_total,
    billing_reconciliation_mismatch_total,
)
from app.core.single_run import claim
from app.shared.helpers import now_utc

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

RECONCILE_INTERVAL_SECONDS = 86400


async def _complete_stale_cycles() -> int:
    """Mark cycles whose end_date has passed but status is not COMPLETED."""
    async with get_transaction_context() as session:
        stmt = (
            update(BillingCycle.__table__)
            .where(
                and_(
                    BillingCycle.__table__.c.end_date < now_utc(),
                    BillingCycle.__table__.c.status != BillingCycleStatus.COMPLETED.value,
                    BillingCycle.__table__.c.completed_at.is_(None),
                )
            )
            .values(
                status=BillingCycleStatus.COMPLETED.value,
                completed_at=BillingCycle.__table__.c.end_date,
                updated_at=now_utc(),
            )
        )
        result = await session.execute(stmt)
        return result.rowcount


async def _get_unreconciled_cycles(limit: int = 100) -> List[Dict[str, Any]]:
    """Find completed cycles eligible for reconciliation."""
    async with get_transaction_context() as session:
        invoice_exists = (
            select(BillingInvoice.__table__.c.id)
            .where(
                and_(
                    BillingInvoice.__table__.c.billing_cycle_id == BillingCycle.id,
                    BillingInvoice.__table__.c.status == InvoiceStatus.PAID.value,
                )
            )
            .limit(1)
            .scalar_subquery()
        )

        completed_cutoff = now_utc() - timedelta(hours=24)

        query = (
            select(
                BillingCycle.id,
                BillingCycle.shop_subscription_id,
                BillingCycle.start_date,
                BillingCycle.end_date,
                BillingCycle.completed_at,
                ShopSubscription.shop_id,
            )
            .join(
                ShopSubscription,
                ShopSubscription.id == BillingCycle.shop_subscription_id,
            )
            .where(
                and_(
                    BillingCycle.status == BillingCycleStatus.COMPLETED.value,
                    BillingCycle.completed_at < completed_cutoff,
                    BillingCycle.reconciled_at.is_(None),
                    invoice_exists.is_not(None),
                )
            )
            .limit(limit)
        )

        result = await session.execute(query)
        rows = result.all()
        return [
            {
                "cycle_id": row.id,
                "shop_subscription_id": row.shop_subscription_id,
                "shop_id": row.shop_id,
                "start_date": row.start_date,
                "end_date": row.end_date,
                "completed_at": row.completed_at,
            }
            for row in rows
        ]


async def _reconcile_cycle(
    cycle_id: str,
    shop_id: str,
    start_date,
    end_date,
) -> Optional[Dict[str, Any]]:
    """Reconcile one billing cycle."""
    async with get_transaction_context() as session:
        intent_query = (
            select(func.coalesce(func.sum(CommissionRecord.commission_charged), Decimal("0")))
            .where(
                and_(
                    CommissionRecord.shop_id == shop_id,
                    CommissionRecord.order_date >= start_date,
                    CommissionRecord.order_date < end_date,
                    CommissionRecord.status == CommissionStatus.RECORDED.value,
                )
            )
        )
        intent_result = await session.execute(intent_query)
        intent = intent_result.scalar_one_or_none() or Decimal("0")

        actual_query = (
            select(func.coalesce(func.sum(BillingInvoice.usage_amount), Decimal("0")))
            .where(
                and_(
                    BillingInvoice.billing_cycle_id == cycle_id,
                    BillingInvoice.status == InvoiceStatus.PAID.value,
                )
            )
        )
        actual_result = await session.execute(actual_query)
        actual = actual_result.scalar_one_or_none() or Decimal("0")

        contributing_query = (
            select(CommissionRecord.id, CommissionRecord.commission_charged)
            .where(
                and_(
                    CommissionRecord.shop_id == shop_id,
                    CommissionRecord.order_date >= start_date,
                    CommissionRecord.order_date < end_date,
                    CommissionRecord.status == CommissionStatus.RECORDED.value,
                )
            )
        )
        contributing_result = await session.execute(contributing_query)
        contributing = [
            {"id": row.id, "commission_charged": float(row.commission_charged)}
            for row in contributing_result.all()
        ]

        delta = actual - intent
        tolerance = Decimal("0.01")
        is_mismatch = abs(delta) > tolerance

        if is_mismatch:
            logger.warning(
                {
                    "shop_id": shop_id,
                    "billing_cycle_id": cycle_id,
                    "intent": float(intent),
                    "actual": float(actual),
                    "delta": float(delta),
                    "contributing_commission_ids": [c["id"] for c in contributing],
                },
                "Billing reconciliation mismatch",
            )
            billing_reconciliation_mismatch_total.add(1)

        await session.execute(
            update(BillingCycle.__table__)
            .where(BillingCycle.__table__.c.id == cycle_id)
            .values(reconciled_at=now_utc(), updated_at=now_utc())
        )
        await session.commit()

    return {
        "cycle_id": cycle_id,
        "shop_id": shop_id,
        "intent": float(intent),
        "actual": float(actual),
        "delta": float(delta),
        "is_mismatch": is_mismatch,
        "contributing_commission_ids": [c["id"] for c in contributing],
    }


async def reconcile_billing_once(
    limit: int = 100,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Execute one reconciliation pass."""
    start_time = time.perf_counter()
    with tracer.start_as_current_span("reconciler.billing.sweep") as span:
        span.set_attribute("dry_run", dry_run)
        try:
            stale_completed = 0
            if not dry_run:
                stale_completed = await _complete_stale_cycles()

            cycles = await _get_unreconciled_cycles(limit)
            results: List[Dict[str, Any]] = []

            if not cycles:
                duration = time.perf_counter() - start_time
                reconciler_runs_total.add(
                    1, {"reconciler": "billing", "status": "success"}
                )
                reconciler_duration.record(duration, {"reconciler": "billing"})
                return {
                    "checked": 0,
                    "stale_completed": stale_completed,
                    "reconciled": 0,
                    "mismatches": 0,
                    "dry_run": dry_run,
                }

            logger.info(
                f"Billing reconciler checking {len(cycles)} cycles",
                extra={"reconciler": "billing", "checked": len(cycles)},
            )

            mismatches = 0
            for cycle in cycles:
                if dry_run:
                    results.append(
                        {
                            "cycle_id": cycle["cycle_id"],
                            "shop_id": cycle["shop_id"],
                            "dry_run": True,
                        }
                    )
                    continue

                try:
                    result = await _reconcile_cycle(
                        cycle_id=cycle["cycle_id"],
                        shop_id=cycle["shop_id"],
                        start_date=cycle["start_date"],
                        end_date=cycle["end_date"],
                    )
                    if result:
                        results.append(result)
                        if result.get("is_mismatch"):
                            mismatches += 1
                except Exception as exc:
                    logger.error(
                        f"Error reconciling cycle {cycle['cycle_id']}: {exc}",
                        exc_info=True,
                    )

            duration = time.perf_counter() - start_time
            reconciler_runs_total.add(
                1, {"reconciler": "billing", "status": "success"}
            )
            reconciler_duration.record(duration, {"reconciler": "billing"})

            logger.info(
                f"Billing reconciler completed: {len(cycles)} cycles checked, "
                f"{mismatches} mismatches, {stale_completed} stale cycles completed",
                extra={
                    "reconciler": "billing",
                    "checked": len(cycles),
                    "mismatches": mismatches,
                    "stale_completed": stale_completed,
                    "duration_sec": duration,
                },
            )

            return {
                "checked": len(cycles),
                "stale_completed": stale_completed,
                "reconciled": len(cycles),
                "mismatches": mismatches,
                "results": results,
                "dry_run": dry_run,
            }
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(StatusCode.ERROR, str(exc))
            duration = time.perf_counter() - start_time
            reconciler_runs_total.add(
                1, {"reconciler": "billing", "status": "error"}
            )
            reconciler_duration.record(duration, {"reconciler": "billing"})
            raise


async def run_forever(interval: int = RECONCILE_INTERVAL_SECONDS) -> None:
    """Run billing reconciler loop forever."""
    logger.info(f"Billing reconciler started (every {interval}s)")
    while True:
        try:
            async with claim("billing_reconciler") as mine:
                if mine:
                    await reconcile_billing_once()
        except asyncio.CancelledError:
            logger.info("Billing reconciler stopped")
            raise
        except Exception as exc:
            logger.error(f"Billing reconciler loop error: {exc}", exc_info=True)
        await asyncio.sleep(interval)
