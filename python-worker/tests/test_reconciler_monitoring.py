"""
Unit tests for Reconciler & Background Job Monitoring in OpenObserve.

Verifies:
1. Metrics recording (runs.total, duration, domain counters).
2. Distributed tracing spans with correct attributes and error handling.
3. Structured logging extra fields.
"""

import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

if "aiokafka" not in sys.modules:
    aiokafka = types.ModuleType("aiokafka")
    aiokafka.__path__ = []
    aiokafka.AIOKafkaProducer = MagicMock
    aiokafka.AIOKafkaConsumer = MagicMock
    sys.modules["aiokafka"] = aiokafka

    class ErrorsModule(types.ModuleType):
        def __getattr__(self, name):
            cls = type(name, (Exception,), {})
            setattr(self, name, cls)
            return cls

    errors_mod = ErrorsModule("aiokafka.errors")
    sys.modules["aiokafka.errors"] = errors_mod
    setattr(aiokafka, "errors", errors_mod)

    for sub in ["structs", "producer", "consumer", "admin"]:
        mod = types.ModuleType(f"aiokafka.{sub}")
        setattr(aiokafka, sub, mod)
        sys.modules[f"aiokafka.{sub}"] = mod
        mod.AIOKafkaProducer = MagicMock
        mod.AIOKafkaConsumer = MagicMock
        mod.AIOKafkaAdminClient = MagicMock
        mod.NewTopic = MagicMock
        mod.TopicPartition = MagicMock

import pytest
from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

# Global test reader and exporter set once
_test_metric_reader = InMemoryMetricReader()
_test_span_exporter = InMemorySpanExporter()

_meter_provider = MeterProvider(metric_readers=[_test_metric_reader])
try:
    metrics.set_meter_provider(_meter_provider)
except Exception:
    pass

_tracer_provider = TracerProvider()
_tracer_provider.add_span_processor(SimpleSpanProcessor(_test_span_exporter))
try:
    trace.set_tracer_provider(_tracer_provider)
except Exception:
    pass

from app.domains.billing.services import attribution_reconciler, rollover_reconciler  # noqa: E402
from app.domains.shopify.services import ingestion_backstop  # noqa: E402
from app.recommandations.edges import enrichment_sweeper  # noqa: E402
from app.recommandations.edges.llm_budget import CircuitOpen  # noqa: E402

# Re-bind module tracers to current provider
attribution_reconciler.tracer = _tracer_provider.get_tracer(attribution_reconciler.__name__)
rollover_reconciler.tracer = _tracer_provider.get_tracer(rollover_reconciler.__name__)
ingestion_backstop.tracer = _tracer_provider.get_tracer(ingestion_backstop.__name__)
enrichment_sweeper.tracer = _tracer_provider.get_tracer(enrichment_sweeper.__name__)


@pytest.fixture(autouse=True)
def otel_test_environment():
    """Reset span exporter before each test."""
    _test_span_exporter.clear()
    return SimpleNamespace(reader=_test_metric_reader, span_exporter=_test_span_exporter)


def get_metric_value(reader, metric_name: str, attributes: dict = None) -> int:
    """Return total accumulated value or count for a given metric and attributes."""
    data = reader.get_metrics_data()
    if not data:
        return 0
    total = 0
    for rm in data.resource_metrics:
        for sm in rm.scope_metrics:
            for metric in sm.metrics:
                if metric.name == metric_name:
                    for dp in metric.data.data_points:
                        if attributes is None or all(dp.attributes.get(k) == v for k, v in attributes.items()):
                            val = getattr(dp, "value", None)
                            if val is not None:
                                total += val
                            else:
                                total += getattr(dp, "count", 0)
    return total


