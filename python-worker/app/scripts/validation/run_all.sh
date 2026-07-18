#!/usr/bin/env bash
#
# Run the full validation workflow end-to-end.
#
# Usage:
#   bash python-worker/app/scripts/validation/run_all.sh
#
# What it does:
#   1. seed_shop.py         — create fake shop record
#   2. seed_test_data.py    — seed products, customers, orders, collections
#   3. seed_interactions.py — seed browsing sessions, events, attributions
#   4. run_pipeline.py      — run feature computation + Gorse sync
#   5. Wait 60 seconds for Gorse to start processing
#   6. validate_recommendations.py — check if recommendations make sense
#
# Prerequisites:
#   - Python worker container is running
#   - Gorse is running (check http://localhost:8088)
#   - venv is activated

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../../.."  # python-worker/ (so .env / .env.local are found)

# Nested BaseSettings classes (e.g. MLSettings) only read from the real
# process environment, not from env_file — so export .env / .env.local here.
# Values (e.g. CORS_ORIGINS=["*", "https://..."]) aren't valid bash syntax,
# so parse with python-dotenv instead of a raw `source`.
eval "$(python - <<'PY'
import shlex
from dotenv import dotenv_values

values = {}
values.update(dotenv_values(".env"))
values.update(dotenv_values(".env.local"))
for key, val in values.items():
    if val is not None:
        print(f"export {key}={shlex.quote(val)}")
PY
)"

echo ""
echo "██████████████████████████████████████████████████"
echo "  Validation Pipeline — Full Run"
echo "██████████████████████████████████████████████████"
echo ""

# ── Step 1: Seed shop ──────────────────────────────────────────────────────
echo "━━━ Step 1/5: Seeding shop ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python app/scripts/validation/seed_shop.py
echo ""

# ── Step 2: Seed products, customers, orders, collections ──────────────────
echo "━━━ Step 2/5: Seeding products, customers, orders ━━━━━━━━━━━━━━━━━━"
python app/scripts/validation/seed_test_data.py
echo ""

# ── Step 3: Seed interactions ──────────────────────────────────────────────
echo "━━━ Step 3/5: Seeding interactions ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
python app/scripts/validation/seed_interactions.py
echo ""

# ── Step 4: Run pipeline ──────────────────────────────────────────────────
echo "━━━ Step 4/5: Running feature computation + Gorse sync ━━━━━━━━━━━━━"
python app/scripts/validation/run_pipeline.py
echo ""

# ── Step 5: Validate ──────────────────────────────────────────────────────
echo "━━━ Step 5/5: Validating recommendations ━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  (waiting 60s for Gorse to start processing...)"
sleep 60
python app/scripts/validation/validate_recommendations.py
echo ""

echo "██████████████████████████████████████████████████"
echo "  Done! Check results above."
echo "  Gorse dashboard: http://localhost:8088"
echo "██████████████████████████████████████████████████"
