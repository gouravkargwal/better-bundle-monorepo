# End-to-End Onboarding Flow Review

## Flow Map

```
Shopify Admin installs app
        │
        ▼
  auth.$.tsx ─── Shopify OAuth ───► /app?...
        │
        ▼
  app._index.tsx  ←─── getShopOnboardingCompleted()
        │
        ├── true  ──► redirect /app/overview
        └── false ──► redirect /app/onboarding
                          │
                          ▼
  app.onboarding.tsx (loader)
      ├── authenticate.admin(request)
      ├── getShopOnboardingCompleted(session.shop) ── redirect to /app if done
      ├── OnboardingService.getOnboardingData(shop, admin)
      │       ├── Shopify GraphQL: shop { id, name, myshopifyDomain, email, currencyCode, plan { displayName, shopifyPlus } }
      │       └── Prisma: subscription_plans.findFirst(is_active && is_default)
      └── renders OnboardingPage
              │
              ▼  user clicks "Start Your X-Day Free Trial"
              │
  app.onboarding.tsx (action)
      ├── authenticate.admin(request)
      ├── OnboardingService.completeOnboarding(session, admin)
      │       ├── 1. Shopify GraphQL: shop info
      │       ├── 2. Prisma $transaction:
      │       │       ├── shops.upsert (create or update shop record)
      │       │       └── shop_subscriptions.create (TRIAL status)
      │       ├── 3. Shopify GraphQL: webPixelCreate mutation
      │       ├── 4. Kafka: publish data-collection job (historical mode)
      │       └── 5. Prisma: shops.update (onboarding_completed = true)
      └── redirect /app/overview
              │
              ▼
  app.tsx ─── checkServiceSuspensionMiddleware()
      ├── TRIAL status  ──► isSuspended=false
      ├── TRIAL_COMPLETED ──► redirect /app/billing
      ├── ACTIVE ──► isSuspended=false
      └── PENDING_APPROVAL ──► redirect /app/billing
              │
              ▼
  Python Worker (async via Kafka)
      ├── Data collection consumer processes job
      ├── Billing scheduler: check_trial_expiry_by_time()
      │       └── TRIAL → TRIAL_COMPLETED after trial_duration_days
      └── Attribution engine runs on orders
```

---

## Findings & Recommendations

### 1. Trial Status Inconsistency Between Frontend and Backend

**Location:** [`onboarding.service.ts`](better-bundle/app/features/onboarding/services/onboarding.service.ts:229) vs [`billing_repository_v2.py`](python-worker/app/domains/billing/repositories/billing_repository_v2.py:98-110)

| Component                          | Subscription Type | Status   |
| ---------------------------------- | ----------------- | -------- |
| Remix `completeOnboarding`         | `TRIAL`           | `TRIAL`  |
| Python `create_trial_subscription` | `TRIAL`           | `ACTIVE` |

