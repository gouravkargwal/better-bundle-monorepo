"""
Reconciliation sweep for orders that were never attributed.

Why this has to exist
---------------------
Attribution is triggered by an order webhook. Webhooks get missed: Shopify
retries for 48 hours and then gives up, an app can be mid-deploy, a tunnel can
be down, a Kafka consumer can be rebalancing. When that happens the order still
reaches us — the periodic collection pulls it — but it arrives labelled as a
backfill, and backfilled orders are deliberately not attributed so that
importing a merchant's pre-install history cannot bill them for it.

The result is a silent revenue leak: the shopper accepted a recommendation, the
merchant made the sale, and we never charged for it or showed it in their
impact dashboard. Silent, because nothing in the system is looking.

Why a sweep can be precise here
-------------------------------
This is not "re-attribute everything and hope". A recommendation that led to a
purchase leaves a stamp on the order line — `_bb_rec_impression_id`, written by
the extension when the shopper added it to the cart. So the set of orders that
*should* have an attribution row is exactly knowable:

    orders with a stamped line item, and no purchase_attributions row

Everything else is left alone. The sweep publishes the same attribution job the
webhook would have, so the attribution engine's own invariants and idempotency
still apply — it cannot double-charge, because `_is_purchase_already_processed`
and the unique constraint on `commission_records.purchase_attribution_id` both
still hold.
"""

import logging
import time
from datetime import timedelta
from typing import Any, Dict, List

from opentelemetry import trace
from opentelemetry.trace import StatusCode
from sqlalchemy import text

from app.core.config.kafka_settings import kafka_settings
from app.core.database.session import get_transaction_context
from app.core.messaging.event_publisher import EventPublisher
from app.core.metrics import (
    attribution_missed_orders,
    reconciler_duration,
    reconciler_runs_total,
)
from app.shared.helpers import now_utc
from app.core.single_run import claim

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# How far back to look. Long enough to cover a weekend outage plus Shopify's
# own 48-hour retry window, short enough that the query stays cheap and that a
# months-old order never suddenly appears on a merchant's bill.
LOOKBACK_DAYS = 14

# Orders published per sweep. Bounded so a backlog drains over several passes
# instead of flooding the attribution consumer in one burst.
MAX_ORDERS_PER_SWEEP = 200

# `properties` is a `json` column, not `jsonb`, so it needs an explicit cast
# before the `?` containment operator will accept it.
# Orders still owing an attribution.
#
# Reads `order_data.attribution_state`, which is set once when the order is
# written, and is backed by a partial index containing only 'pending' rows. So
# the cost of a sweep tracks the size of the backlog — normally zero — not the
# merchant's order volume.
#
# What this replaced, and why: it used to join every order in the window to its
# line items and test `l.properties::jsonb ? :stamp_key`. Casting `properties`
# (a `json` column) to `jsonb` makes the predicate a functional expression, so
# no index can serve it — every pass sequentially scanned every recent line item
# to re-derive a fact already known at write time, 96 times a day, almost always
# finding nothing. That is fine at a hundred orders and ruinous at a hundred
# thousand.
#
# `attribution_attempts` bounds the retries: an order that cannot be attributed
# is dead-lettered rather than republished every 15 minutes until it ages out of
# the window.
_UNATTRIBUTED_STAMPED_ORDERS = text(
    """
    SELECT shop_id, order_id
    FROM order_data
    WHERE attribution_state = 'pending'
      AND order_date >= :since
      AND attribution_attempts < :max_attempts
    ORDER BY order_date DESC
    LIMIT :limit
    """
)

# Attempts before an order is dead-lettered as 'failed'. Matches the shape used
# by product_enrichments, where the same runaway-retry problem was solved.
MAX_ATTRIBUTION_ATTEMPTS = 5

STAMP_KEY = "_bb_rec_impression_id"


async def find_unattributed_orders(
    lookback_days: int = LOOKBACK_DAYS,
    limit: int = MAX_ORDERS_PER_SWEEP,
) -> List[Dict[str, str]]:
    """Orders carrying recommendation evidence but with no attribution row."""
    since = now_utc().replace(microsecond=0) - timedelta(days=lookback_days)

    async with get_transaction_context() as session:
        rows = (
            await session.execute(
                _UNATTRIBUTED_STAMPED_ORDERS,
                {
                    "since": since,
                    "limit": limit,
                    "max_attempts": MAX_ATTRIBUTION_ATTEMPTS,
                },
            )
        ).all()

    return [{"shop_id": r.shop_id, "order_id": r.order_id} for r in rows]


