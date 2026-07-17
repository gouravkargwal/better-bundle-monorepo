#!/usr/bin/env python3
"""
Generate OpenObserve dashboards with the correct JSON schema.

Run: python3 infrastructure/scripts/generate-dashboards.py

This generates files in infrastructure/dashboards/ that match the
exact format OpenObserve expects for UI import (matching the format
produced by OpenObserve's own export function).
"""

import json
import os
from datetime import datetime, timezone

DASHBOARDS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "dashboards"
)

# ── Helper: create a default panel config (required by OpenObserve) ──
def default_config(unit="numbers", decimals=0, legends_position=None):
    return {
        "show_legends": True,
        "legends_position": legends_position,
        "unit": unit,
        "decimals": decimals,
        "line_thickness": 1.5,
        "step_value": "0",
        "top_results_others": False,
        "axis_border_show": False,
        "label_option": {"rotate": 0},
        "show_symbol": True,
        "line_interpolation": "smooth",
        "legend_width": {"unit": "px"},
        "base_map": {"type": "osm"},
        "map_type": {"type": "world"},
        "map_view": {"zoom": 1, "lat": 0, "lng": 0},
        "map_symbol_style": {
            "size": "by Value",
            "size_by_value": {"min": 1, "max": 100},
            "size_fixed": 2,
        },
        "drilldown": [],
        "mark_line": [],
        "override_config": [],
        "connect_nulls": False,
        "no_value_replacement": "",
        "wrap_table_cells": False,
        "table_transpose": False,
        "table_dynamic_columns": False,
        "color": {
            "mode": "palette-classic-by-series",
            "fixedColor": ["#53ca53"],
            "seriesBy": "last",
        },
        "trellis": {"layout": None, "num_of_columns": 1},
    }


def default_query_config():
    return {
        "promql_legend": "",
        "layer_type": "scatter",
        "weight_fixed": 1,
        "limit": 0,
        "min": 0,
        "max": 100,
        "time_shift": [],
    }


def default_filter():
    return {
        "filterType": "group",
        "logicalOperator": "AND",
        "conditions": [],
    }


def field_entry(label, alias, column, aggregation_function=None,
                color=None, sort_by=None):
    entry = {
        "label": label,
        "alias": alias,
        "column": column,
        "color": color,
        "isDerived": False,
        "havingConditions": [],
    }
    if aggregation_function:
        entry["aggregationFunction"] = aggregation_function
    if sort_by:
        entry["sortBy"] = sort_by
    return entry


def make_panel(panel_id, panel_type, title, sql_query, stream,
               stream_type, x_fields, y_fields, breakdown_fields=None,
               config_override=None, description=""):
    if breakdown_fields is None:
        breakdown_fields = []

    return {
        "id": panel_id,
        "type": panel_type,
        "title": title,
        "description": description,
        "config": config_override or default_config(),
        "queryType": "sql",
        "queries": [
            {
                "query": sql_query,
                "vrlFunctionQuery": "",
                "customQuery": False,
                "fields": {
                    "stream": stream,
                    "stream_type": stream_type,
                    "x": x_fields,
                    "y": y_fields,
                    "z": [],
                    "breakdown": breakdown_fields,
                    "filter": default_filter(),
                },
                "config": default_query_config(),
            }
        ],
        "layout": {
            "x": 0,
            "y": 0,
            "w": 12,
            "h": 8,
            "i": "1",
            "moved": False,
        },
        "htmlContent": "",
        "markdownContent": "",
        "customChartContent": (
            " // To know more about ECharts , \n"
            "// visit: https://echarts.apache.org/examples/en/index.html \n"
            "// Define your ECharts 'option' here. \n"
            "option = { \n \n};"
        ),
    }


def make_dashboard(dashboard_id, title, description, tabs,
                   default_time="1h"):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
          datetime.now(timezone.utc).strftime("%f")[:3] + "Z"
    return {
        "version": 5,
        "dashboardId": dashboard_id,
        "title": title,
        "description": description,
        "role": "",
        "owner": "",
        "created": now,
        "tabs": tabs,
        "variables": {
            "list": [],
            "showDynamicFilters": True,
        },
        "defaultDatetimeDuration": {
            "type": "relative",
            "relativeTimePeriod": default_time,
        },
    }


# ── Helper: create panels with layout set properly ──
def set_layout(panel, x, y, w, h, i):
    panel["layout"] = {"x": x, "y": y, "w": w, "h": h, "i": i, "moved": False}
    return panel