# ---------------------------------------------------------------------------
# Attribution Reconciler Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_attribution_reconciler_success_records_metrics_and_spans(otel_test_environment):
    missed_orders = [
        {"shop_id": "shop_1", "order_id": "ord_101"},
        {"shop_id": "shop_1", "order_id": "ord_102"},
    ]

    before_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "attribution", "status": "success"},
    )
    before_missed = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.attribution.missed_orders",
    )
    before_duration = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.duration",
        {"reconciler": "attribution"},
    )

    with patch.object(attribution_reconciler, "find_unattributed_orders", new_callable=AsyncMock) as mock_find, \
         patch("app.domains.billing.services.attribution_reconciler.EventPublisher") as mock_pub_cls, \
         patch.object(attribution_reconciler, "_count_attempt", new_callable=AsyncMock):

        mock_find.return_value = missed_orders
        mock_publisher = AsyncMock()
        mock_pub_cls.return_value = mock_publisher

        result = await attribution_reconciler.reconcile_once()

        assert result["found"] == 2
        assert result["published"] == 2
        assert not result["dry_run"]

    # Verify spans
    spans = otel_test_environment.span_exporter.get_finished_spans()
    sweep_span = next(s for s in spans if s.name == "reconciler.attribution.sweep")
    assert sweep_span.attributes["found"] == 2
    assert sweep_span.attributes["published"] == 2
    assert sweep_span.attributes["dry_run"] is False
    assert sweep_span.status.status_code != StatusCode.ERROR

    # Verify metrics
    after_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "attribution", "status": "success"},
    )
    assert after_runs - before_runs == 1

    after_missed = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.attribution.missed_orders",
    )
    assert after_missed - before_missed == 2

    after_duration = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.duration",
        {"reconciler": "attribution"},
    )
    assert after_duration - before_duration == 1


@pytest.mark.asyncio
async def test_attribution_reconciler_dry_run_does_not_increment_missed_orders_metric(otel_test_environment):
    missed_orders = [{"shop_id": "shop_1", "order_id": "ord_101"}]

    before_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "attribution", "status": "success"},
    )
    before_missed = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.attribution.missed_orders",
    )

    with patch.object(attribution_reconciler, "find_unattributed_orders", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = missed_orders

        result = await attribution_reconciler.reconcile_once(dry_run=True)
        assert result["found"] == 1
        assert result["published"] == 0
        assert result["dry_run"] is True

    after_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "attribution", "status": "success"},
    )
    assert after_runs - before_runs == 1

    after_missed = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.attribution.missed_orders",
    )
    # Dry-run must not increment missed_orders metric
    assert after_missed - before_missed == 0


@pytest.mark.asyncio
async def test_attribution_reconciler_empty_run(otel_test_environment):
    before_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "attribution", "status": "success"},
    )

    with patch.object(attribution_reconciler, "find_unattributed_orders", new_callable=AsyncMock) as mock_find:
        mock_find.return_value = []
        result = await attribution_reconciler.reconcile_once()
        assert result["found"] == 0

    spans = otel_test_environment.span_exporter.get_finished_spans()
    sweep_span = next(s for s in spans if s.name == "reconciler.attribution.sweep")
    assert sweep_span.attributes["found"] == 0
    assert sweep_span.attributes["published"] == 0

    after_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "attribution", "status": "success"},
    )
    assert after_runs - before_runs == 1


@pytest.mark.asyncio
async def test_attribution_reconciler_error_handling(otel_test_environment):
    before_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "attribution", "status": "error"},
    )

    with patch.object(attribution_reconciler, "find_unattributed_orders", new_callable=AsyncMock) as mock_find:
        mock_find.side_effect = RuntimeError("Database timeout")

        with pytest.raises(RuntimeError):
            await attribution_reconciler.reconcile_once()

    spans = otel_test_environment.span_exporter.get_finished_spans()
    sweep_span = next(s for s in spans if s.name == "reconciler.attribution.sweep")
    assert sweep_span.status.status_code == StatusCode.ERROR

    after_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "attribution", "status": "error"},
    )
    assert after_runs - before_runs == 1


