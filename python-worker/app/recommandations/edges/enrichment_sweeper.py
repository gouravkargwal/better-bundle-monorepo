"""
The thing that actually retries failed LLM enrichment.

Everything else in this package records *that* enrichment failed. This is what
comes back and does it again.

Why a sweeper and not in-process retries
----------------------------------------
`GeminiProvider` already retries twice with backoff inside a single call. That
covers a blip. It cannot cover:

  - the container restarting mid-pass (the coroutine dies with it)
  - a daily quota being exhausted (retrying in-process just burns rate limit)
  - a shop whose catalog goes quiet, so no `products/update` webhook ever
    arrives to re-trigger the pipeline

Those need a retry that outlives the request, which means durable state plus
something that reads it. The state is `product_enrichments`; this is the reader.

What it retries
---------------
Only the specific products that are outstanding and past their backoff — never
a full catalog pass. A shop with 2,000 products and 20 failures costs one API
call. See `EdgeInstallPipeline.retry_failed_enrichment`.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List

from opentelemetry import trace
from opentelemetry.trace import StatusCode

from .enrichment_store import shops_needing_enrichment
from .install import EdgeInstallPipeline
from .llm_budget import BudgetExceeded, CircuitOpen, LLMBudget
from app.core.metrics import (
    reconciler_duration,
    reconciler_runs_total,
)
from app.core.single_run import claim

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

# How often to look for outstanding work. The per-product backoff in
# `enrichment_store.RETRY_BACKOFF_MINUTES` decides what is actually due, so
# this only needs to be finer-grained than the shortest backoff.
SWEEP_INTERVAL_SECONDS = 120

# Shops per sweep. Bounded so one sweep cannot fan out across every shop on the
# platform and exhaust the API quota in a single pass.
SHOPS_PER_SWEEP = 10


async def sweep_once() -> Dict[str, Any]:
    """One pass: find shops with due work and retry just their failed products."""
    start_time = time.perf_counter()
    with tracer.start_as_current_span("reconciler.enrichment.sweep") as span:
        try:
            # Ask the guards first. If the circuit is open or the day's ceiling is
            # spent, doing nothing is the correct behaviour — walking the shop list to
            # generate a failure per shop is exactly the spend the breaker exists to
            # prevent.
            budget = LLMBudget()
            try:
                await budget.check()
            except (CircuitOpen, BudgetExceeded) as e:
                duration = time.perf_counter() - start_time
                span.set_attribute("skipped", True)
                span.set_attribute("skip_reason", str(e))
                span.set_attribute("shops", 0)
                span.set_attribute("retried", 0)
                span.set_attribute("recovered", 0)
                reconciler_runs_total.add(1, {"reconciler": "enrichment", "status": "skipped"})
                reconciler_duration.record(duration, {"reconciler": "enrichment"})
                logger.info(
                    f"Enrichment sweep skipped: {e}",
                    extra={"reconciler": "enrichment", "skipped": True, "reason": str(e), "duration_sec": duration},
                )
                return {"shops": 0, "retried": 0, "recovered": 0, "skipped": str(e)}

            shop_ids: List[str] = await shops_needing_enrichment(limit=SHOPS_PER_SWEEP)
            if not shop_ids:
                duration = time.perf_counter() - start_time
                span.set_attribute("shops", 0)
                span.set_attribute("retried", 0)
                span.set_attribute("recovered", 0)
                reconciler_runs_total.add(1, {"reconciler": "enrichment", "status": "success"})
                reconciler_duration.record(duration, {"reconciler": "enrichment"})
                return {"shops": 0, "retried": 0, "recovered": 0}

            pipeline = EdgeInstallPipeline()
            retried = 0
            recovered = 0

            for shop_id in shop_ids:
                try:
                    # Re-check between shops: an outage discovered on shop 1 must stop
                    # shops 2..10, not be rediscovered nine more times.
                    await budget.check()
                    report = await pipeline.retry_failed_enrichment(shop_id)
                    retried += report.products
                    recovered += report.enriched
                    if report.products:
                        logger.info(
                            f"Enrichment retry for shop {shop_id}: "
                            f"{report.enriched}/{report.products} recovered, "
                            f"{report.prior_edges} priors written",
                            extra={
                                "reconciler": "enrichment",
                                "shop_id": shop_id,
                                "recovered": report.enriched,
                                "products": report.products,
                                "prior_edges": report.prior_edges,
                            },
                        )
                except (CircuitOpen, BudgetExceeded) as e:
                    logger.info(
                        f"Enrichment sweep stopping early: {e}",
                        extra={"reconciler": "enrichment", "stopped_early": True, "reason": str(e)},
                    )
                    break
                except Exception as e:
                    # One bad shop must not end the sweep — the others still have work
                    # waiting, and this shop's rows keep their attempt count so it will
                    # be picked up again (or dead-lettered) on a later pass.
                    logger.error(
                        f"Enrichment retry failed for shop {shop_id}: {e}",
                        exc_info=True,
                        extra={"reconciler": "enrichment", "shop_id": shop_id},
                    )

            span.set_attribute("shops", len(shop_ids))
            span.set_attribute("retried", retried)
            span.set_attribute("recovered", recovered)

            duration = time.perf_counter() - start_time
            reconciler_runs_total.add(1, {"reconciler": "enrichment", "status": "success"})
            reconciler_duration.record(duration, {"reconciler": "enrichment"})

            logger.info(
                f"Enrichment sweep complete: {recovered}/{retried} products recovered across {len(shop_ids)} shops",
                extra={
                    "reconciler": "enrichment",
                    "shops": len(shop_ids),
                    "retried": retried,
                    "recovered": recovered,
                    "duration_sec": duration,
                },
            )
            return {"shops": len(shop_ids), "retried": retried, "recovered": recovered}
        except Exception as e:
            span.record_exception(e)
            span.set_status(StatusCode.ERROR, str(e))
            duration = time.perf_counter() - start_time
            reconciler_runs_total.add(1, {"reconciler": "enrichment", "status": "error"})
            reconciler_duration.record(duration, {"reconciler": "enrichment"})
            raise


async def run_forever(interval: int = SWEEP_INTERVAL_SECONDS) -> None:
    """Sweep on a loop. Started at app startup, cancelled at shutdown."""
    logger.info(f"Enrichment sweeper started (every {interval}s)")
    while True:
        try:
            await asyncio.sleep(interval)
            # Only one worker per cycle. Without this, four uvicorn workers
            # each retried the same unenriched products, paying for the same
            # LLM enrichment call four times over.
            async with claim("enrichment_sweeper") as mine:
                if mine:
                    result = await sweep_once()
                    if result["shops"]:
                        logger.info(f"Enrichment sweep: {result}")
        except asyncio.CancelledError:
            logger.info("Enrichment sweeper stopped")
            raise
        except Exception as e:
            # Never let the loop die: a sweeper that exits on its first
            # unexpected error is worse than no sweeper, because the retry
            # guarantee silently disappears.
            logger.error(f"Enrichment sweep failed: {e}", exc_info=True)
