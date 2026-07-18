# Flat Fee Pricing Cleanup — Drop PricingTier, Move Fields to SubscriptionPlan

## Goal

Since pricing is now global USD-only (flat fee), the `PricingTier` model is unnecessary overhead. Move `monthly_fee` and `trial_days` directly onto `SubscriptionPlan`, drop the `PricingTier` table, and remove all legacy usage-based fields.

---

## Decision Tree

| Decision                          | Chosen                               |
| --------------------------------- | ------------------------------------ |
| PricingTier table                 | ❌ Drop entirely                     |
| monthly_fee / trial_days location | `SubscriptionPlan` (not PricingTier) |
| Currency support                  | USD-only (global)                    |
| Legacy fields                     | Remove from all models               |
| DB migration                      | Single raw-SQL script (no Alembic)   |

---

## Affected Files

### Layer 1 — Python Worker Models

1. **`python-worker/app/core/database/models/subscription_plan.py`**

   - **Add** `monthly_fee` (`Numeric(10,2)`, nullable, default 29.00)
   - **Add** `trial_days` (`Integer`, nullable, default 14)
   - **Remove** `default_commission_rate`
   - Update `__repr__` and docstring

2. **`python-worker/app/core/database/models/pricing_tier.py`** — **DELETE** entire file

3. **`python-worker/app/core/database/models/shop_subscription.py`**

   - **Remove** `pricing_tier_id` ForeignKey column
   - **Remove** `pricing_tier` relationship
   - **Remove** legacy columns: `trial_threshold_override`, `user_chosen_cap_amount`
   - **Remove** legacy properties: `effective_trial_threshold`, `effective_commission_rate`, `effective_cap_amount`, `commission_rate_percentage`
   - **Update** `effective_monthly_fee` → read from `self.subscription_plan.monthly_fee` (fallback 29.00)
   - **Update** `effective_trial_days` → read from `self.subscription_plan.trial_days` (fallback 14)
   - **Remove** `selectinload(ShopSubscription.pricing_tier)` references (see repo layer)

4. **`python-worker/app/core/database/models/__init__.py`**

   - **Remove** `PricingTier` import and `__all__` export

5. **`python-worker/app/core/database/models/enums.py`**
   - No changes needed (enums remain)

---

### Layer 2 — Seed Scripts

6. **`python-worker/app/scripts/seed_subscription_plans.py`** (already updated)

   - Plan name: `"Flat Rate Standard"`
   - `plan_type=SubscriptionPlanType.FLAT_RATE`
   - Single plan, no PricingTier creation loop
   - Set `monthly_fee=Decimal("29.00")`, `trial_days=14` on the plan itself

7. **`python-worker/app/scripts/seed_flat_fee_plans.py`**
   - Same pattern: each plan has `monthly_fee` and `trial_days` directly
   - Remove PricingTier creation loop
   - Basic: $29, Pro: $99, Enterprise: $299 (all USD, all 14d trial)

---

### Layer 3 — Repository

8. **`python-worker/app/domains/billing/repositories/billing_repository_v2.py`**
   - **Remove** `PricingTier` import
   - **Remove** entire PRICING TIER OPERATIONS section:
     - `get_pricing_tier_for_plan_and_currency()`
     - `get_pricing_tier_for_country()`
     - `get_pricing_tier()`
   - **Simplify** `create_trial_subscription()`:
     - Remove `pricing_tier_id` param
     - Remove `trial_threshold_override` param
     - Remove those fields from the `ShopSubscription(...)` construction
   - **Simplify** `create_paid_subscription()`:
     - Remove `pricing_tier_id` param
     - Remove `user_chosen_cap_amount` param
     - Remove those fields from the `ShopSubscription(...)` construction
   - **Simplify** `create_flat_fee_subscription()`:
     - Remove `pricing_tier_id` param
     - Get `monthly_fee` from `subscription_plan` (or accept `monthly_fee_override`)
   - **Remove** `complete_trial_subscription()` — revenue-based trial completion is legacy
   - **Remove** `check_trial_completion()` — legacy
   - **Update** `check_trial_expiry_by_time()`:
     - Remove `selectinload(ShopSubscription.pricing_tier)`
     - Read `trial_days` from `subscription_plan.trial_days` instead of `effective_trial_days`
   - **Update** `get_shop_subscription()`:
     - Remove `selectinload(ShopSubscription.pricing_tier)`
     - Add `selectinload(ShopSubscription.subscription_plan)` if not already loaded
   - **Update** `get_shop_subscription_by_id()`:
     - Remove `selectinload(ShopSubscription.pricing_tier)`

---

### Layer 4 — Services

9. **`python-worker/app/domains/billing/services/flat_fee_billing_service.py`**

   - Remove pricing-tier-related lookups in `create_recurring_subscription()`
   - `create_flat_fee_billing_cycle()` already accepts `period_fee` as optional — no change needed
   - `_store_shopify_subscription()` — no pricing_tier reference, OK

10. **`python-worker/app/domains/billing/services/billing_service_v2.py`**
    - Remove any pricing_tier references (review imports and method bodies)

---

### Layer 5 — Admin (Django)

