"""Generate OpenObserve v8 dashboard JSON from a compact spec.

The old files used an invented shape -- {"title","description","panels":[...]}
with a "query" string per panel. OpenObserve accepted the POST, ignored the
unknown "panels" key entirely, and stored a dashboard with zero tabs. That is
why every dashboard in the UI was empty: not a rendering bug, a schema that was
never the product's schema. v8 nests panels inside tabs, and every panel needs
an explicit queries[].fields block naming the stream and the x/y columns.
"""
import json
from pathlib import Path

OUT = Path("openobserve-config/dashboards")

# Must match metrics.py NS.
NS = "betterbundle"


def panel(pid, title, desc, stream, sql, y_label, ptype="line", x=0, y=0, w=12, h=9,
          stream_type="metrics", x_column="_timestamp", x_label="Timestamp"):
    """One panel. `x_column`/`x_label` matter: a bar, table or donut panel groups
    by an attribute, not by time, and leaving its axis described as "Timestamp"
    mislabels the very column the reader is trying to read."""
    return {
        "id": f"panel_{pid}",
        "type": ptype,
        "title": title,
        "description": desc,
        "config": {"show_legends": True, "legends_position": None,
                   "base_map": None, "map_view": None},
        "queryType": "sql",
        "queries": [{
            "query": sql,
            "vrlFunctionQuery": None,
            "customQuery": True,
            "fields": {
                "stream": stream,
                "stream_type": stream_type,
                "x": [{"label": x_label, "alias": "x_axis_1",
                       "column": x_column, "color": None}],
                "y": [{"label": y_label, "alias": "y_axis_1",
                       "column": "value", "color": None}],
                "z": [],
                "filter": {"filterType": "group", "logicalOperator": "AND",
                           "conditions": []},
            },
            "config": {"promql_legend": ""},
        }],
        "layout": {"x": x, "y": y, "w": w, "h": h, "i": pid},
    }


# Panel heights, in OpenObserve grid rows (~30px each).
#
# Everything was h=9 — about 270px — which has to hold a title, a legend, an
# x-axis with timestamps and the plot itself. The plot got whatever was left,
# which is why the cards read as cramped. Tables get more because their content
# is rows: at h=9 a table showing "slowest routes" displayed three of them.
#
# Change these and every dashboard follows: relayout() recomputes the y of each
# row from the heights below, so the panels cannot end up overlapping the way
# hand-maintained coordinates eventually do.
HEIGHTS = {"table": 16, "default": 14}


def height_for(ptype):
    return HEIGHTS.get(ptype, HEIGHTS["default"])


def relayout(dash):
    """Recompute every panel's height and y from its type.

    Rows are taken from the y values already in the spec — panels sharing a y
    are one row — so the intended arrangement is preserved and only the
    vertical sizing changes.
    """
    for tab in dash["tabs"]:
        rows = {}
        for panel_ in tab["panels"]:
            rows.setdefault(panel_["layout"]["y"], []).append(panel_)
        cursor = 0
        for original_y in sorted(rows):
            row = rows[original_y]
            tallest = max(height_for(p_["type"]) for p_ in row)
            for p_ in row:
                p_["layout"]["y"] = cursor
                p_["layout"]["h"] = height_for(p_["type"])
            cursor += tallest
    return dash


def dashboard(title, description, panels):
    return {"title": title, "description": description,
            "tabs": [{"tabId": "default", "name": "Default", "panels": panels}]}


def ts(sql_select, stream, extra=""):
    """A time-bucketed series. histogram() is OpenObserve's time bucketer."""
    return (f"SELECT histogram(_timestamp) as x_axis_1, {sql_select} as y_axis_1"
            f"{extra} FROM \"{stream}\" GROUP BY x_axis_1{', breakdown' if 'breakdown' in extra else ''}"
            f" ORDER BY x_axis_1")


