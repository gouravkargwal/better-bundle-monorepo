# OpenObserve Configuration

Dashboards and alert rules for the BetterBundle observability stack running on OpenObserve.

## Quick Start

```bash
# Make the import script executable
chmod +x import.sh

# Import everything (replace <api_key> with your OpenObserve API key)
./import.sh http://localhost:5080 default <api_key>
```

### Prerequisites

- OpenObserve instance running (see Phase 1 deployment)
- API key with permissions to create dashboards and alerts
- `curl` installed on the machine running the import

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