# ═══════════════════════════════════════════════════════════
# DASHBOARD 1: System Health
# ═══════════════════════════════════════════════════════════
def build_system_health():
    panels = []

    p = make_panel(
        "panel_log_volume", "area", "Log Volume by Service",
        'SELECT histogram(_timestamp) as "time", count(*) as "count" '
        'FROM "default" WHERE service IN '
        "('remix-app', 'python-worker', 'django-admin') "
        "GROUP BY time, service ORDER BY time",
        "default", "logs",
        [field_entry("Time", "time", "_timestamp", "histogram")],
        [field_entry("Count", "count", "_timestamp", "count")],
        [field_entry("Service", "service", "service")],
    )
    panels.append(set_layout(p, 0, 0, 12, 8, 1))

    p = make_panel(
        "panel_error_rate", "area", "Error Rate by Service",
        "SELECT histogram(_timestamp) as \"time\", count(*) as \"count\" "
        "FROM \"default\" WHERE LOWER(level) IN ('error', 'critical', 'fatal') "
        "GROUP BY time, service ORDER BY time",
        "default", "logs",
        [field_entry("Time", "time", "_timestamp", "histogram")],
        [field_entry("Errors", "count", "_timestamp", "count")],
        [field_entry("Service", "service", "service")],
    )
    panels.append(set_layout(p, 12, 0, 12, 8, 2))

    p = make_panel(
        "panel_log_levels", "h-bar", "Log Levels Distribution",
        "SELECT level, count(*) as \"count\" FROM \"default\" "
        "GROUP BY level ORDER BY count DESC",
        "default", "logs",
        [field_entry("Level", "level", "level")],
        [field_entry("Count", "count", "_timestamp", "count")],
    )
    panels.append(set_layout(p, 0, 8, 8, 8, 3))

    p = make_panel(
        "panel_recent_errors", "table", "Recent Errors & Warnings",
        "SELECT _timestamp as \"time\", service, level, logger, message "
        "FROM \"default\" WHERE LOWER(level) IN ('error', 'warning', 'critical') "
        "ORDER BY _timestamp DESC LIMIT 50",
        "default", "logs",
        [
            field_entry("Time", "time", "_timestamp"),
            field_entry("Service", "service", "service"),
            field_entry("Level", "level", "level"),
            field_entry("Logger", "logger", "logger"),
            field_entry("Message", "message", "message"),
        ],
        [],
    )
    panels.append(set_layout(p, 8, 8, 16, 8, 4))

    p = make_panel(
        "panel_service_uptime", "table", "Services Summary (Last 15 min)",
        "SELECT service, count(*) as \"log_count\", "
        "sum(CASE WHEN LOWER(level) IN ('error','critical','fatal') THEN 1 ELSE 0 END) as \"error_count\", "
        "min(_timestamp) as \"first_seen\", max(_timestamp) as \"last_seen\" "
        "FROM \"default\" WHERE _timestamp > now() - INTERVAL '15' MINUTE "
        "GROUP BY service ORDER BY service",
        "default", "logs",
        [
            field_entry("Service", "service", "service"),
            field_entry("Log Count", "log_count", "_timestamp", "count"),
            field_entry("Errors", "error_count", "level", "sum"),
            field_entry("First Seen", "first_seen", "_timestamp", "min"),
            field_entry("Last Seen", "last_seen", "_timestamp", "max"),
        ],
        [],
    )
    panels.append(set_layout(p, 0, 16, 24, 6, 5))

    return make_dashboard(
        "system_health", "System Health",
        "Service health monitoring across Remix, Python Worker, Django Admin, and Extensions",
        [{"name": "Overview", "tabId": "overview", "panels": panels}],
        "1h"
    )