# --- Service Health -------------------------------------------------------
# Stream names are the post-rename, post-semconv ones: http.server.request.*
# arrives once OTEL_SEMCONV_STABILITY_OPT_IN=http is set, and the betterbundle.*
# ones once the worker restarts with the new metrics.py.
health = dashboard(
    "Service Health Overview",
    "Request rate, errors and latency for every service (RED method)",
    [
        panel(1, "Request Rate", "Requests per time bucket, all services",
              "http_server_request_duration_count",
              ts("sum(value)", "http_server_request_duration_count"), "Requests",
              x=0, y=0, w=12, h=9),
        panel(2, "Error Rate (5xx)", "Server errors only",
              "http_server_request_duration_count",
              "SELECT histogram(_timestamp) as x_axis_1, sum(value) as y_axis_1 "
              "FROM \"http_server_request_duration_count\" "
              "WHERE http_response_status_code >= 500 GROUP BY x_axis_1 ORDER BY x_axis_1",
              "5xx", x=12, y=0, w=12, h=9),
        panel(3, "Average Latency", "sum/count of the duration histogram, in seconds",
              "http_server_request_duration_sum",
              "SELECT histogram(_timestamp) as x_axis_1, sum(value) as y_axis_1 "
              "FROM \"http_server_request_duration_sum\" GROUP BY x_axis_1 ORDER BY x_axis_1",
              "Seconds", x=0, y=9, w=12, h=9),
        panel(4, "In-flight Requests", "Concurrent requests being served",
              "http_server_active_requests",
              ts("max(value)", "http_server_active_requests"), "Active",
              x=12, y=9, w=12, h=9),
        panel(5, "Requests by Status Code", "Where the traffic is landing",
              "http_server_request_duration_count",
              "SELECT http_response_status_code as x_axis_1, sum(value) as y_axis_1 "
              "FROM \"http_server_request_duration_count\" "
              "GROUP BY x_axis_1 ORDER BY y_axis_1 DESC", "Requests",
              ptype="bar", x=0, y=18, w=12, h=9,
              x_column="http_response_status_code", x_label="Status Code"),
        panel(7, "Client Errors (4xx)", "Separate from 5xx on purpose: a 404 storm is a "
              "broken link or a bad integration, not a failing service",
              "http_server_request_duration_count",
              "SELECT histogram(_timestamp) as x_axis_1, sum(value) as y_axis_1 "
              "FROM \"http_server_request_duration_count\" "
              "WHERE http_response_status_code >= 400 AND http_response_status_code < 500 "
              "GROUP BY x_axis_1 ORDER BY x_axis_1", "4xx",
              x=0, y=27, w=24, h=9),
        panel(6, "Slowest Routes", "By total time, so a slow rare route still shows",
              "http_server_request_duration_sum",
              "SELECT http_route as x_axis_1, sum(value) as y_axis_1 "
              "FROM \"http_server_request_duration_sum\" "
              "GROUP BY x_axis_1 ORDER BY y_axis_1 DESC", "Seconds",
              ptype="table", x=12, y=18, w=12, h=9,
              x_column="http_route", x_label="Route"),
    ])

# Saturation — the fourth golden signal, and the one nothing else here reports.
# Latency, traffic and errors all describe what the SERVICE did; these describe
# whether the process itself is the thing in the way.
#
# Stream names carry the `cpython` runtime segment
# (`process.runtime.cpython.cpu.utilization`), which is the instrumentation's
# doing, not ours — worth knowing before writing a query against a guessed name.
health["tabs"][0]["panels"] += [
    panel(8, "Process CPU", "Utilisation of the worker process, 0-1 per core",
          "process_runtime_cpython_cpu_utilization",
          ts("max(value)", "process_runtime_cpython_cpu_utilization"), "Utilisation",
          x=0, y=36, w=8, h=9),
    panel(9, "Process Memory (RSS)", "Resident set size in bytes",
          "process_runtime_cpython_memory",
          ts("max(value)", "process_runtime_cpython_memory"), "Bytes",
          x=8, y=36, w=8, h=9),
    panel(10, "Thread Count", "A climbing thread count under steady traffic is a leak",
          "process_runtime_cpython_thread_count",
          ts("max(value)", "process_runtime_cpython_thread_count"), "Threads",
          x=16, y=36, w=8, h=9),
]

