# OpenObserve Configuration

Dashboards and alert rules for the BetterBundle observability stack running on OpenObserve.

## Quick Start

```bash
# Make the import script executable
chmod +x import.sh

# Import everything (replace <api_key> with your OpenObserve API key)
./import.sh http://localhost:5080 default <api_key>
```

Nothing has to be run by hand, though. A one-shot `openobserve-import` service
runs the same import on `docker compose up` in dev and local, and
`.github/workflows/deploy-prod.yml` runs it on every production deploy. The
import is idempotent — it matches dashboards by title and alerts by name and
updates them in place, so repeated runs never accumulate duplicates.

### Prerequisites

- OpenObserve instance running (see Phase 1 deployment)
- API key with permissions to create dashboards and alerts
- `python3` on the machine running the import (stdlib only — no pip install,
  no `jq`, so it works unchanged on a bare Ubuntu host)

### SLACK_WEBHOOK_URL

Not currently set in `.env.dev` or `.env.prod`. Without it:

- the Slack **destination** cannot be created (the webhook is the one field only
  the secret can supply);
- **alerts** are still imported, as long as a destination already exists in the
  org — an alert left pointing at a renamed stream does not error, it silently
  never fires, so getting the definitions in matters more than the delivery path;
- **dashboards** are unaffected.

Set it to get Slack delivery working.

## Verifying the dashboards

```bash
KEY=$(grep -m1 '^OPENOBSERVE_API_KEY=' ../.env.dev | cut -d= -f2-) \
  python3 dashboards/verify_panels.py
```

Runs every panel's real query and classifies each one. This exists because the
OpenObserve UI cannot tell you the difference between the four:

| Result | Meaning |
|---|---|
| `ok` | returned rows |
| `BROKEN` | unknown field, and OpenObserve suggested a real one — a typo in our query |
| `UNSEEN` | unknown field with no suggestion, on a stream that exists — an attribute nothing has sent yet |
| `EMPTY` | query is valid, nothing matched — e.g. no 5xx in the window |

A panel with a misspelled column renders in the UI as an empty chart, identical
to a healthy panel in a quiet period. Exits non-zero only on `BROKEN`, so it can
gate a deploy.

## Editing dashboards

Edit `dashboards/generate.py`, not the JSON. The JSON is generated:

```bash
python3 dashboards/generate.py
```

OpenObserve's dashboard schema is v8 — panels live under `tabs[].panels[]`, and
each panel needs an explicit `queries[].fields` block naming the stream and the
x/y columns. A POST with an unrecognised shape returns 200 and silently stores a
dashboard with no panels, so hand-editing is unusually easy to get wrong.

## Dashboards

### 1. Service Health (`dashboards/service-health.json`)

Core service health at a glance:
| Panel | Type | Stream | Description |
|---|---|---|---|
| HTTP Request Rate | line | `python-worker-metrics` | Request throughput per minute |
| HTTP Error Rate | line | `python-worker-metrics` | Rate of HTTP 5xx responses |
| Request Latency (p50/p95/p99) | line | `python-worker-metrics` | Histogram percentiles of request duration |
| Kafka Consumer Lag | gauge | `python-worker-metrics` | Latest consumer lag value |
| DB Connection Pool Size | gauge | `python-worker-metrics` | Current database pool size |
| Cache Hit Ratio | stat | `python-worker-metrics` | cache_hits / (cache_hits + cache_misses) |
| Active Services | table | `python-worker-logs` | Services emitting logs in the last 5m |

### 2. Business KPIs (`dashboards/business-kpis.json`)

Business and recommendation metrics:
| Panel | Type | Stream | Description |
|---|---|---|---|
| Recommendations Served | line | `python-worker-metrics` | Recommendation throughput |
| Recommendation Latency (p50/p95) | line | `python-worker-metrics` | Recommendation duration percentiles |
| Top Recommendation Sources | bar | `python-worker-metrics` | Recommendations broken down by source label |
| Function Error Rate by Module | line | `python-worker-metrics` | Error rate segmented by module |
| Slow Functions | table | `python-worker-metrics` | `function.threshold_exceeded` events |

### 3. Logs Explorer (`dashboards/logs-explorer.json`)

Log analysis and search:
| Panel | Type | Stream | Description |
|---|---|---|---|
| Log Volume by Service | bar | `python-worker-logs` | Log count grouped by service |
| Log Volume by Level | bar | `python-worker-logs` | Log count grouped by severity level |
| Error Logs Timeline | line | `python-worker-logs` | Error log rate per 5 minutes |
| Log Search | table | `python-worker-logs` | Searchable log table (last 100 entries) |
| Top Error Messages | table | `python-worker-logs` | Most frequent error messages (24h) |

## Alert Rules

All alerts are defined under `alerts/` and shipped with sensible defaults.

| Alert                       | Stream                  | Condition                              | Evaulation Window | Frequency | Severity |
| --------------------------- | ----------------------- | -------------------------------------- | ----------------- | --------- | -------- |
| High HTTP Error Rate        | `python-worker-metrics` | `error_rate > 0.05` (5% errors per 5m) | 5m                | 5m        | critical |
| High P95 Latency            | `python-worker-metrics` | `p95 > 2.0s`                           | 5m                | 5m        | warning  |
| Kafka Consumer Lag Too High | `python-worker-metrics` | `max_lag > 10000`                      | 5m                | 5m        | warning  |
| Python Worker Down          | `python-worker-logs`    | `log_count < 1` (no logs for 2m)       | 2m                | 1m        | critical |
| Low Cache Hit Ratio         | `python-worker-metrics` | `hit_ratio < 0.5`                      | 10m               | 10m       | warning  |

### Adjusting Thresholds

Edit the `condition` field in any alert JSON file. For example, to raise the latency threshold to 3 seconds:

```json
"condition": "p95 > 3.0"
```

Re-run the import script to update the alert in OpenObserve.

## Notifications

All alerts ship with a Slack notification channel. Set the environment variable `SLACK_WEBHOOK_URL` before importing, or replace the webhook URL inline:

```json
"notifications": [
  {
    "type": "slack",
    "webhook_url": "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
  }
]
```

Other supported notification types (check [OpenObserve docs](https://openobserve.ai/docs)) can be added to the `notifications` array.

## Stream Reference

The dashboards query two OpenObserve streams:

- **`python-worker-metrics`** — Time-series metrics (counters, histograms, gauges) emitted by the Python worker via OpenTelemetry.
- **`python-worker-logs`** — Structured log entries from the Python worker.

Metric names match the definitions in [`python-worker/app/core/metrics.py`](../python-worker/app/core/metrics.py).
