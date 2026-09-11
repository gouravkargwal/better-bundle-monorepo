# Telemetry: Working Traces & Working Alerts — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the OpenTelemetry instrumentation that is already installed actually emit traces end-to-end (Node → Kafka → Python), and make the five committed alerts actually fire into Slack.

**Architecture:** Services keep exporting OTLP directly to OpenObserve — no collector. Both services already run an OTel SDK; each is missing only a `TracerProvider` + span exporter, so the auto-instrumentation currently writes to the no-op provider and every span is silently dropped. W3C `traceparent` is carried across Kafka in message headers so the two halves of a trace join up. Alerts are rewritten to OpenObserve's real REST schema with a named destination, and the import script is made to fail loudly instead of swallowing HTTP errors.

**Tech Stack:** OpenTelemetry SDK (Python 1.30.0 / JS 0.55.0), OpenObserve (OTLP HTTP ingest), aiokafka, kafkajs, FastAPI, Remix.

**Spec:** `.kilo/plans/1789092299921-openobserve-telemetry-plan.md` — superseded by this plan. That document's Phase 2 and Phase 3 describe work already committed; its Phase 1 (OTel Collector) and Phase 4 (frontend RUM) are deliberately **not** implemented here (see "Deliberately Out of Scope").

## Global Constraints

- **Do not add an OTel Collector.** All services share the compose network and OpenObserve ingests OTLP natively. Revisit only when infra scraping (Postgres/Redis/Kafka exporters) is actually wanted.
- **Do not add frontend RUM.** Out of scope; see below.
- Python OTel pinned at `1.30.0` / instrumentation `0.51b0`. Do not bump versions in this plan.
- Node OTel pinned at `^0.55.0` (SDK/exporters) and `^1.28.0` (api/resources/semconv). Do not bump.
- Existing `OPENOBSERVE_ENDPOINT` / `OPENOBSERVE_ORG` / `OPENOBSERVE_API_KEY` env vars are reused everywhere. Do not introduce new telemetry env vars.
- OpenObserve OTLP HTTP trace path is `/api/{org}/v1/traces`.
- Resource attributes must match what the existing log/metric exporters already send, so the three signals correlate: `service.name` (`python-worker` / `remix-app`), `service.version`, `deployment.environment`.
- Every file created must follow the docstring/comment style of its neighbours (see `otel_logger.py`, `otel_metrics.py`).

---

## File Structure

| File | Responsibility |
|---|---|
| `python-worker/app/core/logging/otel_tracing.py` | **Create.** `init_otel_tracing(settings) -> TracerProvider`. Mirror of `otel_logger.py`. |
| `python-worker/app/main.py` | **Modify.** Init tracer provider first in lifespan, shut it down last. |
| `better-bundle/app/utils/otel-logger.ts` | **Modify.** Add `traceExporter` to the existing `NodeSDK`. One file — the SDK already exists here, a second init file would double-register instrumentation. |
| `python-worker/app/core/kafka/producer.py` | **Modify.** Inject `traceparent` into message headers. |
| `python-worker/app/core/kafka/consumer.py` | **Modify.** Extract `traceparent` from headers, open a consumer span. |
| `better-bundle/app/services/kafka/kafka-producer.service.ts` | **Modify.** Inject `traceparent` into message headers. |
| `python-worker/tests/test_kafka_trace_propagation.py` | **Create.** Round-trip test: inject → extract preserves trace id. |
| `openobserve-config/destinations/slack.json` | **Create.** Named webhook destination the alerts reference. |
| `openobserve-config/templates/slack.json` | **Create.** Message body template for that destination. |
| `openobserve-config/alerts/*.json` (5 files) | **Modify.** Rewrite to OpenObserve's real alert schema. |
| `openobserve-config/import.sh` | **Modify.** Import templates → destinations → alerts in order; fail on non-2xx. |

---

## Task 1: Python span export

Without this, `@trace_func`, `FastAPIInstrumentor`, `HTTPXClientInstrumentor` and `RedisInstrumentor` all resolve `trace.get_tracer()` to the no-op provider and discard every span. This task is the single highest-value change in the plan.