# ═══════════════════════════════════════════════════════════
# DASHBOARD 2: Billing Operations
# ═══════════════════════════════════════════════════════════
def build_billing_operations():
    panels = []

    p = make_panel(
        "panel_billing_activity", "area", "Billing Events Over Time",
        "SELECT histogram(_timestamp) as \"time\", count(*) as \"count\" "
        "FROM \"default\" WHERE service = 'python-worker' AND "
        "(message LIKE '%commission%' OR message LIKE '%billing%' "
        "OR message LIKE '%subscription%') GROUP BY time ORDER BY time",
        "default", "logs",
        [field_entry("Time", "time", "_timestamp", "histogram")],
        [field_entry("Events", "count", "_timestamp", "count")],
    )
    panels.append(set_layout(p, 0, 0, 12, 8, 1))

    p = make_panel(
        "panel_billing_errors", "v-bar", "Billing Errors",
        "SELECT histogram(_timestamp) as \"time\", count(*) as \"count\" "
        "FROM \"default\" WHERE service = 'python-worker' AND "
        "LOWER(level) IN ('error','critical') AND "
        "(message LIKE '%commission%' OR message LIKE '%billing%') "
        "GROUP BY time ORDER BY time",
        "default", "logs",
        [field_entry("Time", "time", "_timestamp", "histogram")],
        [field_entry("Errors", "count", "_timestamp", "count")],
    )
    panels.append(set_layout(p, 12, 0, 12, 8, 2))

    p = make_panel(
        "panel_commission_processing", "area", "Commission Processing Activity",
        "SELECT histogram(_timestamp) as \"time\", count(*) as \"count\" "
        "FROM \"default\" WHERE message LIKE '%commission%' "
        "GROUP BY time, level ORDER BY time",
        "default", "logs",
        [field_entry("Time", "time", "_timestamp", "histogram")],
        [field_entry("Count", "count", "_timestamp", "count")],
        [field_entry("Level", "level", "level")],
    )
    panels.append(set_layout(p, 0, 8, 12, 8, 3))

    p = make_panel(
        "panel_webhook_events", "area", "Webhook Activity (Remix App)",
        "SELECT histogram(_timestamp) as \"time\", count(*) as \"count\" "
        "FROM \"default\" WHERE service = 'remix-app' "
        "AND message LIKE '%webhook%' GROUP BY time ORDER BY time",
        "default", "logs",
        [field_entry("Time", "time", "_timestamp", "histogram")],
        [field_entry("Webhooks", "count", "_timestamp", "count")],
    )
    panels.append(set_layout(p, 12, 8, 12, 8, 4))

    p = make_panel(
        "panel_subscription_events", "table", "Recent Subscription & Billing Events",
        "SELECT _timestamp as \"time\", service, level, message "
        "FROM \"default\" WHERE (message LIKE '%subscription%' "
        "OR message LIKE '%billing_cycle%' OR message LIKE '%cap%') "
        "AND LENGTH(message) > 0 ORDER BY _timestamp DESC LIMIT 50",
        "default", "logs",
        [
            field_entry("Time", "time", "_timestamp"),
            field_entry("Service", "service", "service"),
            field_entry("Level", "level", "level"),
            field_entry("Message", "message", "message"),
        ],
        [],
    )
    panels.append(set_layout(p, 0, 16, 24, 8, 5))

    p = make_panel(
        "panel_billing_summary", "table", "Billing Summary Stats",
        "SELECT service, count(*) as \"total_logs\", "
        "sum(CASE WHEN LOWER(level) = 'error' THEN 1 ELSE 0 END) as \"errors\", "
        "sum(CASE WHEN message LIKE '%commission%' THEN 1 ELSE 0 END) as \"commissions\", "
        "sum(CASE WHEN message LIKE '%billing%' THEN 1 ELSE 0 END) as \"billing_events\", "
        "sum(CASE WHEN message LIKE '%subscription%' THEN 1 ELSE 0 END) as \"subscription_changes\" "
        "FROM \"default\" WHERE _timestamp > now() - INTERVAL '1' HOUR AND "
        "(message LIKE '%commission%' OR message LIKE '%billing%' "
        "OR message LIKE '%subscription%' OR service = 'remix-app') "
        "GROUP BY service ORDER BY service",
        "default", "logs",
        [
            field_entry("Service", "service", "service"),
            field_entry("Total Logs", "total_logs", "_timestamp", "count"),
            field_entry("Errors", "errors", "level", "sum"),
            field_entry("Commissions", "commissions", "message", "sum"),
            field_entry("Billing Events", "billing_events", "message", "sum"),
            field_entry("Subscription Changes", "subscription_changes", "message", "sum"),
        ],
        [],
    )
    panels.append(set_layout(p, 0, 24, 24, 6, 6))

    return make_dashboard(
        "billing_operations", "Billing Operations",
        "Billing-specific monitoring: commissions, subscriptions, billing events, and revenue",
        [{"name": "Billing", "tabId": "billing", "panels": panels}],
        "24h"
    )