# --- Application Performance ---------------------------------------------
perf = dashboard(
    "Application Performance",
    "Recommendation serving, cache behaviour and Kafka consumption",
    [
        panel(1, "Recommendation Latency", "Total seconds spent serving recommendations",
              "betterbundle_recommendation_duration_sum",
              ts("sum(value)", "betterbundle_recommendation_duration_sum"), "Seconds",
              x=0, y=0, w=12, h=9),
        panel(2, "Recommendation Requests", "Served requests, from the histogram count",
              "betterbundle_recommendation_duration_count",
              ts("sum(value)", "betterbundle_recommendation_duration_count"), "Requests",
              x=12, y=0, w=12, h=9),
        panel(3, "Cache Hits", "Lookups served from Redis",
              "betterbundle_cache_hits",
              ts("sum(value)", "betterbundle_cache_hits"), "Hits",
              x=0, y=9, w=8, h=9),
        panel(4, "Cache Misses", "Lookups that fell through to the source",
              "betterbundle_cache_misses",
              ts("sum(value)", "betterbundle_cache_misses"), "Misses",
              x=8, y=9, w=8, h=9),
        panel(5, "Cache Misses by Namespace", "Which cache is cold",
              "betterbundle_cache_misses",
              "SELECT namespace as x_axis_1, sum(value) as y_axis_1 "
              "FROM \"betterbundle_cache_misses\" GROUP BY x_axis_1 ORDER BY y_axis_1 DESC",
              "Misses", ptype="bar", x=16, y=9, w=8, h=9,
              x_column="namespace", x_label="Namespace"),
        panel(6, "Kafka Messages Consumed", "By topic",
              "messaging_client_consumed_messages",
              "SELECT topic as x_axis_1, sum(value) as y_axis_1 "
              "FROM \"messaging_client_consumed_messages\" "
              "GROUP BY x_axis_1 ORDER BY y_axis_1 DESC", "Messages",
              ptype="bar", x=0, y=18, w=24, h=9,
              x_column="topic", x_label="Topic"),
    ])

# --- Business KPIs --------------------------------------------------------
kpi = dashboard(
    "Business KPIs",
    "What the product actually delivered to shoppers",
    [
        panel(1, "Recommendations Served", "Individual recommendations returned",
              "betterbundle_recommendations_served",
              ts("sum(value)", "betterbundle_recommendations_served"), "Recommendations",
              x=0, y=0, w=24, h=9),
        panel(2, "By Surface", "Which storefront surface asked",
              "betterbundle_recommendations_served",
              "SELECT context as x_axis_1, sum(value) as y_axis_1 "
              "FROM \"betterbundle_recommendations_served\" "
              "GROUP BY x_axis_1 ORDER BY y_axis_1 DESC", "Recommendations",
              ptype="bar", x=0, y=9, w=12, h=9,
              x_column="context", x_label="Surface"),
        panel(3, "By Source", "Edges, fallback or cache -- how the answer was found",
              "betterbundle_recommendations_served",
              "SELECT source as x_axis_1, sum(value) as y_axis_1 "
              "FROM \"betterbundle_recommendations_served\" "
              "GROUP BY x_axis_1 ORDER BY y_axis_1 DESC", "Recommendations",
              ptype="donut", x=12, y=9, w=12, h=9,
              x_column="source", x_label="Source"),
    ])

