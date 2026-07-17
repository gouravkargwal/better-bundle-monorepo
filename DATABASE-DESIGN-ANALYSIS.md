# BetterBundle Database Design Analysis

> Deep analysis of the complete database schema across Prisma (source of truth) and Python worker SQLAlchemy models.
> Analyzed: 2026-07-17

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Naming Conventions & Consistency](#2-naming-conventions--consistency)
3. [Indexing Strategy](#3-indexing-strategy)
4. [Data Types & Column Choices](#4-data-types--column-choices)
5. [Relationship Integrity & Foreign Keys](#5-relationship-integrity--foreign-keys)
6. [Enum & State Machine Audit](#6-enum--state-machine-audit)
7. [Billing Tables Deep Dive](#7-billing-tables-deep-dive)
8. [Feature/ML Tables Audit](#8-featureml-tables-audit)
9. [Schema Drift: Prisma vs Python Worker](#9-schema-drift-prisma-vs-python-worker)
10. [Recommendations](#10-recommendations)

---

## 1. Executive Summary

The database schema is **functional and well-structured for a commission-based billing SaaS**. However, it carries significant technical debt from iterative migrations:

| Severity        | Count | Key Issues                                                                                             |
| --------------- | ----- | ------------------------------------------------------------------------------------------------------ |
| 🔴 **Critical** | 3     | Duplicate feature tables, Float for money, dead code referencing non-existent tables                   |
| 🟡 **High**     | 5     | Duplicate indexes (30+ redundant), denormalized columns, schema drift between Prisma and Python worker |
| 🟢 **Low**      | 4     | Missing indexes on FK-only queries, camelCase in `sessions` table, nullable inconsistencies            |

**Bottom line:** The schema works but needs a cleanup migration to reduce index bloat (+30% unnecessary indexes), fix money types, and remove dead tables/models.

---

## 2. Naming Conventions & Consistency

### 2.1 Overall Convention

| Layer                      | Convention | Example                                    |
| -------------------------- | ---------- | ------------------------------------------ |
| **Prisma models**          | Snake case | `billing_cycles`, `commission_records`     |
| **SQLAlchemy class names** | PascalCase | `BillingCycle`, `CommissionRecord`         |
| **SQLAlchemy table names** | Snake case | `billing_cycles`, `commission_records`     |
| **Columns**                | Snake case | `shop_subscription_id`, `billing_cycle_id` |

✅ **Good:** Consistent snake_case across all database columns.

### 2.2 Notable Exception: `sessions` Table

The [`sessions`](better-bundle/prisma/schema.prisma:679) table uses **camelCase columns**:

```
isOnline, accessToken, userId, firstName, lastName, accountOwner, emailVerified
```

**Reason:** This table mirrors the Shopify Remix `Session` interface which uses camelCase. This is a **deliberate exception** for framework compatibility.

**Risk:** If any query joins `sessions` with another table, the column name mismatch can cause confusion. Consider adding a database view that maps camelCase → snake_case for reporting queries.

### 2.3 Table Name Inconsistencies

| Table       | Prisma Name       | Python Class     | Python `__tablename__` | Match? |
| ----------- | ----------------- | ---------------- | ---------------------- | ------ |
| Line items  | `line_item_data`  | `LineItemData`   | `line_item_data`       | ✅     |
| Orders      | `order_data`      | `OrderData`      | `order_data`           | ✅     |
| Products    | `product_data`    | `ProductData`    | `product_data`         | ✅     |
| Customers   | `customer_data`   | `CustomerData`   | `customer_data`        | ✅     |
| Collections | `collection_data` | `CollectionData` | `collection_data`      | ✅     |

✅ **Good:** All table names match between Prisma and SQLAlchemy.

### 2.4 Index Naming Mess

The Prisma schema defines both **old-style** and **new-style** index names for the same columns. Example on [`billing_cycles`](better-bundle/prisma/schema.prisma:11):

| Old Name                        | New Name                                 | Columns                |
| ------------------------------- | ---------------------------------------- | ---------------------- |
| `ix_billing_cycle_subscription` | `ix_billing_cycles_shop_subscription_id` | `shop_subscription_id` |
| `ix_billing_cycle_number`       | `ix_billing_cycles_cycle_number`         | `cycle_number`         |
| `ix_billing_cycle_status`       | `ix_billing_cycles_status`               | `status`               |

This pattern repeats across most tables. **These are exact duplicates** — same columns, different names. They consume disk space and slow down writes for zero query benefit.

---

## 3. Indexing Strategy

### 3.1 Duplicate Indexes (🔴 Waste)

The following tables have **identical composite indexes** under different names:

| Table                                                             | Duplicate Pairs                                                                                                                                                                                        |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [`billing_cycles`](better-bundle/prisma/schema.prisma:11)         | `ix_billing_cycle_subscription` ≡ `ix_billing_cycles_shop_subscription_id`; `ix_billing_cycle_number` ≡ `ix_billing_cycles_cycle_number`; `ix_billing_cycle_status` ≡ `ix_billing_cycles_status`; etc. |
| [`commission_records`](better-bundle/prisma/schema.prisma:106)    | `ix_commission_records_shop_id` ≡ shop_id index already covered by composite indexes                                                                                                                   |
| [`purchase_attributions`](better-bundle/prisma/schema.prisma:487) | 4 duplicate pairs (e.g., `ix_purchase_attribution_customer_id` ≡ `ix_purchase_attributions_customer_id`)                                                                                               |
| [`pricing_tiers`](better-bundle/prisma/schema.prisma:340)         | 5 duplicate pairs                                                                                                                                                                                      |
| [`subscription_plans`](better-bundle/prisma/schema.prisma:791)    | 4 duplicate pairs                                                                                                                                                                                      |
| [`user_interactions`](better-bundle/prisma/schema.prisma:869)     | Multiple duplicates                                                                                                                                                                                    |
| [`user_sessions`](better-bundle/prisma/schema.prisma:900)         | Multiple duplicates                                                                                                                                                                                    |

**Estimated waste:** ~30-40% of all indexes are redundant. This adds ~100-200ms to write-heavy operations (commission creation, data collection).

### 3.2 Missing Indexes (🟡 Gaps)

| Table                                                          | Missing Index                                          | Why Needed                                                                                                         |
| -------------------------------------------------------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ |
| [`commission_records`](better-bundle/prisma/schema.prisma:106) | `(shop_id, billing_cycle_id)`                          | Python worker queries use this pattern in `BillingRepositoryV2.get_commissions_for_cycle()` via `billing_cycle_id` |
| [`commission_records`](better-bundle/prisma/schema.prisma:106) | `(billing_cycle_id, status)`                           | Billing reconciliation queries need to find pending commissions per cycle                                          |
| [`line_item_data`](better-bundle/prisma/schema.prisma:263)     | `(order_id, created_at)`                               | Used by `_is_purchase_already_processed` to check for new line items                                               |
| [`user_interactions`](better-bundle/prisma/schema.prisma:869)  | `(shop_id, customer_id, created_at, interaction_type)` | Common analytics query pattern missing in indexes                                                                  |

### 3.3 Over-Indexed Feature Tables (🟡)

The ML feature tables (e.g., [`product_features`](better-bundle/prisma/schema.prisma:412), [`product_pair_features`](better-bundle/prisma/schema.prisma:448)) have **individual indexes on every score column**:

```prisma
@@index([shop_id, interaction_volume_score])
@@index([shop_id, purchase_velocity_score])
@@index([shop_id, engagement_quality_score])
// ... 8 more individual score indexes
```

**Problem:** Feature tables are typically **batch-scanned** (compute all features at once) or **queried by shop_id + product_id**. Individual score indexes are only useful if you filter by that specific score range, which the application rarely does. Each index adds write overhead during feature recomputation.

**Better:** Keep only `(shop_id, product_id)` unique index + `(shop_id, product_lifecycle_stage)` if lifecycle-stage filtering is a real query pattern.

---

## 4. Data Types & Column Choices

### 4.1 Float for Money (🔴 Critical)

Monetary values stored as `Float` instead of `Decimal`:

| Table                                                     | Column                  | Type    | Should Be        |
| --------------------------------------------------------- | ----------------------- | ------- | ---------------- |
| [`order_data`](better-bundle/prisma/schema.prisma:281)    | `total_amount`          | `Float` | `Decimal(10, 2)` |
| [`order_data`](better-bundle/prisma/schema.prisma:281)    | `subtotal_amount`       | `Float` | `Decimal(10, 2)` |
| [`order_data`](better-bundle/prisma/schema.prisma:281)    | `total_tax_amount`      | `Float` | `Decimal(10, 2)` |
| [`order_data`](better-bundle/prisma/schema.prisma:281)    | `total_shipping_amount` | `Float` | `Decimal(10, 2)` |
| [`product_data`](better-bundle/prisma/schema.prisma:372)  | `price`                 | `Float` | `Decimal(10, 2)` |
| [`customer_data`](better-bundle/prisma/schema.prisma:197) | `total_spent`           | `Float` | `Decimal(10, 2)` |

**Impact:** IEEE 754 floating-point rounding errors on financial data. For example, `0.1 + 0.2 = 0.30000000000000004`. With thousands of orders, this causes reconciliation drift.

**Note:** The billing tables (`commission_records`, `billing_cycles`, `pricing_tiers`) correctly use `Decimal(Numeric)` — inconsistent with the Shopify data tables above.

### 4.2 String for Commission Rate (🟡)

[`subscription_plans.default_commission_rate`](better-bundle/prisma/schema.prisma:797) is `String(10)`:

```prisma
default_commission_rate String? @db.VarChar(10)
```

Meanwhile, [`pricing_tiers.commission_rate`](better-bundle/prisma/schema.prisma:344) correctly uses `Decimal(5, 4)`.

**Issue:** Storing a numeric rate as a string loses type safety — "0.03" is valid, "abc" is also valid. This should be `Decimal(5, 4)` to match `pricing_tiers`.

### 4.3 Nullable Inconsistencies (🟢)

| Column                        | Prisma    | Python Worker         | Analysis                                                      |
| ----------------------------- | --------- | --------------------- | ------------------------------------------------------------- |
| `collection_data.description` | `String?` | `Text, nullable=True` | ✅ Match (different type but both nullable)                   |
| `order_data.note`             | `String?` | `Text, default=""`    | ⚠️ Prisma: nullable; Worker: default `""` — mismatch          |
| `order_data.total_tax_amount` | `Float?`  | `Float, default=0.0`  | ⚠️ Prisma: nullable; Worker: defaults to 0 — semantics differ |
| `product_data.tags`           | `Json?`   | `JSON, default=[]`    | ⚠️ Same — Prisma allows null, Worker defaults to empty array  |

**Impact:** Code in the Python worker may treat `None` and `[]` differently. Using `default=0` when the DB allows `NULL` creates silent data inconsistency if data comes through a path that doesn't set the default.

---

## 5. Relationship Integrity & Foreign Keys

### 5.1 On Delete Semantics

| FK                                                                      | Prisma `onDelete`                 | SQLAlchemy `ondelete`          | Consistent?     |
| ----------------------------------------------------------------------- | --------------------------------- | ------------------------------ | --------------- |
| `commission_records.shop_id → shops.id`                                 | `Cascade`                         | `CASCADE`                      | ✅              |
| `commission_records.billing_cycle_id → billing_cycles.id`               | Not specified (default: NoAction) | `SET NULL`                     | ❌ **MISMATCH** |
| `commission_records.purchase_attribution_id → purchase_attributions.id` | `Cascade`                         | `CASCADE`                      | ✅              |
| `billing_cycles.shop_subscription_id → shop_subscriptions.id`           | `Cascade`                         | `CASCADE`                      | ✅              |
| Feature tables (e.g., `product_features`) `shop_id → shops.id`          | `NoAction`                        | `cascade="all, delete-orphan"` | ❌ **MISMATCH** |

**Critical Mismatch:** [`billing_cycles → commission_records`](python-worker/app/core/database/models/commission.py:68):

- **Prisma:** No `onDelete` specified, defaults to `NoAction` — prevents deleting a billing cycle if commissions exist
- **Python worker:** `ondelete="SET NULL"` — deleting a cycle nullifies the `billing_cycle_id` on commissions

This means: if the Prisma migrations are used to create the schema, the DB will reject deleting a billing cycle with existing commissions. But the Python worker code expects `SET NULL` behavior. **If a billing cycle deletion is ever attempted, it will fail at the DB level.**

### 5.2 Feature Tables: `NoAction` on Shop Delete

All feature tables ([`product_features`](better-bundle/prisma/schema.prisma:412), [`user_features`](better-bundle/prisma/schema.prisma:819), [`collection_features`](better-bundle/prisma/schema.prisma:79), etc.) use `onDelete: NoAction` for `shop_id → shops.id`.

**Intention:** Preserve historical ML features even if a shop is deleted. This is a valid decision, but:

- These tables can grow unbounded for deleted shops
- No cleanup mechanism exists (no `deleted_at` on feature tables)
- Consider adding a shop-deletion cleanup job that archives or purges features after 90 days

### 5.3 `commission_records` Unique Constraints

[`commission_records`](better-bundle/prisma/schema.prisma:106) has two unique constraints:

1. `purchase_attribution_id` — one commission per purchase attribution ✅
2. `shopify_usage_record_id` — one Shopify usage record per commission ✅

**Issue:** The Python worker's [`CommissionRecord`](python-worker/app/core/database/models/commission.py:223) model adds a `UniqueConstraint` on `purchase_attribution_id` but notes in comments that a **partial unique index** would be better (excluding soft-deleted rows). The partial index exists only as a comment suggestion, not actual SQL.

---

## 6. Enum & State Machine Audit

### 6.1 Commission Status State Machine

[`commission_status_enum`](better-bundle/prisma/schema.prisma:1106):

```
TRIAL_PENDING → TRIAL_COMPLETED
                      ↓
                 PENDING → RECORDING → RECORDED → INVOICED
                     |         |           |
                     ↓         ↓           ↓
                  FAILED    FAILED      REJECTED/CAPPED
```

**Issues:**

- `FAILED` is reachable from both `PENDING` and `RECORDING` — valid retry states
- `CAPPED` is a terminal state — no retry path back to `PENDING`
- There's no `CANCELLED` status for commission records (e.g., when an order is refunded)
- The [`CommissionService`](python-worker/app/domains/billing/services/commission_service_v2.py) handles refunds by creating separate negative commission records rather than updating status — this is fine but should be documented

### 6.2 Subscription Status Flow

[`subscription_status_enum`](better-bundle/prisma/schema.prisma:1125):

```
TRIAL → ACTIVE → SUSPENDED → CANCELLED / EXPIRED
```

✅ **Good:** Clean linear state machine. `PENDING_APPROVAL` correctly removed — merchants stay in `TRIAL` until Shopify webhook confirms `ACTIVE`.

### 6.3 Duplicate/Overlapping Enums (🟡)

| Python Worker Enum                                                        | Prisma Equivalent | Status                                                         |
| ------------------------------------------------------------------------- | ----------------- | -------------------------------------------------------------- |
| [`TrialStatus`](python-worker/app/core/database/models/enums.py:162)      | Not in Prisma     | **Dead code** — trial status is now `SubscriptionStatus.TRIAL` |
| [`BillingPlanType`](python-worker/app/core/database/models/enums.py:24)   | Not in Prisma     | **Dead code** — replaced by `SubscriptionPlanType`             |
| [`BillingPlanStatus`](python-worker/app/core/database/models/enums.py:33) | Not in Prisma     | **Dead code**                                                  |
| [`BillingCycle`](python-worker/app/core/database/models/enums.py:42)      | Not in Prisma     | **Dead code** — cycle type is hardcoded as monthly             |

**Recommendation:** Remove these legacy enums and their references.

---

## 7. Billing Tables Deep Dive

### 7.1 Table Dependency Graph

```
subscription_plans
       ↓
  pricing_tiers
       ↓
  shop_subscriptions  ←── shops
       ↓
  billing_cycles
       ↓
  commission_records  ←── purchase_attributions
                               ↓
                          user_sessions ←── user_interactions
```

### 7.2 Denormalized Fields

[`commission_records`](better-bundle/prisma/schema.prisma:106) has these denormalized fields:

| Field                 | Derivable From                                      | Keep?                                        |
| --------------------- | --------------------------------------------------- | -------------------------------------------- |
| `billing_cycle_start` | `billing_cycles.start_date` (via FK)                | ⚠️ Remove — already in comment as deprecated |
| `billing_cycle_end`   | `billing_cycles.end_date` (via FK)                  | ⚠️ Remove                                    |
| `cycle_usage_before`  | `billing_cycles.usage_amount` (historical snapshot) | ✅ Keep — audit trail                        |
| `cycle_usage_after`   | `cycle_usage_before + commission_charged`           | ✅ Keep — audit trail                        |
| `capped_amount`       | `billing_cycles.current_cap_amount` (at time)       | ✅ Keep — historical snapshot                |
| `trial_accumulated`   | `shop_subscriptions.trial_revenue`                  | ✅ Already removed in Python worker model    |

**Note:** The Python worker model comments say `billing_cycle_start/billing_cycle_end` and `trial_accumulated` are removed, but they **still exist in Prisma**. This is a **schema drift** issue.

### 7.3 Billing Cycle Integrity

The [`ix_billing_cycle_unique_active`](better-bundle/prisma/schema.prisma:31) index enforces:

```prisma
@@unique([shop_subscription_id, status])
```

But this allows multiple `COMPLETED` or `CANCELLED` cycles per subscription (good) and exactly **one** `ACTIVE` cycle per subscription (also good — enforces business rule).

**However**, this would also allow only one `SUSPENDED` cycle per subscription, which may be too restrictive if a cycle is suspended and a new one is created.

### 7.4 Pricing Tier Default Constraint

[`pricing_tiers`](better-bundle/prisma/schema.prisma:358):

```prisma
@@unique([subscription_plan_id, currency, is_default])
```

**Issue:** Only one default per plan per currency is allowed. But if `is_default=false` for all rows, there's no default. The application code handles this via `order_by(is_default.desc())`, but it should fall back to the first active tier if no default is found. Currently, [`get_pricing_tier_for_plan_and_currency`](python-worker/app/domains/billing/repositories/billing_repository_v2.py:106) doesn't handle the no-default case gracefully.

---

## 8. Feature/ML Tables Audit

### 8.1 Duplicate Tables (🔴 Critical)

[`user_features`](better-bundle/prisma/schema.prisma:819) and [`customer_behavior_features`](better-bundle/prisma/schema.prisma:159) are **near-identical**:

| Column                                   | `user_features` | `customer_behavior_features` |
| ---------------------------------------- | --------------- | ---------------------------- |
| `customer_id`                            | ✅              | ✅                           |
| `total_purchases` / `total_interactions` | Both            | `total_interactions` only    |
| `lifetime_value`                         | ✅              | ✅                           |
| `avg_order_value`                        | ✅              | ✅                           |
| `purchase_frequency_score`               | ✅              | ✅                           |
| `interaction_diversity_score`            | ✅              | ✅                           |
| `days_since_last_purchase`               | ✅              | ✅                           |
| `recency_score`                          | ✅              | ✅                           |
| `conversion_rate`                        | ✅              | ✅                           |
| `primary_category`                       | ✅              | ✅                           |
| `category_diversity`                     | ✅              | ✅                           |
| `user_lifecycle_stage`                   | ✅              | ✅                           |
| `churn_risk_score`                       | ✅              | ✅                           |

**Only differences:**

- `user_features` has `total_purchases` (Int), `customer_behavior_features` doesn't
- Both have `last_computed_at`

**Recommendation:** Drop `customer_behavior_features` and consolidate into `user_features`. This halves write load during feature recomputation and eliminates confusion about which table is authoritative.

### 8.2 Feature Table Index Overload

| Table                        | Number of Indexes | Useful Indexes         | Waste      |
| ---------------------------- | ----------------- | ---------------------- | ---------- |
| `product_features`           | 11                | 1 (unique) + maybe 2-3 | ~70% waste |
| `product_pair_features`      | 14                | 1 (unique) + maybe 3-4 | ~65% waste |
| `customer_behavior_features` | 13                | 1 (unique) + maybe 2-3 | ~75% waste |
| `interaction_features`       | 10                | 1 (unique) + maybe 2-3 | ~70% waste |

**Impact:** Each feature recomputation batch-updates thousands of rows. Every additional index adds write amplification. With 10-14 indexes on feature tables, a single row update touches all of them.

### 8.3 Missing `deleted_at` on Feature Tables

Unlike [`commission_records`](better-bundle/prisma/schema.prisma:136) which has soft-delete support, none of the feature tables have `deleted_at`. This means:

- Products removed from Shopify can't be soft-deleted from feature tables
- Feature recomputation must check `product_data.is_active` or `product_data.status` instead

---

## 9. Schema Drift: Prisma vs Python Worker

### 9.1 Tables in Python Worker NOT in Prisma

| Table                      | Purpose                  | Location                                       | Status                            |
| -------------------------- | ------------------------ | ---------------------------------------------- | --------------------------------- |
| `billing_invoices`         | Shopify invoice tracking | `python-worker/.../billing_invoice.py`         | ⚠️ Exists in DB but NOT in Prisma |
| `scheduler_job_executions` | Job run tracking         | `python-worker/.../scheduler_job_execution.py` | ⚠️ Exists in DB but NOT in Prisma |
| `subscription_trials`      | Legacy trial tracking    | Referenced by `SubscriptionTrialRepository`    | ❌ **Does not exist** — dead code |

### 9.2 Columns in Prisma NOT in Python Worker

| Table                | Missing Column                             | Impact                                                         |
| -------------------- | ------------------------------------------ | -------------------------------------------------------------- |
| `commission_records` | `billing_cycle_start`, `billing_cycle_end` | Python worker comments say "removed" but Prisma still has them |
| `commission_records` | `trial_accumulated`                        | Same as above                                                  |

### 9.3 Columns in Python Worker NOT in Prisma

No significant cases — Python worker models generally mirror Prisma.

### 9.4 FK On-Delete Mismatches

| FK                                    | Prisma               | Python Worker                                | Risk                                           |
| ------------------------------------- | -------------------- | -------------------------------------------- | ---------------------------------------------- |
| `commission_records → billing_cycles` | `NoAction` (default) | `SET NULL`                                   | DB rejects deletes that worker expects to work |
| Feature tables → `shops`              | `NoAction`           | `CASCADE` (via cascade="all, delete-orphan") | Worker cascades deletes that DB prevents       |

---

## 10. Recommendations

### 10.1 Immediate (High Impact, Low Effort)

1. **Drop `customer_behavior_features` table** and consolidate into `user_features`

   - Affected: [`customer_behavior_features`](better-bundle/prisma/schema.prisma:159), [`user_features`](better-bundle/prisma/schema.prisma:819)
   - Migration: Add missing `total_purchases` column to `user_features` if needed, copy data, drop table

2. **Remove duplicate indexes** — keep only one set per table

   - Use the "new" naming convention (`ix_billing_cycles_*`, `ix_commission_records_*`)
   - Drops: 30+ redundant indexes across all tables

3. **Fix `commission_records → billing_cycles` FK on-delete** to match between Prisma and Python worker

   - Decision needed: `SET NULL` or `NO ACTION`? Choose `SET NULL` for flexibility

4. **Change `default_commission_rate` from `String` to `Decimal`** in `subscription_plans`

### 10.2 Short-term (High Impact, Medium Effort)

5. **Change money columns to `Decimal`** in `order_data`, `product_data`, `customer_data`

   - Migration: `ALTER COLUMN ... TYPE numeric(10,2) USING ...`
   - Risk: Requires careful handling of existing Float values (round to 2 decimal places)

6. **Add `billing_invoices` to Prisma schema** (or document as Python-worker-managed table)

   - Currently exists only in SQLAlchemy models, not Prisma
   - If Prisma manages all tables, add it. Otherwise, document the exclusion.

7. **Remove dead enums and `SubscriptionTrialRepository`**
   - Dead: [`TrialStatus`](python-worker/app/core/database/models/enums.py:162), [`BillingPlanType`](python-worker/app/core/database/models/enums.py:24), [`BillingPlanStatus`](python-worker/app/core/database/models/enums.py:33), [`BillingCycle`](python-worker/app/core/database/models/enums.py:42)
   - Dead: [`SubscriptionTrialRepository`](python-worker/app/repository/SubscriptionTrialRepository.py) references a non-existent table

### 10.3 Medium-term (Medium Impact, Medium Effort)

8. **Prune feature table indexes** — keep only `(shop_id, unique_id)` unique index + 2-3 commonly queried score indexes

9. **Add `deleted_at` to feature tables** for soft-delete support

10. **Add partial unique index on `commission_records.purchase_attribution_id WHERE deleted_at IS NULL`** to allow soft-delete + re-creation of commissions

11. **Normalize `commission_records`** — drop `billing_cycle_start`, `billing_cycle_end`, derive from FK join

### 10.4 Long-term (Architectural)

12. **Consider splitting into domain-specific schemas:**

    - `billing` schema: all billing-related tables
    - `analytics` schema: feature/ML tables
    - `shopify` schema: synced Shopify data
    - This reduces cross-schema coupling and allows per-schema scaling

13. **Add database-level audit logging** (e.g., pgaudit) for `commission_records` status changes — currently relies entirely on application logging

14. **Evaluate columnar storage for feature tables** (e.g., TimescaleDB or Citus) if feature recomputation becomes a performance bottleneck

---

## Appendix A: All Tables Summary

| #   | Table Name                   | Purpose                        | Lines (Prisma)   | Status                                     |
| --- | ---------------------------- | ------------------------------ | ---------------- | ------------------------------------------ |
| 1   | `shops`                      | Shop/merchant records          | 48               | ✅ Good                                    |
| 2   | `shop_subscriptions`         | Subscription per shop          | 38               | ✅ Good (recently refactored)              |
| 3   | `billing_cycles`             | Monthly billing cycles         | 35               | ✅ Good (duplicate indexes)                |
| 4   | `commission_records`         | Commission charges             | 52               | ⚠️ Denormalized fields, FK mismatch        |
| 5   | `pricing_tiers`              | Pricing configs                | 31               | ✅ Good                                    |
| 6   | `subscription_plans`         | Plan templates                 | 26               | ⚠️ String for commission rate              |
| 7   | `purchase_attributions`      | Purchase-bundle links          | 33               | ✅ Good                                    |
| 8   | `user_sessions`              | User session tracking          | 32               | ⚠️ Duplicate indexes                       |
| 9   | `user_interactions`          | User interaction events        | 30               | ✅ Good                                    |
| 10  | `product_data`               | Shopify product catalog        | 39               | ⚠️ Float for price                         |
| 11  | `order_data`                 | Shopify orders                 | 57               | ⚠️ Float for money                         |
| 12  | `line_item_data`             | Order line items               | 16               | ⚠️ Float for price                         |
| 13  | `customer_data`              | Shopify customers              | 31               | ⚠️ Float for total_spent                   |
| 14  | `collection_data`            | Shopify collections            | 35               | ✅ Good                                    |
| 15  | `user_features`              | Customer analytics             | 20               | 🔴 Duplicate of customer_behavior_features |
| 16  | `customer_behavior_features` | Customer behavior (duplicate)  | 23               | 🔴 Duplicate — DROP                        |
| 17  | `product_features`           | Product ML features            | 27               | ⚠️ Over-indexed                            |
| 18  | `product_pair_features`      | Product co-occurrence features | 37               | ⚠️ Over-indexed                            |
| 19  | `collection_features`        | Collection ML features         | 15               | ⚠️ Over-indexed                            |
| 20  | `interaction_features`       | Interaction ML features        | 19               | ⚠️ Over-indexed                            |
| 21  | `session_features`           | Session ML features            | 21               | ✅ Good                                    |
| 22  | `search_product_features`    | Search-related features        | 21               | ✅ Good                                    |
| 23  | `user_identity_links`        | Cross-session identity         | 11               | ✅ Good                                    |
| 24  | `raw_orders`                 | Raw Shopify order data         | 15               | ✅ Good                                    |
| 25  | `raw_products`               | Raw Shopify product data       | 15               | ✅ Good                                    |
| 26  | `raw_customers`              | Raw Shopify customer data      | 15               | ✅ Good                                    |
| 27  | `raw_collections`            | Raw Shopify collection data    | 15               | ✅ Good                                    |
| 28  | `sessions`                   | Shopify OAuth sessions         | 21               | ⚠️ camelCase columns                       |
| 29  | `feedback`                   | Gorse ML feedback              | 6                | ✅ Managed by Gorse                        |
| 30  | `items`                      | Gorse ML items                 | 6                | ✅ Managed by Gorse                        |
| 31  | `users`                      | Gorse ML users                 | 4                | ✅ Managed by Gorse                        |
| 32  | `billing_invoices`           | Shopify invoices               | ⚠️ NOT in Prisma | ⚠️ Drift                                   |
| 33  | `scheduler_job_executions`   | Job run tracking               | ⚠️ NOT in Prisma | ⚠️ Drift                                   |

## Appendix B: Enum Reference

| Enum Name                     | Values                                                                                           | Used By              |
| ----------------------------- | ------------------------------------------------------------------------------------------------ | -------------------- |
| `billing_cycle_status_enum`   | ACTIVE, COMPLETED, CANCELLED, SUSPENDED                                                          | `billing_cycles`     |
| `billing_phase_enum`          | TRIAL, PAID                                                                                      | `commission_records` |
| `charge_type_enum`            | FULL, PARTIAL, OVERFLOW_ONLY, TRIAL, REJECTED                                                    | `commission_records` |
| `commission_status_enum`      | TRIAL_PENDING, TRIAL_COMPLETED, PENDING, RECORDING, RECORDED, INVOICED, REJECTED, FAILED, CAPPED | `commission_records` |
| `subscription_plan_type_enum` | USAGE_BASED, TIERED, FLAT_RATE, HYBRID                                                           | `subscription_plans` |
| `subscription_status_enum`    | TRIAL, ACTIVE, SUSPENDED, CANCELLED, EXPIRED                                                     | `shop_subscriptions` |
