"""
Metric definitions for the BetterBundle Python Worker.

Naming follows OpenTelemetry semantic conventions where one exists, and the
`betterbundle.*` namespace where one does not — which is what semconv itself
prescribes for application-specific metrics, so that ours can never collide
with a name the spec later standardises.

Two rules this file now obeys that it did not before:

1. NOTHING HERE DUPLICATES AUTO-INSTRUMENTATION. `http.requests.total` and
   `http.requests.duration` used to be recorded by a middleware in main.py,
   while opentelemetry-instrumentation-fastapi was independently recording the
   same three facts as `http.server.duration`, `http.server.active_requests`
   and friends. That is where half of the 42 metric streams in OpenObserve came
   from: two names for one measurement, neither obviously canonical. The
   middleware is gone; the auto-instrumentation is the single source.

2. NOTHING HERE IS UNRECORDED. Six metrics were defined and never called from
   anywhere: db.query.duration, db.connection_pool.size, kafka.messages.produced,
   kafka.consumer.lag, llm.token_usage and llm.cost. They are deleted rather
   than kept "for later" — an always-empty stream is worse than a missing one,
   because a dashboard panel or alert built on it looks healthy while measuring
   nothing. The Kafka consumer-lag alert was doing exactly that.

Add a metric here at the moment you add the call that records it, not before.
"""

from functools import lru_cache

from opentelemetry import metrics

# Namespace for metrics with no OpenTelemetry semantic convention. Prefixing is
# the spec's own guidance for application metrics: it keeps ours distinguishable
# from anything the ecosystem standardises later.
NS = "betterbundle"


@lru_cache(maxsize=1)
def get_meter() -> metrics.Meter:
    """Return the application meter singleton.

    ``lru_cache`` ensures the meter is created only once per process.
    """
    return metrics.get_meter(__name__)


# ---------------------------------------------------------------------------
# Messaging — OpenTelemetry semantic conventions
# ---------------------------------------------------------------------------
# `messaging.client.consumed.messages` is the semconv name; the old
# `kafka.messages.consumed` said the same thing in a vocabulary only this repo
# spoke, so no off-the-shelf dashboard or exporter could read it.
kafka_messages_consumed = get_meter().create_counter(
    "messaging.client.consumed.messages",
    description="Messages consumed from the broker",
    unit="{message}",
)

# ---------------------------------------------------------------------------
# Recommendations — application-specific, namespaced
# ---------------------------------------------------------------------------
recommendations_served = get_meter().create_counter(
    f"{NS}.recommendations.served",
    description="Recommendations returned to a storefront surface",
    unit="{recommendation}",
)
recommendation_duration = get_meter().create_histogram(
    f"{NS}.recommendation.duration",
    description="Time to serve a recommendation request",
    unit="s",
)

# ---------------------------------------------------------------------------
# LLM usage — OpenTelemetry GenAI semantic conventions
# ---------------------------------------------------------------------------
# `gen_ai.client.token.usage` is the semconv name and shape: a histogram, split
# by a `gen_ai.token.type` attribute of "input" or "output", because input and
# output tokens are priced differently everywhere and a single total cannot be
# costed after the fact.
#
# This replaces an `llm.token_usage` counter that was defined here and recorded
# nowhere — the reason the old "Application Performance & Costs" dashboard had a
# cost section with no cost in it.
gen_ai_token_usage = get_meter().create_histogram(
    "gen_ai.client.token.usage",
    description="Tokens used per LLM request, split by input/output",
    unit="{token}",
)

# No semantic convention exists for spend, so it is namespaced. Recorded in USD
# at the moment of the call, because the price of a model is a property of when
# it ran — repricing old usage from today's table gives the wrong number.
gen_ai_cost = get_meter().create_counter(
    f"{NS}.gen_ai.cost",
    description="Estimated LLM spend in USD",
    unit="USD",
)

# ---------------------------------------------------------------------------
# Cache — application-specific, namespaced
# ---------------------------------------------------------------------------
# Two counters rather than one with a `hit`/`miss` attribute: the hit-ratio
# alert divides one by the other, and OpenObserve cannot divide across two
# attribute values of a single stream without a subquery per side.
cache_hits = get_meter().create_counter(
    f"{NS}.cache.hits",
    description="Cache lookups served from cache",
    unit="{operation}",
)
cache_misses = get_meter().create_counter(
    f"{NS}.cache.misses",
    description="Cache lookups that fell through to the source",
    unit="{operation}",
)

# ---------------------------------------------------------------------------
# Reconcilers & background jobs — application-specific, namespaced
# ---------------------------------------------------------------------------
reconciler_runs_total = get_meter().create_counter(
    f"{NS}.reconciler.runs.total",
    description="Background reconciler run executions",
    unit="{run}",
)
reconciler_duration = get_meter().create_histogram(
    f"{NS}.reconciler.duration",
    description="Time taken to execute a reconciler run pass",
    unit="s",
)
attribution_missed_orders = get_meter().create_counter(
    f"{NS}.reconciler.attribution.missed_orders",
    description="Missed stamped orders discovered during attribution reconciliation",
    unit="{order}",
)
rollover_reactivated_shops = get_meter().create_counter(
    f"{NS}.reconciler.rollover.reactivated_shops",
    description="Suspended shops reactivated upon Shopify usage cycle renewal",
    unit="{shop}",
)
rollover_drained_commissions = get_meter().create_counter(
    f"{NS}.reconciler.rollover.drained_commissions",
    description="Pending commissions drained upon shop reactivation",
    unit="{commission}",
)
backstop_missed_orders = get_meter().create_counter(
    f"{NS}.reconciler.backstop.missed_orders",
    description="Missing orders detected and ingested by the ingestion backstop",
    unit="{order}",
)