# --- Logs -----------------------------------------------------------------
logs = dashboard(
    "Logs Explorer",
    "Log volume and errors across every service",
    [
        # Counts are scaled by 1/log_sample_rate, not count(*).
        #
        # In production only ~10% of INFO records are shipped (see
        # app/core/logging/sampling.py), and each kept one carries the rate it
        # was kept at. A raw count(*) would therefore report a tenth of the
        # real volume and read as a service that had gone quiet — the exact
        # failure the panel exists to catch. WARNING and above are never
        # sampled and have no rate attribute, so COALESCE(..., 1) counts them
        # once each.
        panel(1, "Log Volume by Service", "Sampling-corrected: each record counts "
              "as 1/log_sample_rate, so this is real volume, not shipped volume",
              "default",
              "SELECT histogram(_timestamp) as x_axis_1, "
              "SUM(1.0 / COALESCE(log_sample_rate, 1.0)) as y_axis_1 "
              "FROM \"default\" GROUP BY x_axis_1 ORDER BY x_axis_1", "Log lines (est.)",
              x=0, y=0, w=24, h=9, stream_type="logs"),
        panel(2, "Errors by Service", "severity ERROR or above",
              "default",
              "SELECT service_name as x_axis_1, count(*) as y_axis_1 FROM \"default\" "
              "WHERE severity IN ('ERROR','FATAL','CRITICAL') "
              "GROUP BY x_axis_1 ORDER BY y_axis_1 DESC", "Errors",
              ptype="bar", x=0, y=9, w=12, h=9, stream_type="logs",
              x_column="service_name", x_label="Service"),
        panel(3, "Volume by Severity", "Sampling-corrected. Without the correction "
              "ERROR looks disproportionately common, because only INFO is sampled",
              "default",
              "SELECT severity as x_axis_1, "
              "SUM(1.0 / COALESCE(log_sample_rate, 1.0)) as y_axis_1 FROM \"default\" "
              "GROUP BY x_axis_1 ORDER BY y_axis_1 DESC", "Log lines (est.)",
              ptype="donut", x=12, y=9, w=12, h=9, stream_type="logs",
              x_column="severity", x_label="Severity"),
    ])

# --- LLM Cost ------------------------------------------------------------
# `gen_ai.client.token.usage` is a histogram, so OpenObserve splits it into
# _sum/_count/_bucket streams; _sum is the token TOTAL and is what a usage chart
# wants. Cost is a counter, so its stream is undivided.
llm = dashboard(
    "LLM Cost",
    "Gemini spend and token usage, priced at call time",
    [
        panel(1, "Spend Over Time", "USD, summed per time bucket",
              f"{NS}_gen_ai_cost",
              ts("sum(value)", f"{NS}_gen_ai_cost"), "USD",
              x=0, y=0, w=24, h=9),
        panel(2, "Spend by Model", "Which model the money is going to",
              f"{NS}_gen_ai_cost",
              f'SELECT gen_ai_request_model as x_axis_1, sum(value) as y_axis_1 '
              f'FROM "{NS}_gen_ai_cost" GROUP BY x_axis_1 ORDER BY y_axis_1 DESC',
              "USD", ptype="bar", x=0, y=9, w=12, h=9,
              x_column="gen_ai_request_model", x_label="Model"),
        panel(3, "Tokens by Type", "Input vs output -- they are priced differently, "
              "so the split is what explains the bill",
              "gen_ai_client_token_usage_sum",
              'SELECT gen_ai_token_type as x_axis_1, sum(value) as y_axis_1 '
              'FROM "gen_ai_client_token_usage_sum" GROUP BY x_axis_1 ORDER BY y_axis_1 DESC',
              "Tokens", ptype="donut", x=12, y=9, w=12, h=9,
              x_column="gen_ai_token_type", x_label="Token Type"),
        panel(4, "Token Volume Over Time", "Total tokens per time bucket",
              "gen_ai_client_token_usage_sum",
              ts("sum(value)", "gen_ai_client_token_usage_sum"), "Tokens",
              x=0, y=18, w=12, h=9),
        panel(5, "LLM Calls", "Request count, from the histogram's _count series",
              "gen_ai_client_token_usage_count",
              ts("sum(value)", "gen_ai_client_token_usage_count"), "Calls",
              x=12, y=18, w=12, h=9),
    ])