11. **`admin/apps/billing/models.py`**

    - **Remove** entire `PricingTier` class
    - **Remove** `pricing_tier` ForeignKey from `ShopSubscription`
    - **Add** `monthly_fee` and `trial_days` to `SubscriptionPlan`
    - **Update** `ShopSubscription.effective_monthly_fee` → read from `subscription_plan.monthly_fee`
    - **Update** `ShopSubscription.effective_trial_days` → read from `subscription_plan.trial_days`

12. **`admin/apps/billing/admin.py`**

    - **Remove** `PricingTierAdmin` registration
    - **Update** `ShopSubscriptionAdmin.list_display` — replace `pricing_tier` with `subscription_plan`
    - **Update** `ShopSubscriptionAdmin.fieldsets` — remove `pricing_tier` field

13. **`admin/apps/billing/migrations/0001_initial.py`**

    - No direct edit; create a new migration via `python manage.py makemigrations billing`
    - Remove references to `pricing_tier` in the migration if regenerating

14. **`admin/apps/core/management/commands/check_db.py`** and **`verify_no_tables.py`**
    - Remove `'pricing_tiers'` from the expected table lists

---

### Layer 6 — DB Migration Script

15. **`python-worker/app/scripts/migrate_to_flat_fee_pricing.sql`** (new file)

    ```sql
    -- Migration: Drop PricingTier, move fields to SubscriptionPlan
    -- Run this ONCE per environment (dev/staging/prod) before restarting the app.

    BEGIN;

    -- 1. Add new columns to subscription_plans
    ALTER TABLE subscription_plans
      ADD COLUMN monthly_fee NUMERIC(10,2) DEFAULT 29.00,
      ADD COLUMN trial_days INTEGER DEFAULT 14;

    -- 2. Migrate existing default pricing tier data to subscription_plans
    -- (if any tiers exist, use the USD one as the plan-level default)
    UPDATE subscription_plans sp
    SET monthly_fee = pt.monthly_fee,
        trial_days  = pt.trial_days
    FROM (
        SELECT DISTINCT ON (subscription_plan_id)
            subscription_plan_id,
            monthly_fee,
            trial_days
        FROM pricing_tiers
        WHERE currency = 'USD'
          AND monthly_fee IS NOT NULL
        ORDER BY subscription_plan_id, is_default DESC, created_at DESC
    ) pt
    WHERE sp.id = pt.subscription_plan_id;

    -- 3. Drop pricing_tier_id FK from shop_subscriptions
    ALTER TABLE shop_subscriptions DROP CONSTRAINT IF EXISTS shop_subscriptions_pricing_tier_id_fkey;
    DROP INDEX IF EXISTS ix_shop_subscriptions_pricing_tier_id;
    ALTER TABLE shop_subscriptions DROP COLUMN IF EXISTS pricing_tier_id;

    -- 4. Drop legacy columns from shop_subscriptions
    ALTER TABLE shop_subscriptions DROP COLUMN IF EXISTS trial_threshold_override;
    ALTER TABLE shop_subscriptions DROP COLUMN IF EXISTS user_chosen_cap_amount;

    -- 5. Drop legacy columns from subscription_plans
    ALTER TABLE subscription_plans DROP COLUMN IF EXISTS default_commission_rate;

    -- 6. Drop pricing_tiers table
    DROP TABLE IF EXISTS pricing_tiers CASCADE;

    -- 7. Remove legacy index on subscription_plans (if it referenced commission rate)
    -- No action needed unless there are orphan indexes.

    COMMIT;
    ```

---

## Implementation Order

```
 1. Python Worker Models    (subscription_plan.py, delete pricing_tier.py, shop_subscription.py, __init__.py)
 2. Seed Scripts            (seed_subscription_plans.py, seed_flat_fee_plans.py)
 3. Repository              (billing_repository_v2.py)
 4. Services                (flat_fee_billing_service.py, billing_service_v2.py)
 5. Admin Django            (models.py, admin.py, migration)
 6. SQL migration script    (migrate_to_flat_fee_pricing.sql)
 7. Verification            (check_db.py, verify_no_tables.py)
```

Each step should be implemented and verified before moving to the next.

---

## Validation

1. Run the SQL migration against a staging DB, then restart the python-worker
2. Run both seed scripts — they should create plans without PricingTier
3. Verify admin panel loads without errors (no `PricingTier` model or FK issues)
4. Trigger a trial subscription creation flow end-to-end
5. Verify `shop_subscriptions` table has no `pricing_tier_id` column and `subscription_plans` has `monthly_fee`

---

## Risks & Edge Cases

- **Existing data**: The SQL migration handles existing rows with defaults. If shops have non-USD pricing tiers selected, those shops will inherit the plan-level default ($29). This is acceptable since we're going global USD.
- **Rollback**: If needed, restore from backup. The migration is destructive (drops columns/table).
- **Admin downtime**: The admin app will 500 on any page referencing `PricingTier` until the admin models are updated and a new migration runs. Deploy admin + SQL migration together.
- **Repository callers**: Must audit every caller of the removed methods (`create_trial_subscription`, `create_paid_subscription`, `create_flat_fee_subscription`, etc.) across the entire `python-worker` codebase. Any missed caller will cause a runtime error.