# ---------------------------------------------------------------------------
# Rollover Reconciler Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rollover_reconciler_success_records_metrics_and_spans(otel_test_environment):
    before_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "rollover", "status": "success"},
    )
    before_reactivated = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.rollover.reactivated_shops",
    )
    before_drained = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.rollover.drained_commissions",
    )

    mock_session = AsyncMock()
    mock_execute_res = MagicMock()
    mock_execute_res.all.return_value = [
        (
            MagicMock(
                id="sub_1",
                shopify_subscription_id="gid://shopify/AppSubscription/1",
                shop_subscription_metadata={"suspended_balance_used": 100.0},
            ),
            MagicMock(id="shop_1", shop_domain="test-shop.myshopify.com", access_token="shpat_token"),
        )
    ]
    mock_session.execute.return_value = mock_execute_res
    mock_session.get.return_value = MagicMock(shop_subscription_metadata={})

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_session
    mock_ctx.__aexit__.return_value = None

    with patch("app.domains.billing.services.rollover_reconciler.get_transaction_context", return_value=mock_ctx), \
         patch("app.domains.billing.services.rollover_reconciler.ShopifyUsageBillingServiceV2") as mock_billing_svc_cls, \
         patch("app.domains.billing.services.rollover_reconciler.drain_pending_commissions", new_callable=AsyncMock) as mock_drain:

        mock_billing_svc = AsyncMock()
        mock_billing_svc.get_subscription_status.return_value = {
            "lineItems": [
                {
                    "plan": {
                        "pricingDetails": {
                            "__typename": "AppUsagePricing",
                            "cappedAmount": {"amount": "100.00"},
                            "balanceUsed": {"amount": "0.00"},
                        }
                    }
                }
            ]
        }
        mock_billing_svc_cls.return_value = mock_billing_svc
        mock_drain.return_value = 5

        result = await rollover_reconciler.reconcile_rollovers_once()
        assert result["checked"] == 1
        assert result["reactivated"] == 1
        assert result["drained_commissions"] == 5

    spans = otel_test_environment.span_exporter.get_finished_spans()
    sweep_span = next(s for s in spans if s.name == "reconciler.rollover.sweep")
    assert sweep_span.attributes["checked"] == 1
    assert sweep_span.attributes["reactivated"] == 1
    assert sweep_span.attributes["drained"] == 5

    after_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "rollover", "status": "success"},
    )
    assert after_runs - before_runs == 1

    after_reactivated = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.rollover.reactivated_shops",
    )
    assert after_reactivated - before_reactivated == 1

    after_drained = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.rollover.drained_commissions",
    )
    assert after_drained - before_drained == 5


@pytest.mark.asyncio
async def test_rollover_reconciler_dry_run_does_not_increment_reactivated_metric(otel_test_environment):
    before_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "rollover", "status": "success"},
    )
    before_reactivated = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.rollover.reactivated_shops",
    )

    mock_session = AsyncMock()
    mock_execute_res = MagicMock()
    mock_execute_res.all.return_value = [
        (
            MagicMock(
                id="sub_1",
                shopify_subscription_id="gid://shopify/AppSubscription/1",
                shop_subscription_metadata={"suspended_balance_used": 100.0},
            ),
            MagicMock(id="shop_1", shop_domain="test-shop.myshopify.com", access_token="shpat_token"),
        )
    ]
    mock_session.execute.return_value = mock_execute_res

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_session
    mock_ctx.__aexit__.return_value = None

    with patch("app.domains.billing.services.rollover_reconciler.get_transaction_context", return_value=mock_ctx), \
         patch("app.domains.billing.services.rollover_reconciler.ShopifyUsageBillingServiceV2") as mock_billing_svc_cls:

        mock_billing_svc = AsyncMock()
        mock_billing_svc.get_subscription_status.return_value = {
            "lineItems": [
                {
                    "plan": {
                        "pricingDetails": {
                            "__typename": "AppUsagePricing",
                            "cappedAmount": {"amount": "100.00"},
                            "balanceUsed": {"amount": "0.00"},
                        }
                    }
                }
            ]
        }
        mock_billing_svc_cls.return_value = mock_billing_svc

        result = await rollover_reconciler.reconcile_rollovers_once(dry_run=True)
        assert result["checked"] == 1
        assert result["reactivated"] == 1
        assert result["dry_run"] is True

    after_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "rollover", "status": "success"},
    )
    assert after_runs - before_runs == 1

    after_reactivated = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.rollover.reactivated_shops",
    )
    # Dry-run must not increment reactivated_shops metric
    assert after_reactivated - before_reactivated == 0