**Files:**
- Create: `python-worker/app/core/logging/otel_tracing.py`
- Modify: `python-worker/app/main.py` (imports ~line 18, lifespan startup ~line 50, lifespan shutdown ~line 132)

**Interfaces:**
- Consumes: `app.core.config.settings.Settings` — fields `OPENOBSERVE_ENDPOINT: str`, `OPENOBSERVE_ORG: str`, `OPENOBSERVE_API_KEY: str`, `VERSION: str`, `ENVIRONMENT: str`.
- Produces: `init_otel_tracing(settings: Settings) -> TracerProvider`. Task 3 relies on the global tracer provider being set by this function before any Kafka span is opened.

- [ ] **Step 1: Create the tracing module**

Create `python-worker/app/core/logging/otel_tracing.py`:

```python
"""
OpenTelemetry tracing configuration for BetterBundle Python Worker
Exports spans to OpenObserve via OTLP HTTP protocol
"""

from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

if TYPE_CHECKING:
    from app.core.config.settings import Settings


def init_otel_tracing(settings: "Settings") -> TracerProvider:
    """Initialize OpenTelemetry tracing SDK with OTLP exporter for OpenObserve.

    Must run before any instrumentor is applied and before the first span is
    opened — anything that calls ``trace.get_tracer()`` earlier binds to the
    no-op provider for the life of the process and its spans are discarded.

    Returns the ``TracerProvider`` so callers can shut it down gracefully.
    """
    resource = Resource.create(
        {
            "service.name": "python-worker",
            "service.version": settings.VERSION,
            "deployment.environment": settings.ENVIRONMENT,
        }
    )

    base = settings.OPENOBSERVE_ENDPOINT.rstrip("/")
    endpoint = f"{base}/api/{settings.OPENOBSERVE_ORG}/v1/traces"

    exporter = OTLPSpanExporter(
        endpoint=endpoint,
        headers=(("Authorization", f"Basic {settings.OPENOBSERVE_API_KEY}"),),
    )

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    return provider
```

- [ ] **Step 2: Import it in main.py**

In `python-worker/app/main.py`, directly after the `init_otel_metrics` import (~line 18):

```python
from app.core.logging.otel_tracing import init_otel_tracing
```

- [ ] **Step 3: Add the module-level provider handle**

Replace the two-line block at ~line 42:

```python
# OTel provider instances – kept alive for graceful shutdown
_otel_provider = None
_metrics_provider = None
```

with:

```python
# OTel provider instances – kept alive for graceful shutdown
_otel_provider = None
_metrics_provider = None
_tracer_provider = None
```

- [ ] **Step 4: Initialize tracing first in lifespan**

In `lifespan`, insert **before** the existing `global _otel_provider` block (i.e. tracing is the first thing initialized — `FastAPIInstrumentor.instrument_app` at module scope has already run by then, but it resolves its tracer lazily per request, so this ordering is correct and gives the logger a live trace context to stamp onto records):

```python
    # Initialize OpenTelemetry tracing (must precede logs so log records
    # carry trace_id/span_id)
    global _tracer_provider
    _tracer_provider = init_otel_tracing(settings)
    logger.info("✅ OpenTelemetry tracing initialized")
```

- [ ] **Step 5: Shut it down last**

In the shutdown half of `lifespan`, after the existing `_metrics_provider.shutdown()` block (~line 140):

```python
    if _tracer_provider is not None and hasattr(_tracer_provider, "shutdown"):
        _tracer_provider.shutdown()
        logger.info("✅ OpenTelemetry tracing provider shut down")
```

- [ ] **Step 6: Verify spans actually land in OpenObserve**

Start the stack and hit the worker, then query OpenObserve for the trace stream:

```bash
docker compose -f docker-compose.local.yml up -d
sleep 30
curl -s http://localhost:8000/health > /dev/null

# BatchSpanProcessor flushes on a 5s schedule; give it room.
sleep 15

curl -s -u "$OPENOBSERVE_USER:$OPENOBSERVE_PASSWORD" \
  "http://localhost:5080/api/default/default/_search?type=traces" \
  -H "Content-Type: application/json" \
  -d '{"query":{"sql":"SELECT service_name, operation_name FROM default WHERE service_name = '\''python-worker'\'' LIMIT 5","start_time":0,"end_time":9999999999999999,"from":0,"size":5}}'
```

