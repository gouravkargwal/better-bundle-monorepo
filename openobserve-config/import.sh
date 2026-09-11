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