The Python repository creates a trial but sets `status=ACTIVE`. The suspension middleware and billing status endpoints check for `status === "TRIAL"`. If the Python path is ever used to create a trial (it's currently only called from Python code paths), the trial would bypass suspension logic because the status would be `ACTIVE`, not `TRIAL`.

**Recommendation:** Align on a single convention. The Remix path is the one actually used during onboarding. Either:

- Delete the unused `create_trial_subscription` Python method, or
- Fix it to match: `status=SubscriptionStatus.TRIAL, subscription_type=SubscriptionType.TRIAL`

---

### 2. Missing `trial_duration_days` in Python's `create_trial_subscription`

**Location:** [`billing_repository_v2.py`](python-worker/app/domains/billing/repositories/billing_repository_v2.py:98-122)

When the Python backend creates a trial subscription, it does not set `trial_duration_days`. The field stays NULL in the DB. The frontend [`api.billing.status.tsx`](better-bundle/app/routes/api.billing.status.tsx:121-129) falls back to `14` as default. The Python `ShopSubscription.effective_trial_days` property falls back to `subscription_plan.trial_days`. All paths converge on 14 for the default plan, but if a plan with a different trial duration is ever used, the NULL field would cause inconsistency depending on which code path reads it.

**Recommendation:** Set `trial_duration_days` from the plan in the Python repository method, matching what the Remix path does.

---

### 3. No Loading State During Initial Data Fetch

**Location:** [`useOnboarding.ts`](better-bundle/app/features/onboarding/hooks/useOnboarding.ts:1-11), [`OnboardingPage.tsx`](better-bundle/app/features/onboarding/components/OnboardingPage.tsx:19-20)

The hook only tracks `navigation.state === "submitting"` (form submission). There is no loading indicator during the initial loader fetch, which involves:

1. Shopify Admin API authentication
2. Shopify GraphQL query for shop info
3. Prisma query for subscription plan

If any of these are slow (high latency store, transient DB slowness), the page appears blank/static until complete.

**Recommendation:** Add a skeleton or spinner for the initial load. Use `useNavigation().state === "loading"` or implement a Suspense boundary.

---

### 4. Action/Loader Error Type Ambiguity

**Location:** [`app.onboarding.tsx`](better-bundle/app/routes/app.onboarding.tsx:74-82)

```typescript
const hasLoaderError = "error" in loaderData;
```

This duck-typing check works but is fragile. If the type of `loaderData` ever gains an `error` property through normal data (e.g., a subscription plan with an `error` field), this breaks. The loader can return either `{ subscriptionPlan: ... }` or `{ error: string }` (with status 500), but the return type is `json(...)` so TypeScript infers a union incorrectly.

**Recommendation:** Use a discriminated union or a `success` flag in the loader response. Or return a consistent shape:

```typescript
type LoaderResponse =
  | { ok: true; subscriptionPlan: ... }
  | { ok: false; error: string };
```

---

### 5. `api.billing.status.tsx` Hardcodes `trial_days_remaining: 14` for Missing Subscription

**Location:** [`api.billing.status.tsx`](better-bundle/app/routes/api.billing.status.tsx:33-47)

When no subscription record exists, the endpoint assumes a 14-day trial with no reference to the actual plan configuration. If the default plan's `trial_days` is changed, this endpoint would report the wrong value.

**Recommendation:** Look up `subscription_plans.findFirst({ is_default: true })` for the fallback case.

---

### 6. `getShopOnboardingCompleted` Silently Returns `false` on Error

**Location:** [`shop.service.ts`](better-bundle/app/services/shop.service.ts:16-29)

```typescript
catch (error) {
  logger.error({ error }, "Error getting shop onboarding completed");
  return false;
}
```

A transient DB error causes the app to treat the merchant as not-onboarded, redirecting them to `/app/onboarding`. If they resubmit, the idempotency check in `activateTrialBillingPlan` prevents duplicate subscriptions, but the user experiences a confusing redirect loop.

**Recommendation:** Consider returning `true` (fail-open) for non-critical DB errors, or add a retry mechanism. At minimum, add a health check before making this determination.

---

### 7. Web Pixel Activation Has No Retry

**Location:** [`onboarding.service.ts`](better-bundle/app/features/onboarding/services/onboarding.service.ts:267-325)

The web pixel activation catches all errors and returns `null`, allowing onboarding to proceed. This is a deliberate trade-off, but there is no retry mechanism or alert. If the web pixel fails silently, the app's tracking capabilities are degraded without anyone knowing.

**Recommendation:** Add a background retry mechanism (e.g., a queued job) that retries web pixel creation if it failed during onboarding. Log a metric counter for observability.

---

### 8. Reinstall Resets `setup_guide_visited` Always

**Location:** [`onboarding.service.ts`](better-bundle/app/features/onboarding/services/onboarding.service.ts:150)

```typescript
setup_guide_visited: false,
```

This is set in both create and update paths of the upsert. For a reinstall, this resets any setup guide progress. While the `onboarding_completed` field is preserved, the setup guide progress is lost. Minor UX friction.

**Recommendation:** This is acceptable, but document why in a comment. If setup guide state should persist through reinstalls, use the same `isReinstall` pattern as `onboarding_completed`.

---

### 9. Suspension Cache Invalidation Loops Over All Matching Shop Records

**Location:** [`api.billing.activate.tsx`](better-bundle/app/routes/api.billing.activate.tsx:170-178)

```typescript
const shopRecords = await prisma.shops.findMany({
  where: { shop_domain: shop },
  select: { id: true },
});
for (const shopRecord of shopRecords) {
  await invalidateSuspensionCache(shopRecord.id);
}
```

`shop_domain` has a unique constraint, so `findMany` will return at most one record. The loop is unnecessary. Additionally, if multiple records (e.g., from a data inconsistency) exist, invalidating only the ones matching the domain may miss others.

**Recommendation:** Simplify to `findUnique` or just use the ID already fetched earlier in the function.

---

### 10. Subscription Status Enum Drift Risk

The Prisma schema (database `subscription_status_enum`), the Python model (`SubscriptionStatus`), and the frontend code all reference subscription statuses. There is no single source of truth. Adding a new status (e.g., `EXPIRED`) requires coordinated changes across three layers.

- [`schema.prisma`](better-bundle/prisma/schema.prisma:615-650) (PostgreSQL enum)
- [`enums.py`](python-worker/app/core/database/models/enums.py:139-156) (Python enum)
- [`serviceSuspension.ts`](better-bundle/app/middleware/serviceSuspension.ts:148-211) (string comparisons)

**Recommendation:** Add a pre-commit hook or migration test that verifies enum alignment across layers. Document the enum values in a single reference file.

---

### 11. No Onboarding Retry Limit or Debounce

The onboarding action has no idempotency key/retry protection beyond the database idempotency checks. A double-click or page refresh during submission could cause concurrent requests. The `$transaction` provides some protection, but the outer operations (web pixel creation, Kafka publish, `markOnboardingCompleted`) are not idempotent at the application level.

**Recommendation:** Add a client-side disabled state on the submit button (already done via `loading` prop), but also add a server-side idempotency key check (e.g., store a `onboarding_started_at` timestamp and reject submissions within a 30-second window).

---

### 12. `completeOnboarding` Transaction Order Creates Orphan State Risk

**Location:** [`onboarding.service.ts`](better-bundle/app/features/onboarding/services/onboarding.service.ts:27-47)

The order is:

1. `completeOnboardingTransaction` (commits shop + trial to DB)
2. `activateWebPixel` (Shopify API)
3. `triggerAnalysis` (Kafka) — **throws on failure**
4. `markOnboardingCompleted` (DB)

If step 3 fails, step 4 never runs. The shop is created, the trial subscription exists, but `onboarding_completed` is `false`. On next visit, `app._index.tsx` redirects to `/app/onboarding` again. On retry, the upsert and transaction succeed, and this time `markOnboardingCompleted` runs. **However**, the `triggerAnalysis` (Kafka) call may also fail again, creating a loop.

**Recommendation:** Either:

- Make `triggerAnalysis` non-fatal (log + alert, don't throw), or
- Move `markOnboardingCompleted` inside the transaction so the DB state is consistent regardless of downstream failures, and have a background job that retries the analysis.

---

## Strengths Acknowledged

- **Idempotency checks:** The trial subscription creation checks for existing subscriptions before creating a new one.
- **Web pixel TAKEN handling:** Gracefully handles the case where a pixel already exists.
- **Kafka partitioning by shop:** Ensures ordering of events for the same shop.
- **Fail-open suspension middleware:** When Redis and DB both fail, service is allowed through rather than falsely blocked.
- **Subscription ownership verification:** Activate endpoint verifies the subscription belongs to the requesting shop.
- **Reinstall protection:** `onboarding_completed` is preserved for reinstalling shops.
- **Comprehensive test coverage:** Both happy-path and bug-catching tests exist for the core service.

---

## UX Assessment: Gorse Training Timing vs Industry Standards

**Question asked:** When the user clicks "Start Free Trial", the backend fires a Gorse (data collection) training job, and the user lands on a 3-step setup progress card that polls until AI is ready. Is this how the industry does it?

**Answer: Partially — but the current UX has a significant disconnect from B2B SaaS norms.**

### The actual flow

```
[Start Free Trial button]
    ↓
Onboarding action: shop upsert → trial subscription → web pixel → Kafka data-collection job
    ↓
Redirect to /app/overview
    ↓
SetupProgressCard shows 3 steps:
  ✅ Step 1: Store connected (immediate)
  ⏳ Step 2: AI engine ready (polls every 15s via [`app.overview.tsx`](better-bundle/app/routes/app.overview.tsx:48-50))
  ❌ Step 3: Set up extensions (gated behind step 2)
```

### The core problem

The button says **"Start Your Free Trial"** — a _billing act_ — but the immediate effect is a _data pipeline_. The user expects either a dashboard or a clear setup wizard. Instead they get a progress bar saying "AI is learning your catalog..." with no actionable path forward until the backend finishes. This violates the **first-run experience principle**: deliver immediate value, then progressively reveal complexity.

### Industry patterns compared

| Pattern                                | Example apps                                     | How it works                                                                                          |
| -------------------------------------- | ------------------------------------------------ | ----------------------------------------------------------------------------------------------------- |
| **A: Value-first** ✅                  | Shopify apps (ReConvert, Growave), Stripe, Slack | Show dashboard immediately with available data; run background jobs asynchronously; notify when ready |
| **B: Explicit setup wizard**           | Klaviyo, Mailchimp                               | Clear 2-3 step wizard _before_ trial starts; user drives each step with explicit actions              |
| **C: Gated-onboarding** ❌ _(current)_ | —                                                | User action triggers backend job; user must wait for completion to proceed                            |

Pattern C is **not** standard in B2B SaaS for a reason: most shops at onboarding have minimal data. Gorse training will complete with few products/orders, making the gate feel arbitrary and the spinner feel like a bug.

### Specific issues

1. **Step 2 polls forever if analysis fails.** [`app.overview.tsx:42-55`](better-bundle/app/routes/app.overview.tsx:42-55) sets a 15s polling interval that only stops when `isSetupComplete` is true. If the Kafka job fails or the data pipeline errors, the user sees a perpetually spinning "AI is learning your catalog..." message with no error state or fallback.

2. **Extensions are gated behind AI readiness.** [`SetupProgressCard.tsx:44,51`](better-bundle/app/features/overview/components/SetupProgressCard.tsx:44,51) sets `isCurrent` for step 3 only when `recommendationsReady` is true. Users cannot install theme extensions and start getting value until the AI finishes training — even though extensions and AI are independent.

3. **No error state on the progress card.** If `productsAnalyzed` is `false` and stays false, the description is the vague "We're analyzing your product catalog. This usually takes a few minutes." There's no timeout, no retry action, no contact-support link.

### ⚠️ Critique of the "Value-first" recommendation above

I need to be honest: the Value-first approach (Option A) I sketched above has a flaw. Showing a dashboard with basic Shopify stats (product count, order count, revenue) is **not delivering value** — it's repackaging data the merchant already sees in their Shopify admin. The app's entire value proposition is _AI-powered recommendations that boost revenue_. Until those exist, the dashboard is a store stats page with a spinner, which undermines trust.

The industry examples I cited (Stripe, Slack) work because their value is immediate — Stripe shows payment activity, Slack shows team messages. BetterBundle's value depends on a pipeline that hasn't finished yet.

### ✅ My actual recommendation: "Honest Setup + Immediate Action"

A two-phase approach that respects the user's time and sets clear expectations:

**Phase 1 — The interstitial (after "Start Free Trial"):**

A single, beautiful card that replaces the current blank-redirect-to-overview:

```
┌─────────────────────────────────────────────┐
│  🔍 Let's power up your AI recommendations  │
│                                              │
│  BetterBundle will analyze your store's:     │
│                                              │
│  🛍️  Products & collections                  │
│  📦  Order history & trends                  │
│  👥  Customer shopping patterns              │
│                                              │
│  This takes ~2 minutes for most stores.      │
│  You can set up extensions in the meantime.  │
│                                              │
│  ┌─────────────────────────────────┐         │
│  │   Start Analysis →              │         │
│  └─────────────────────────────────┘         │
│                                              │
│  No charge during 14-day trial.              │
│  Cancel anytime.                             │
└─────────────────────────────────────────────┘
```

**Why this works:**

- Sets expectation: "we're going to analyze your data"
- Gives user control: they click the button, it's not happening invisibly
- Manages timeline: "~2 minutes" prevents the infinite spinner problem
- Decouples concerns: user knows they can do other things (extensions) while AI runs

**Phase 2 — The dashboard (after clicking "Start Analysis"):**

```
┌─────────────────────────────────────────────┐
│  ✅ Free trial — 14 days remaining          │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │  ⚡ AI is analyzing your store...    │    │
│  │  [████████░░░░] 60%                 │    │
│  │  Analyzing products (150/250)...    │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │  📋 Setup Guide                    │    │
│  │                                     │    │
│  │  ✅ Store connected                │    │
│  │  🔄 AI analyzing catalog...         │    │
│  │  📋 [Install Theme Extensions →]   │    │
│  │       (not gated — clickable now)  │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │  📊 Store Snapshot                  │    │
│  │  Products: 250   Orders: 1,234     │    │
│  │  Revenue: $45K   Avg order: $36    │    │
│  │  (basic stats, acknowledged as     │    │
│  │   "while you wait" context)        │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

**Key UX rules this follows:**

1. **Progress indicator with ETA** — users tolerate waiting when they know the timeline and see progress
2. **Actionable while waiting** — extensions are NOT gated, user can install widgets immediately
3. **Honest framing** — store stats are labeled as "while you wait" context, not as the product's value
4. **Single CTA** — one button on the interstitial, not multiple confusing choices

**What this replaces in the current code:**

- The current `SetupProgressCard` polls every 15s with no ETA or error state → replaced by progress bar with status text and retry button
- The current gating of extensions behind AI readiness → removed, extensions clickable immediately
- The current silent background data collection → made visible and user-initiated

---

## Summary of Required Actions

| Priority | Area                                           | Action                                                                                 |
| -------- | ---------------------------------------------- | -------------------------------------------------------------------------------------- |
| **High** | Trial status inconsistency                     | Align Python `create_trial_subscription` status with Remix path, or remove unused code |
| **High** | Missing `trial_duration_days` in Python        | Set field from plan in Python repository                                               |
| Medium   | No loading state on initial fetch              | Add skeleton/spinner for loader phase                                                  |
| Medium   | Error type ambiguity                           | Use discriminated union in loader response                                             |
| Medium   | Hardcoded trial days in status endpoint        | Look up actual plan config                                                             |
| Medium   | Silent `false` on DB error in onboarding check | Fail-open or add retry                                                                 |
| Low      | No web pixel retry                             | Add background retry job + metric                                                      |
| Low      | Reset `setup_guide_visited` on reinstall       | Document intent or preserve state                                                      |
| Low      | Suspension cache invalidation loop             | Simplify to use already-fetched ID                                                     |
| Low      | Status enum drift risk                         | Add cross-layer enum alignment checks                                                  |
| Low      | No onboarding idempotency key                  | Add server-side rate gate                                                              |
| Low      | Orphan state on Kafka failure                  | Decide: non-fatal Kafka or atomic onboarding flag                                      |

---

## Next Steps

1. Decide which of the above issues to address (some are deliberate trade-offs)
2. Switch to **Code mode** to implement fixes
3. Write targeted tests for each behavioral change
4. Verify the flow end-to-end with a test Shopify store