# ═══════════════════════════════════════════════════════════
# DASHBOARD 3: Tracing & Latency
# ═══════════════════════════════════════════════════════════
def build_tracing_latency():
    panels = []

    p = make_panel(
        "panel_trace_volume", "area", "Trace Volume by Service",
        "SELECT histogram(_timestamp) as \"time\", count(*) as \"count\" "
        "FROM \"default\" WHERE _timestamp > now() - INTERVAL '1' HOUR "
        "AND service IN ('remix-app', 'python-worker', 'django-admin') "
        "GROUP BY time, service ORDER BY time",
        "default", "logs",
        [field_entry("Time", "time", "_timestamp", "histogram")],
        [field_entry("Requests", "count", "_timestamp", "count")],
        [field_entry("Service", "service", "service")],
    )
    panels.append(set_layout(p, 0, 0, 12, 8, 1))

    p = make_panel(
        "panel_slowest_services", "h-bar", "Slowest Services (Avg Duration)",
        "SELECT service, avg(duration_ms) as \"avg_duration\" "
        "FROM (SELECT service, cast(split_part(message, 'duration=', 2) as double) "
        "as duration_ms FROM \"default\" WHERE message LIKE '%duration=%' "
        "AND _timestamp > now() - INTERVAL '1' HOUR) "
        "GROUP BY service ORDER BY avg_duration DESC LIMIT 10",
        "default", "logs",
        [field_entry("Service", "service", "service")],
        [field_entry("Avg Duration (ms)", "avg_duration", "duration_ms", "avg")],
    )
    panels.append(set_layout(p, 12, 0, 12, 8, 2))

    p = make_panel(
        "panel_error_traces", "area", "Error Traces Over Time",
        "SELECT histogram(_timestamp) as \"time\", count(*) as \"count\" "
        "FROM \"default\" WHERE LOWER(level) IN ('error', 'critical', 'fatal') "
        "AND _timestamp > now() - INTERVAL '1' HOUR "
        "GROUP BY time, service ORDER BY time",
        "default", "logs",
        [field_entry("Time", "time", "_timestamp", "histogram")],
        [field_entry("Errors", "count", "_timestamp", "count")],
        [field_entry("Service", "service", "service")],
    )
    panels.append(set_layout(p, 0, 8, 12, 8, 3))

    p = make_panel(
        "panel_webhook_latency", "area", "Webhook Processing Latency",
        "SELECT histogram(_timestamp) as \"time\", count(*) as \"count\" "
        "FROM \"default\" WHERE service = 'remix-app' "
        "AND message LIKE '%webhook%' "
        "AND _timestamp > now() - INTERVAL '1' HOUR "
        "GROUP BY time ORDER BY time",
        "default", "logs",
        [field_entry("Time", "time", "_timestamp", "histogram")],
        [field_entry("Webhooks", "count", "_timestamp", "count")],
    )
    panels.append(set_layout(p, 12, 8, 12, 8, 4))

    p = make_panel(
        "panel_recent_traces", "table", "Recent Traces",
        "SELECT _timestamp as \"time\", service, level, message "
        "FROM \"default\" WHERE _timestamp > now() - INTERVAL '30' MINUTE "
        "ORDER BY _timestamp DESC LIMIT 50",
        "default", "logs",
        [
            field_entry("Time", "time", "_timestamp"),
            field_entry("Service", "service", "service"),
            field_entry("Level", "level", "level"),
            field_entry("Message", "message", "message"),
        ],
        [],
    )
    panels.append(set_layout(p, 0, 16, 24, 8, 5))

    return make_dashboard(
        "tracing_latency", "Tracing & Latency",
        "Distributed trace monitoring: latency, error traces, service performance",
        [{"name": "Traces", "tabId": "traces", "panels": panels}],
        "1h"
    )


