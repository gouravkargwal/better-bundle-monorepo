#!/bin/bash
# Thin wrapper kept so the command in README.md and any muscle memory still
# works. The importer itself is import.py — it has to be idempotent (this runs
# on every deploy now, and POSTing a dashboard twice creates two dashboards),
# and that is much less painful in Python than in bash with curl and jq.
#
# Usage: SLACK_WEBHOOK_URL=https://... ./import.sh <endpoint> <org> <api_key>
exec python3 "$(cd "$(dirname "$0")" && pwd)/import.py" "$@"