# --- Database Performance -------------------------------------------------
# Built on the TRACES stream, not on a metric. opentelemetry-instrumentation-
# sqlalchemy emits a span per statement and no duration metric, and the spans
# are strictly richer: they carry the statement and the table, so a slow
# endpoint can be followed down to the query that made it slow. `duration` on an
# OpenObserve span is MICROSECONDS, hence the /1000 into milliseconds.
db = dashboard(
    "Database Performance",
    "Query latency, throughput and pool saturation for Postgres and Redis",
    [
        panel(1, "Query Latency (avg ms)", "Mean statement duration across all engines",
              "default",
              'SELECT histogram(_timestamp) as x_axis_1, avg(duration)/1000 as y_axis_1 '
              'FROM "default" WHERE db_system IS NOT NULL '
              'GROUP BY x_axis_1 ORDER BY x_axis_1', "Milliseconds",
              x=0, y=0, w=12, h=9, stream_type="traces"),
        panel(2, "Query Throughput", "Statements executed per time bucket",
              "default",
              'SELECT histogram(_timestamp) as x_axis_1, count(*) as y_axis_1 '
              'FROM "default" WHERE db_system IS NOT NULL '
              'GROUP BY x_axis_1 ORDER BY x_axis_1', "Statements",
              x=12, y=0, w=12, h=9, stream_type="traces"),
        panel(3, "Slowest Operations", "By average duration -- a rare slow query still shows",
              "default",
              'SELECT operation_name as x_axis_1, avg(duration)/1000 as y_axis_1 '
              'FROM "default" WHERE db_system IS NOT NULL '
              'GROUP BY x_axis_1 ORDER BY y_axis_1 DESC', "Avg ms",
              ptype="table", x=0, y=9, w=12, h=9, stream_type="traces",
              x_column="operation_name", x_label="Operation"),
        panel(4, "Statements by Engine", "Postgres vs Redis share of the traffic",
              "default",
              'SELECT db_system as x_axis_1, count(*) as y_axis_1 FROM "default" '
              'WHERE db_system IS NOT NULL GROUP BY x_axis_1 ORDER BY y_axis_1 DESC',
              "Statements", ptype="donut", x=12, y=9, w=12, h=9, stream_type="traces",
              x_column="db_system", x_label="Engine"),
        panel(5, "Connection Pool In Use", "The saturation signal: a pool pinned at its "
              "ceiling is why requests queue",
              "db_client_connections_usage",
              ts("max(value)", "db_client_connections_usage"), "Connections",
              x=0, y=18, w=12, h=9),
        panel(6, "Failed Statements", "Spans whose status is ERROR",
              "default",
              'SELECT histogram(_timestamp) as x_axis_1, count(*) as y_axis_1 '
              'FROM "default" WHERE db_system IS NOT NULL AND span_status = \'ERROR\' '
              'GROUP BY x_axis_1 ORDER BY x_axis_1', "Errors",
              x=12, y=18, w=12, h=9, stream_type="traces"),
    ])

