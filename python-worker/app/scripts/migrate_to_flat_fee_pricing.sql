-- Migration: Drop PricingTier, move monthly_fee/trial_days to SubscriptionPlan
-- Run this ONCE per environment (dev/staging/prod) BEFORE restarting the app.
-- This is a one-way migration. Take a DB backup before running.

BEGIN;

-- ===================== 1. Add columns to subscription_plans =====================
ALTER TABLE subscription_plans
  ADD COLUMN IF NOT EXISTS monthly_fee NUMERIC(10,2) DEFAULT 29.00,
  ADD COLUMN IF NOT EXISTS trial_days INTEGER DEFAULT 14;

-- ===================== 2. Migrate existing pricing tier data =====================
-- For plans that have a USD pricing tier, copy the monthly_fee and trial_days
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

-- For plans WITHOUT a USD pricing tier, use defaults (already set via ADD COLUMN DEFAULT)

-- ===================== 3. Drop pricing_tier_id from shop_subscriptions =====================
ALTER TABLE shop_subscriptions
  DROP CONSTRAINT IF EXISTS shop_subscriptions_pricing_tier_id_fkey;

DROP INDEX IF EXISTS ix_shop_subscriptions_pricing_tier_id;

ALTER TABLE shop_subscriptions
  DROP COLUMN IF EXISTS pricing_tier_id;

-- ===================== 4. Drop legacy columns from shop_subscriptions =====================
ALTER TABLE shop_subscriptions
  DROP COLUMN IF EXISTS trial_threshold_override,
  DROP COLUMN IF EXISTS user_chosen_cap_amount;

-- ===================== 5. Drop legacy columns from subscription_plans =====================
ALTER TABLE subscription_plans
  DROP COLUMN IF EXISTS default_commission_rate;

-- ===================== 6. Drop pricing_tiers table =====================
DROP TABLE IF EXISTS pricing_tiers CASCADE;

-- ===================== 7. Drop indexes on pricing_tiers (handled by DROP TABLE) =====================

COMMIT;