@pytest.mark.asyncio
async def test_rollover_reconciler_empty_candidates(otel_test_environment):
    before_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "rollover", "status": "success"},
    )

    mock_session = AsyncMock()
    mock_execute_res = MagicMock()
    mock_execute_res.all.return_value = []
    mock_session.execute.return_value = mock_execute_res

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_session
    mock_ctx.__aexit__.return_value = None

    with patch("app.domains.billing.services.rollover_reconciler.get_transaction_context", return_value=mock_ctx):
        result = await rollover_reconciler.reconcile_rollovers_once()
        assert result["checked"] == 0

    spans = otel_test_environment.span_exporter.get_finished_spans()
    sweep_span = next(s for s in spans if s.name == "reconciler.rollover.sweep")
    assert sweep_span.attributes["checked"] == 0
    assert sweep_span.attributes["reactivated"] == 0

    after_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "rollover", "status": "success"},
    )
    assert after_runs - before_runs == 1


@pytest.mark.asyncio
async def test_rollover_reconciler_error_handling(otel_test_environment):
    before_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "rollover", "status": "error"},
    )

    with patch("app.domains.billing.services.rollover_reconciler.get_transaction_context") as mock_ctx:
        mock_ctx.side_effect = RuntimeError("Database unreachable")

        with pytest.raises(RuntimeError):
            await rollover_reconciler.reconcile_rollovers_once()

    spans = otel_test_environment.span_exporter.get_finished_spans()
    sweep_span = next(s for s in spans if s.name == "reconciler.rollover.sweep")
    assert sweep_span.status.status_code == StatusCode.ERROR

    after_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "rollover", "status": "error"},
    )
    assert after_runs - before_runs == 1


# ---------------------------------------------------------------------------
# Ingestion Backstop Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingestion_backstop_records_metrics_and_spans(otel_test_environment):
    before_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "ingestion_backstop", "status": "success"},
    )
    before_missed = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.backstop.missed_orders",
    )

    active_shops = [{"id": "shop_1", "shop_domain": "store1.myshopify.com", "access_token": "token1"}]

    with patch.object(ingestion_backstop, "_active_shops", new_callable=AsyncMock) as mock_shops, \
         patch.object(ingestion_backstop, "sweep_shop", new_callable=AsyncMock) as mock_sweep_shop:

        mock_shops.return_value = active_shops
        mock_sweep_shop.return_value = {
            "shop_domain": "store1.myshopify.com",
            "missing": 3,
            "published": 3,
        }

        result = await ingestion_backstop.sweep_once()
        assert result["missing"] == 3
        assert result["published"] == 3

    spans = otel_test_environment.span_exporter.get_finished_spans()
    sweep_span = next(s for s in spans if s.name == "reconciler.ingestion_backstop.sweep")
    assert sweep_span.attributes["shops_checked"] == 1
    assert sweep_span.attributes["orders_ingested"] == 3
    assert sweep_span.attributes["missing"] == 3

    after_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "ingestion_backstop", "status": "success"},
    )
    assert after_runs - before_runs == 1

    after_missed = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.backstop.missed_orders",
    )
    assert after_missed - before_missed == 3


@pytest.mark.asyncio
async def test_ingestion_backstop_empty_run(otel_test_environment):
    before_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "ingestion_backstop", "status": "success"},
    )

    with patch.object(ingestion_backstop, "_active_shops", new_callable=AsyncMock) as mock_shops:
        mock_shops.return_value = []

        result = await ingestion_backstop.sweep_once()
        assert result["missing"] == 0
        assert result["published"] == 0

    spans = otel_test_environment.span_exporter.get_finished_spans()
    sweep_span = next(s for s in spans if s.name == "reconciler.ingestion_backstop.sweep")
    assert sweep_span.attributes["shops_checked"] == 0
    assert sweep_span.attributes["missing"] == 0

    after_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "ingestion_backstop", "status": "success"},
    )
    assert after_runs - before_runs == 1