# --- Theme Adaptation -----------------------------------------------------
# Reads the theme_adapt.* span attributes the storefront sends on every
# recommendations request (see theme-adapt.js and _record_theme_adapt). Its one
# job is to name the themes whose CSS our probe lists fail on, which is the only
# question we cannot answer from our own side.
#
# These panels stay empty until a storefront running the updated Phoenix
# extension serves a request -- the attributes do not exist in the traces schema
# before the first one arrives.
theme = dashboard(
    "Theme Adaptation",
    "Which storefront themes the CSS probes succeed and fail on",
    [
        panel(1, "Themes Where The Button Probe Failed", "These are the themes to fix "
              "first: the widget fell back to its own colours",
              "default",
              'SELECT theme_adapt_theme_name as x_axis_1, count(*) as y_axis_1 '
              'FROM "default" WHERE theme_adapt_button = \'none\' '
              'GROUP BY x_axis_1 ORDER BY y_axis_1 DESC', "Requests",
              ptype="bar", x=0, y=0, w=24, h=9, stream_type="traces",
              x_column="theme_adapt_theme_name", x_label="Theme"),
        panel(2, "Which Selector Tier Answered", "platform / structural / substring -- "
              "a long tail here means the lists are carrying too much",
              "default",
              'SELECT theme_adapt_button as x_axis_1, count(*) as y_axis_1 '
              'FROM "default" WHERE theme_adapt_button IS NOT NULL '
              'GROUP BY x_axis_1 ORDER BY y_axis_1 DESC', "Requests",
              ptype="donut", x=0, y=9, w=12, h=9, stream_type="traces",
              x_column="theme_adapt_button", x_label="Selector"),
        panel(3, "Button Fill Style", "outline-inverted is the branch where we change "
              "the theme's intent rather than copy it",
              "default",
              'SELECT theme_adapt_button_fill as x_axis_1, count(*) as y_axis_1 '
              'FROM "default" WHERE theme_adapt_button_fill IS NOT NULL '
              'GROUP BY x_axis_1 ORDER BY y_axis_1 DESC', "Requests",
              ptype="bar", x=12, y=9, w=12, h=9, stream_type="traces",
              x_column="theme_adapt_button_fill", x_label="Fill"),
        panel(4, "Price Probe Outcome", "The probe most likely to miss, since it has no "
              "platform-guaranteed selector",
              "default",
              'SELECT theme_adapt_price as x_axis_1, count(*) as y_axis_1 '
              'FROM "default" WHERE theme_adapt_price IS NOT NULL '
              'GROUP BY x_axis_1 ORDER BY y_axis_1 DESC', "Requests",
              ptype="bar", x=0, y=18, w=12, h=9, stream_type="traces",
              x_column="theme_adapt_price", x_label="Selector"),
        panel(5, "Adaptation Switched Off", "Merchants driving colours from block "
              "settings instead",
              "default",
              'SELECT theme_adapt_enabled as x_axis_1, count(*) as y_axis_1 '
              'FROM "default" WHERE theme_adapt_enabled IS NOT NULL '
              'GROUP BY x_axis_1 ORDER BY y_axis_1 DESC', "Requests",
              ptype="donut", x=12, y=18, w=12, h=9, stream_type="traces",
              x_column="theme_adapt_enabled", x_label="Enabled"),
    ])

