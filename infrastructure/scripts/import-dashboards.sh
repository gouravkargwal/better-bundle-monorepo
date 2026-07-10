#!/bin/bash
# ================================================
# OpenObserve Dashboard Auto-Importer
# ================================================
# Used as a sidecar/init container. It:
#   1. Waits for OpenObserve to be healthy
#   2. Iterates over all *.json files in DASHBOARDS_DIR
#   3. Imports each one via the OpenObserve REST API
#   4. Logs success/failure for each
# ================================================

set -euo pipefail

OPENOBSERVE_URL="${OPENOBSERVE_URL:-http://openobserve:5080}"
OPENOBSERVE_EMAIL="${OPENOBSERVE_EMAIL:-admin@betterbundle.com}"
OPENOBSERVE_PASSWORD="${OPENOBSERVE_PASSWORD:-BetterBundle2024!OpenObserve}"
DASHBOARDS_DIR="${DASHBOARDS_DIR:-/dashboards}"
MAX_RETRIES="${MAX_RETRIES:-30}"
RETRY_INTERVAL="${RETRY_INTERVAL:-5}"

echo "============================================"
echo " OpenObserve Dashboard Importer"
echo "============================================"
echo "Endpoint:    $OPENOBSERVE_URL"
echo "Dashboards:  $DASHBOARDS_DIR"
echo "Max retries: $MAX_RETRIES"
echo "============================================"

# --------------------------------------------------
# Step 1: Wait for OpenObserve to be healthy
# --------------------------------------------------
echo ""
echo "[1/3] Waiting for OpenObserve to be ready..."

for i in $(seq 1 "$MAX_RETRIES"); do
    if curl -sf "$OPENOBSERVE_URL/healthz" > /dev/null 2>&1; then
        echo "  ✅ OpenObserve is ready (attempt $i)"
        break
    fi
    if [ "$i" -eq "$MAX_RETRIES" ]; then
        echo "  ❌ OpenObserve did not become healthy after $MAX_RETRIES attempts"
        exit 1
    fi
    echo "  ⏳ Waiting... attempt $i/$MAX_RETRIES"
    sleep "$RETRY_INTERVAL"
done

# --------------------------------------------------
# Step 2: Find dashboard JSON files
# --------------------------------------------------
echo ""
echo "[2/3] Finding dashboard files in $DASHBOARDS_DIR..."

# shellcheck disable=SC2231
shopt -s nullglob
dashboard_files=("$DASHBOARDS_DIR"/*.json)

if [ ${#dashboard_files[@]} -eq 0 ]; then
    echo "  ⚠️  No dashboard JSON files found in $DASHBOARDS_DIR"
    exit 0
fi

echo "  Found ${#dashboard_files[@]} dashboard(s):"
for f in "${dashboard_files[@]}"; do
    echo "    - $(basename "$f")"
done

# --------------------------------------------------
# Step 3: Import each dashboard
# --------------------------------------------------
echo ""
echo "[3/3] Importing dashboards..."

success_count=0
fail_count=0

for f in "${dashboard_files[@]}"; do
    filename=$(basename "$f")
    echo -n "  📥 Importing $filename ... "

    response=$(curl -s -o /dev/null -w "%{http_code}" \
        -u "$OPENOBSERVE_EMAIL:$OPENOBSERVE_PASSWORD" \
        -X POST \
        -H "Content-Type: application/json" \
        -d "@$f" \
        "$OPENOBSERVE_URL/api/default/dashboards" 2>&1)

    if [ "$response" = "200" ] || [ "$response" = "201" ]; then
        echo "✅ (HTTP $response)"
        success_count=$((success_count + 1))
    else
        echo "❌ (HTTP $response)"
        fail_count=$((fail_count + 1))
    fi
done

# --------------------------------------------------
# Summary
# --------------------------------------------------
echo ""
echo "============================================"
echo " Import Complete"
echo "============================================"
echo "  Successful: $success_count"
echo "  Failed:     $fail_count"
echo "============================================"

if [ "$fail_count" -gt 0 ]; then
    exit 2
fi

exit 0