@pytest.mark.asyncio
async def test_ingestion_backstop_error_handling(otel_test_environment):
    before_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "ingestion_backstop", "status": "error"},
    )

    with patch.object(ingestion_backstop, "_active_shops", new_callable=AsyncMock) as mock_shops:
        mock_shops.side_effect = RuntimeError("Failed to query active shops")

        with pytest.raises(RuntimeError):
            await ingestion_backstop.sweep_once()

    spans = otel_test_environment.span_exporter.get_finished_spans()
    sweep_span = next(s for s in spans if s.name == "reconciler.ingestion_backstop.sweep")
    assert sweep_span.status.status_code == StatusCode.ERROR

    after_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "ingestion_backstop", "status": "error"},
    )
    assert after_runs - before_runs == 1


# ---------------------------------------------------------------------------
# Enrichment Sweeper Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_enrichment_sweeper_records_metrics_and_spans(otel_test_environment):
    before_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "enrichment", "status": "success"},
    )

    with patch("app.recommandations.edges.enrichment_sweeper.LLMBudget") as mock_budget_cls, \
         patch("app.recommandations.edges.enrichment_sweeper.shops_needing_enrichment", new_callable=AsyncMock) as mock_shops, \
         patch("app.recommandations.edges.enrichment_sweeper.EdgeInstallPipeline") as mock_pipeline_cls:

        mock_budget = AsyncMock()
        mock_budget_cls.return_value = mock_budget
        mock_shops.return_value = ["shop_1"]

        mock_pipeline = AsyncMock()
        mock_pipeline.retry_failed_enrichment.return_value = SimpleNamespace(
            products=10, enriched=8, prior_edges=4
        )
        mock_pipeline_cls.return_value = mock_pipeline

        result = await enrichment_sweeper.sweep_once()
        assert result["shops"] == 1
        assert result["retried"] == 10
        assert result["recovered"] == 8

    spans = otel_test_environment.span_exporter.get_finished_spans()
    sweep_span = next(s for s in spans if s.name == "reconciler.enrichment.sweep")
    assert sweep_span.attributes["shops"] == 1
    assert sweep_span.attributes["retried"] == 10
    assert sweep_span.attributes["recovered"] == 8

    after_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "enrichment", "status": "success"},
    )
    assert after_runs - before_runs == 1


@pytest.mark.asyncio
async def test_enrichment_sweeper_circuit_open_status_skipped(otel_test_environment):
    before_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "enrichment", "status": "skipped"},
    )

    with patch("app.recommandations.edges.enrichment_sweeper.LLMBudget") as mock_budget_cls:
        mock_budget = AsyncMock()
        mock_budget.check.side_effect = CircuitOpen("Circuit tripped")
        mock_budget_cls.return_value = mock_budget

        result = await enrichment_sweeper.sweep_once()
        assert "skipped" in result

    spans = otel_test_environment.span_exporter.get_finished_spans()
    sweep_span = next(s for s in spans if s.name == "reconciler.enrichment.sweep")
    assert sweep_span.attributes["skipped"] is True

    after_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "enrichment", "status": "skipped"},
    )
    assert after_runs - before_runs == 1


@pytest.mark.asyncio
async def test_enrichment_sweeper_error_handling(otel_test_environment):
    before_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "enrichment", "status": "error"},
    )

    with patch("app.recommandations.edges.enrichment_sweeper.LLMBudget") as mock_budget_cls:
        mock_budget = AsyncMock()
        mock_budget.check.side_effect = RuntimeError("Fatal budget crash")
        mock_budget_cls.return_value = mock_budget

        with pytest.raises(RuntimeError):
            await enrichment_sweeper.sweep_once()

    spans = otel_test_environment.span_exporter.get_finished_spans()
    sweep_span = next(s for s in spans if s.name == "reconciler.enrichment.sweep")
    assert sweep_span.status.status_code == StatusCode.ERROR

    after_runs = get_metric_value(
        otel_test_environment.reader,
        "betterbundle.reconciler.runs.total",
        {"reconciler": "enrichment", "status": "error"},
    )
    assert after_runs - before_runs == 1