# --- Reconcilers ----------------------------------------------------------
# The six periodic loops started in main.py's lifespan had metrics and spans
# but nothing that read them: no panel, no alert. A loop whose task dies simply
# stops incrementing its counter, and with nothing watching, that is
# indistinguishable from a quiet period — the same silent-failure shape the
# ingestion backstop exists to catch for webhooks.
#
# "Runs by Reconciler" is the liveness panel: every loop that is alive appears,
# so a MISSING series is the signal. Read it knowing the intervals differ by
# two orders of magnitude (enrichment 120s, fx_refresher 24h), so a flat line
# for fx_refresher is normal and a flat line for enrichment is not.
reconcilers = dashboard(
    "Reconcilers & Background Jobs",
    "Liveness, failures and business effect of the six periodic loops",
    [
        panel(1, "Runs by Reconciler", "One series per loop. A series that "
              "disappears is a dead task — that is the thing to look for here",
              f"{NS}_reconciler_runs_total",
              f'SELECT reconciler as x_axis_1, sum(value) as y_axis_1 '
              f'FROM "{NS}_reconciler_runs_total" GROUP BY x_axis_1 '
              f'ORDER BY y_axis_1 DESC', "Runs",
              ptype="bar", x=0, y=0, w=12, h=9,
              x_column="reconciler", x_label="Reconciler"),
        panel(2, "Failed Runs", "status=error only. Empty is the healthy state, "
              "which is why the panel next to it exists to prove the loops ran at all",
              f"{NS}_reconciler_runs_total",
              f'SELECT reconciler as x_axis_1, sum(value) as y_axis_1 '
              f'FROM "{NS}_reconciler_runs_total" WHERE status = \'error\' '
              f'GROUP BY x_axis_1 ORDER BY y_axis_1 DESC', "Failures",
              ptype="bar", x=12, y=0, w=12, h=9,
              x_column="reconciler", x_label="Reconciler"),
        panel(3, "Run Rate Over Time", "Liveness as a time series: each loop should "
              "show a steady cadence at its own interval",
              f"{NS}_reconciler_runs_total",
              ts("sum(value)", f"{NS}_reconciler_runs_total"), "Runs",
              x=0, y=9, w=24, h=9),
        panel(4, "Time Spent Reconciling", "Total seconds per bucket. A sweep growing "
              "without the work growing means it is falling behind",
              f"{NS}_reconciler_duration_sum",
              ts("sum(value)", f"{NS}_reconciler_duration_sum"), "Seconds",
              x=0, y=18, w=12, h=9),
        panel(5, "Slowest Reconcilers", "By total time, so a slow rare sweep still shows",
              f"{NS}_reconciler_duration_sum",
              f'SELECT reconciler as x_axis_1, sum(value) as y_axis_1 '
              f'FROM "{NS}_reconciler_duration_sum" GROUP BY x_axis_1 '
              f'ORDER BY y_axis_1 DESC', "Seconds",
              ptype="table", x=12, y=18, w=12, h=9,
              x_column="reconciler", x_label="Reconciler"),
        # The business counters below had no home anywhere. Each one is a
        # recovery: a number above zero means the primary path failed and the
        # backstop caught it, so a sustained non-zero line is a bug report
        # about the primary path, not a success story about the backstop.
        panel(6, "Orders Recovered by the Ingestion Backstop", "Orders Shopify had "
              "that we did not. Persistently non-zero means webhook delivery is broken",
              f"{NS}_reconciler_backstop_missed_orders",
              ts("sum(value)", f"{NS}_reconciler_backstop_missed_orders"), "Orders",
              x=0, y=27, w=12, h=9),
        panel(7, "Orders Recovered by Attribution", "Stamped orders that were never "
              "attributed — each one is revenue that would not have been billed",
              f"{NS}_reconciler_attribution_missed_orders",
              ts("sum(value)", f"{NS}_reconciler_attribution_missed_orders"), "Orders",
              x=12, y=27, w=12, h=9),
        panel(8, "Shops Reactivated on Cycle Rollover", "Suspended shops whose Shopify "
              "usage cycle renewed",
              f"{NS}_reconciler_rollover_reactivated_shops",
              ts("sum(value)", f"{NS}_reconciler_rollover_reactivated_shops"), "Shops",
              x=0, y=36, w=12, h=9),
        panel(9, "Commissions Drained on Reactivation", "Backlogged commissions billed "
              "once a shop came back",
              f"{NS}_reconciler_rollover_drained_commissions",
              ts("sum(value)", f"{NS}_reconciler_rollover_drained_commissions"),
              "Commissions", x=12, y=36, w=12, h=9),
        panel(10, "Reconciler Errors in Logs", "The traceback behind a failed run",
              "default",
              'SELECT histogram(_timestamp) as x_axis_1, count(*) as y_axis_1 '
              'FROM "default" WHERE severity = \'ERROR\' '
              'AND instrumentation_library_name LIKE \'%reconcil%\' '
              'GROUP BY x_axis_1 ORDER BY x_axis_1', "Errors",
              x=0, y=45, w=24, h=9, stream_type="logs"),
    ])


for name, d in [("service-health", health), ("application-performance", perf),
                ("business-kpis", kpi), ("logs-explorer", logs),
                ("llm-cost", llm), ("database-performance", db),
                ("theme-adaptation", theme), ("reconcilers", reconcilers)]:
    relayout(d)
    p = OUT / f"{name}.json"
    p.write_text(json.dumps(d, indent=2) + "\n")
    n = sum(len(t["panels"]) for t in d["tabs"])
    print(f"  {p}  ({n} panels)")
