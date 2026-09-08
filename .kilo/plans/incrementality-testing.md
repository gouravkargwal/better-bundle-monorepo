# Incrementality Testing & Merchant Dashboard Plan

## 1. Goal

Replace the legacy Gorse-era dashboard with one truth: **"This app added $X / +Y% AOV"** backed by a holdout experiment, not attributed revenue.

## 2. Architecture

```
Shopify Storefront
  Apollo (post-purchase) ──┐
  Mercury (checkout)       ──┤──→ Python Worker /recommend
                            │     → stable-hash bucketing
                            │     → returns holdout flag + optional impression_id
                            │
                            └──→ offer_impressions table ←── outcome callback
                                    │                       (accept/decline)
                                    │
                            ┌───────┘
                            ▼
                    Dashboard API (Remix)
                      reads offer_impressions directly
                      with indexed date-range queries
                            │
                            ▼
                    Impact UI (3 tabs)
```

## 3. Schema

### Single new table: `offer_impressions`

```sql
CREATE TABLE offer_impressions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shop_id         VARCHAR(255) NOT NULL REFERENCES shops(id),
    session_id      VARCHAR(255),          -- session at time of impression
    customer_id     VARCHAR(255),          -- nullable for anonymous
    surface         VARCHAR(20) NOT NULL,  -- 'apollo' | 'mercury'
    offer_type      VARCHAR(20) NOT NULL,  -- 'upsell' | 'cross_sell' | 'bundle' | 'control'
    offer_id        VARCHAR(255),          -- product/bundle ID shown; NULL for control
    variant_id      VARCHAR(255),          -- specific variant; NULL for control
    is_control      BOOLEAN NOT NULL,      -- TRUE for holdout sessions
    outcome         VARCHAR(20) NOT NULL DEFAULT 'shown',
                                          -- 'shown' | 'accepted' | 'declined' | 'ignored'
    outcome_at      TIMESTAMPTZ,           -- when outcome happened
    revenue_added   DECIMAL(10,2),         -- line-item revenue if accepted
    metadata        JSONB,                 -- internal: algorithm name, position, page_url
    impression_group_id UUID,              -- groups multiple offers shown in one session
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_oi_shop_date ON offer_impressions (shop_id, created_at DESC);
CREATE INDEX idx_oi_funnel ON offer_impressions (shop_id, surface, created_at DESC);
CREATE INDEX idx_oi_control ON offer_impressions (shop_id, is_control, created_at DESC);
CREATE INDEX idx_oi_offers ON offer_impressions (shop_id, offer_id, outcome);
```

**Why just 1 table:**
- No rollup table needed — covering index makes date-range GROUP BY queries fast for single-shop dashboards
- No config table needed — holdout settings live in code defaults + optional `shops.holdout_disabled` boolean
- No pair-performance table needed — computed on-demand via `SELECT offer_id, COUNT(*), SUM(revenue_added) ... GROUP BY offer_id`

**Holdout config:** Hardcoded defaults (10% initial, 2% sentinel, p<0.05 threshold). If a merchant wants to disable holdout, we add a `holdout_disabled` boolean column to the existing `shops` table. No new table.

## 4. Bucketing (Python Worker)

Deterministic stable hash in the recommendation endpoint:

```python
def is_held_out(shop_id: str, customer_id: str | None, session_id: str) -> bool:
    if not shop.holdout_disabled:
        return False
    key = f"{shop_id}:{customer_id or session_id}"
    bucket = int(hashlib.md5(key.encode()).hexdigest(), 16) % 100
    return bucket < HOLDOUT_PERCENT  # 10 initially, 2 after significance
```

**For control sessions:** API returns `{"recommendations": [], "holdout": {"is_control": true}}`. Extension renders nothing.

## 5. Write Path

### Impression
After returning recommendations, worker writes one row per offer (batch insert) + one row for the control group marker.

### Outcome callback
When user accepts or declines an offer, extension calls:
```
POST /api/interaction/outcome
{ "impression_id": "uuid", "outcome": "accepted", "revenue_added": 29.99 }
```
Worker does `UPDATE offer_impressions SET outcome = $1, revenue_added = $2, outcome_at = NOW() WHERE id = $3`.

**Apollo shows multiple offers per session** (up to 3). Each offer gets its own `offer_impressions` row with a shared `impression_group_id`. Outcomes are tracked independently per row — user might accept offer 1 and decline offers 2 and 3 in the same session.

