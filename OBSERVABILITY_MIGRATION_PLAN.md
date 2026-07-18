# OpenObserve Migration Plan — BetterBundle

> **Replace Grafana + Loki + Promtail + dead Prometheus code with [OpenObserve](https://openobserve.ai/).**

## Table of Contents

1. [Phase 1: Side-by-Side Deployment](#phase-1-side-by-side-deployment)
2. [Phase 2: Log Source Migration](#phase-2-log-source-migration)
3. [Phase 3: Metrics & Distributed Tracing](#phase-3-metrics--distributed-tracing)
4. [Phase 4: Dashboards & Alerting](#phase-4-dashboards--alerting)
5. [Phase 5: Cleanup & Decommission](#phase-5-cleanup--decommission)
6. [Appendix A: Environment Variables — Old vs New Mapping](#appendix-a-environment-variables--old-vs-new-mapping)
7. [Appendix B: Docker Compose Service Diff](#appendix-b-docker-compose-service-diff)
8. [Appendix C: Dependency Changes](#appendix-c-dependency-changes)
9. [Appendix D: Rollback Plan](#appendix-d-rollback-plan)

---

## Phase 1: Side-by-Side Deployment

**Goal:** Deploy OpenObserve alongside the existing Loki/Grafana stack. Validate ingestion. No application code changes yet — only infra config.

### 1.1 Docker Compose Changes

All three compose files need changes. The pattern is identical across [`docker-compose.dev.yml`](docker-compose.dev.yml), [`docker-compose.prod.yml`](docker-compose.prod.yml), and [`docker-compose.local.yml`](docker-compose.local.yml).

#### Add `openobserve` service

| Field          | Value                                                                                       |
| -------------- | ------------------------------------------------------------------------------------------- |
| Image          | `quay.io/openobserve/openobserve:latest`                                                    |
| Container name | `betterbundle-openobserve-dev` / `betterbundle-openobserve`                                 |
| Ports          | `5080:5080` (UI + API)                                                                      |
| Volumes        | `openobserve_data:/data`                                                                    |
| Env vars       | `ZO_ROOT_USER_EMAIL`, `ZO_ROOT_USER_PASSWORD`, `ZO_S3_*` (dev uses MinIO, prod uses AWS S3) |
| Networks       | Same as existing services (backend for prod, default for dev)                               |
| Restart        | `unless-stopped`                                                                            |

```yaml
openobserve:
  image: quay.io/openobserve/openobserve:latest
  container_name: betterbundle-openobserve-dev
  ports:
    - "5080:5080"
  volumes:
    - openobserve_data:/data
  env_file:
    - .env.dev
  environment:
    ZO_ROOT_USER_EMAIL: ${ZO_ROOT_USER_EMAIL}
    ZO_ROOT_USER_PASSWORD: ${ZO_ROOT_USER_PASSWORD}
    ZO_S3_STORAGE: ${ZO_S3_STORAGE:-false}
    ZO_LOCAL_MODE: ${ZO_LOCAL_MODE:-true}
    ZO_DATA_DIR: /data
    ZO_DATA_WAL_DIR: /data/wal
  restart: unless-stopped
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:5080/health"]
    interval: 30s
    timeout: 10s
    retries: 5
    start_period: 30s
  logging:
    driver: json-file
    options:
      max-size: "5m"
      max-file: "2"
```

#### Add `minio` service (dev/local only)

For development, provide S3-compatible storage. Production uses AWS S3 directly.

```yaml
minio:
  image: minio/minio:latest
  container_name: betterbundle-minio-dev
  ports:
    - "9000:9000"
    - "9001:9001"
  volumes:
    - minio_data:/data
  environment:
    MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
    MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-minioadmin}
  command: server /data --console-address ":9001"
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
    interval: 30s
    timeout: 10s
    retries: 3
```

#### Add volumes

```yaml
volumes:
  openobserve_data:
  minio_data:
```

#### Prod-specific changes in [`docker-compose.prod.yml`](docker-compose.prod.yml)

- No MinIO — use AWS S3 directly via `ZO_S3_*` env vars
- Add resource limits matching other services (e.g., `cpus: "1.0"`, `memory: 1G`)
- Add `logging: "promtail"` label for dual-write during migration
- Add to both `frontend` and `backend` networks

### 1.2 Environment Variable Changes

#### New OpenObserve variables to add

Add to [`env.example`](env.example), [`env.dev.example`](env.dev.example), [`env.prod.example`](env.prod.example):

```bash
# ===========================================
# OPENOBSERVE CONFIGURATION
# ===========================================
ZO_ROOT_USER_EMAIL=openobserve@betterbundle.com
ZO_ROOT_USER_PASSWORD=your_openobserve_password_here

# Storage backend (S3-compatible)
ZO_S3_STORAGE=false
ZO_S3_BUCKET=betterbundle-observability
ZO_S3_REGION=us-east-1
ZO_S3_ACCESS_KEY=
ZO_S3_SECRET_KEY=
ZO_S3_ENDPOINT=           # MinIO URL for dev: http://minio:9000

# OpenObserve local mode (true for dev/local)
ZO_LOCAL_MODE=true
ZO_DATA_DIR=/data
ZO_DATA_WAL_DIR=/data/wal

# OpenObserve connection (used by app code)
OPENOBSERVE_ENDPOINT=http://openobserve:5080
OPENOBSERVE_ORG=default
OPENOBSEREVE_API_KEY=    # Generated from OpenObserve UI after first login
OPENOBSERVE_STREAM_NAME=betterbundle-logs

# Dual-write mode: send to both Loki and OpenObserve during migration
OPENOBSERVE_DUAL_WRITE=true
```

#### Deprecate old variables

Add comments marking these as deprecated:

```bash
# DEPRECATED — will be removed in Phase 5
# Grafana Configuration
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=your_grafana_password_here

# Loki Configuration (for log aggregation)
LOKI_URL=http://loki:3100
```

### 1.3 Gorse OTLP Quick Win

In [`config.toml`](config.toml:133-134), change:

```toml
[opentelemetry]
enabled = false
```

to:

```toml
[opentelemetry]
enabled = true
endpoint = "http://openobserve:5080/api/default/gorselogs/_json"
# Or use OTLP gRPC endpoint:
# endpoint = "http://openobserve:5080/api/default/gorselogs"
service_name = "gorse"
```

**Note:** OpenObserve supports both JSON push and OTLP. Gorse uses OTLP exporter. We'll need to verify the exact endpoint format in OpenObserve docs — it may be `http://openobserve:5080/api/default/gorse/_json` for JSON or the OTLP gRPC endpoint at `http://openobserve:5080/api/otlp/v1/logs`.

### 1.4 Python Worker Settings

In [`python-worker/app/core/config/settings.py`](python-worker/app/core/config/settings.py), add a new `OpenObserveSettings` class:

```python
class OpenObserveSettings(BaseSettings):
    """OpenObserve configuration settings"""

    OPENOBSERVE_ENDPOINT: str = Field(
        default="http://openobserve:5080", env="OPENOBSERVE_ENDPOINT"
    )
    OPENOBSERVE_ORG: str = Field(default="default", env="OPENOBSERVE_ORG")
    OPENOBSERVE_API_KEY: str = Field(default="", env="OPENOBSERVE_API_KEY")
    OPENOBSERVE_STREAM_NAME: str = Field(
        default="betterbundle-logs", env="OPENOBSERVE_STREAM_NAME"
    )
    OPENOBSERVE_DUAL_WRITE: bool = Field(
        default=True, env="OPENOBSERVE_DUAL_WRITE"
    )
```

Add `openobserve: OpenObserveSettings = OpenObserveSettings()` to the `Settings` class.

### 1.5 Verification Steps

1. `docker-compose -f docker-compose.dev.yml up -d openobserve minio`
2. Visit `http://localhost:5080` — verify OpenObserve UI loads
3. Login with `ZO_ROOT_USER_EMAIL` / `ZO_ROOT_USER_PASSWORD`
4. Create an API token via UI (Settings → API Keys)
5. `curl -X POST http://localhost:5080/api/default/_json -H "Authorization: Bearer <token>" -d '{"test":"hello"}'` — verify ingestion
6. Check Loki is still running and ingesting — dual-wire working

### 1.6 Rollback

```bash
docker-compose -f docker-compose.dev.yml stop openobserve minio
docker-compose -f docker-compose.dev.yml rm -f openobserve minio
# Remove volumes
docker volume rm betterbundle_openobserve_data betterbundle_minio_data
```

---

## Phase 2: Log Source Migration

**Goal:** Migrate all application-level log shipping from Loki (custom handlers, pino-loki, browser relay) to OpenObserve via OTLP/JSON push. Keep dual-write mode until Phase 5.

### 2.1 Python Worker — Replace LokiHandler with OpenTelemetry SDK

#### Files to modify

| File                                                                                               | Change                                                                     |
| -------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| [`python-worker/requirements.txt`](python-worker/requirements.txt)                                 | Add `opentelemetry-*` packages, remove `prometheus-client`                 |
| [`python-worker/app/core/logging/loki_handler.py`](python-worker/app/core/logging/loki_handler.py) | Replace entire file with OpenTelemetry OTLP handler                        |
| [`python-worker/app/core/logging/handlers.py`](python-worker/app/core/logging/handlers.py)         | Replace `GrafanaHandler` with `OpenObserveHandler`, stub out dead handlers |
| [`python-worker/app/core/logging/config.py`](python-worker/app/core/logging/config.py)             | Replace `GrafanaConfig` with `OpenObserveConfig`, remove dead configs      |
| [`python-worker/app/core/logging/logger.py`](python-worker/app/core/logging/logger.py)             | Wire OpenObserve handler instead of Grafana handler                        |
| [`python-worker/app/core/config/settings.py`](python-worker/app/core/config/settings.py)           | Already done in Phase 1.4, but update `LoggingSettings` to use new config  |

#### Detailed changes

**`python-worker/requirements.txt`** — replace the monitoring section:

```txt
# Logging and Monitoring - OpenTelemetry
opentelemetry-sdk==1.22.0
opentelemetry-api==1.22.0
opentelemetry-exporter-otlp==1.22.0
opentelemetry-exporter-otlp-proto-grpc==1.22.0
opentelemetry-exporter-otlp-proto-http==1.22.0
opentelemetry-instrumentation-fastapi==0.43b0
opentelemetry-instrumentation-httpx==0.43b0
opentelemetry-instrumentation-sqlalchemy==0.43b0
opentelemetry-instrumentation-kafka-python==0.43b0   # if using kafka-python
# prometheus-client is removed (or kept for Phase 3 vanilla /metrics)
```

**`python-worker/app/core/logging/loki_handler.py`** — replace with OTLP log exporter:

The new `ottl_log_handler.py` (or rename the file) should:

```python
"""
OpenTelemetry OTLP Log Handler
Replaces the old LokiHandler with OTLP exporter to OpenObserve.
"""
import logging
from opentelemetry.sdk._logs import LoggerProvider, LogRecord
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk.resources import Resource


class OTLPLogHandler(logging.Handler):
    """Python logging handler that exports logs via OTLP to OpenObserve."""

    def __init__(self, endpoint: str, api_key: str, service_name: str = "python-worker"):
        super().__init__()
        resource = Resource.create({"service.name": service_name})
        logger_provider = LoggerProvider(resource=resource)
        exporter = OTLPLogExporter(
            endpoint=f"{endpoint}/api/otlp/v1/logs",  # OTLP gRPC
            headers={"Authorization": f"Bearer {api_key}"},
            insecure=True,  # Set False in prod with TLS
        )
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
        self._logger_provider = logger_provider

    def emit(self, record: logging.LogRecord):
        # Convert Python LogRecord → OTLP LogRecord
        # Add structured attributes from record
        pass
```

**`python-worker/app/core/logging/handlers.py`**:

- Replace `GrafanaHandler.create_handler()` with `OpenObserveHandler.create_handler()` that creates `OTLPLogHandler`
- Remove `PrometheusHandler`, `TelemetryHandler`, `GCPHandler`, `AWSHandler` (all return None — dead code)
- Keep `FileHandler` and `ConsoleHandler` as-is (they're useful)

**`python-worker/app/core/logging/config.py`**:

- Replace `GrafanaConfig` with `OpenObserveConfig`:
  ```python
  @dataclass
  class OpenObserveConfig:
      enabled: bool = False
      endpoint: str = "http://openobserve:5080"
      api_key: str = ""
      org: str = "default"
      stream_name: str = "betterbundle-logs"
      dual_write: bool = True  # Still send to Loki too
  ```
- Remove `PrometheusHandlerConfig`, `TelemetryConfig`, `GCPConfig`, `AWSConfig`
- Update `LoggingConfig` model accordingly

**`python-worker/app/core/logging/logger.py`**:

- In `setup_logging()`, replace `GrafanaHandler` wiring with `OpenObserveHandler`
- Add dual-write logic: if `OPENOBSERVE_DUAL_WRITE` is true, still create a `GrafanaHandler` too

#### OTel Instrumentation (bonus)

In [`python-worker/app/main.py`](python-worker/app/main.py), add:

```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Before starting app
FastAPIInstrumentor.instrument_app(app)
```

Similarly, instrument httpx and SQLAlchemy at import time or at startup.

### 2.2 Remix App — Replace pino-loki with OpenTelemetry JS SDK

#### Files to modify

| File                                                                     | Change                                              |
| ------------------------------------------------------------------------ | --------------------------------------------------- |
| [`better-bundle/package.json`](better-bundle/package.json)               | Add `@opentelemetry/*` packages, remove `pino-loki` |
| [`better-bundle/app/utils/logger.ts`](better-bundle/app/utils/logger.ts) | Replace pino-loki transport with OTel exporter      |

#### Detailed changes

**`better-bundle/package.json`** — add to `dependencies`:

```json
"@opentelemetry/api": "^1.8.0",
"@opentelemetry/sdk-node": "^0.49.0",
"@opentelemetry/exporter-otlp-logs-grpc": "^0.49.0",
"@opentelemetry/exporter-otlp-grpc": "^0.49.0",
"@opentelemetry/instrumentation-http": "^0.49.0",
"@opentelemetry/instrumentation-express": "^0.38.0",
"@opentelemetry/instrumentation-remix": "NOTE: check if exists, else manual"
```

**Remove** `pino-loki` and `pino-pretty` (keep `pino` if used elsewhere).

**`better-bundle/app/utils/logger.ts`** — replace with OTel-based logger:

```typescript
import { logs } from "@opentelemetry/api-logs";
import {
  LoggerProvider,
  SimpleLogRecordProcessor,
} from "@opentelemetry/sdk-logs";
import { OTLPLogExporter } from "@opentelemetry/exporter-otlp-logs-grpc";
import { Resource } from "@opentelemetry/resources";

const openobserveEndpoint =
  process.env.OPENOBSERVE_ENDPOINT || "http://openobserve:5080";
const apiKey = process.env.OPENOBSERVE_API_KEY || "";
const dualWrite = process.env.OPENOBSERVE_DUAL_WRITE === "true";

// Initialize OTel logger
const loggerProvider = new LoggerProvider({
  resource: new Resource({
    "service.name": "remix-app",
    "service.version": "1.0.0",
  }),
});
loggerProvider.addLogRecordProcessor(
  new SimpleLogRecordProcessor(
    new OTLPLogExporter({
      url: `${openobserveEndpoint}/api/otlp/v1/logs`,
      headers: { Authorization: `Bearer ${apiKey}` },
      compression: "gzip",
    })
  )
);
logs.setGlobalLoggerProvider(loggerProvider);

export const logger = {
  info: (msg: string, attrs?: Record<string, unknown>) => {
    logs
      .getLogger("remix-app")
      .emit({ body: msg, attributes: attrs, severityNumber: 9 });
  },
  error: (msg: string, attrs?: Record<string, unknown>) => {
    logs
      .getLogger("remix-app")
      .emit({ body: msg, attributes: attrs, severityNumber: 17 });
  },
  warn: (msg: string, attrs?: Record<string, unknown>) => {
    logs
      .getLogger("remix-app")
      .emit({ body: msg, attributes: attrs, severityNumber: 13 });
  },
  debug: (msg: string, attrs?: Record<string, unknown>) => {
    logs
      .getLogger("remix-app")
      .emit({ body: msg, attributes: attrs, severityNumber: 5 });
  },
};
```

**Alternative simpler approach:** Instead of full OTel JS SDK (which may conflict with Remix/Vite), replace with a lightweight HTTP JSON push to OpenObserve:

```typescript
// lighter-weight approach — direct HTTP JSON push
const logger = {
  _send: async (
    level: string,
    msg: string,
    attrs?: Record<string, unknown>
  ) => {
    if (openobserveEndpoint && apiKey) {
      await fetch(
        `${openobserveEndpoint}/api/default/betterbundle-logs/_json`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${apiKey}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            level,
            message: msg,
            service: "remix-app",
            ...attrs,
            timestamp: new Date().toISOString(),
          }),
        }
      ).catch(() => {}); // fire-and-forget
    }
  },
  info: (msg: string, attrs?: Record<string, unknown>) =>
    logger._send("info", msg, attrs),
  error: (msg: string, attrs?: Record<string, unknown>) =>
    logger._send("error", msg, attrs),
  warn: (msg: string, attrs?: Record<string, unknown>) =>
    logger._send("warn", msg, attrs),
  debug: (msg: string, attrs?: Record<string, unknown>) =>
    logger._send("debug", msg, attrs),
};
```

**Recommendation:** Start with the simpler HTTP JSON push approach (less complexity, fewer dependencies). Only add full OTel JS SDK if distributed tracing across Remix is needed in Phase 3.

### 2.3 Browser Extension Logs

#### Files to modify

| File                                                                                                           | Change                                                             |
| -------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| [`python-worker/app/api/v1/logs.py`](python-worker/app/api/v1/logs.py)                                         | Dual-write to OpenObserve + Loki, or switch entirely               |
| [`better-bundle/extensions/atlas/src/utils/logger.ts`](better-bundle/extensions/atlas/src/utils/logger.ts)     | No change — they POST to `/logs` endpoint, backend handles routing |
| [`better-bundle/extensions/apollo/src/utils/logger.ts`](better-bundle/extensions/apollo/src/utils/logger.ts)   | Same                                                               |
| [`better-bundle/extensions/mercury/src/utils/logger.js`](better-bundle/extensions/mercury/src/utils/logger.js) | Same                                                               |

#### Detailed change for [`python-worker/app/api/v1/logs.py`](python-worker/app/api/v1/logs.py)

Replace `forward_to_loki()` with `forward_to_openobserve()`:

```python
async def forward_to_openobserve(logs_data: Dict[str, Any]) -> bool:
    """
    Forward logs to OpenObserve (and optionally dual-write to Loki).
    """
    if not LOKI_ENABLED:  # Rename to OPENOBSERVE_ENABLED
        return True

    try:
        logs = logs_data.get("logs", {})
        source = logs_data.get("source", "unknown")
        timestamp = logs_data.get("timestamp", datetime.utcnow().isoformat())

        # Transform to OpenObserve JSON format
        openobserve_payload = [
            {
                "timestamp": log_entry.get("time", timestamp),
                "level": log_entry.get("level", "info"),
                "service": log_entry.get("service", "browser-extension"),
                "source": source,
                "message": log_entry.get("msg", ""),
                **{k: v for k, v in log_entry.items() if k not in ("time", "level", "msg", "service")},
            }
            for log_entry in logs
        ]

        # Send to OpenObserve
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{OPENOBSERVE_ENDPOINT}/api/{OPENOBSERVE_ORG}/{OPENOBSERVE_STREAM_NAME}/_json",
                json=openobserve_payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {OPENOBSERVE_API_KEY}",
                },
            )
            # Handle response...

        # Dual-write to Loki if flag is set
        if OPENOBSERVE_DUAL_WRITE:
            await forward_to_loki(logs_data)

        return True
    except Exception as e:
        logger.error(f"Failed to forward logs to OpenObserve: {str(e)}")
        return False
```

Also update the `/logs/health` endpoint to report OpenObserve status.

**Note:** Extension loggers themselves don't change — they POST to `/logs` on the Python worker, which handles the routing. This is good: one change at the backend covers all three extensions.

### 2.4 Replace Promtail

**Decision needed.** Options:

| Option                                 | Pros                                                              | Cons                                                               |
| -------------------------------------- | ----------------------------------------------------------------- | ------------------------------------------------------------------ |
| **A. Docker log driver → OpenObserve** | Zero extra infra, Docker native                                   | OpenObserve must accept syslog or HTTP; may lose structured fields |
| **B. Vector**                          | Rich transforms, OTLP output, single binary                       | Extra service to manage                                            |
| **C. FluentBit**                       | CNCF-graduated, OTLP output, minimal footprint                    | Another config format                                              |
| **D. Keep Promtail temporarily**       | Zero change now, Promtail → Loki still works, OZO can scrape Loki | Defeats purpose of migration                                       |

**Recommendation:** Option B (Vector). Add a lightweight Vector sidecar or daemon that reads Docker logs and ships them to OpenObserve via OTLP. Keep Promtail running in dual mode for Phase 1-2.

**Vector service in compose:**

```yaml
vector:
  image: timberio/vector:0.40-alpine
  container_name: betterbundle-vector-dev
  volumes:
    - ./vector.toml:/etc/vector/vector.toml:ro
    - /var/lib/docker/containers:/var/lib/docker/containers:ro
    - /var/run/docker.sock:/var/run/docker.sock:ro # Optional: for Docker API
  command: --config /etc/vector/vector.toml
  depends_on:
    openobserve:
      condition: service_healthy
  restart: unless-stopped
```

**Simpler Option A approach** (minimalist — aligns with lazy philosophy):

Since all app-level code logs already go through the Python worker or Remix app (which we're instrumenting directly with OTel), Promtail's main job is collecting Docker container logs (stdout/stderr from services like Postgres, Redis, Kafka, etc.). For those:

1. Configure Docker JSON-file log driver with `max-size` (already done)
2. Use OpenObserve's built-in **syslog** or **Docker plugin** support (if available)
3. Or simply rely on the fact that critical infra logs are accessible via `docker logs`

Since the instruction says "Deletion over addition", the **simplest path is to eventually remove Promtail and rely on app-level OTel logging for Python/Remix and Docker log driver for infrastructure**. Add Vector only if Docker log collection is critical.

**Decision for plan:** Skip Vector for now. Remove Promtail in Phase 5. Accept that infra container logs (Postgres, Redis, Kafka) won't be in OpenObserve unless explicitly needed. If needed later, add Vector as a single standalone change.

### 2.5 Verification Steps

1. Set `OPENOBSERVE_DUAL_WRITE=true` in `.env.dev`
2. Restart Python worker — verify logs appear in both OpenObserve and Loki
3. Open OpenObserve UI → Logs → filter by `service:python-worker`
4. Trigger a Remix request — verify logs appear with `service:remix-app`
5. Open a browser extension (Atlas, Apollo, Mercury) — verify logs appear with `service:browser-extension`
6. Set `OPENOBSERVE_DUAL_WRITE=false` — verify Loki stops receiving but OpenObserve continues
7. Check Loki still works (dual-write mode)

---

## Phase 3: Metrics & Distributed Tracing

**Goal:** Enable metrics (Counters, Histograms) and distributed tracing (span propagation across services).

### 3.1 Python Worker Metrics

#### Option A: Vanilla prometheus-client (minimal effort)

Keep `prometheus-client==0.19.0` in [`python-worker/requirements.txt`](python-worker/requirements.txt) and wire a real `/metrics` endpoint in [`python-worker/app/main.py`](python-worker/app/main.py):

```python
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import Counter, Histogram, Gauge
from fastapi.responses import Response

# Define metrics
REQUESTS_TOTAL = Counter("http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"])
REQUEST_DURATION = Histogram("http_request_duration_seconds", "HTTP request duration", ["method", "endpoint"])

@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

Then add a Prometheus scraper config to OpenObserve (OpenObserve can scrape Prometheus endpoints natively). **This is the shortest path.**

#### Option B: OTel Metrics SDK (preferred for unification)

Add to [`python-worker/requirements.txt`](python-worker/requirements.txt):

```txt
opentelemetry-api==1.22.0
opentelemetry-sdk==1.22.0
opentelemetry-exporter-otlp-proto-grpc==1.22.0
```

Create [`python-worker/app/core/observability/metrics.py`](python-worker/app/core/observability/metrics.py) (new file):

```python
"""OTel metrics setup."""
from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

def setup_metrics(endpoint: str, api_key: str):
    exporter = OTLPMetricExporter(
        endpoint=f"{endpoint}/api/otlp/v1/metrics",
        headers={"Authorization": f"Bearer {api_key}"},
        insecure=True,
    )
    reader = PeriodicExportingMetricReader(exporter, export_interval_ms=10_000)
    provider = MeterProvider(metric_readers=[reader])
    metrics.set_meter_provider(provider)
```

Then replace `@monitor`, `@timing`, `@performance_monitor` decorators with OTel instruments.

#### Decision

Start with **Option A** (prometheus-client + `/metrics` endpoint) because:

- Zero new dependencies (already installed)
- OpenObserve can scrape Prometheus endpoints natively
- Simpler than OTel metrics SDK
- Can migrate to Option B later if needed

**Files to modify:**

| File                                                                                                     | Change                                                                             |
| -------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| [`python-worker/app/main.py`](python-worker/app/main.py)                                                 | Add `/metrics` endpoint, instrument FastAPI                                        |
| [`python-worker/app/shared/decorators/monitoring.py`](python-worker/app/shared/decorators/monitoring.py) | Add prometheus_client counters and histograms to `@monitor` and `@async_monitor`   |
| [`python-worker/app/shared/decorators/timing.py`](python-worker/app/shared/decorators/timing.py)         | Add OTel Histogram recording to `@timing`, `@async_timing`, `@performance_monitor` |

**Detailed change for `@monitor` decorator** ([`python-worker/app/shared/decorators/monitoring.py`](python-worker/app/shared/decorators/monitoring.py:15)):

```python
from prometheus_client import Counter, Histogram

FUNCTION_CALLS = Counter(
    "function_calls_total",
    "Total function calls",
    ["function", "status"],
)
FUNCTION_DURATION = Histogram(
    "function_duration_seconds",
    "Function execution duration",
    ["function"],
)

def monitor(func_name: Optional[str] = None):
    def decorator(func):
        name = func_name or func.__name__
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                FUNCTION_CALLS.labels(function=name, status="success").inc()
                FUNCTION_DURATION.labels(function=name).observe(time.time() - start)
                return result
            except Exception as e:
                FUNCTION_CALLS.labels(function=name, status="error").inc()
                raise
        return wrapper
    return decorator
```

### 3.2 Distributed Tracing

#### Python worker

Add tracing setup at app startup:

```python
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HttpxInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.propagators.w3c.tracecontext import W3CTraceContextPropagator

# Set up propagation
trace.set_tracer_provider(TracerProvider())
span_processor = BatchSpanProcessor(
    OTLPSpanExporter(
        endpoint=f"{settings.openobserve.OPENOBSERVE_ENDPOINT}/api/otlp/v1/traces",
        headers={"Authorization": f"Bearer {settings.openobserve.OPENOBSERVE_API_KEY}"},
        insecure=True,
    )
)
trace.get_tracer_provider().add_span_processor(span_processor)
trace.set_tracer_provider(trace.get_tracer_provider())

# Instrument frameworks
FastAPIInstrumentor.instrument_app(app)
HttpxInstrumentor().instrument()
SQLAlchemyInstrumentor().instrument()
```

**Added to [`python-worker/app/main.py`](python-worker/app/main.py)** in `lifespan` startup.

#### Remix app

For distributed tracing across Python → Remix, we need `traceparent` header propagation. The Remix app would need:

```typescript
import { propagation, context, trace } from "@opentelemetry/api";
import { W3CTraceContextPropagator } from "@opentelemetry/core";
import { OTLPTraceExporter } from "@opentelemetry/exporter-otlp-grpc";
import {
  BasicTracerProvider,
  BatchSpanProcessor,
} from "@opentelemetry/sdk-trace-base";
import { HttpInstrumentation } from "@opentelemetry/instrumentation-http";

function setupTracing() {
  const provider = new BasicTracerProvider({
    resource: new Resource({ "service.name": "remix-app" }),
  });
  provider.addSpanProcessor(
    new BatchSpanProcessor(
      new OTLPTraceExporter({
        url: `${openobserveEndpoint}/api/otlp/v1/traces`,
        headers: { Authorization: `Bearer ${apiKey}` },
      })
    )
  );
  provider.register({
    propagator: new W3CTraceContextPropagator(),
  });
  // Instrument HTTP
  new HttpInstrumentation().instrument({});
}
```

**However**, for Phase 3 the **minimum viable tracing** is:

1. Python worker auto-instrumentation (FastAPI, httpx, SQLAlchemy)
2. Kafka message headers propagation (`traceparent` in Kafka message headers)
3. Verify traces appear in OpenObserve

Remix tracing and cross-service trace propagation can be deferred.

#### Kafka trace context propagation

When publishing Kafka messages, inject the current trace context into the message headers:

```python
from opentelemetry import trace
from opentelemetry.propagators.wazero import inject

async def publish_with_tracing(self, topic, value):
    headers = {}
    trace.get_current_span().set_attribute("messaging.system", "kafka")
    trace.get_current_span().set_attribute("messaging.destination", topic)
    # Inject trace context into Kafka headers
    inject(type(headers).setdefault, headers)  # Simplified — use actual carrier
    await producer.send(topic, value=value, headers=headers)
```

### 3.3 Verification Steps

1. Set `OPENOBSERVE_DUAL_WRITE=false` (stop sending to Loki)
2. Hit Python worker API endpoints — verify `/metrics` returns Prometheus data
3. In OpenObserve, check Metrics section — verify `function_calls_total`, `function_duration_seconds` appear
4. Make a request through FastAPI — verify traces appear in OpenObserve Traces section
5. Check that trace includes spans for httpx calls, SQLAlchemy queries
6. Verify that `traceparent` header propagates through Kafka messages

---

## Phase 4: Dashboards & Alerting

**Goal:** Recreate essential dashboards in OpenObserve and configure alert rules.

### 4.1 Dashboard Migration

#### Current Grafana dashboards

The directory [`grafana-provisioning/`](grafana-provisioning/) is mounted in compose files but **does not currently exist** in the working tree (the search returned no results). However, the Git commit history shows:

```
deleted: grafana-provisioning/datasources/datasources.yaml
```

So dashboards were either removed or never committed. **This means we need to create fresh dashboards in OpenObserve from scratch.**

#### Dashboards to create in OpenObserve

| Dashboard            | Panels                                                      | Purpose                |
| -------------------- | ----------------------------------------------------------- | ---------------------- |
| **Service Health**   | Uptime, ping status, error rate, response time              | Quick health overview  |
| **Log Analytics**    | Log volume by service, error rate trend, top error messages | Debugging              |
| **API Performance**  | p50/p95/p99 latency, request rate, error rate by endpoint   | Performance monitoring |
| **Kafka Health**     | Consumer lag, message rate, topic partition count           | Pipeline health        |
| **Database**         | Connection pool usage, query latency, slow queries          | DB health              |
| **Business Metrics** | Recommendations served, conversion rate, top products       | Business KPIs          |

OpenObserve has a built-in dashboard editor — dashboards are stored in the OpenObserve database, not as files. So there's no "file migration" to do. Instead:

1. Log in to OpenObserve UI
2. Create each dashboard manually or via OpenObserve API
3. Export dashboards as JSON and commit to repo for version control

#### Redis dashboards

OpenObserve **cannot query Redis directly** (Grafana could via redis-datasource plugin). If Redis metrics visibility is needed:

- Option 1: Expose Redis metrics via Python worker `/metrics` endpoint (gather Redis INFO command output and expose as Prometheus metrics)
- Option 2: Keep a lightweight Grafana instance solely for Redis dashboards (not recommended — two dashboards tools)
- Option 3: Use OpenObserve's custom dashboard panels with data from OTel metrics exported from the Python worker

**Recommendation:** Option 1 — Python worker exposes `redis_*` Prometheus metrics on the `/metrics` endpoint. This is a small addition:

```python
from prometheus_client import Gauge, Info

REDIS_CONNECTIONS = Gauge("redis_connected_clients", "Connected Redis clients")
REDIS_USED_MEMORY = Gauge("redis_used_memory_bytes", "Used Redis memory")

# In health check or periodic task
async def collect_redis_metrics():
    info = await redis_client.info()
    REDIS_CONNECTIONS.set(info.get("connected_clients", 0))
    REDIS_USED_MEMORY.set(info.get("used_memory", 0))
```

### 4.2 Alert Rules

#### Alert rules to configure in OpenObserve

| Alert Name                      | Condition                                      | Severity | Notification |
| ------------------------------- | ---------------------------------------------- | -------- | ------------ |
| `service_down`                  | No logs/service health check failure for 5 min | Critical | Slack, email |
| `high_error_rate`               | Error rate > 5% over 5 min window              | Warning  | Slack        |
| `high_latency`                  | p95 latency > 2s over 5 min window             | Warning  | Slack        |
| `kafka_consumer_lag`            | Consumer lag > 1000 messages                   | Warning  | Slack        |
| `db_connection_pool_exhaustion` | DB pool utilization > 80%                      | Critical | Slack, email |
| `disk_space`                    | Disk usage > 80% on any volume                 | Warning  | Slack        |
| `high_cpu`                      | CPU usage > 90% for 10+ min                    | Warning  | Slack        |

#### Slack notification channel

In OpenObserve:

1. Settings → Alert Channels → Add Webhook
2. URL: `https://hooks.slack.com/services/YOUR/WEBHOOK/URL`
3. Create alert rules using the OpenObserve query builder:
   - `service:python-worker AND level:error | stats count() by level | where count > 50`
   - Schedule every 5 minutes
   - Trigger if result count > 5

### 4.3 Verification Steps

1. OpenObserve UI → Dashboards → confirm each dashboard renders with data
2. Trigger an error (e.g., invalid API request) — verify dashboard reflects it
3. Trigger a high-latency scenario — verify p95 panel shows the spike
4. Configure Slack alert — verify test notification arrives in Slack channel
5. Stop Python worker — verify `service_down` alert fires

---

## Phase 5: Cleanup & Decommission

**Goal:** Remove all Loki/Promtail/Grafana references, dead code, and old config. Update documentation.

### 5.1 Dead Code Removal Checklist

#### Docker Compose files

| File                                                   | Remove                                                                                   |
| ------------------------------------------------------ | ---------------------------------------------------------------------------------------- |
| [`docker-compose.dev.yml`](docker-compose.dev.yml)     | Entire `# LOGGING STACK` section (lines 223-297): `loki`, `promtail`, `grafana` services |
| [`docker-compose.dev.yml`](docker-compose.dev.yml)     | `loki_data:` and `grafana_data:` from `volumes:` (lines 305-306)                         |
| [`docker-compose.prod.yml`](docker-compose.prod.yml)   | `loki`, `promtail`, `grafana` services (lines 443-577)                                   |
| [`docker-compose.prod.yml`](docker-compose.prod.yml)   | `loki_data:` and `grafana_data:` from `volumes:` (lines 619-620)                         |
| [`docker-compose.local.yml`](docker-compose.local.yml) | Entire `# LOGGING STACK` section (lines 171-253)                                         |
| [`docker-compose.local.yml`](docker-compose.local.yml) | `loki_data:` and `grafana_data:` from `volumes:` (lines 261-262)                         |

#### Config files (if they exist, else the mount references are harmless)

- Remove `loki-config.yaml` (referenced in compose files, already deleted per Git history)
- Remove `promtail-config.yaml` (same)
- Remove `grafana-provisioning/` directory (if it exists)

#### Python worker files

| File                                                                                               | Action                                                                                                                                                                                  |
| -------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`python-worker/app/core/logging/loki_handler.py`](python-worker/app/core/logging/loki_handler.py) | **Delete** — replaced by OTLP handler                                                                                                                                                   |
| [`python-worker/app/core/logging/handlers.py`](python-worker/app/core/logging/handlers.py)         | **Rewrite** — remove `GrafanaHandler`, `PrometheusHandler`, `TelemetryHandler`, `GCPHandler`, `AWSHandler`. Keep `FileHandler`, `ConsoleHandler`, add `OpenObserveHandler`              |
| [`python-worker/app/core/logging/config.py`](python-worker/app/core/logging/config.py)             | **Rewrite** — remove `GrafanaConfig`, `PrometheusHandlerConfig`, `TelemetryConfig`, `GCPConfig`, `AWSConfig`. Keep `FileHandlerConfig`, `ConsoleHandlerConfig`, add `OpenObserveConfig` |
| [`python-worker/app/core/logging/logger.py`](python-worker/app/core/logging/logger.py)             | **Simplify** — remove all dead handler wiring in `setup_logging()`                                                                                                                      |
| [`python-worker/app/core/config/settings.py`](python-worker/app/core/config/settings.py)           | **Clean** — remove `GF_SECURITY_ENABLED`, `GF_SECURITY_URL`, `GF_SECURITY_ADMIN_USER`, `GF_SECURITY_ADMIN_PASSWORD` from `LoggingSettings`                                              |
| [`python-worker/app/core/config/settings.py`](python-worker/app/core/config/settings.py)           | **Clean** — remove grafana from `LOGGING` dict default                                                                                                                                  |
| [`python-worker/app/api/v1/logs.py`](python-worker/app/api/v1/logs.py)                             | **Simplify** — remove `forward_to_loki()`, keep only `forward_to_openobserve()`                                                                                                         |
| [`python-worker/requirements.txt`](python-worker/requirements.txt)                                 | **Remove** `prometheus-client==0.19.0` (if moving to OTel metrics), or keep if using Option A from Phase 3                                                                              |

#### Remix app files

| File                                                                     | Action                                                     |
| ------------------------------------------------------------------------ | ---------------------------------------------------------- |
| [`better-bundle/app/utils/logger.ts`](better-bundle/app/utils/logger.ts) | **Rewrite** — remove pino-loki import and transport        |
| [`better-bundle/package.json`](better-bundle/package.json)               | **Remove** `pino-loki` and `pino-pretty` from dependencies |

#### Environment files

| File                                   | Action                                                    |
| -------------------------------------- | --------------------------------------------------------- |
| [`env.example`](env.example)           | **Remove** GRAFANA\_\* and LOKI_URL sections              |
| [`env.dev.example`](env.dev.example)   | **Remove** GRAFANA*ADMIN*\* and LOKI_URL lines            |
| [`env.prod.example`](env.prod.example) | **Remove** GRAFANA*ADMIN*_, GF*SECURITY*_, LOKI_URL lines |

#### Gorse config

| File                         | Action                                                |
| ---------------------------- | ----------------------------------------------------- |
| [`config.toml`](config.toml) | Already enabled in Phase 1 — no further change needed |

### 5.2 Multi-stage Cleanup Strategy

To minimize risk, cleanup happens in stages:

**Stage A — Code first** (works with both stacks running):

1. Update Python loggers to prefer OpenObserve, fall back to Loki
2. Update Remix logger
3. Update logs API endpoint
4. Deploy these changes while both stacks run

**Stage B — Config cleanup** (after verification):

1. Remove Loki/Promtail/Grafana from compose files
2. Remove Loki/Promtail config files
3. Remove Grafana provisioning dir
4. Remove env vars for old stack

**Stage C — Dead code removal** (after config cleanup):

1. Delete `loki_handler.py`
2. Clean up `handlers.py`, `config.py`
3. Remove `prometheus-client` from requirements if using OTel metrics

### 5.3 Verification Steps

1. `docker-compose -f docker-compose.dev.yml down loki promtail grafana`
2. Restart Python worker — verify no errors about missing handlers
3. Check logs appear in OpenObserve — nothing breaks
4. `docker-compose -f docker-compose.dev.yml rm -f loki promtail grafana`
5. Remove volumes: `docker volume rm betterbundle_loki_data betterbundle_grafana_data`
6. Full `docker-compose up -d` — verify all services start cleanly
7. Run the app through normal flows — verify logging, metrics, tracing all work

---

## Appendix A: Environment Variables — Old vs New Mapping

| Old Variable                 | Old Purpose                 | New Variable              | New Purpose                             |
| ---------------------------- | --------------------------- | ------------------------- | --------------------------------------- |
| `LOKI_URL`                   | Loki HTTP endpoint          | `OPENOBSERVE_ENDPOINT`    | OpenObserve HTTP/OTLP endpoint          |
| `GRAFANA_ADMIN_USER`         | Grafana admin login         | `ZO_ROOT_USER_EMAIL`      | OpenObserve admin login                 |
| `GRAFANA_ADMIN_PASSWORD`     | Grafana admin password      | `ZO_ROOT_USER_PASSWORD`   | OpenObserve admin password              |
| —                            | —                           | `OPENOBSERVE_ORG`         | OpenObserve organization (default)      |
| —                            | —                           | `OPENOBSERVE_API_KEY`     | API key for programmatic access         |
| —                            | —                           | `OPENOBSERVE_STREAM_NAME` | Default log stream name                 |
| —                            | —                           | `OPENOBSERVE_DUAL_WRITE`  | Dual-write to old Loki during migration |
| —                            | —                           | `ZO_S3_STORAGE`           | Enable S3 storage backend               |
| —                            | —                           | `ZO_S3_BUCKET`            | S3 bucket name                          |
| —                            | —                           | `ZO_S3_REGION`            | S3 region                               |
| —                            | —                           | `ZO_S3_ACCESS_KEY`        | S3 access key                           |
| —                            | —                           | `ZO_S3_SECRET_KEY`        | S3 secret key                           |
| —                            | —                           | `ZO_S3_ENDPOINT`          | S3-compatible endpoint (MinIO in dev)   |
| —                            | —                           | `ZO_LOCAL_MODE`           | Local mode flag (no S3 needed)          |
| —                            | —                           | `ZO_DATA_DIR`             | Local data directory                    |
| `GF_SECURITY_ENABLED`        | Grafana Loki handler toggle | Removed                   | Replaced by OpenObserve                 |
| `GF_SECURITY_URL`            | Grafana Loki URL            | Removed                   | Replaced by OPENOBSERVE_ENDPOINT        |
| `GF_SECURITY_ADMIN_USER`     | Grafana admin user          | Removed                   | Replaced by ZO_ROOT_USER_EMAIL          |
| `GF_SECURITY_ADMIN_PASSWORD` | Grafana admin password      | Removed                   | Replaced by ZO_ROOT_USER_PASSWORD       |
| `GF_INSTALL_PLUGINS`         | Grafana Redis plugin        | Removed                   | Not applicable to OpenObserve           |

---

## Appendix B: Docker Compose Service Diff

### Dev — Old Stack (to remove)

```yaml
services:
  loki:
    image: grafana/loki:3.4.1
    container_name: betterbundle-loki-dev
    ports: ["3100:3100"]
    volumes: [./loki-config.yaml:/etc/loki/loki-config.yaml, loki_data:/loki]
    command: -config.file=/etc/loki/loki-config.yaml -config.expand-env=true
    healthcheck: ...

  promtail:
    image: grafana/promtail:3.4.1
    container_name: betterbundle-promtail-dev
    volumes: [./promtail-config.yaml:/etc/promtail/promtail-config.yaml, ...]
    command: -config.file=/etc/promtail/promtail-config.yaml
    depends_on: [loki]

  grafana:
    image: grafana/grafana:11.4.0
    container_name: betterbundle-grafana-dev
    ports: ["3001:3000"]
    environment: [GF_*]
    volumes:
      [
        grafana_data:/var/lib/grafana,
        ./grafana-provisioning:/etc/grafana/provisioning,
      ]
    depends_on: [loki]

volumes:
  loki_data:
  grafana_data:
```

### Dev — New Stack (to add)

```yaml
services:
  openobserve:
    image: quay.io/openobserve/openobserve:latest
    container_name: betterbundle-openobserve-dev
    ports: ["5080:5080"]
    volumes: [openobserve_data:/data]
    env_file: [.env.dev]
    environment:
      ZO_ROOT_USER_EMAIL: ${ZO_ROOT_USER_EMAIL}
      ZO_ROOT_USER_PASSWORD: ${ZO_ROOT_USER_PASSWORD}
      ZO_LOCAL_MODE: ${ZO_LOCAL_MODE:-true}
    healthcheck: ...

  minio:
    image: minio/minio:latest
    container_name: betterbundle-minio-dev
    ports: ["9000:9000", "9001:9001"]
    volumes: [minio_data:/data]
    command: server /data --console-address ":9001"

volumes:
  openobserve_data:
  minio_data:
```

**Note:** Remove old stack only in Phase 5. Phase 1-4 run both stacks side-by-side.

---

## Appendix C: Dependency Changes

### Python Worker (`python-worker/requirements.txt`)

**Add:**

```txt
# OpenTelemetry
opentelemetry-sdk==1.22.0
opentelemetry-api==1.22.0
opentelemetry-exporter-otlp==1.22.0
opentelemetry-exporter-otlp-proto-grpc==1.22.0
opentelemetry-exporter-otlp-proto-http==1.22.0
opentelemetry-instrumentation-fastapi==0.43b0
opentelemetry-instrumentation-httpx==0.43b0
opentelemetry-instrumentation-sqlalchemy==0.43b0
```

**Remove (Phase 5):**

```txt
prometheus-client==0.19.0
```

**Keep (still in use):**

```txt
httpx==0.27.0  # Used for OpenObserve HTTP push and Loki dual-write
```

### Remix App (`better-bundle/package.json`)

**Add to `dependencies`:**

```json
"@opentelemetry/api": "^1.8.0",
"@opentelemetry/sdk-logs": "^0.49.0",
"@opentelemetry/exporter-otlp-logs-grpc": "^0.49.0",
"@opentelemetry/resources": "^1.22.0",
"@opentelemetry/semantic-conventions": "^1.22.0"
```

Or if using the simpler HTTP push approach (recommended):

```json
(no new dependencies — use native fetch)
```

**Remove from `dependencies` (Phase 5):**

```json
"pino-loki": "^2.6.0",
"pino-pretty": "^13.1.2"
```

**Keep (still in use):**

```json
"pino": "^10.1.0"  # May be used elsewhere; if not, remove too
```

---

## Appendix D: Rollback Plan

If migration fails or OpenObserve has issues, roll back per-phase:

### Phase 1 Rollback

```bash
# Stop and remove OpenObserve services
docker-compose -f docker-compose.dev.yml stop openobserve minio
docker-compose -f docker-compose.dev.yml rm -f openobserve minio

# Remove volumes
docker volume rm betterbundle_openobserve_data betterbundle_minio_data

# Revert env files (git checkout)
git checkout env.example env.dev.example env.prod.example

# Revert settings.py (git checkout)
git checkout python-worker/app/core/config/settings.py
```

### Phase 2 Rollback

```bash
# Revert all Python logging changes
git checkout python-worker/app/core/logging/
git checkout python-worker/app/core/config/settings.py
git checkout python-worker/requirements.txt

# Reinstall dependencies
cd python-worker && pip install -r requirements.txt

# Revert Remix logger
git checkout better-bundle/app/utils/logger.ts
git checkout better-bundle/package.json
cd better-bundle && npm install

# Revert logs API
git checkout python-worker/app/api/v1/logs.py

# Set OPENOBSERVE_DUAL_WRITE=false and ensure LOKI_URL still works
```

### Phase 3 Rollback

```bash
# Remove /metrics endpoint and instrumentation
git checkout python-worker/app/main.py
git checkout python-worker/app/shared/decorators/
git checkout python-worker/requirements.txt
cd python-worker && pip install -r requirements.txt
```

### Phase 4 Rollback

No code rollback needed — dashboards are in OpenObserve UI. Simply delete them.

### Phase 5 Rollback (full revert)

```bash
# Restore all old stack services
git checkout docker-compose.dev.yml docker-compose.prod.yml docker-compose.local.yml
git checkout env.example env.dev.example env.prod.example
git checkout config.toml
git checkout python-worker/app/core/logging/
git checkout python-worker/app/core/config/settings.py
git checkout python-worker/requirements.txt
git checkout python-worker/app/api/v1/logs.py
git checkout better-bundle/app/utils/logger.ts
git checkout better-bundle/package.json

# Reinstall all deps
cd python-worker && pip install -r requirements.txt
cd better-bundle && npm install

# Restore Loki/Promtail/Grafana configs
# (If loki-config.yaml/promtail-config.yaml were deleted, recreate from git history)

# Restart full old stack
docker-compose -f docker-compose.dev.yml up -d
```

---

## Migration Dependencies Graph

```
Phase 1 ───► Phase 2 ───► Phase 3 ───► Phase 4 ───► Phase 5
  │              │              │              │
  ├─ Compose     ├─ OTel SDK    ├─ /metrics    ├─ Dashboards
  ├─ Env vars    ├─ Python      ├─ Tracing     ├─ Alerts
  ├─ Gorse OTel  ├─ Remix       ├─ Decorators  │
  └─ Settings    ├─ Browser     └─ Kafka       └─ Cleanup
                 └─ Promtail
```

**Phase 1** must be complete before Phase 2 (need OpenObserve running to test log shipping).

**Phase 2** can proceed independently per service (Python, Remix, Browser) — no hard cross-dependency.

**Phase 3** can start partially in parallel with Phase 2 (adding `/metrics` endpoint doesn't depend on logging migration).

**Phase 4** depends on Phase 2-3 having data flowing into OpenObserve.

**Phase 5** must be last — only remove old stack after everything is verified.