Expected: a non-empty `hits` array containing `service_name: "python-worker"`.
If empty: check the worker logs for `Failed to export spans` — a 401 means `OPENOBSERVE_API_KEY` is not the base64 `user:password` pair the other two exporters use; a 404 means the `/v1/traces` path is wrong for your OpenObserve version, in which case try `/api/default/traces`.

- [ ] **Step 7: Commit**

```bash
git add python-worker/app/core/logging/otel_tracing.py python-worker/app/main.py
git commit -m "feat(telemetry): export Python spans to OpenObserve

Instrumentation was registered but no TracerProvider was ever set, so
every span went to the no-op provider and was discarded."
```

---

## Task 2: Node span export

Same defect on the Remix side: `NodeSDK` is constructed with only a `logRecordProcessor`, so `HttpInstrumentation` and `ExpressInstrumentation` produce spans that go nowhere.

**Files:**
- Modify: `better-bundle/app/utils/otel-logger.ts`
- Modify: `better-bundle/package.json` (one new dependency)

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: a live global `TracerProvider` in the Node process. Task 3's producer injection depends on it — without this task, `propagation.inject()` on the Node side writes nothing.

- [ ] **Step 1: Add the trace exporter dependency**

```bash
cd better-bundle && npm install --save-exact @opentelemetry/exporter-trace-otlp-http@0.55.0
```

- [ ] **Step 2: Import the exporter**

In `better-bundle/app/utils/otel-logger.ts`, after the `OTLPLogExporter` import:

```typescript
import { OTLPTraceExporter } from "@opentelemetry/exporter-trace-otlp-http";
```

- [ ] **Step 3: Wire the exporter into the SDK**

In the `new NodeSDK({...})` call, add a `traceExporter` field immediately after the `logRecordProcessor` field:

```typescript
    traceExporter: new OTLPTraceExporter({
      url: `${endpoint}/api/${org}/v1/traces`,
      headers: apiKey ? { Authorization: `Basic ${apiKey}` } : {},
    }),
```

Note the path asymmetry with the log exporter above it, which uses `/api/${org}/otlp/v1/logs`. Both prefixes are accepted by OpenObserve; leave the log exporter alone rather than risk breaking working log ingestion.

- [ ] **Step 4: Verify spans land**

```bash
cd better-bundle && npm run dev
# in another shell, hit any app route, then:
sleep 15
curl -s -u "$OPENOBSERVE_USER:$OPENOBSERVE_PASSWORD" \
  "http://localhost:5080/api/default/default/_search?type=traces" \
  -H "Content-Type: application/json" \
  -d '{"query":{"sql":"SELECT service_name FROM default WHERE service_name = '\''remix-app'\'' LIMIT 5","start_time":0,"end_time":9999999999999999,"from":0,"size":5}}'
```

Expected: non-empty `hits` with `service_name: "remix-app"`.

- [ ] **Step 5: Commit**

```bash
git add better-bundle/app/utils/otel-logger.ts better-bundle/package.json better-bundle/package-lock.json
git commit -m "feat(telemetry): export Remix spans to OpenObserve

NodeSDK had a logRecordProcessor but no traceExporter, so http/express
instrumentation spans were discarded."
```

---

## Task 3: Kafka trace context propagation

Node → Kafka → Python is the critical path. Without header propagation the Remix span and the worker span are two unrelated traces, and the end-to-end latency question the whole exercise exists to answer stays unanswerable.

**Files:**
- Modify: `python-worker/app/core/kafka/producer.py` (`send`, ~lines 45-110)
- Modify: `python-worker/app/core/kafka/consumer.py` (`consume`, ~lines 86-121)
- Modify: `better-bundle/app/services/kafka/kafka-producer.service.ts` (`publishShopifyEvent`)
- Create: `python-worker/tests/test_kafka_trace_propagation.py`

**Interfaces:**
- Consumes: the global tracer providers set in Tasks 1 and 2.
- Produces: `KafkaProducer.send()` gains no signature change but now writes a `traceparent` Kafka header. `KafkaConsumer.consume()` gains no signature change; each yielded message is produced inside an active span named `kafka.consume {topic}`.

