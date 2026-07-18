"""
Standard metric definitions for BetterBundle Python Worker

All application metrics are defined here so they are created once (module-level)
and can be imported anywhere instrumentation is needed.
"""

from opentelemetry import metrics
from functools import lru_cache


@lru_cache(maxsize=1)
def get_meter() -> metrics.Meter:
    """Return the application meter singleton.

    ``lru_cache`` ensures the meter is created only once per process.
    """
    return metrics.get_meter(__name__)


# ---------------------------------------------------------------------------
# HTTP / request metrics
# ---------------------------------------------------------------------------
request_count = get_meter().create_counter(
    "http.requests.total",
    description="Total number of HTTP requests",
    unit="1",
)
request_duration = get_meter().create_histogram(
    "http.requests.duration",
    description="HTTP request duration in seconds",
    unit="s",
)

# ---------------------------------------------------------------------------
# Kafka metrics
# ---------------------------------------------------------------------------
kafka_messages_consumed = get_meter().create_counter(
    "kafka.messages.consumed",
    description="Total number of Kafka messages consumed",
    unit="1",
)
kafka_messages_produced = get_meter().create_counter(
    "kafka.messages.produced",
    description="Total number of Kafka messages produced",
    unit="1",
)
kafka_consumer_lag = get_meter().create_gauge(
    "kafka.consumer.lag",
    description="Current Kafka consumer lag",
    unit="1",
)

# ---------------------------------------------------------------------------
# Database metrics
# ---------------------------------------------------------------------------
db_query_duration = get_meter().create_histogram(
    "db.query.duration",
    description="Database query duration in seconds",
    unit="s",
)
db_connection_pool_size = get_meter().create_gauge(
    "db.connection_pool.size",
    description="Current database connection pool size",
    unit="1",
)

# ---------------------------------------------------------------------------
# Business metrics
# ---------------------------------------------------------------------------
recommendations_served = get_meter().create_counter(
    "recommendations.served",
    description="Total number of recommendations served",
    unit="1",
)
recommendation_duration = get_meter().create_histogram(
    "recommendation.duration",
    description="Recommendation computation duration in seconds",
    unit="s",
)

# ---------------------------------------------------------------------------
# Cache metrics
# ---------------------------------------------------------------------------
cache_hits = get_meter().create_counter(
    "cache.hits",
    description="Total number of cache hits",
    unit="1",
)
cache_misses = get_meter().create_counter(
    "cache.misses",
    description="Total number of cache misses",
    unit="1",
)