**Why track declines:** The decline signal (`outcome='declined'`) is not strictly needed for the AOV holdout calculation, but costs nothing (single UPDATE on an existing row) and the Apollo extension already has a `trackRecommendationDecline()` function we can reuse. Having it means the funnel can later distinguish "user saw and rejected" vs. "user never noticed" — useful for debugging low accept rates.

## 6. Progressive Holdout

- **Phase 1:** 10% holdout, status = `'collecting'`
- **Rollup job** (daily cron): aggregates last N days, runs two-proportion z-test on accept rate
- **Phase 2:** When p<0.05 & 100+ control orders → drop to 2% sentinel, status = `'sentinel'`
- **Shop override:** `shops.holdout_disabled = true` bypasses holdout entirely

## 7. Dashboard (Replaces Existing)

Single route: `app.impact.tsx`

**Tab 1 — Impact (default):**
- *"$4,230 incremental revenue / +12.3% AOV lift"*
- *"95% CI: +$3,200 – $4,100"*
- Methodology badge: *"Causal measurement — 5% holdout — p<0.01"*
- Weekly trend chart
- Status: *"Collecting data..."* | *"Significant results!"* | *"Monitoring (2% sentinel)"*

**Tab 2 — Funnel per surface:**
| Surface | Impressions | Accepted | Revenue | Conv.% |
|---------|------------|----------|---------|--------|
| Apollo | 1,240 | 112 | $2,150 | 9.0% |
| Mercury | 890 | 95 | $1,880 | 10.7% |

**Tab 3 — Top / Worst Offers:**
Top 10 pairs ranked by accepts. Worst 5 for suppression decisions.

**Settings area:** Holdout toggle (on/off), methodology explainer card.

## 8. Merchant-Facing vs. Internal

**Dashboard shows:** Incremental revenue, AOV lift, CI, funnel, top/worst offers, methodology card.

**NOT shown:** Algorithm names (FP-Growth, cross-encoder), internal confidence scores, bandit status. These are logged in `metadata` JSON for our debugging only.

## 9. What Changes in the App

| Component | Change |
|-----------|--------|
| **Python worker** | Add `is_held_out()` to recommendation endpoint. Add `/api/interaction/outcome` endpoint. Write `offer_impressions` rows. |
| **Apollo extension** | Handle `holdout.is_control` flag (render nothing). Call outcome callback on accept/decline. |
| **Mercury extension** | Same as Apollo. |
| **Remix dashboard** | Replace all `app.dashboard.*` routes with `app.impact.tsx`. Remove legacy components (KPICards, RecentActivity, TopProductsTable, etc.). |
| **`shops` table** | Add `holdout_disabled` boolean column (default false). |
| **New table** | `offer_impressions` — 1 table, 4 indexes. |

## 10. Rollout Sequence

1. Create `offer_impressions` table + `shops.holdout_disabled` column (SQL migration)
2. Add `HoldoutService` + `/api/interaction/outcome` to Python worker
3. Modify `/api/v1/recommendations` to check holdout + log impressions
4. Update Apollo/Mercury extensions to handle holdout flag + outcome callback
5. Build `app/features/impact/` module (types, service, 3 tab components)
6. Replace `app.dashboard.tsx` → `app.impact.tsx`, delete old dashboard routes
7. Daily cron: rollup + significance check (simple Python script or Django command)
8. Deploy and monitor

## 11. Dead Components — Cleanup

These components existed for the Gorse ML pipeline and have no consumer in the new architecture:

| Component | Status | Action |
|-----------|--------|--------|
| **Atlas web pixel** | ❌ Dead | Remove entirely — no longer sends useful data |
| **`user_sessions` table** | ⚠️ Low value | Leave in schema (referenced by legacy FKs), stop writing to it in new code |
| **`user_identity_links` / customer linking** | ❌ Dead | Remove entirely — no consumer without Atlas |
| **`user_interactions` table** | ❌ Dead | Leave for backwards compat, stop reading/writing |

The `offer_impressions` table replaces all three: it logs who saw what offer, what happened, and how much revenue came from it. No behavioral tracking, no session linking, no identity stitching needed.

## 12. Future Work (Not v1)

- **Merchant-configurable offer pairs** (feature/suppress toggle) — needs a new table + API
- **Offer variant testing** — same data, new consumer, out of scope
- **CSV export** — trivial later, not needed for v1