- [ ] **Step 1: Write the failing test**

Create `python-worker/tests/test_kafka_trace_propagation.py`:

```python
"""Kafka W3C trace-context propagation must survive the header round trip.

If this breaks, Node->Kafka->Python traces silently split into two
unrelated traces and nobody notices until someone asks why end-to-end
latency cannot be measured.
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from app.core.kafka.producer import inject_trace_headers
from app.core.kafka.consumer import extract_trace_context


def test_trace_id_survives_kafka_headers():
    trace.set_tracer_provider(TracerProvider())
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("producer-side") as span:
        expected_trace_id = span.get_span_context().trace_id
        headers = inject_trace_headers()

    assert any(k == "traceparent" for k, _ in headers), headers

    ctx = extract_trace_context({k: v for k, v in headers})
    restored = trace.get_current_span(ctx).get_span_context()

    assert restored.trace_id == expected_trace_id


def test_extract_tolerates_missing_headers():
    ctx = extract_trace_context({})
    assert trace.get_current_span(ctx).get_span_context().trace_id == 0
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `cd python-worker && pytest tests/test_kafka_trace_propagation.py -v`
Expected: FAIL with `ImportError: cannot import name 'inject_trace_headers'`.

- [ ] **Step 3: Add the injection helper to the Python producer**

In `python-worker/app/core/kafka/producer.py`, after the `logger = logging.getLogger(__name__)` line:

```python
from opentelemetry import propagate


def inject_trace_headers() -> List[tuple]:
    """Serialize the active span context into Kafka headers (W3C traceparent).

    Returns aiokafka's header format: a list of (str, bytes) pairs. Empty
    when there is no active span, which is a valid state, not an error.
    """
    carrier: Dict[str, str] = {}
    propagate.inject(carrier)
    return [(k, v.encode("utf-8")) for k, v in carrier.items()]
```

- [ ] **Step 4: Attach the headers on every send**

In `KafkaProducer.send`, the method currently calls `self._producer.send(...)` in four places. Rather than edit four call sites, compute the headers once at the top of the `try:` block, immediately after `message_with_metadata` is built:

```python
            headers = inject_trace_headers()
```

then add `headers=headers` to each of the four `self._producer.send(...)` calls. For example the final `else:` branch becomes:

```python
            else:
                # Industry practice: rely on key-based partitioning; do not specify partition
                future = self._producer.send(
                    topic, value=message_with_metadata, key=key, headers=headers
                )
                record_metadata = await future
```

Apply the same `headers=headers` argument to the other three `self._producer.send(...)` calls in the method (the explicit-partition call, its partition-error retry, and the no-partition-determined call).

- [ ] **Step 5: Add the extraction helper to the Python consumer**

In `python-worker/app/core/kafka/consumer.py`, after `logger = logging.getLogger(__name__)`:

```python
from opentelemetry import context as otel_context, propagate, trace

_tracer = trace.get_tracer(__name__)


def extract_trace_context(headers: Dict[str, Any]) -> otel_context.Context:
    """Rebuild the producer's span context from Kafka headers.

    Accepts aiokafka's ``dict`` of header name -> bytes. Missing or malformed
    headers yield an empty context, which starts a fresh trace rather than
    raising — a bad header must never drop a message.
    """
    carrier = {
        k: v.decode("utf-8") if isinstance(v, bytes) else str(v)
        for k, v in (headers or {}).items()
    }
    return propagate.extract(carrier)
```

- [ ] **Step 6: Open a consumer span around each yielded message**

In `KafkaConsumer.consume`, the `kafka_message` dict is built and then yielded at ~line 121. Wrap the yield so the consumer's work runs inside a span linked to the producer. Replace:

```python
                    self._message_count += 1
                    kafka_messages_consumed.add(
                        1,
                        {
                            "topic": message.topic,
                            "group_id": self._group_id,
                        },
                    )
                    yield kafka_message
