"""Steps a shop's holdout down once its lift can be measured.

Why this exists
---------------
A shop starts with a large control arm because time-to-proof is the thing that
matters: until there is a measured lift, the claim that recommendations caused
revenue rests on attribution alone, and attribution is exactly what merchants
distrust about every competitor in this category. The merchant is asked to pay
before we can show them anything, which is the worst possible order.

Once enough control orders exist to measure lift, the large arm has done its
job. Holding shoppers back after that is withholding revenue to re-answer a
question already answered, so this drops the shop to the smaller monitoring
rate.

One way, once
-------------
The step is deliberately monotonic. `is_held_out` buckets on
`md5(shop:surface:identity) % 100 < percent`, so control is the band
`[0, percent)`. Lowering the percent leaves buckets below the new rate exactly
where they were and moves the rest into treatment; raising it later would move
them back, and a shopper seen in both arms inside one analysis window is
discarded by `partition_shoppers` as a crossover. Oscillating the rate would
therefore quietly delete the data it was trying to gather.

So a shop that has stepped down stays down, and `holdout_percent` is never
written again once set.
"""

import asyncio
import time
from typing import Any, Dict

from opentelemetry import trace
from opentelemetry.trace import StatusCode
from sqlalchemy import text

from app.core.database.session import get_transaction_context
from app.core.logging import get_logger
from app.core.metrics import reconciler_duration, reconciler_runs_total
from app.core.single_run import claim
from app.services.holdout_service import (
    EARNING_HOLDOUT_PERCENT,
    MIN_CONTROL_ORDERS,
)

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

# Hourly. The step-down is not urgent — being a few orders late costs a
# fraction of one order's lift — and a shop only ever crosses this line once.
TUNER_INTERVAL_SECONDS = 3600

# Distinct shoppers who were held out *and* bought. Counted over all time
# rather than a rolling window: this asks "have we ever gathered enough to
# measure?", which is a fact that does not expire, unlike the lift itself.
_CONTROL_ORDERS_SQL = text(
    """
    SELECT s.id AS shop_id,
           COUNT(DISTINCT COALESCE(oi.customer_id, oi.session_id)) AS control_buyers
    FROM shops s
    JOIN offer_impressions oi ON oi.shop_id = s.id
    WHERE s.holdout_percent IS NULL
      AND s.holdout_disabled = false
      AND oi.is_control = true
      AND oi.paid = true
      AND COALESCE(oi.customer_id, oi.session_id) IS NOT NULL
    GROUP BY s.id
    HAVING COUNT(DISTINCT COALESCE(oi.customer_id, oi.session_id)) >= :threshold
    """
)


async def sweep_once() -> Dict[str, Any]:
    """Step down every shop that has gathered enough control orders."""
    start_time = time.perf_counter()

    with tracer.start_as_current_span("reconciler.holdout_tuner.sweep") as span:
        try:
            async with get_transaction_context() as session:
                rows = (
                    await session.execute(
                        _CONTROL_ORDERS_SQL, {"threshold": MIN_CONTROL_ORDERS}
                    )
                ).all()

                stepped = []
                for row in rows:
                    await session.execute(
                        text(
                            """
                            UPDATE shops
                            SET holdout_percent = :pct
                            WHERE id = :shop_id AND holdout_percent IS NULL
                            """
                        ),
                        {"pct": EARNING_HOLDOUT_PERCENT, "shop_id": row.shop_id},
                    )
                    stepped.append((row.shop_id, row.control_buyers))

                await session.commit()

            duration = time.perf_counter() - start_time
            span.set_attribute("stepped_down", len(stepped))
            reconciler_runs_total.add(
                1, {"reconciler": "holdout_tuner", "status": "success"}
            )
            reconciler_duration.record(duration, {"reconciler": "holdout_tuner"})

            for shop_id, buyers in stepped:
                logger.info(
                    f"📉 Shop {shop_id}: {buyers} control orders reached, holdout "
                    f"stepped down to {EARNING_HOLDOUT_PERCENT}% — lift is now "
                    f"measurable and the large control arm has done its job",
                    extra={
                        "reconciler": "holdout_tuner",
                        "shop_id": shop_id,
                        "control_buyers": buyers,
                        "holdout_percent": EARNING_HOLDOUT_PERCENT,
                    },
                )

            return {"stepped_down": len(stepped), "duration_sec": duration}

        except Exception as e:
            duration = time.perf_counter() - start_time
            span.set_status(StatusCode.ERROR, str(e))
            reconciler_runs_total.add(
                1, {"reconciler": "holdout_tuner", "status": "error"}
            )
            reconciler_duration.record(duration, {"reconciler": "holdout_tuner"})
            logger.error(f"Holdout tuner sweep failed: {e}", exc_info=True)
            raise


async def run_forever(interval: int = TUNER_INTERVAL_SECONDS) -> None:
    """Sweep on a loop. Started at app startup, cancelled at shutdown."""
    logger.info(f"Holdout tuner started (every {interval}s)")
    while True:
        try:
            async with claim("holdout_tuner") as mine:
                if mine:
                    await sweep_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Holdout tuner sweep failed: {e}", exc_info=True)
        await asyncio.sleep(interval)