async def _count_attempt(rows: List[Dict[str, str]]) -> None:
    """Charge each republished order an attempt, dead-lettering at the ceiling.

    Counted on publish rather than on failure, because the failure usually
    happens somewhere this function cannot see — a consumer that never picks the
    job up, or picks it up and dies. Counting the attempt here means an order
    that silently never completes still stops being retried, which is the whole
    point of the ceiling.
    """
    if not rows:
        return

    async with get_transaction_context() as session:
        for row in rows:
            await session.execute(
                text(
                    """
                    UPDATE order_data
                    SET attribution_attempts = attribution_attempts + 1,
                        attribution_state = CASE
                            WHEN attribution_attempts + 1 >= :max_attempts
                            THEN 'failed' ELSE attribution_state END,
                        attribution_last_error = CASE
                            WHEN attribution_attempts + 1 >= :max_attempts
                            THEN 'gave up after ' || (attribution_attempts + 1)
                                 || ' reconciliation attempts'
                            ELSE attribution_last_error END
                    WHERE shop_id = :shop_id AND order_id = :order_id
                      AND attribution_state = 'pending'
                    """
                ),
                {
                    "shop_id": row["shop_id"],
                    "order_id": row["order_id"],
                    "max_attempts": MAX_ATTRIBUTION_ATTEMPTS,
                },
            )


async def reconcile_once(
    lookback_days: int = LOOKBACK_DAYS,
    limit: int = MAX_ORDERS_PER_SWEEP,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """One pass: find missed orders and republish their attribution jobs."""
    start_time = time.perf_counter()
    with tracer.start_as_current_span("reconciler.attribution.sweep") as span:
        span.set_attribute("dry_run", dry_run)
        try:
            missed = await find_unattributed_orders(lookback_days, limit)
            span.set_attribute("found", len(missed))
            if not missed:
                span.set_attribute("published", 0)
                duration = time.perf_counter() - start_time
                reconciler_runs_total.add(1, {"reconciler": "attribution", "status": "success"})
                reconciler_duration.record(duration, {"reconciler": "attribution"})
                return {"found": 0, "published": 0, "dry_run": dry_run}

            logger.warning(
                f"⚠️ Attribution reconciliation found {len(missed)} stamped orders with "
                f"no attribution — a webhook was almost certainly missed",
                extra={"reconciler": "attribution", "found": len(missed), "dry_run": dry_run},
            )

            if dry_run:
                span.set_attribute("published", 0)
                duration = time.perf_counter() - start_time
                reconciler_runs_total.add(1, {"reconciler": "attribution", "status": "success"})
                reconciler_duration.record(duration, {"reconciler": "attribution"})
                return {"found": len(missed), "published": 0, "dry_run": True}

            attribution_missed_orders.add(len(missed))

            publisher = EventPublisher(kafka_settings.model_dump())
            await publisher.initialize()
            published = 0
            try:
                for row in missed:
                    try:
                        await publisher.publish_purchase_attribution_event(
                            {
                                "event_type": "purchase_ready_for_attribution",
                                "shop_id": row["shop_id"],
                                "order_id": row["order_id"],
                                "timestamp": now_utc().isoformat(),
                                # Marked so the origin of a late attribution is
                                # traceable when a merchant asks why a charge appeared
                                # days after the order.
                                "trigger": "reconciliation",
                            }
                        )
                        published += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to republish attribution for order "
                            f"{row['order_id']}: {e}"
                        )
            finally:
                await publisher.close()

            await _count_attempt(missed)

            span.set_attribute("published", published)
            duration = time.perf_counter() - start_time
            reconciler_runs_total.add(1, {"reconciler": "attribution", "status": "success"})
            reconciler_duration.record(duration, {"reconciler": "attribution"})

            logger.info(
                f"✅ Attribution reconciliation republished {published}/{len(missed)} orders",
                extra={
                    "reconciler": "attribution",
                    "found": len(missed),
                    "published": published,
                    "duration_sec": duration,
                },
            )
            return {"found": len(missed), "published": published, "dry_run": False}
        except Exception as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            duration = time.perf_counter() - start_time
            reconciler_runs_total.add(1, {"reconciler": "attribution", "status": "error"})
            reconciler_duration.record(duration, {"reconciler": "attribution"})
            raise


# How often to sweep. Attribution is not latency-critical — a missed order
# being picked up within the hour is fine — and a long interval keeps the
# query off the hot path.
RECONCILE_INTERVAL_SECONDS = 900


async def run_forever(interval: int = RECONCILE_INTERVAL_SECONDS) -> None:
    """Sweep on a loop. Started at app startup, cancelled at shutdown."""
    import asyncio

    logger.info(f"Attribution reconciler started (every {interval}s)")
    while True:
        try:
            await asyncio.sleep(interval)
            # Only one worker per cycle, or four of them sweep the same rows.
            async with claim("attribution_reconciler") as mine:
                if mine:
                    result = await reconcile_once()
                    if result["found"]:
                        logger.info(f"Attribution reconciliation: {result}")
        except asyncio.CancelledError:
            logger.info("Attribution reconciler stopped")
            raise
        except Exception as e:
            # Never let the loop die. A reconciler that exits on its first
            # unexpected error removes the safety net without saying so.
            logger.error(f"Attribution reconciliation failed: {e}", exc_info=True)