```

with:

```python
                    self._message_count += 1
                    kafka_messages_consumed.add(
                        1,
                        {
                            "topic": message.topic,
                            "group_id": self._group_id,
                        },
                    )

                    parent_ctx = extract_trace_context(kafka_message["headers"])
                    with _tracer.start_as_current_span(
                        f"kafka.consume {message.topic}",
                        context=parent_ctx,
                        kind=trace.SpanKind.CONSUMER,
                    ) as span:
                        span.set_attribute("messaging.system", "kafka")
                        span.set_attribute("messaging.destination.name", message.topic)
                        span.set_attribute("messaging.kafka.partition", message.partition)
                        span.set_attribute("messaging.kafka.offset", message.offset)
                        span.set_attribute("messaging.consumer.group.name", self._group_id)
                        yield kafka_message
```

The span stays open for the duration of the caller's handling of the message, because the generator suspends inside the `with` block — that is the behaviour we want, it is what makes downstream DB and HTTP spans children of this one.

- [ ] **Step 7: Run the test and confirm it passes**

Run: `cd python-worker && pytest tests/test_kafka_trace_propagation.py -v`
Expected: both tests PASS.

- [ ] **Step 8: Inject traceparent on the Node producer**

In `better-bundle/app/services/kafka/kafka-producer.service.ts`, add to the imports at the top:

```typescript
import { propagation, context } from "@opentelemetry/api";
```

In `publishShopifyEvent`, immediately before the `await this.producer.send({...})` call:

```typescript
      // W3C trace context so the worker's spans join this request's trace.
      const traceHeaders: Record<string, string> = {};
      propagation.inject(context.active(), traceHeaders);
```

and add `headers: traceHeaders,` to the message object, alongside `key` and `value`:

```typescript
          {
            key,
            value: JSON.stringify(messageWithMetadata),
            headers: traceHeaders,
          },