# ═══════════════════════════════════════════════════════════
# DASHBOARD 4: Shop Operations
# ═══════════════════════════════════════════════════════════
def build_shop_operations():
    panels = []

    p = make_panel(
        "panel_top_shops_volume", "h-bar", "Top Shops by Log Volume (Last 24h)",
        "SELECT shop_id, count(*) as \"log_count\" "
        "FROM \"default\" WHERE shop_id IS NOT NULL "
        "AND _timestamp > now() - INTERVAL '24' HOUR "
        "GROUP BY shop_id ORDER BY log_count DESC LIMIT 20",
        "default", "logs",
        [field_entry("Shop ID", "shop_id", "shop_id")],
        [field_entry("Log Count", "log_count", "_timestamp", "count")],
    )
    panels.append(set_layout(p, 0, 0, 12, 8, 1))

    p = make_panel(
        "panel_top_shops_errors", "h-bar", "Shops with Most Errors (Last 24h)",
        "SELECT shop_id, count(*) as \"error_count\" "
        "FROM \"default\" WHERE shop_id IS NOT NULL "
        "AND LOWER(level) IN ('error', 'critical', 'fatal') "
        "AND _timestamp > now() - INTERVAL '24' HOUR "
        "GROUP BY shop_id ORDER BY error_count DESC LIMIT 20",
        "default", "logs",
        [field_entry("Shop ID", "shop_id", "shop_id")],
        [field_entry("Errors", "error_count", "_timestamp", "count")],
    )
    panels.append(set_layout(p, 12, 0, 12, 8, 2))

    p = make_panel(
        "panel_shop_activity_timeline", "area", "Shop Activity Timeline",
        "SELECT histogram(_timestamp) as \"time\", count(*) as \"count\" "
        "FROM \"default\" WHERE shop_id IS NOT NULL "
        "AND _timestamp > now() - INTERVAL '6' HOUR "
        "GROUP BY time ORDER BY time",
        "default", "logs",
        [field_entry("Time", "time", "_timestamp", "histogram")],
        [field_entry("Events", "count", "_timestamp", "count")],
    )
    panels.append(set_layout(p, 0, 8, 16, 8, 3))

    p = make_panel(
        "panel_shop_errors_timeline", "area", "Shop Error Timeline",
        "SELECT histogram(_timestamp) as \"time\", count(*) as \"count\" "
        "FROM \"default\" WHERE shop_id IS NOT NULL "
        "AND LOWER(level) IN ('error', 'warning') "
        "AND _timestamp > now() - INTERVAL '6' HOUR "
        "GROUP BY time ORDER BY time",
        "default", "logs",
        [field_entry("Time", "time", "_timestamp", "histogram")],
        [field_entry("Issues", "count", "_timestamp", "count")],
    )
    panels.append(set_layout(p, 16, 8, 8, 8, 4))

    p = make_panel(
        "panel_shop_recent_errors", "table", "Recent Errors by Shop",
        "SELECT _timestamp as \"time\", shop_id, service, level, message "
        "FROM \"default\" WHERE shop_id IS NOT NULL "
        "AND LOWER(level) IN ('error', 'critical') "
        "ORDER BY _timestamp DESC LIMIT 50",
        "default", "logs",
        [
            field_entry("Time", "time", "_timestamp"),
            field_entry("Shop ID", "shop_id", "shop_id"),
            field_entry("Service", "service", "service"),
            field_entry("Level", "level", "level"),
            field_entry("Message", "message", "message"),
        ],
        [],
    )
    panels.append(set_layout(p, 0, 16, 24, 8, 5))

    return make_dashboard(
        "shop_operations", "Shop Operations",
        "Per-shop activity monitoring: top shops, error hotspots, recent activity",
        [{"name": "Shops", "tabId": "shops", "panels": panels}],
        "24h"
    )


