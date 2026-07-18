#!/bin/bash
# Import OpenObserve configuration
# Usage: ./import.sh <openobserve_endpoint> <org> <api_key>

set -euo pipefail

ENDPOINT="${1:-http://localhost:5080}"
ORG="${2:-default}"
API_KEY="${3:-}"

if [ -z "$API_KEY" ]; then
  echo "Error: API key is required. Usage: $0 [endpoint] [org] <api_key>" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Import dashboards
for f in "$SCRIPT_DIR"/dashboards/*.json; do
  name=$(basename "$f" .json)
  echo "Importing dashboard: $name"
  curl -s -X POST "$ENDPOINT/api/$ORG/dashboards" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "@$f"
  echo ""
done

# Import alerts
for f in "$SCRIPT_DIR"/alerts/*.json; do
  name=$(basename "$f" .json)
  echo "Importing alert: $name"
  curl -s -X POST "$ENDPOINT/api/$ORG/alerts" \
    -H "Authorization: Bearer $API_KEY" \
    -H "Content-Type: application/json" \
    -d "@$f"
  echo ""
done

echo "Done!"