```

Check the rest of this file for any other `this.producer.send(` call and apply the same two changes there; each un-propagated publish is a trace that silently breaks.

- [ ] **Step 9: Verify end-to-end**

Trigger a Shopify webhook (or whatever path publishes to `shopify-events`), wait for the worker to consume it, then find a trace containing both services:

```bash
sleep 20
curl -s -u "$OPENOBSERVE_USER:$OPENOBSERVE_PASSWORD" \
  "http://localhost:5080/api/default/default/_search?type=traces" \
  -H "Content-Type: application/json" \
  -d '{"query":{"sql":"SELECT trace_id, service_name, operation_name FROM default WHERE operation_name LIKE '\''kafka.consume%'\'' LIMIT 10","start_time":0,"end_time":9999999999999999,"from":0,"size":10}}'
```

Take one `trace_id` from the result and query for every span sharing it. Expected: spans from **both** `remix-app` and `python-worker` under a single `trace_id`. If you only see `python-worker`, the Node injection is not reaching the broker — confirm Task 2 landed, since `propagation.inject` writes nothing without a live tracer provider.

- [ ] **Step 10: Commit**

```bash
git add python-worker/app/core/kafka/producer.py python-worker/app/core/kafka/consumer.py \
        python-worker/tests/test_kafka_trace_propagation.py \
        better-bundle/app/services/kafka/kafka-producer.service.ts
git commit -m "feat(telemetry): propagate W3C trace context across Kafka

Node->Kafka->Python traces previously split at the broker into two
unrelated traces, making end-to-end latency unmeasurable."
```

---

## Task 4: Make alerting actually work

The five committed alerts use a schema OpenObserve's API does not accept (`condition`, `eval_period`, inline `notifications[].webhook_url`), reference a `${SLACK_WEBHOOK_URL}` that is never expanded, and are POSTed by an import script that discards the response body and the HTTP status. The current state is worse than having no alerts, because it looks like alerting exists.

**Files:**
- Create: `openobserve-config/templates/slack.json`
- Create: `openobserve-config/destinations/slack.json`
- Modify: `openobserve-config/alerts/high-error-rate.json`
- Modify: `openobserve-config/alerts/high-latency.json`
- Modify: `openobserve-config/alerts/service-down.json`
- Modify: `openobserve-config/alerts/cache-hit-ratio-low.json`
- Modify: `openobserve-config/alerts/kafka-consumer-lag.json`
- Modify: `openobserve-config/import.sh`

**Interfaces:**
- Consumes: nothing from Tasks 1-3.
- Produces: an importable, verified alert configuration. `import.sh` keeps its existing CLI contract: `./import.sh [endpoint] [org] <api_key>`, plus it now reads `SLACK_WEBHOOK_URL` from the environment.

- [ ] **Step 1: Capture the canonical alert schema from your own OpenObserve**

Do not trust the payloads below verbatim — OpenObserve's alert schema shifts between versions and you are on `:latest`. Create one trivial alert through the OpenObserve UI (any stream, any condition, name it `schema-probe`), then read it back:

```bash
curl -s -u "$OPENOBSERVE_USER:$OPENOBSERVE_PASSWORD" \
  "http://localhost:5080/api/default/alerts" | python3 -m json.tool
```

Keep that output open. Where it disagrees with the payloads in the next steps, **the API output wins** — adjust the JSON files to match it. Delete `schema-probe` when done.

- [ ] **Step 2: Create the Slack message template**

Create `openobserve-config/templates/slack.json`:

```json
{
  "name": "slack-webhook",
  "body": "{\"text\": \":rotating_light: *{alert_name}* fired on stream `{stream_name}` at {timestamp}\"}",
  "type": "http",
  "isDefault": false
}
```

- [ ] **Step 3: Create the Slack destination**

Create `openobserve-config/destinations/slack.json`. The literal `SLACK_WEBHOOK_URL_PLACEHOLDER` is substituted by `import.sh` in Step 10 — keeping a real webhook out of git is the point.

```json
{
  "name": "slack",
  "url": "SLACK_WEBHOOK_URL_PLACEHOLDER",
  "method": "post",
  "skip_tls_verify": false,
  "template": "slack-webhook",
  "headers": {
    "Content-Type": "application/json"
  }
}
```

- [ ] **Step 4: Rewrite the error-rate alert**

Replace the entire contents of `openobserve-config/alerts/high-error-rate.json`:

```json
{
  "name": "High HTTP Error Rate",
  "stream_type": "logs",
  "stream_name": "default",
  "is_real_time": false,
  "enabled": true,
  "description": "5xx responses exceeded 10 in the last 5 minutes",
  "query_condition": {
    "type": "sql",
    "sql": "SELECT COUNT(*) AS error_count FROM \"default\" WHERE status >= 500",
    "aggregation": {
      "group_by": [],
      "function": "count",
      "having": {
        "column": "error_count",
        "operator": ">=",
        "value": 10
      }
    }
  },
  "trigger_condition": {
    "period": 5,
    "operator": ">=",
    "threshold": 1,
    "frequency": 5,
    "silence": 30
  },
  "destinations": ["slack"]
}
```

Note the change from a rate to an absolute count. The old `rate(count(*), 5m) > 0.05` was both non-standard SQL and a threshold so low that a single slow afternoon would page someone. `silence: 30` suppresses re-firing for 30 minutes, which is the difference between an alert and a pager storm.

- [ ] **Step 5: Rewrite the latency alert**

Replace the entire contents of `openobserve-config/alerts/high-latency.json`:

```json
{
  "name": "High Request Latency",
  "stream_type": "logs",
  "stream_name": "default",
  "is_real_time": false,
  "enabled": true,
  "description": "p95-ish request duration above 2s over 5 minutes",
  "query_condition": {
    "type": "sql",
    "sql": "SELECT approx_percentile_cont(duration, 0.95) AS p95 FROM \"default\" WHERE service_name = 'python-worker'",
    "aggregation": {
      "group_by": [],
      "function": "max",
      "having": {
        "column": "p95",
        "operator": ">=",
        "value": 2000
      }
    }
  },
  "trigger_condition": {
    "period": 5,
    "operator": ">=",
    "threshold": 1,
    "frequency": 5,
    "silence": 30
  },
  "destinations": ["slack"]
}
```

Confirm the `duration` column name and its unit against a real row in your log stream before accepting this — if the field is seconds rather than milliseconds, the threshold is wrong by 1000x and the alert will never fire.

- [ ] **Step 6: Rewrite the service-down alert**

Replace the entire contents of `openobserve-config/alerts/service-down.json`:

```json
{
  "name": "Service Down",
  "stream_type": "logs",
  "stream_name": "default",
  "is_real_time": false,
  "enabled": true,
  "description": "python-worker produced no log lines for 10 minutes",
  "query_condition": {
    "type": "sql",
    "sql": "SELECT COUNT(*) AS line_count FROM \"default\" WHERE service_name = 'python-worker'",
    "aggregation": {
      "group_by": [],
      "function": "count",
      "having": {
        "column": "line_count",
        "operator": "<",
        "value": 1
      }
    }
  },
  "trigger_condition": {
    "period": 10,
    "operator": ">=",
    "threshold": 1,
    "frequency": 5,
    "silence": 30
  },
  "destinations": ["slack"]
}
```

Absence-of-logs is a proxy for liveness, not a real health check. It is the honest version of what the old file claimed to do, and it costs nothing.

- [ ] **Step 7: Rewrite the cache-hit-ratio alert**

Replace the entire contents of `openobserve-config/alerts/cache-hit-ratio-low.json`:

```json
{
  "name": "Cache Hit Ratio Low",
  "stream_type": "metrics",
  "stream_name": "cache_hits_total",
  "is_real_time": false,
  "enabled": true,
  "description": "Cache hits fell below 100 in 15 minutes, suggesting the cache is cold or bypassed",
  "query_condition": {
    "type": "sql",
    "sql": "SELECT SUM(value) AS hits FROM \"cache_hits_total\"",
    "aggregation": {
      "group_by": [],
      "function": "sum",
      "having": {
        "column": "hits",
        "operator": "<",
        "value": 100
      }
    }
  },
  "trigger_condition": {
    "period": 15,
    "operator": ">=",
    "threshold": 1,
    "frequency": 15,
    "silence": 60
  },
  "destinations": ["slack"]
}
```

Verify `cache_hits_total` is the actual metric stream name — check `python-worker/app/core/metrics.py` for the instrument name and confirm the stream exists in OpenObserve. If the metric does not exist yet, **delete this alert file** rather than shipping one that can never fire.

- [ ] **Step 8: Rewrite the Kafka consumer-lag alert**

Replace the entire contents of `openobserve-config/alerts/kafka-consumer-lag.json`:

```json
{
  "name": "Kafka Consumption Stalled",
  "stream_type": "metrics",
  "stream_name": "kafka_messages_consumed",
  "is_real_time": false,
  "enabled": true,
  "description": "No Kafka messages consumed in 15 minutes",
  "query_condition": {
    "type": "sql",
    "sql": "SELECT SUM(value) AS consumed FROM \"kafka_messages_consumed\"",
    "aggregation": {
      "group_by": [],
      "function": "sum",
      "having": {
        "column": "consumed",
        "operator": "<",
        "value": 1
      }
    }
  },
  "trigger_condition": {
    "period": 15,
    "operator": ">=",
    "threshold": 1,
    "frequency": 15,
    "silence": 60
  },
  "destinations": ["slack"]
}
```

True consumer *lag* needs a Kafka exporter that does not exist yet; stalled consumption is the signal you can actually get from the `kafka_messages_consumed` counter already emitted by `consumer.py`. Confirm that stream name in OpenObserve before accepting.

- [ ] **Step 9: Make import.sh fail loudly and import in dependency order**

Replace the entire contents of `openobserve-config/import.sh`:

```bash
#!/bin/bash
# Import OpenObserve configuration
# Usage: SLACK_WEBHOOK_URL=https://... ./import.sh <openobserve_endpoint> <org> <api_key>

set -euo pipefail

ENDPOINT="${1:-http://localhost:5080}"
ORG="${2:-default}"
API_KEY="${3:-}"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"

if [ -z "$API_KEY" ]; then
  echo "Error: API key is required. Usage: $0 [endpoint] [org] <api_key>" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# POST a file and fail on any non-2xx. The previous version discarded both
# the status and the body, so a rejected alert looked exactly like an
# accepted one and the whole alerting config was silently absent.
post() {
  local path="$1" file="$2" name="$3"
  local body status
  body=$(mktemp)
  status=$(curl -s -o "$body" -w "%{http_code}" -X POST "$ENDPOINT/api/$ORG/$path" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    --data-binary "@$file")
  if [ "$status" -lt 200 ] || [ "$status" -ge 300 ]; then
    echo "FAILED ($status) importing $name:" >&2
    cat "$body" >&2
    rm -f "$body"
    return 1
  fi
  echo "  ok: $name"
  rm -f "$body"
}

# Order matters: alerts reference destinations, destinations reference templates.
echo "Importing templates..."
for f in "$SCRIPT_DIR"/templates/*.json; do
  post "alerts/templates" "$f" "$(basename "$f" .json)"
done

echo "Importing destinations..."
if [ -z "$SLACK_WEBHOOK_URL" ]; then
  echo "Error: SLACK_WEBHOOK_URL is not set; alerts would have nowhere to go." >&2
  exit 1
fi
for f in "$SCRIPT_DIR"/destinations/*.json; do
  rendered=$(mktemp)
  sed "s|SLACK_WEBHOOK_URL_PLACEHOLDER|$SLACK_WEBHOOK_URL|" "$f" > "$rendered"
  post "alerts/destinations" "$rendered" "$(basename "$f" .json)"
  rm -f "$rendered"
done

echo "Importing dashboards..."
for f in "$SCRIPT_DIR"/dashboards/*.json; do
  post "dashboards" "$f" "$(basename "$f" .json)"
done

echo "Importing alerts..."
for f in "$SCRIPT_DIR"/alerts/*.json; do
  post "alerts" "$f" "$(basename "$f" .json)"
done

echo "Done!"
```

Confirm the template and destination API paths (`alerts/templates`, `alerts/destinations`) against your running instance — some versions expose them at the org root instead. The `schema-probe` output from Step 1 or `curl -s -u ... http://localhost:5080/api/default/alerts/destinations` will tell you.

- [ ] **Step 10: Run the import and confirm every object exists**

```bash
cd openobserve-config
SLACK_WEBHOOK_URL="$SLACK_WEBHOOK_URL" ./import.sh http://localhost:5080 default "$OPENOBSERVE_API_KEY"
```

Expected: an `ok:` line per file and exit status 0. Then confirm the server agrees:

```bash
curl -s -u "$OPENOBSERVE_USER:$OPENOBSERVE_PASSWORD" \
  "http://localhost:5080/api/default/alerts" | python3 -c "import json,sys; print([a['name'] for a in json.load(sys.stdin)['list']])"
```

Expected: all five alert names listed.

- [ ] **Step 11: Prove one alert actually reaches Slack**

A configured alert is not a working alert. Force the error-rate alert to fire by writing 10+ synthetic 5xx log lines into the stream, then wait one evaluation period:

```bash
for i in $(seq 1 15); do
  curl -s -u "$OPENOBSERVE_USER:$OPENOBSERVE_PASSWORD" \
    -X POST "http://localhost:5080/api/default/default/_json" \
    -H "Content-Type: application/json" \
    -d '[{"level":"error","status":500,"service_name":"python-worker","message":"alert smoke test"}]' > /dev/null
done
echo "wait up to 5 minutes for the evaluation window"
```

Expected: a message in the Slack channel. If nothing arrives, check OpenObserve's alert trigger history in the UI — a triggered-but-undelivered alert points at the destination/template, a never-triggered alert points at the SQL or the threshold.

- [ ] **Step 12: Commit**

```bash
git add openobserve-config/
git commit -m "fix(observability): make alerts importable and deliverable

Alert JSON did not match OpenObserve's API schema, referenced an
unexpanded webhook variable, and import.sh discarded HTTP status, so
every alert failed to import silently."
```

---

## Deliberately Out of Scope

Recorded so the next person does not re-propose them without new information.

- **OTel Collector / gateway.** All three services share the compose network and OpenObserve ingests OTLP directly. A collector adds a container and a config file and buys nothing until there is a browser client whose API key must be hidden, or infra exporters to scrape. Add it then, with those as the driving requirement.
- **Frontend (Vite/React) RUM.** Highest effort in the original plan — new deps, a proxy route, CORS, ad-blocker evasion — for the least signal, on an embedded Shopify admin app with a small user base. Revisit when a question arises that backend traces demonstrably cannot answer.
- **Postgres / Redis / Kafka metric exporters.** Worth doing, but they depend on the collector and none of the current alerts need them. Separate plan.
- **New dashboards.** The three committed dashboards should be checked against real trace data after Task 3 lands; designing new ones before any trace has ever been recorded is guesswork.