# ═══════════════════════════════════════════════════════════
# DASHBOARD 5: Kafka & Infrastructure
# ═══════════════════════════════════════════════════════════
def build_kafka_infrastructure():
    panels = []

    p = make_panel(
        "panel_kafka_activity", "area", "Kafka Consumer Activity",
        "SELECT histogram(_timestamp) as \"time\", count(*) as \"count\" "
        "FROM \"default\" WHERE message LIKE '%consumer%' "
        "OR message LIKE '%kafka%' OR message LIKE '%topic%' "
        "AND _timestamp > now() - INTERVAL '6' HOUR "
        "GROUP BY time, service ORDER BY time",
        "default", "logs",
        [field_entry("Time", "time", "_timestamp", "histogram")],
        [field_entry("Events", "count", "_timestamp", "count")],
        [field_entry("Service", "service", "service")],
    )
    panels.append(set_layout(p, 0, 0, 12, 8, 1))

    p = make_panel(
        "panel_kafka_errors", "v-bar", "Kafka Errors",
        "SELECT histogram(_timestamp) as \"time\", count(*) as \"count\" "
        "FROM \"default\" WHERE (message LIKE '%kafka%' "
        "OR message LIKE '%consumer%') "
        "AND LOWER(level) IN ('error', 'warning') "
        "AND _timestamp > now() - INTERVAL '6' HOUR "
        "GROUP BY time ORDER BY time",
        "default", "logs",
        [field_entry("Time", "time", "_timestamp", "histogram")],
        [field_entry("Errors", "count", "_timestamp", "count")],
    )
    panels.append(set_layout(p, 12, 0, 12, 8, 2))

    p = make_panel(
        "panel_job_processing", "area", "Job Processing Activity",
        "SELECT histogram(_timestamp) as \"time\", count(*) as \"count\" "
        "FROM \"default\" WHERE message LIKE '%job%' "
        "OR message LIKE '%processing%' OR message LIKE '%event%' "
        "AND _timestamp > now() - INTERVAL '6' HOUR "
        "GROUP BY time, level ORDER BY time",
        "default", "logs",
        [field_entry("Time", "time", "_timestamp", "histogram")],
        [field_entry("Jobs", "count", "_timestamp", "count")],
        [field_entry("Level", "level", "level")],
    )
    panels.append(set_layout(p, 0, 8, 12, 8, 3))

    p = make_panel(
        "panel_infrastructure_summary", "table", "Infrastructure Summary (Last 1h)",
        "SELECT service, count(*) as \"log_count\", "
        "sum(CASE WHEN LOWER(level) = 'error' THEN 1 ELSE 0 END) as \"errors\", "
        "sum(CASE WHEN message LIKE '%kafka%' THEN 1 ELSE 0 END) as \"kafka_events\", "
        "sum(CASE WHEN message LIKE '%job%' THEN 1 ELSE 0 END) as \"jobs\", "
        "sum(CASE WHEN (message LIKE '%db%' OR message LIKE '%database%' "
        "OR message LIKE '%redis%') THEN 1 ELSE 0 END) as \"data_events\" "
        "FROM \"default\" WHERE _timestamp > now() - INTERVAL '1' HOUR "
        "GROUP BY service ORDER BY service",
        "default", "logs",
        [
            field_entry("Service", "service", "service"),
            field_entry("Log Count", "log_count", "_timestamp", "count"),
            field_entry("Errors", "errors", "level", "sum"),
            field_entry("Kafka Events", "kafka_events", "message", "sum"),
            field_entry("Jobs", "jobs", "message", "sum"),
            field_entry("Data Events", "data_events", "message", "sum"),
        ],
        [],
    )
    panels.append(set_layout(p, 0, 16, 24, 6, 4))

    p = make_panel(
        "panel_recent_infra_events", "table", "Recent Infrastructure Events",
        "SELECT _timestamp as \"time\", service, level, message "
        "FROM \"default\" WHERE (message LIKE '%kafka%' "
        "OR message LIKE '%consumer%' OR message LIKE '%redis%' "
        "OR message LIKE '%database%' OR message LIKE '%job%' "
        "OR message LIKE '%initialized%' OR message LIKE '%started%' "
        "OR message LIKE '%shutdown%') ORDER BY _timestamp DESC LIMIT 50",
        "default", "logs",
        [
            field_entry("Time", "time", "_timestamp"),
            field_entry("Service", "service", "service"),
            field_entry("Level", "level", "level"),
            field_entry("Message", "message", "message"),
        ],
        [],
    )
    panels.append(set_layout(p, 0, 22, 24, 8, 5))

    return make_dashboard(
        "kafka_infrastructure", "Kafka & Infrastructure",
        "Kafka consumer activity, job processing, and infrastructure health monitoring",
        [{"name": "Infrastructure", "tabId": "infrastructure", "panels": panels}],
        "24h"
    )


# ═══════════════════════════════════════════════════════════
# Generate all dashboards
# ═══════════════════════════════════════════════════════════
def main():
    os.makedirs(DASHBOARDS_DIR, exist_ok=True)

    dashboards = [
        ("system-health.json", build_system_health()),
        ("billing-operations.json", build_billing_operations()),
        ("tracing-latency.json", build_tracing_latency()),
        ("shop-operations.json", build_shop_operations()),
        ("kafka-infrastructure.json", build_kafka_infrastructure()),
    ]

    for filename, data in dashboards:
        filepath = os.path.join(DASHBOARDS_DIR, filename)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        print(f"✅ Generated {filename}")

    print(f"\nAll dashboards generated in {DASHBOARDS_DIR}/")


if __name__ == "__main__":
    main()
