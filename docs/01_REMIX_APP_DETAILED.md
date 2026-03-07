# BetterBundle Remix App -- Exhaustive Code Reference

> Generated from source code. This document covers every function, Prisma query, GraphQL mutation/query, Kafka event, Redis operation, and return type for unit test authoring.

All file paths are relative to `/Users/gouravkargwal/Desktop/BetterBundle/better-bundle/`.

---

## Table of Contents

1. [Prisma Schema Overview](#1-prisma-schema-overview)
2. [API Routes -- Billing](#2-api-routes----billing)
3. [API Route -- Sign Changeset](#3-api-route----sign-changeset)
4. [App Routes -- Layout & Navigation](#4-app-routes----layout--navigation)
5. [App Routes -- Pages](#5-app-routes----pages)
6. [Webhook Routes](#6-webhook-routes)
7. [Services (app/services/)](#7-services)
8. [Features -- Billing](#8-features----billing)
9. [Features -- Onboarding](#9-features----onboarding)
10. [Features -- Overview](#10-features----overview)
11. [Features -- Dashboard](#11-features----dashboard)
12. [Middleware -- Service Suspension](#12-middleware----service-suspension)
13. [Known Bugs & Issues](#13-known-bugs--issues)

---

## 1. Prisma Schema Overview

**File:** `prisma/schema.prisma`

### Key Models

| Model | Primary Key | Notable Fields |
|-------|------------|----------------|
| `shops` | `id` (UUID) | `shop_domain` (unique), `is_active`, `onboarding_completed`, `suspended_at`, `suspension_reason`, `service_impact`, `currency_code`, `access_token`, `shopify_plus` |
| `shop_subscriptions` | `id` (UUID) | `shop_id` FK, `subscription_type` (enum), `status` (enum), `shopify_subscription_id`, `shopify_line_item_id`, `shopify_status`, `confirmation_url`, `user_chosen_cap_amount`, `is_active`, `trial_threshold_override` |
| `billing_cycles` | `id` (UUID) | `shop_subscription_id` FK, `cycle_number`, `start_date`, `end_date`, `initial_cap_amount`, `current_cap_amount`, `usage_amount`, `commission_count`, `status` (enum) |
| `commission_records` | `id` (VARCHAR) | `shop_id` FK, `purchase_attribution_id` (unique), `billing_cycle_id` FK, `order_id`, `attributed_revenue`, `commission_rate`, `commission_earned`, `commission_charged`, `billing_phase` (enum), `status` (enum), `shopify_usage_record_id` (unique) |
| `subscription_plans` | `id` (UUID) | `name` (unique), `plan_type` (enum), `is_active`, `is_default` |
| `pricing_tiers` | `id` (UUID) | `subscription_plan_id` FK, `currency`, `commission_rate`, `trial_threshold_amount`, `is_active`, `is_default`, `tier_metadata` |
| `purchase_attributions` | `id` (UUID) | `shop_id` FK, `session_id` FK, `total_revenue`, `purchase_at`, `contributing_extensions`, `metadata` |
| `billing_invoices` | `id` (UUID) | `shop_subscription_id`, `shopify_invoice_id` (unique), `status`, `amount_due`, `amount_paid`, `total_amount`, `failure_reason` |
| `user_interactions` | `id` (UUID) | `shop_id`, `session_id`, `interaction_type`, `interaction_metadata` (JSON), `customer_id` |
| `user_sessions` | `id` (UUID) | `shop_id`, `customer_id`, `extensions_used` (JSON), `last_active`, `total_interactions` |
| `order_data` | `id` (UUID) | `shop_id`, `order_id`, `order_name`, `order_date`, `total_amount` |
| `product_data` | `id` (UUID) | `shop_id`, `product_id`, `title` |
| `sessions` | `id` | Shopify session storage, `shop`, `scope` |

### Key Enums

```prisma
enum billing_cycle_status_enum { ACTIVE, COMPLETED, CANCELLED, SUSPENDED }
enum billing_phase_enum { TRIAL, PAID }
enum commission_status_enum { TRIAL_PENDING, TRIAL_COMPLETED, PENDING, RECORDED, INVOICED, REJECTED, FAILED, CAPPED }
enum charge_type_enum { FULL, PARTIAL, OVERFLOW_ONLY, TRIAL, REJECTED }
enum subscription_status_enum { TRIAL, TRIAL_COMPLETED, PENDING_APPROVAL, ACTIVE, SUSPENDED, CANCELLED }
enum subscription_type_enum { TRIAL, PAID }
enum subscription_plan_type_enum { USAGE_BASED, RECURRING, HYBRID }
enum invoice_status_enum { DRAFT, PENDING, PAID, FAILED, CANCELLED, REFUNDED }
```

### Unique Constraints

- `shops.shop_domain` -- unique
- `commission_records.purchase_attribution_id` -- unique
- `commission_records.shopify_usage_record_id` -- unique
- `billing_cycles (shop_subscription_id, status)` -- unique (only one ACTIVE cycle per subscription)
- `billing_invoices.shopify_invoice_id` -- unique

---

## 2. API Routes -- Billing

### 2.1 `api.billing.setup` (POST action)

**File:** `app/routes/api.billing.setup.tsx`
**Signature (line 6):**
```typescript
export async function action({ request }: ActionFunctionArgs): Promise<Response>
```

**Authentication:** `authenticate.admin(request)` -- returns `{ session, admin }`

**Request Body:** `await request.json()` -- expects `{ monthlyCap: number }`

**Prisma Queries:**

1. **Line 27-30** -- Find shop:
```typescript
prisma.shops.findUnique({
  where: { shop_domain: shop },
  select: { id: true, currency_code: true },
})
```

2. **Line 37-42** -- Find subscription:
```typescript
prisma.shop_subscriptions.findFirst({
  where: { shop_id: shopRecord.id },
  include: { pricing_tiers: true },
})
```

3. **Line 56-67** -- Aggregate trial revenue (only if status === "PENDING_APPROVAL"):
```typescript
prisma.commission_records.aggregate({
  where: {
    shop_id: shopRecord.id,
    billing_phase: "TRIAL",
    status: { in: ["TRIAL_PENDING", "TRIAL_COMPLETED"] },
  },
  _sum: { attributed_revenue: true },
})
```

4. **Line 93-98** -- Find default plan:
```typescript
prisma.subscription_plans.findFirst({
  where: { is_active: true, is_default: true },
})
```

5. **Line 107-114** -- Find pricing tier:
```typescript
prisma.pricing_tiers.findFirst({
  where: {
    subscription_plan_id: defaultPlan.id,
    currency: shopRecord.currency_code || "USD",
    is_active: true,
    is_default: true,
  },
})
```

6. **Line 215-223** -- Mark subscription as SUSPENDED:
```typescript
prisma.shop_subscriptions.update({
  where: { id: shopSubscription.id },
  data: {
    status: "SUSPENDED" as any,
    user_chosen_cap_amount: monthlyCap,
    is_active: false,
    updated_at: new Date(),
  },
})
```

7. **Line 226-235** -- Store Shopify subscription info:
```typescript
prisma.shop_subscriptions.update({
  where: { id: shopSubscription.id },
  data: {
    shopify_subscription_id: subscription.id,
    shopify_line_item_id: subscription.lineItems[0].id,
    confirmation_url: confirmationUrl,
    shopify_status: "PENDING",
    updated_at: new Date(),
  },
})
```

**Shopify GraphQL Mutation (line 127-162):**
```graphql
mutation appSubscriptionCreate($name: String!, $returnUrl: URL!, $lineItems: [AppSubscriptionLineItemInput!]!, $test: Boolean!) {
  appSubscriptionCreate(name: $name, returnUrl: $returnUrl, lineItems: $lineItems, test: $test) {
    userErrors { field, message }
    confirmationUrl
    appSubscription {
      id, name, status
      lineItems {
        id
        plan {
          pricingDetails {
            __typename
            ... on AppUsagePricing {
              terms
              cappedAmount { amount, currencyCode }
            }
          }
        }
      }
    }
  }
}
```

**Variables (line 169-187):**
```typescript
{
  name: "Better Bundle - Usage Based",
  returnUrl: `https://admin.shopify.com/store/${shop}/apps/${appHandle}/app/billing`,
  test: process.env.NODE_ENV === "development",
  lineItems: [{
    plan: {
      appUsagePricingDetails: {
        terms: `3% of attributed revenue (capped at $${cappedAmount}/month)`,
        cappedAmount: { amount: cappedAmount, currencyCode: currency },
      },
    },
  }],
}
```

**Return Value (line 237-242):**
```typescript
{ success: true, subscription_id: string, confirmationUrl: string, message: string }
```

**Error Returns:**
- 400: `{ success: false, error: "Monthly cap is required..." }`
- 400: `{ success: false, error: "No subscription found" }`
- 400: `{ success: false, error: "Trial threshold not reached..." }`
- 404: `{ success: false, error: "Shop not found" }`
- 500: `{ success: false, error: "No default subscription plan found" }`
- 500: `{ success: false, error: "No pricing tier found for currency" }`
- 500: `{ success: false, error: "Failed to create subscription" }`

---

### 2.2 `api.billing.activate` (POST action)

**File:** `app/routes/api.billing.activate.tsx`
**Signature (line 7):**
```typescript
export async function action({ request }: ActionFunctionArgs): Promise<Response>
```

**Request Body:** `await request.formData()` -- expects `subscription_id` field

**Prisma Queries:**

1. **Line 23-26** -- Find shop:
```typescript
prisma.shops.findUnique({
  where: { shop_domain: shop },
  select: { id: true },
})
```

2. **Line 33-38** -- Find active subscription:
```typescript
prisma.shop_subscriptions.findFirst({
  where: { shop_id: shopRecord.id, is_active: true },
})
```

3. **Line 49-58** -- Update subscription to ACTIVE/PAID:
```typescript
prisma.shop_subscriptions.update({
  where: { id: shopSubscription.id },
  data: {
    shopify_subscription_id: subscriptionId,
    shopify_status: "ACTIVE",
    subscription_type: "PAID",
    status: "ACTIVE",
    updated_at: new Date(),
  },
})
```

4. **Line 61-70** -- Reactivate shop:
```typescript
prisma.shops.updateMany({
  where: { shop_domain: shop },
  data: {
    is_active: true,
    suspended_at: null,
    suspension_reason: null,
    service_impact: null,
    updated_at: new Date(),
  },
})
```

5. **Line 73-76** -- Find all shops by domain for cache invalidation:
```typescript
prisma.shops.findMany({
  where: { shop_domain: shop },
  select: { id: true },
})
```

**Redis Operations:**
- `invalidateSuspensionCache(shopRecord.id)` -- deletes key `suspension:{shopId}` (line 79)

**Return Value (line 82-86):**
```typescript
{ success: true, message: "Subscription activated successfully", subscription_id: string }
```

---

### 2.3 `api.billing.cancel` (POST action)

**File:** `app/routes/api.billing.cancel.tsx`
**Signature (line 8):**
```typescript
export async function action({ request }: ActionFunctionArgs): Promise<Response>
```

**Prisma Queries:**

1. **Line 13-16** -- Find shop:
```typescript
prisma.shops.findUnique({
  where: { shop_domain: shop },
  select: { id: true },
})
```

2. **Line 22-31** -- Find subscription (active or suspended):
```typescript
prisma.shop_subscriptions.findFirst({
  where: {
    shop_id: shopRecord.id,
    OR: [{ is_active: true }, { status: "SUSPENDED" }],
  },
  orderBy: { created_at: "desc" },
})
```

3. **Line 103-113** -- Reset subscription:
```typescript
prisma.shop_subscriptions.update({
  where: { id: shopSubscription.id },
  data: {
    user_chosen_cap_amount: null,
    shopify_status: "CANCELLED",
    status: "TRIAL_COMPLETED",
    is_active: true,
    cancelled_at: new Date(),
    updated_at: new Date(),
  },
})
```

**Shopify GraphQL Mutation (line 46-59):**
```graphql
mutation appSubscriptionCancel($id: ID!) {
  appSubscriptionCancel(id: $id) {
    userErrors { field, message }
    appSubscription { id, status }
  }
}
```

**Variables:** `{ id: shopSubscription.shopify_subscription_id }`

**Return Value (line 117-120):**
```typescript
{ success: true, message: "Subscription cancelled. You can set up a new subscription." }
```

---

### 2.4 `api.billing.increase-cap` (POST action)

**File:** `app/routes/api.billing.increase-cap.tsx`
**Signature (line 7):**
```typescript
export async function action({ request }: ActionFunctionArgs): Promise<Response>
```

**Request Body:** `await request.json()` -- expects `{ spendingLimit: number }`
Default value: `body.spendingLimit || 1000.0` (line 14)

**Prisma Queries:**

1. **Line 17-24** -- Find shop:
```typescript
prisma.shops.findUnique({
  where: { shop_domain: shop },
  select: { id: true, currency_code: true, suspension_reason: true },
})
```

2. **Line 31-44** -- Find active subscription with active billing cycle:
```typescript
prisma.shop_subscriptions.findFirst({
  where: { shop_id: shopRecord.id, is_active: true, status: "ACTIVE" },
  include: {
    billing_cycles: {
      where: { status: "ACTIVE" },
      orderBy: { cycle_number: "desc" },
      take: 1,
    },
  },
})
```

3. **Line 166-174** -- Atomic cap update with race condition protection:
```typescript
prisma.billing_cycles.update({
  where: {
    id: currentCycle.id,
    current_cap_amount: currentCap, // Only update if cap hasn't changed
  },
  data: { current_cap_amount: newSpendingLimit },
})
```

4. **Line 179-185** -- Reactivate subscription if suspended:
```typescript
prisma.shop_subscriptions.update({
  where: { id: shopSubscription.id },
  data: { status: "ACTIVE", updated_at: new Date() },
})
```

**Shopify GraphQL Mutation (line 83-115):**
```graphql
mutation appSubscriptionLineItemUpdate($id: ID!, $cappedAmount: MoneyInput!) {
  appSubscriptionLineItemUpdate(id: $id, cappedAmount: $cappedAmount) {
    userErrors { field, message }
    confirmationUrl
    appSubscription {
      id, status
      lineItems {
        id
        plan {
          pricingDetails {
            __typename
            ... on AppUsagePricing {
              terms
              cappedAmount { amount, currencyCode }
            }
          }
        }
      }
    }
  }
}
```

**Variables (line 117-123):**
```typescript
{ id: shopifyLineItemId, cappedAmount: { amount: newSpendingLimit.toString(), currencyCode: currency } }
```

**Kafka Message (line 203-210):**
- **Topic:** `shopify-usage-events`
- **Method:** `kafkaProducer.publishShopifyUsageEvent(...)`
- **Payload:**
```typescript
{
  event_type: "cap_increase",
  shop_id: shopRecord.id,
  shop_domain: shop,
  billing_cycle_id: currentCycle.id,
  new_cap_amount: newSpendingLimit,
  old_cap_amount: currentCap,
}
```

**Redis Operations:**
- `invalidateSuspensionCache(shopRecord.id)` -- deletes key `suspension:{shopId}` (line 188)

**Return Values:**
- Success with approval required: `{ success: true, requiresApproval: true, confirmationUrl: string, message: string }`
- Success: `{ success: true, message: "Cap increased successfully", newCap: number, previousCap: number }`

---

### 2.5 `api.billing.status` (GET loader)

**File:** `app/routes/api.billing.status.tsx`
**Signature (line 6):**
```typescript
export async function loader({ request }: LoaderFunctionArgs): Promise<Response>
```

**Prisma Queries:**

1. **Line 12-15** -- Find shop:
```typescript
prisma.shops.findUnique({
  where: { shop_domain: shop },
  select: { id: true, currency_code: true, is_active: true },
})
```

2. **Line 22-27** -- Find billing plan:
```typescript
prisma.billing_plans.findFirst({
  where: { shop_id: shopRecord.id, status: { in: ["active", "suspended"] } },
})
```

3. **Line 43-47** -- Aggregate purchase attributions (when trial active):
```typescript
prisma.purchase_attributions.aggregate({
  where: { shop_id: shopRecord.id },
  _sum: { total_revenue: true },
})
```

**Return Value (line 67-80):**
```typescript
{
  shop_id: string,
  billing_status: "trial_active" | "subscription_active" | "subscription_pending" | "subscription_declined" | "suspended" | "no_plan",
  message: string,
  trial_active: boolean,
  trial_revenue: number,
  trial_threshold: number,
  subscription_id: string | null,
  subscription_status: string | null,
  subscription_confirmation_url: string | null,
  requires_subscription_approval: boolean,
  shop_active: boolean,
}
```

**Known Bug (line 22):** References `billing_plans` model which does not exist in the Prisma schema. This likely references a legacy table or will throw at runtime.

---

## 3. API Route -- Sign Changeset

**File:** `app/routes/api.sign-changeset.tsx`

### `loader` (line 4)
```typescript
export const loader = async ({ request }: { request: Request }) => Response
```
Handles CORS preflight (OPTIONS) with headers: `Access-Control-Allow-Origin: *`, `Access-Control-Max-Age: 86400`.

### `action` (line 21)
```typescript
export const action = async ({ request }: { request: Request }) => Response
```

**Request Body:** `await request.json()` -- expects `{ changes: any, referenceId: string }`

**JWT Creation (line 28-39):**
```typescript
new SignJWT({ changes: body.changes })
  .setProtectedHeader({ alg: "HS256" })
  .setIssuer(process.env.SHOPIFY_API_KEY!)
  .setSubject(body.referenceId)
  .setIssuedAt()
  .setJti(crypto.randomUUID())
  .setExpirationTime("5m")
  .sign(new TextEncoder().encode(process.env.SHOPIFY_API_SECRET!))
```

**Return Value:** `{ token: string }` with CORS headers.

---

## 4. App Routes -- Layout & Navigation

### 4.1 `app.tsx` (Layout)

**File:** `app/routes/app.tsx`

**loader (line 21):**
```typescript
export const loader = async ({ request }: LoaderFunctionArgs)
```

Calls `getShopOnboardingCompleted(session.shop)` from `shop.service`.

**Return Value:**
```typescript
{ apiKey: string, session: Session, isOnboarded: boolean }
```

**Component:** Renders `<AppProvider>` with `<Frame>`, `<EnhancedNavMenu>`, loading indicator, and `<Outlet />`.

### 4.2 `app._index.tsx` (Redirect)

**File:** `app/routes/app._index.tsx`

**loader (line 5):**
```typescript
export const loader = async ({ request }: LoaderFunctionArgs)
```

Pure redirect route:
- If onboarded: redirects to `/app/overview`
- If not onboarded: redirects to `/app/onboarding`

No component exported.

---

## 5. App Routes -- Pages

### 5.1 `app.onboarding.tsx`

**File:** `app/routes/app.onboarding.tsx`

**loader (line 11):**
```typescript
export const loader = async ({ request }: LoaderFunctionArgs)
```
- Checks `getShopOnboardingCompleted(session.shop)` -- if true, redirects to `/app`
- Creates `new OnboardingService()` and calls `onboardingService.getOnboardingData(session.shop, admin)`

**action (line 42):**
```typescript
export const action = async ({ request }: ActionFunctionArgs)
```
- Creates `new OnboardingService()` and calls `onboardingService.completeOnboarding(session, admin)`
- On success, redirects to `/app`

---

### 5.2 `app.overview.tsx`

**File:** `app/routes/app.overview.tsx`

**loader (line 10):**
```typescript
export const loader = async ({ request }: LoaderFunctionArgs)
```
- Creates `new OverviewService()` and calls `overviewService.getOverviewData(session.shop)`
- Returns `json(data)` (see OverviewService for structure)

---

### 5.3 `app.billing.tsx`

**File:** `app/routes/app.billing.tsx`

**loader (line 9):**
```typescript
export async function loader({ request }: LoaderFunctionArgs)
```

**Prisma Queries:**

1. **Line 15-18** -- Find shop:
```typescript
prisma.shops.findUnique({
  where: { shop_domain: shop },
  select: { id: true, currency_code: true },
})
```

2. **Line 24-27** -- Get billing state:
```typescript
BillingService.getBillingState(shopRecord.id, admin)
```

**Return Value (line 33-38):**
```typescript
{
  shopId: string,
  shopCurrency: string,
  billingState: BillingState,
  subscriptionStatus: string | null, // from URL search param
}
```

---

### 5.4 `app.billing.cycles.tsx`

**File:** `app/routes/app.billing.cycles.tsx`

**loader (line 7):**
```typescript
export async function loader({ request }: LoaderFunctionArgs)
```

**URL Params:** `page` (default 1), `limit` (default 10)

**Prisma Queries:**

1. **Line 18-21** -- Find shop:
```typescript
prisma.shops.findUnique({
  where: { shop_domain: session.shop },
  select: { id: true, currency_code: true },
})
```

2. **Line 28-38** -- Find subscription:
```typescript
prisma.shop_subscriptions.findFirst({
  where: { shop_id: shop.id, is_active: true },
  select: { id: true, status: true, subscription_type: true },
})
```

3. **Line 49-73** -- Paginated billing cycles with count:
```typescript
Promise.all([
  prisma.billing_cycles.findMany({
    where: { shop_subscription_id: shopSubscription.id },
    orderBy: { cycle_number: "desc" },
    skip: offset,
    take: limit,
    select: {
      id: true, cycle_number: true, start_date: true, end_date: true,
      status: true, usage_amount: true, current_cap_amount: true, commission_count: true,
    },
  }),
  prisma.billing_cycles.count({
    where: { shop_subscription_id: shopSubscription.id },
  }),
])
```

**Return Value:**
```typescript
{
  cycles: Array<{
    id: string, cycleNumber: number, startDate: string, endDate: string,
    status: string, usageAmount: number, capAmount: number, commissionCount: number,
  }>,
  pagination: { page, limit, totalCount, totalPages, hasNext, hasPrevious },
  shopCurrency: string,
  shopId: string,
  subscriptionStatus: string,
  subscriptionType: string,
}
```

---

### 5.5 `app.billing.invoices.tsx`

**File:** `app/routes/app.billing.invoices.tsx`

**loader (line 49):**
```typescript
export async function loader({ request }: LoaderFunctionArgs)
```

**URL Params:** `page` (default 1), `limit` (default 10), `startDate`, `endDate`

**Shopify GraphQL Query (line 82-178):**
```graphql
query GetAppSubscriptions {
  currentAppInstallation {
    activeSubscriptions {
      id, name, status, createdAt
      lineItems {
        id
        plan {
          pricingDetails {
            __typename
            ... on AppRecurringPricing { price { amount, currencyCode } }
            ... on AppUsagePricing {
              balanceUsed { amount, currencyCode }
              cappedAmount { amount, currencyCode }
            }
          }
        }
        usageRecords(first: 250) {
          edges { node { id, createdAt, description, price { amount, currencyCode } } }
        }
      }
    }
    allSubscriptions(first: 20) {
      edges {
        node {
          id, name, status, createdAt
          lineItems {
            id
            plan { pricingDetails { ... } }
            usageRecords(first: 250) { edges { node { ... } } }
          }
        }
      }
    }
  }
}
```

**Fallback Prisma Query (line 277-299)** -- When no Shopify usage records found:
```typescript
prisma.commission_records.findMany({
  where: {
    shop_id: shop.id,
    shopify_usage_record_id: { not: null },
    deleted_at: null,
    billing_phase: "PAID",
    status: "RECORDED",
  },
  select: {
    shopify_usage_record_id: true, shopify_response: true,
    commission_charged: true, created_at: true, order_id: true, attributed_revenue: true,
  },
  orderBy: { created_at: "desc" },
  take: 250,
})
```

**Enrichment Prisma Query (line 417-431)** -- Link usage records to commission records:
```typescript
prisma.commission_records.findMany({
  where: {
    shop_id: shop.id,
    shopify_usage_record_id: { in: usageRecordIds },
    deleted_at: null,
  },
  select: { shopify_usage_record_id: true, order_id: true, attributed_revenue: true },
})
```

**Return Value (interface `InvoicesLoaderData`):**
```typescript
{
  invoices: InvoiceItem[],
  pagination: { page, limit, totalCount, totalPages, hasNext, hasPrevious },
  shopCurrency: string,
  shopId: string,
  shopDomain: string,
  filters: { startDate: string | null, endDate: string | null },
}
```

---

### 5.6 `app.billing.commissions.tsx`

**File:** `app/routes/app.billing.commissions.tsx`

**loader (line 5):** Pure redirect to `/app/billing/invoices`.

---

### 5.7 `app.dashboard.tsx` (Layout)

**File:** `app/routes/app.dashboard.tsx`

**loader (line 7):**
```typescript
export const loader = async ({ request }: LoaderFunctionArgs)
```
- If path is `/app/dashboard`, redirects to `/app/dashboard/revenue` preserving query params
- Otherwise returns `{ startDate, endDate }` from URL

---

### 5.8 `app.dashboard.revenue.tsx`

**File:** `app/routes/app.dashboard.revenue.tsx`

**loader (line 6):** Delegates to `loadRevenueData` from `features/dashboard/services/revenue.service`. See Section 11.1.

---

### 5.9 `app.dashboard.performance.tsx`

**File:** `app/routes/app.dashboard.performance.tsx`

**loader (line 6):** Delegates to `loadPerformanceData` from `features/dashboard/services/performance.service`. See Section 11.2.

---

### 5.10 `app.dashboard.products.tsx`

**File:** `app/routes/app.dashboard.products.tsx`

**loader (line 6):** Delegates to `loadProductsData` from `features/dashboard/services/products.service`. See Section 11.3.

---

### 5.11 `app.dashboard.activity.tsx`

**File:** `app/routes/app.dashboard.activity.tsx`

**loader (line 6):** Delegates to `loadActivityData` from `features/dashboard/services/activity.service`. See Section 11.4.

---

### 5.12 `app.extensions.tsx`

**File:** `app/routes/app.extensions.tsx`

**loader (line 19):**
```typescript
export const loader = async ({ request }: LoaderFunctionArgs)
```

**Prisma Queries:**

1. **Line 23-25** -- Find shop:
```typescript
prisma.shops.findUnique({
  where: { shop_domain: session.shop },
})
```

2. **Line 32-46** -- Find recent sessions with extensions:
```typescript
prisma.user_sessions.findMany({
  where: {
    shop_id: shop.id,
    last_active: { gt: cutoffTime }, // 24 hours ago
    extensions_used: { not: [] },
  },
  orderBy: { last_active: "desc" },
  take: 50,
})
```

**Return Value (line 93-96):**
```typescript
{
  shopDomain: string,
  extensions: {
    venus: { active: boolean, last_seen: string | null, app_blocks: [] },
    apollo: { active: boolean, last_seen: string | null, app_blocks: [] },
    phoenix: { active: boolean, last_seen: string | null, app_blocks: [] },
  },
}
```

---

## 6. Webhook Routes

### 6.1 `webhooks.app.uninstalled.tsx`

**File:** `app/routes/webhooks.app.uninstalled.tsx`

**action (line 6):**
```typescript
export const action = async ({ request }: ActionFunctionArgs) => Response
```

**Prisma Queries:**

1. **Line 14-17** -- Find shop:
```typescript
prisma.shops.findUnique({ where: { shop_domain: shop }, select: { id: true } })
```

2. **Line 21-32** -- Deactivate subscriptions:
```typescript
prisma.shop_subscriptions.updateMany({
  where: { shop_id: shopRecord.id, is_active: true },
  data: {
    is_active: false,
    status: "CANCELLED" as any,
    cancelled_at: new Date(),
    updated_at: new Date(),
  },
})
```

3. **Line 35-44** -- Mark shop inactive:
```typescript
prisma.shops.update({
  where: { id: shopRecord.id },
  data: {
    is_active: false,
    suspended_at: new Date(),
    suspension_reason: "app_uninstalled",
    service_impact: "All services disabled",
    updated_at: new Date(),
  },
})
```

4. **Line 48** -- Delete sessions:
```typescript
prisma.sessions.deleteMany({ where: { shop } })
```

**Return:** `new Response()` (200 empty body)

---

### 6.2 `webhooks.app.scopes_update.tsx`

**File:** `app/routes/webhooks.app.scopes_update.tsx`

**action (line 5):**
```typescript
export const action = async ({ request }: ActionFunctionArgs) => Response
```

**Prisma Query (line 10-17):**
```typescript
db.sessions.update({
  where: { id: session.id },
  data: { scope: current.toString() },
})
```

---

### 6.3 `webhooks.billing.approaching_cap.tsx`

**File:** `app/routes/webhooks.billing.approaching_cap.tsx`

**action (line 7):**
```typescript
export async function action({ request }: ActionFunctionArgs): Promise<Response>
```

**Prisma Query (line 28-31):**
```typescript
prisma.shops.findUnique({
  where: { shop_domain: shop },
  select: { id: true, shop_domain: true },
})
```

Logs warning with `usagePercentage`, `currentUsage`, `cappedAmount`. No business logic implemented beyond logging (placeholder for email notifications).

---

### 6.4 `webhooks.billing.billing_failed.tsx`

**File:** `app/routes/webhooks.billing.billing_failed.tsx`

**action (line 6):**
```typescript
export async function action({ request }: ActionFunctionArgs): Promise<Response>
```

**Prisma Queries:**

1. **Line 25-28** -- Find shop
2. **Line 36-42** -- Find subscription:
```typescript
prisma.shop_subscriptions.findFirst({
  where: { shop_id: shopRecord.id, is_active: true },
  select: { id: true },
})
```

3. **Line 73-84** -- Upsert billing invoice:
```typescript
prisma.billing_invoices.upsert({
  where: { shopify_invoice_id: invoiceData.shopify_invoice_id },
  update: {
    status: "FAILED",
    failure_reason: failureReason,
    shopify_response: invoiceData.shopify_response,
    updated_at: new Date(),
  },
  create: invoiceData,
})
```

---

### 6.5 `webhooks.billing.billing_success.tsx`

**File:** `app/routes/webhooks.billing.billing_success.tsx`

**action (line 6):**
```typescript
export async function action({ request }: ActionFunctionArgs): Promise<Response>
```

**Prisma Queries:**

1. **Line 24-27** -- Find shop
2. **Line 35-41** -- Find subscription
3. **Line 72-86** -- Upsert billing invoice with PAID status:
```typescript
prisma.billing_invoices.upsert({
  where: { shopify_invoice_id: invoiceData.shopify_invoice_id },
  update: {
    amount_paid: invoiceData.amount_paid,
    status: "PAID",
    paid_at: invoiceData.paid_at,
    payment_method: invoiceData.payment_method,
    payment_reference: invoiceData.payment_reference,
    shopify_response: invoiceData.shopify_response,
    updated_at: new Date(),
  },
  create: invoiceData as any,
})
```

---

### 6.6 `webhooks.billing.subscription_update.tsx`

**File:** `app/routes/webhooks.billing.subscription_update.tsx`

**action (line 7):**
```typescript
export async function action({ request }: ActionFunctionArgs): Promise<Response>
```

Dispatches to handler based on `status`:
- `"ACTIVE"` -> `handleActiveSubscription()`
- `"CANCELLED"` / `"DECLINED"` -> `handleCancelledSubscription()`
- `"APPROACHING_CAPPED_AMOUNT"` -> `handleCapApproach()`

#### `handleActiveSubscription` (line 94-328)

**Shopify GraphQL Query (line 105-124)** -- Fetch capped amount if not in webhook:
```graphql
query($id: ID!) {
  node(id: $id) {
    ... on AppSubscription {
      lineItems {
        plan {
          pricingDetails {
            ... on AppUsagePricing {
              cappedAmount { amount, currencyCode }
            }
          }
        }
      }
    }
  }
}
```

**Prisma Queries:**

1. **Line 160-166** -- Find subscription with cycles:
```typescript
prisma.shop_subscriptions.findFirst({
  where: { shop_id: shopRecord.id },
  include: { pricing_tiers: true, billing_cycles: true },
})
```

2. **Line 178-188** -- Update subscription to ACTIVE/PAID:
```typescript
prisma.shop_subscriptions.update({
  where: { id: shopSubscription.id },
  data: {
    shopify_subscription_id: subscriptionId,
    shopify_status: "ACTIVE",
    subscription_type: "PAID",
    status: "ACTIVE",
    is_active: true,
    updated_at: new Date(),
  },
})
```

3. **Line 215-228** -- Create billing cycle if none exists:
```typescript
prisma.billing_cycles.create({
  data: {
    shop_subscription_id: shopSubscription.id,
    cycle_number: 1,
    start_date: new Date(),
    end_date: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
    initial_cap_amount: capAmount,
    current_cap_amount: capAmount,
    usage_amount: 0,
    commission_count: 0,
    status: "ACTIVE",
    activated_at: new Date(),
  },
})
```

4. **Line 261-267** -- Update billing cycle cap if changed:
```typescript
prisma.billing_cycles.update({
  where: { id: activeCycle.id },
  data: { current_cap_amount: newCapAmount, updated_at: new Date() },
})
```

5. **Line 301-309** -- Reactivate shop:
```typescript
prisma.shops.update({
  where: { id: shopRecord.id },
  data: {
    is_active: true,
    suspended_at: null,
    suspension_reason: null,
    service_impact: null,
    updated_at: new Date(),
  },
})
```

**Redis:** `invalidateSuspensionCache(shopRecord.id)` (line 313)

#### `handleCancelledSubscription` (line 330-385)

**Prisma Queries:**

1. **Line 336-338** -- Find subscription:
```typescript
prisma.shop_subscriptions.findFirst({ where: { shop_id: shopRecord.id } })
```

2. **Line 349-359** -- Cancel subscription:
```typescript
prisma.shop_subscriptions.update({
  where: { id: shopSubscription.id },
  data: {
    shopify_subscription_id: subscriptionId,
    shopify_status: "CANCELLED",
    status: "CANCELLED",
    is_active: false,
    cancelled_at: new Date(),
    updated_at: new Date(),
  },
})
```

3. **Line 362-371** -- Suspend shop:
```typescript
prisma.shops.update({
  where: { id: shopRecord.id },
  data: {
    is_active: false,
    suspended_at: new Date(),
    suspension_reason: "subscription_cancelled",
    service_impact: "suspended",
    updated_at: new Date(),
  },
})
```

---

### 6.7 Kafka-Forwarding Webhook Routes

All these routes follow the same pattern: authenticate webhook, check suspension, publish to Kafka.

| Route File | Event Type | Kafka Topic | Shopify ID Source |
|------------|-----------|-------------|-------------------|
| `webhooks.orders.updated.tsx` | `"order_updated"` | `shopify-events` | `payload.id` |
| `webhooks.orders.paid.tsx` | `"order_paid"` | `shopify-events` | `payload.id` |
| `webhooks.refunds.create.tsx` | `"refund_created"` | `shopify-events` | `payload.order_id` (+ metadata.refund_id) |
| `webhooks.products.create.tsx` | `"product_created"` | `shopify-events` | `payload.id` |
| `webhooks.products.update.tsx` | `"product_updated"` | `shopify-events` | `payload.id` |
| `webhooks.products.delete.tsx` | `"product_deleted"` | `shopify-events` | `payload.id` |
| `webhooks.collections.create.tsx` | `"collection_created"` | `shopify-events` | `payload.id` |
| `webhooks.collections.update.tsx` | `"collection_updated"` | `shopify-events` | `payload.id` |
| `webhooks.collections.delete.tsx` | `"collection_deleted"` | `shopify-events` | `payload.id` |
| `webhooks.customers.create.tsx` | `"customer_created"` | `shopify-events` | `payload.id` |
| `webhooks.customers.update.tsx` | `"customer_updated"` | `shopify-events` | `payload.id` |
| `webhooks.inventory_levels.update.tsx` | `"inventory_updated"` | `shopify-events` | `payload.inventory_item_id` |

**Standard Kafka Payload (for shopify-events topic):**
```typescript
{
  event_type: string,
  shop_domain: string,
  shopify_id: string,
  timestamp: string, // ISO 8601
}
```

**Refund-specific Kafka Payload:**
```typescript
{
  event_type: "refund_created",
  shop_domain: string,
  shopify_id: string, // order_id, not refund_id
  metadata: {
    trigger: "refund_created",
    refund_id: string,
    purpose: "order_data_update_only",
  },
  timestamp: string,
}
```

**Inventory-specific Kafka Payload:**
```typescript
{
  event_type: "inventory_updated",
  shop_domain: string,
  shopify_id: string, // inventory_item_id
  inventory_data: {
    inventory_item_id: string,
    location_id: string,
    available: number,
    updated_at: string,
  },
  timestamp: string,
}
```

**Suspension Check:** All use `checkServiceSuspensionByDomain(shop)`. If suspended, return:
```typescript
{ success: true, message: "... skipped - services suspended", suspended: true, reason: string }
```

---

### 6.8 `webhooks.domain-update.tsx`

**File:** `app/routes/webhooks.domain-update.tsx`

**action (line 6):**
```typescript
export const action = async ({ request }: ActionFunctionArgs) => Response
```

**Shopify GraphQL Query (line 15-26):**
```graphql
query {
  shop {
    id
    myshopifyDomain
    primaryDomain { host, url }
  }
}
```

**Prisma Query (line 42-48):**
```typescript
prisma.shops.update({
  where: { shop_domain: session.shop },
  data: { custom_domain: customDomain, updated_at: new Date() },
})
```

---

### 6.9 GDPR Webhooks

| Route | Behavior |
|-------|----------|
| `webhooks.gdpr.shop_redact.tsx` | Logs and returns `new Response()` (200). Returns 401 on HMAC failure. |
| `webhooks.gdpr.customers_redact.tsx` | Logs customer ID and returns `new Response()` (200). Returns 401 on HMAC failure. |
| `webhooks.gdpr.customers_data_request.tsx` | Logs customer ID and returns `new Response()` (200). Returns 401 on HMAC failure. |

---

## 7. Services

### 7.1 `services/billing.service.ts`

**File:** `app/services/billing.service.ts`

#### `getTrialRevenueData(shopId: string): Promise<TrialRevenueData>` (line 54)

**Prisma Queries:**

1. **Line 59-67** -- Find subscription:
```typescript
prisma.shop_subscriptions.findFirst({
  where: { shop_id: shopId, is_active: true },
  include: { pricing_tiers: true },
})
```

2. **Line 77-88** -- Aggregate trial revenue:
```typescript
prisma.commission_records.aggregate({
  where: {
    shop_id: shopSubscription.shop_id,
    billing_phase: "TRIAL",
    status: { in: ["TRIAL_PENDING", "TRIAL_COMPLETED"] },
  },
  _sum: { attributed_revenue: true },
})
```

**Return:** `{ attributedRevenue: number, commissionEarned: number }`

#### `getUsageRevenueData(shopId: string): Promise<TrialRevenueData>` (line 110)

**Prisma Queries:**

1. **Line 115-123** -- Find active billing cycle:
```typescript
prisma.billing_cycles.findFirst({
  where: {
    shop_subscriptions: { shop_id: shopId, is_active: true },
    status: "ACTIVE",
  },
})
```

2. **Line 133-144** -- Aggregate commission records:
```typescript
prisma.commission_records.aggregate({
  where: {
    shop_id: shopId,
    billing_cycle_id: currentCycle.id,
    billing_phase: "PAID",
    status: "RECORDED",
  },
  _sum: { attributed_revenue: true, commission_earned: true },
})
```

#### `getCurrentCycleMetrics(shopId: string, shopSubscription: any): Promise<CurrentCycleMetrics>` (line 159)

**Prisma Queries:**

1. **Line 165-170** -- Find active billing cycle:
```typescript
prisma.billing_cycles.findFirst({
  where: { shop_subscription_id: shopSubscription.id, status: "ACTIVE" },
})
```

2. **Line 184-189** -- Find commission records:
```typescript
prisma.commission_records.findMany({
  where: {
    shop_id: shopId,
    billing_cycle_id: currentCycle.id,
    billing_phase: "PAID",
  },
})
```

**Note:** Hardcoded 3% commission rate at line 204: `const commission = netRevenue * 0.03;`

#### `getBillingSummary(shopId: string): Promise<BillingSummary | null>` (line 246)

**Prisma Query (line 251-265):**
```typescript
prisma.shop_subscriptions.findFirst({
  where: { shop_id: shopId, is_active: true },
  include: {
    subscription_plans: true,
    pricing_tiers: true,
    billing_cycles: {
      where: { status: "ACTIVE" },
      orderBy: { cycle_number: "desc" },
      take: 1,
    },
  },
})
```

**Known Bug (line 297):** `progress_percentage` is hardcoded to `0` -- never calculated.

**Known Bug (line 306):** `usage_percentage` and `days_remaining` are hardcoded to `0` -- never calculated.

#### `createShopSubscription(shopId: string, shopDomain: string): Promise<any>` (line 326)

**Prisma Queries:**

1. **Line 332-345** -- Idempotency check:
```typescript
prisma.shop_subscriptions.findFirst({
  where: {
    shop_id: shopId,
    OR: [
      { is_active: true },
      { status: { in: ["TRIAL", "PENDING_APPROVAL", "ACTIVE", "SUSPENDED"] as any } },
    ],
  },
  orderBy: { created_at: "desc" },
})
```

2. **Line 351-356** -- Find default plan:
```typescript
prisma.subscription_plans.findFirst({
  where: { is_active: true, is_default: true },
})
```

3. **Line 363-368** -- Find default pricing tier:
```typescript
prisma.pricing_tiers.findFirst({
  where: {
    subscription_plan_id: defaultPlan.id,
    is_active: true,
    is_default: true,
  },
})
```

4. **Line 376-388** -- Create subscription:
```typescript
prisma.shop_subscriptions.create({
  data: {
    shop_id: shopId,
    subscription_plan_id: defaultPlan.id,
    pricing_tier_id: defaultPricingTier.id,
    subscription_type: "TRIAL",
    status: "TRIAL",
    started_at: new Date(),
    is_active: true,
    auto_renew: true,
    user_chosen_cap_amount: defaultPricingTier.trial_threshold_amount,
  },
})
```

#### `completeTrialAndCreateCycle(shopId: string): Promise<any>` (line 413)

Updates subscription status to `"PENDING_APPROVAL"`.

#### `activateSubscription(shopId: string, shopifySubscriptionId: string): Promise<any>` (line 455)

Creates first billing cycle with 30-day duration and calls `reactivateShopIfSuspended`.

#### `increaseBillingCycleCap(shopId: string, newCapAmount: number, adjustedBy: string = "user"): Promise<any>` (line 523)

Updates `current_cap_amount` on active billing cycle.

#### `reactivateShopIfSuspended(shopId: string): Promise<void>` (line 567)

Sets `is_active: true`, clears suspension fields, invalidates Redis cache.

---

### 7.2 `services/shop.service.ts`

**File:** `app/services/shop.service.ts`

| Function | Signature (line) | Prisma Query | Return |
|----------|-----------------|-------------|--------|
| `getShopInfoFromShopify(admin)` (line 5) | `async (admin: any) => shop` | N/A -- GraphQL `query { shop { id, name, myshopifyDomain, primaryDomain { host, url }, email, currencyCode, plan { displayName, shopifyPlus } } }` | Shop object from Shopify |
| `getShop(shopDomain)` (line 41) | `async (shopDomain: string) => shop \| null` | `prisma.shops.findUnique({ where: { shop_domain } })` | Full shop record or null |
| `getShopOnboardingCompleted(shopDomain)` (line 53) | `async (shopDomain: string) => boolean` | `prisma.shops.findUnique({ where: { shop_domain } })` | `!!shop.onboarding_completed` |
| `getShopifyPlusStatus(shopDomain)` (line 69) | `async (shopDomain: string) => boolean` | `prisma.shops.findUnique({ where: { shop_domain }, select: { shopify_plus, plan_type } })` | `shop.shopify_plus \|\| false` |
| `createShopAndSetOnboardingCompleted(session, shopData, tx?)` (line 85) | `async (session: Session, shopData: any, tx?: any) => shop` | `prisma.shops.upsert(...)` -- see below | Shop record |
| `getShopSubscription(shopDomain)` (line 131) | `async (shopDomain: string) => subscription \| null` | `prisma.shop_subscriptions.findFirst({ where: { shop_domain, status: "ACTIVE" } })` | Subscription or null |
| `markOnboardingCompleted(shopDomain, tx?)` (line 138) | `async (shopDomain: string, tx?) => void` | `db.shops.update({ where: { shop_domain }, data: { onboarding_completed: true } })` | void |
| `activateAtlasWebPixel(admin, shopDomain)` (line 146) | `async (admin: any, shopDomain: string) => webPixel \| null` | N/A -- GraphQL mutation `webPixelCreate` | WebPixel object or null |
| `deactivateShopBilling(shopDomain, reason?)` (line 215) | `async (shopDomain: string, reason: string = "app_uninstalled") => result` | Multiple queries | `{ success: true, plans_deactivated_count, reason }` |

**`createShopAndSetOnboardingCompleted` upsert (line 102-126):**
```typescript
db.shops.upsert({
  where: { shop_domain: shopData.myshopifyDomain },
  update: {
    access_token: session.accessToken,
    currency_code: shopData.currencyCode,
    email: shopData.email,
    plan_type: shopData.plan.displayName,
    shopify_plus: shopData.plan.shopifyPlus || false,
    is_active: true,
    // For reinstalls, preserve onboarding if completed
  },
  create: {
    shop_domain: shopData.myshopifyDomain,
    access_token: session.accessToken,
    currency_code: shopData.currencyCode,
    email: shopData.email,
    plan_type: shopData.plan.displayName,
    shopify_plus: shopData.plan.shopifyPlus || false,
    is_active: true,
    onboarding_completed: false,
  },
})
```

**`activateAtlasWebPixel` GraphQL Mutation (line 149-163):**
```graphql
mutation webPixelCreate($webPixel: WebPixelInput!) {
  webPixelCreate(webPixel: $webPixel) {
    userErrors { code, field, message }
    webPixel { id, settings }
  }
}
```
**Variables:** `{ webPixel: { settings: "{}" } }`

**Known Bug (line 131-136):** `getShopSubscription` queries `shop_subscriptions` with `where: { shop_domain }` but `shop_subscriptions` does not have a `shop_domain` field. This will fail at runtime.

---

### 7.3 `services/pricing-tier.service.ts`

**File:** `app/services/pricing-tier.service.ts`

#### `getPricingTierConfig(shopDomain: string, shopCurrency: string): Promise<PricingTierConfig | null>` (line 14)

**Prisma Query (line 20-29):**
```typescript
prisma.pricing_tiers.findFirst({
  where: { currency: shopCurrency, is_active: true, is_default: true },
  include: { subscription_plans: true },
})
```

**Return:**
```typescript
{
  currency_code: string,
  threshold_amount: number,
  symbol: string,
  tier: string,
  description: string,
  commission_rate: number,
}
```

---

### 7.4 `services/subscription.service.ts`

**File:** `app/services/subscription.service.ts`

#### `hasActiveSubscription(shopId: string): Promise<boolean>` (line 4)

**Prisma Query (line 6-14):**
```typescript
prisma.billing_plans.findFirst({
  where: { shop_id: shopId, status: "active" },
  select: { configuration: true },
})
```

**Known Bug (line 6):** References `billing_plans` model which does not exist in the Prisma schema.

---

### 7.5 `services/redis.service.ts`

**File:** `app/services/redis.service.ts`

#### `getRedisClient(): Promise<RedisClientType>` (line 7)

Singleton pattern. Reads from env vars: `REDIS_URL`, `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`, `REDIS_DB`.

**Reconnect strategy:** Retries up to 10 times, backoff `Math.min(retries * 100, 3000)` ms.

#### `CacheService` class (line 57)

| Method | Signature | Operation | Default TTL |
|--------|----------|-----------|-------------|
| `get<T>(key)` | `async get<T>(key: string): Promise<T \| null>` | `client.get(key)` + JSON.parse | N/A |
| `set(key, value, ttl)` | `async set(key: string, value: any, ttlSeconds: number = 300): Promise<void>` | `client.setEx(key, ttlSeconds, JSON.stringify(value))` | 300s (5 min) |
| `del(key)` | `async del(key: string): Promise<void>` | `client.del(key)` | N/A |
| `delPattern(pattern)` | `async delPattern(pattern: string): Promise<void>` | `client.keys(pattern)` then `client.del(keys)` | N/A |
| `exists(key)` | `async exists(key: string): Promise<boolean>` | `client.exists(key) === 1` | N/A |
| `getOrSet<T>(key, fn, ttl)` | `async getOrSet<T>(key: string, fallbackFn: () => Promise<T>, ttlSeconds: number = 300): Promise<T>` | get, if miss execute fn and set | 300s |
| `invalidateDashboard(shopId)` | `async invalidateDashboard(shopId: string): Promise<void>` | Deletes patterns: `dashboard:{shopId}:*`, `overview:*`, `performance:*`, `context:*`, `products:*`, `activity:*` | N/A |
| `invalidateShop(shopDomain)` | `async invalidateShop(shopDomain: string): Promise<void>` | Deletes `shop:{shopDomain}` | N/A |

#### Cache Key Patterns (`CacheKeys` object, line 167):

| Key | Pattern | Used By |
|-----|---------|---------|
| `shop` | `shop:{domain}` | Shop lookups |
| `dashboard` | `dashboard:{shopId}:{period}:{startDate}:{endDate}` | Dashboard |
| `overview` | `overview:{shopId}:{startDate}:{endDate}` | Overview |
| `performance` | `performance:{shopId}:{startDate}:{endDate}` | Performance |
| `context` | `context:{shopId}:{startDate}:{endDate}` | Context |
| `products` | `products:{shopId}:{startDate}:{endDate}:{limit}` | Products |
| `activity` | `activity:{shopId}:{startDate}:{endDate}` | Activity |

#### Cache TTL Constants (`CacheTTL`, line 192):

| Constant | TTL (seconds) |
|----------|--------------|
| `SHOP` | 3600 (1 hour) |
| `DASHBOARD` | 300 (5 min) |
| `OVERVIEW` | 300 (5 min) |
| `PERFORMANCE` | 300 (5 min) |
| `CONTEXT` | 300 (5 min) |
| `PRODUCTS` | 600 (10 min) |
| `ACTIVITY` | 120 (2 min) |

---

### 7.6 `services/kafka/kafka-producer.service.ts`

**File:** `app/services/kafka/kafka-producer.service.ts`

Singleton pattern with `getInstance()`.

#### `publishShopifyEvent(eventData: ShopifyEventData): Promise<string>` (line 71)

**Topic:** `"shopify-events"`
**Key:** `eventData.shop_id || eventData.shop_domain || "unknown"`

**Message format:**
```typescript
{
  key: string,
  value: JSON.stringify({
    ...eventData,
    timestamp: ISO string,
    worker_id: kafkaConfig.workerId,
    source: "shopify_webhook",
  }),
  headers: {
    "event-type": eventData.event_type,
    "shop-id": eventData.shop_id || eventData.shop_domain || "unknown",
    timestamp: ISO string,
  },
}
```

**Return:** `"{topicName}:{partition}:{offset}"`

#### `publishDataJobEvent(jobData: any): Promise<string>` (line 125)

**Topic:** `"data-collection-jobs"`
**Key:** `jobData.shop_id`
**Source:** `"data_collection"`

#### `publishShopifyUsageEvent(usageData: any): Promise<string>` (line 173)

**Topic:** `"shopify-usage-events"`
**Key:** `usageData.shop_id || usageData.commission_id || usageData.shop_domain || "unknown"`
**Source:** `"shopify_usage"`

#### `publishAccessControlEvent(accessData: any): Promise<string>` (line 232)

**Topic:** `"access-control"`
**Key:** `accessData.shop_id`
**Source:** `"access_control"`

#### `publishBatch(events: Array<{ topic, data, key? }>): Promise<string[]>` (line 280)

Sends events sequentially (not atomically). Each event gets `timestamp` and `worker_id` metadata.

#### `getMetrics(): { messagesSent, errors, successRate }` (line 328)

Returns in-memory counters.

#### `close(): Promise<void>` (line 346)

Disconnects producer and resets state.

---

### 7.7 `services/kafka/kafka-client.service.ts`

**File:** `app/services/kafka/kafka-client.service.ts`

Singleton Kafka client wrapper.

| Method | Return | Notes |
|--------|--------|-------|
| `getInstance()` | `Promise<KafkaClientService>` | Creates Kafka instance with `kafkaConfig.clientId` and `kafkaConfig.bootstrapServers`. Retry: 8 retries, 100ms initial. |
| `getProducer()` | `Promise<Producer>` | `maxInFlightRequests: 1`, `idempotent: true`, `transactionTimeout: 30000` |
| `getConsumer(groupId)` | `Promise<Consumer>` | `sessionTimeout: 30000`, `heartbeatInterval: 3000`, `maxWaitTimeInMs: 5000` |
| `getAdmin()` | `Promise<Admin>` | Admin client |
| `healthCheck()` | `Promise<{ status, details }>` | Calls `admin.describeCluster()` |
| `close()` | `Promise<void>` | Disconnects all clients |
| `isConnected` (getter) | `boolean` | Connection status |

---

## 8. Features -- Billing

### 8.1 `features/billing/services/billing.service.ts`

**File:** `app/features/billing/services/billing.service.ts`

#### `BillingService.getBillingState(shopId: string, admin?: any): Promise<BillingState>` (line 10)

**Flow:**
1. Get trial revenue via `getTrialRevenue(shopId)` (commission_records aggregate)
2. Get trial threshold from subscription + pricing_tiers
3. If `trialRevenue < trialThreshold`: return `status: "trial_active"`
4. If admin available: check Shopify GraphQL for subscription status
5. If active/pending in Shopify: return `status: "subscription_active"`
6. Otherwise: return `status: "trial_completed"`
7. On error: returns `status: "trial_active"` with error

**Prisma Query -- Find subscription (line 20-29):**
```typescript
prisma.shop_subscriptions.findFirst({
  where: { shop_id: shopId, is_active: true },
  include: { pricing_tiers: true },
  orderBy: { created_at: "desc" },
})
```

#### `BillingService.getTrialRevenue(shopId: string): Promise<number>` (line 116) -- private static

**Prisma Query (line 117-129):**
```typescript
prisma.commission_records.aggregate({
  where: {
    shop_id: shopId,
    billing_phase: "TRIAL",
    status: { in: ["TRIAL_PENDING", "TRIAL_COMPLETED"] },
  },
  _sum: { attributed_revenue: true },
})
```

#### `BillingService.getTrialDataFromRevenue(shopId, revenue, threshold)` (line 135) -- private static

**Prisma Query (line 143-146):**
```typescript
prisma.shops.findUnique({
  where: { id: shopId },
  select: { currency_code: true },
})
```

**Return:**
```typescript
{ isActive: boolean, thresholdAmount: number, accumulatedRevenue: number, progress: number, currency: string }
```

#### `BillingService.getSubscriptionDataFromShopify(shopSubscription, shopifyStatus)` (line 160) -- private static

Calls `getCommissionBreakdown` and computes `currentUsage = shopifyUsage + expectedCharge`.

#### `BillingService.getCommissionBreakdown(shopId, subscriptionId)` (line 206) -- private static

**Prisma Queries:**

1. **Line 212-217** -- Find active cycle:
```typescript
prisma.billing_cycles.findFirst({
  where: { shop_subscription_id: subscriptionId, status: "ACTIVE" },
})
```

2. **Line 224-237** -- Aggregate pending commissions:
```typescript
prisma.commission_records.aggregate({
  where: {
    shop_id: shopId,
    billing_cycle_id: currentCycle.id,
    billing_phase: "PAID",
    status: "PENDING",
    commission_charged: { gt: 0 },
  },
  _sum: { commission_charged: true },
})
```

3. **Line 240-249** -- Aggregate rejected commissions:
```typescript
prisma.commission_records.aggregate({
  where: {
    shop_id: shopId,
    billing_cycle_id: currentCycle.id,
    billing_phase: "PAID",
    status: "REJECTED",
  },
  _sum: { commission_earned: true },
})
```

**Return:** `{ expectedCharge: number, rejectedAmount: number }`

#### `BillingService.getShopifySubscriptionStatus(shopId, admin)` (line 269) -- static

**Shopify GraphQL Query 1 -- activeSubscriptions (line 283-318):**
```graphql
query {
  currentAppInstallation {
    activeSubscriptions {
      id, name, status, test, currentPeriodEnd
      lineItems {
        plan {
          pricingDetails {
            ... on AppUsagePricing { cappedAmount { amount, currencyCode }, balanceUsed { amount, currencyCode }, terms }
            ... on AppRecurringPricing { price { amount, currencyCode }, interval }
          }
        }
      }
    }
  }
}
```

**Side effect (line 358-379):** If active subscription found via GraphQL, syncs DB:
```typescript
prisma.shop_subscriptions.update({
  where: { id: dbSubscription.id },
  data: {
    shopify_subscription_id: subscription.id,
    shopify_status: subscription.status,
    subscription_type: "PAID",
    status: subscription.status === "ACTIVE" ? "ACTIVE" : subscription.status === "PENDING" ? "ACTIVE" : dbSubscription.status,
    updated_at: new Date(),
  },
})
```

**Shopify GraphQL Query 2 -- node query (line 413-449):**
```graphql
query($id: ID!) {
  node(id: $id) {
    ... on AppSubscription {
      id, name, status, test, currentPeriodEnd
      lineItems {
        plan {
          pricingDetails {
            ... on AppUsagePricing { cappedAmount { amount, currencyCode }, balanceUsed { amount, currencyCode }, terms }
            ... on AppRecurringPricing { price { amount, currencyCode }, interval }
          }
        }
      }
    }
  }
}
```

---

### 8.2 `features/billing/types/billing.types.ts`

**File:** `app/features/billing/types/billing.types.ts`

```typescript
interface BillingState {
  status: BillingStatus;
  trialData?: TrialData;
  subscriptionData?: SubscriptionData;
  error?: BillingError;
}

type BillingStatus = "trial_active" | "trial_completed" | "subscription_pending"
  | "subscription_active" | "subscription_suspended" | "subscription_cancelled";

interface TrialData {
  isActive: boolean;
  thresholdAmount: number;
  accumulatedRevenue: number;
  progress: number; // 0-100
  daysRemaining?: number;
  currency: string;
}

interface SubscriptionData {
  id: string;
  status: "PENDING" | "ACTIVE" | "DECLINED" | "CANCELLED" | "EXPIRED";
  spendingLimit: number;
  currentUsage: number;
  shopifyUsage: number;
  expectedCharge: number;
  rejectedAmount?: number;
  usagePercentage: number;
  confirmationUrl?: string;
  currency: string;
  billingCycle?: { startDate: string; endDate: string; cycleNumber: number };
}

interface BillingError { code: string; message: string; actionRequired?: boolean; actionUrl?: string; }
interface BillingSetupData { spendingLimit: number; currency: string; }
interface BillingMetrics { totalRevenue: number; attributedRevenue: number; commissionEarned: number; commissionRate: number; currency: string; }
```

---

## 9. Features -- Onboarding

### 9.1 `features/onboarding/services/onboarding.service.ts`

**File:** `app/features/onboarding/services/onboarding.service.ts`

#### `OnboardingService.getOnboardingData(shopDomain: string, admin: any)` (line 7)

1. Calls `getShopInfoFromShopify(admin)` -- GraphQL query for shop info
2. Calls `getPricingTierConfig(shopDomain, shopData.currencyCode)`

**Return:** `{ pricingTier: { symbol: string, threshold_amount: number } }`

#### `OnboardingService.completeOnboarding(session: any, admin: any)` (line 27)

1. `getShopInfoFromShopify(admin)`
2. `completeOnboardingTransaction(session, shopData)` -- runs in `prisma.$transaction`
3. `activateWebPixel(admin, session.shop)` -- GraphQL mutation
4. `triggerAnalysis(session.shop)` -- publishes Kafka event

#### `completeOnboardingTransaction` (line 119) -- private

Runs in `prisma.$transaction`:
1. `createOrUpdateShop(session, shopData, tx)` -- `tx.shops.upsert(...)`
2. `activateTrialBillingPlan(session.shop, shop, tx)` -- creates shop_subscription
3. `markOnboardingCompleted(session.shop, tx)` -- `tx.shops.update({ data: { onboarding_completed: true } })`

#### `activateTrialBillingPlan` (line 183) -- private

**Idempotency check (line 190-207):**
```typescript
tx.shop_subscriptions.findFirst({
  where: {
    shop_id: shopRecord.id,
    OR: [
      { is_active: true },
      { status: { in: ["TRIAL", "PENDING_APPROVAL", "ACTIVE", "SUSPENDED"] as any } },
    ],
  },
  orderBy: { created_at: "desc" },
})
```

**Creates subscription (line 237-248):**
```typescript
tx.shop_subscriptions.create({
  data: {
    shop_id: shopRecord.id,
    subscription_plan_id: defaultPlan.id,
    pricing_tier_id: pricingTier.id,
    subscription_type: "TRIAL",
    status: "TRIAL",
    started_at: new Date(),
    is_active: true,
    auto_renew: true,
  },
})
```

#### `triggerAnalysis` (line 339) -- private

**Kafka Message:**
- **Topic:** `"data-collection-jobs"` (via `publishDataJobEvent`)
- **Payload:**
```typescript
{
  event_type: "data_collection",
  job_id: `analysis_${shopDomain}_${Date.now()}`,
  shop_id: shop.id,
  job_type: "data_collection",
  mode: "historical",
  collection_payload: {
    data_types: ["products", "orders", "customers", "collections"],
  },
  trigger_source: "analysis",
  timestamp: ISO string,
}
```

#### `activateWebPixel` (line 279) -- private

Same as `shop.service.ts` `activateAtlasWebPixel` -- GraphQL `webPixelCreate` mutation.

---

### 9.2 `features/onboarding/services/onboarding.types.ts`

```typescript
interface OnboardingData {
  pricingTier: { symbol: string; threshold_amount: number } | null;
}
interface OnboardingError { error: string; }
interface ShopData {
  id: string; name: string; myshopifyDomain: string;
  primaryDomain: { host: string; url: string };
  email: string; currencyCode: string;
  plan: { displayName: string };
}
```

---

## 10. Features -- Overview

### 10.1 `features/overview/services/overview.service.ts`

**File:** `app/features/overview/services/overview.service.ts`

#### `OverviewService.getOverviewData(shopDomain: string)` (line 4)

Calls in sequence:
1. `getShopInfo(shopDomain)`
2. `getBillingPlan(shop.id)`
3. `getOverviewMetrics(shop.id, currencyCode)`
4. `getPerformanceData(shop.id, currencyCode)`

**Return:** `{ shop, billingPlan, overviewData, performanceData }`

#### `getShopInfo` (line 31) -- private

**Prisma Query (line 32-41):**
```typescript
prisma.shops.findUnique({
  where: { shop_domain: shopDomain },
  select: { id: true, shop_domain: true, currency_code: true, plan_type: true, created_at: true },
})
```

#### `getBillingPlan` (line 50) -- private

**Prisma Query (line 51-67):**
```typescript
prisma.shop_subscriptions.findFirst({
  where: { shop_id: shopId, status: "ACTIVE" },
  select: {
    id: true, subscription_plan_id: true, pricing_tier_id: true,
    status: true, started_at: true, expires_at: true,
    is_active: true, auto_renew: true, shop_subscription_metadata: true,
  },
})
```

#### `getOverviewMetrics` (line 72) -- private

**Prisma Queries (multiple):**

1. **Line 74-83** -- Find subscription status:
```typescript
prisma.shop_subscriptions.findFirst({
  where: { shop_id: shopId, is_active: true },
  select: { status: true, id: true },
})
```

2. **Trial Phase Queries (line 95-116):**
```typescript
prisma.commission_records.aggregate({
  where: {
    shop_id: shopId,
    billing_phase: "TRIAL",
    status: { in: ["TRIAL_PENDING", "TRIAL_COMPLETED"] },
  },
  _sum: { attributed_revenue: true },
})

prisma.commission_records.count({
  where: {
    shop_id: shopId,
    billing_phase: "TRIAL",
    status: { in: ["TRIAL_PENDING", "TRIAL_COMPLETED"] },
  },
})
```

3. **Paid Phase Queries (line 119-147):**
```typescript
prisma.commission_records.aggregate({
  where: {
    shop_id: shopId,
    billing_phase: "PAID",
    status: { in: ["RECORDED", "INVOICED"] },
  },
  _sum: { attributed_revenue: true, commission_charged: true },
})

prisma.commission_records.count({
  where: {
    shop_id: shopId,
    billing_phase: "PAID",
    status: { in: ["RECORDED", "INVOICED"] },
  },
})
```

4. **Line 151-155** -- Total orders:
```typescript
prisma.order_data.count({ where: { shop_id: shopId } })
```

5. **Line 162-183** -- Active plan details:
```typescript
prisma.shop_subscriptions.findFirst({
  where: { shop_id: shopId, is_active: true },
  include: {
    subscription_plans: { select: { name, plan_type, description } },
    pricing_tiers: { select: { commission_rate, trial_threshold_amount, currency } },
  },
})
```

6. **Line 188-200** -- Commission charged for PAID phase:
```typescript
prisma.commission_records.aggregate({
  where: {
    shop_id: shopId,
    billing_phase: "PAID",
    status: { in: ["RECORDED", "INVOICED"] },
  },
  _sum: { commission_charged: true },
})
```

#### `getPerformanceData` (line 238) -- private

**Prisma Queries:**

1. **Line 262-286** -- Commission records with purchase attributions:
```typescript
prisma.commission_records.findMany({
  where: {
    shop_id: shopId,
    status: { in: statusFilter }, // ["TRIAL_PENDING","TRIAL_COMPLETED"] or ["RECORDED","INVOICED"]
  },
  select: {
    id: true, attributed_revenue: true, order_id: true,
    created_at: true, commission_metadata: true,
    purchase_attributions: {
      select: { contributing_extensions: true, metadata: true },
    },
  },
  orderBy: { attributed_revenue: "desc" },
  take: 10,
})
```

2. **Line 305-315** -- Order details for naming:
```typescript
prisma.order_data.findMany({
  where: { order_id: { in: orderIds }, shop_id: shopId },
  select: { order_id: true, order_name: true, total_amount: true },
})
```

3. **Line 404-421** -- Current month revenue:
```typescript
prisma.commission_records.aggregate({
  where: {
    shop_id: shopId,
    created_at: { gte: firstOfCurrentMonth },
    status: { in: statusFilter },
  },
  _sum: { attributed_revenue: true },
})
```

4. **Line 423-441** -- Last month revenue (for growth calculation):
```typescript
prisma.commission_records.aggregate({
  where: {
    shop_id: shopId,
    created_at: { gte: firstOfLastMonth, lt: firstOfCurrentMonth },
    status: { in: statusFilter },
  },
  _sum: { attributed_revenue: true },
})
```

---

### 10.2 `features/overview/services/overview.types.ts`

See type definitions in the file. Key types: `ShopInfo`, `BillingPlan`, `OverviewMetrics`, `PerformanceData`, `OverviewData`, `OverviewError`.

---

## 11. Features -- Dashboard

### 11.1 `features/dashboard/services/revenue.service.ts`

**File:** `app/features/dashboard/services/revenue.service.ts`

#### `loadRevenueData({ request }: LoaderFunctionArgs)` (line 7)

**Prisma Query -- Shop (line 14-17):**
```typescript
prisma.shops.findUnique({
  where: { shop_domain: session.shop },
  select: { id: true, currency_code: true, money_format: true },
})
```

Calls `getRevenueOverview(...)` and `getAttributedMetrics(...)` in parallel.

#### `getMetricsForPeriod(shopId, startDate, endDate)` (line 119) -- module-private

**Prisma Queries (all in `Promise.all`):**

1. **View count (line 126-133):**
```typescript
prisma.user_interactions.count({
  where: {
    shop_id: shopId,
    created_at: { gte: startDate, lte: endDate },
    interaction_type: { in: ["recommendation_viewed", "product_viewed", "page_viewed"] },
  },
})
```

2. **Click count (line 135-142):**
```typescript
prisma.user_interactions.count({
  where: {
    shop_id: shopId,
    created_at: { gte: startDate, lte: endDate },
    interaction_type: { in: ["recommendation_add_to_cart", "product_added_to_cart"] },
  },
})
```

3. **Purchase revenue (line 144-151):**
```typescript
prisma.purchase_attributions.aggregate({
  where: { shop_id: shopId, purchase_at: { gte: startDate, lte: endDate } },
  _sum: { total_revenue: true },
  _avg: { total_revenue: true },
})
```

4. **Customer count (line 152-162):**
```typescript
prisma.user_sessions.groupBy({
  by: ["customer_id"],
  where: {
    shop_id: shopId,
    created_at: { gte: startDate, lte: endDate },
    customer_id: { not: null },
  },
}).then(result => result.length)
```

#### `getAttributedMetrics(shopId, startDate, endDate, currencyCode)` (line 174)

**Prisma Queries (in parallel):**

1. **Attributed revenue:**
```typescript
prisma.purchase_attributions.aggregate({
  where: { shop_id: shopId, purchase_at: { gte: startDate, lte: endDate } },
  _sum: { total_revenue: true },
})
```

2. **Total revenue:**
```typescript
prisma.order_data.aggregate({
  where: { shop_id: shopId, order_date: { gte: startDate, lte: endDate } },
  _sum: { total_amount: true },
})
```

**Return:**
```typescript
{
  attributed_revenue: number,
  attributed_refunds: 0, // Hardcoded
  net_attributed_revenue: number,
  attribution_rate: number,
  refund_rate: 0, // Hardcoded
  currency_code: string,
}
```

---

### 11.2 `features/dashboard/services/performance.service.ts`

**File:** `app/features/dashboard/services/performance.service.ts`

#### `loadPerformanceData({ request }: LoaderFunctionArgs)` (line 7)

Same shop lookup, then `getPerformanceMetrics(shop.id, start, end)`.

#### `getMetricsForPeriod(shopId, startDate, endDate)` (line 94)

**Prisma Queries (in parallel):**
1. View count: same interaction_type filter as revenue
2. Click count: same as revenue
3. Customer count: same groupBy as revenue

**Return:**
```typescript
{
  total_recommendations: number, total_clicks: number,
  conversion_rate: number, total_customers: number,
  recommendations_change: number | null, clicks_change: number | null,
  conversion_rate_change: number | null, customers_change: number | null,
}
```

---

### 11.3 `features/dashboard/services/products.service.ts`

**File:** `app/features/dashboard/services/products.service.ts`

#### `loadProductsData({ request }: LoaderFunctionArgs)` (line 7)

Calls `getTopProducts(shop.id, start, end, 10, currencyCode)`.

#### `getTopProducts(shopId, startDate, endDate, limit, currencyCode)` (line 47)

**Prisma Queries:**

1. **Line 55-73** -- User interactions:
```typescript
prisma.user_interactions.findMany({
  where: {
    shop_id: shopId,
    created_at: { gte: startDate, lte: endDate },
    interaction_type: {
      in: ["recommendation_viewed", "product_viewed", "recommendation_add_to_cart", "product_added_to_cart"],
    },
  },
  select: { interaction_type: true, interaction_metadata: true, customer_id: true },
})
```

2. **Line 125-128** -- Product titles:
```typescript
prisma.product_data.findMany({
  where: { product_id: { in: productIds }, shop_id: shopId },
  select: { product_id: true, title: true },
})
```

**Product ID Extraction from metadata (line 86-93):**
- `metadata.data.recommendations[0].id`
- `metadata.data.productVariant.product.id`
- `metadata.data.cartLine.merchandise.product.id`

**Return:** Array of `TopProductData` sorted by conversion_rate then clicks, limited to `limit`.

**Note:** `revenue` is always 0 (line 137): `revenue: 0, // No reliable per-product attribution yet`

---

### 11.4 `features/dashboard/services/activity.service.ts`

**File:** `app/features/dashboard/services/activity.service.ts`

#### `loadActivityData({ request }: LoaderFunctionArgs)` (line 7)

Calls `getRecentActivityData(shop.id, start, end, currencyCode)`.

#### `getRecentActivityData(shopId, startDate, endDate, currencyCode)` (line 46)

Computes 3 time periods: today, yesterday, this_week (7 days).

#### `getActivityMetrics(shopId, startDate, endDate)` (line 95)

**Prisma Queries (all in `Promise.all`):**

1. **Recommendations:**
```typescript
prisma.user_interactions.count({
  where: {
    shop_id: shopId,
    created_at: { gte: startDate, lte: endDate },
    interaction_type: { in: ["recommendation_viewed", "product_viewed"] },
  },
})
```

2. **Clicks:**
```typescript
prisma.user_interactions.count({
  where: {
    shop_id: shopId,
    created_at: { gte: startDate, lte: endDate },
    interaction_type: { in: ["recommendation_add_to_cart", "product_added_to_cart"] },
  },
})
```

3. **Revenue:**
```typescript
prisma.purchase_attributions.aggregate({
  where: { shop_id: shopId, purchase_at: { gte: startDate, lte: endDate } },
  _sum: { total_revenue: true },
}).then(result => Number(result._sum.total_revenue) || 0)
```

4. **Customers:**
```typescript
prisma.user_sessions.groupBy({
  by: ["customer_id"],
  where: {
    shop_id: shopId,
    created_at: { gte: startDate, lte: endDate },
    customer_id: { not: null },
  },
}).then(result => result.length)
```

**Return:**
```typescript
{
  today: { recommendations, clicks, revenue, customers },
  yesterday: { recommendations, clicks, revenue, customers },
  this_week: { recommendations, clicks, revenue, customers },
  currency_code: string,
}
```

---

### 11.5 `features/dashboard/types/dashboard.types.ts`

```typescript
interface DashboardOverview {
  total_revenue: number; conversion_rate: number; total_recommendations: number;
  total_clicks: number; average_order_value: number; period: string;
  currency_code: string; money_format: string;
  revenue_change: number | null; conversion_rate_change: number | null;
  recommendations_change: number | null; clicks_change: number | null;
  aov_change: number | null; total_customers: number; customers_change: number | null;
}
interface TopProductData {
  product_id: string; title: string; revenue: number; clicks: number;
  conversion_rate: number; recommendations_shown: number;
  currency_code: string; customers: number;
}
interface RecentActivityData {
  today: ActivityMetrics; yesterday: ActivityMetrics;
  this_week: ActivityMetrics; currency_code: string;
}
interface ActivityMetrics { recommendations: number; clicks: number; revenue: number; customers: number; }
interface AttributedMetrics {
  attributed_revenue: number; attributed_refunds: number;
  net_attributed_revenue: number; attribution_rate: number;
  refund_rate: number; currency_code: string;
}
interface PerformanceMetrics {
  total_recommendations: number; total_clicks: number; conversion_rate: number;
  total_customers: number; recommendations_change: number | null;
  clicks_change: number | null; conversion_rate_change: number | null;
  customers_change: number | null;
}
interface DashboardData {
  overview: DashboardOverview; topProducts: TopProductData[];
  recentActivity: RecentActivityData; attributedMetrics: AttributedMetrics;
  performance: PerformanceMetrics;
}
```

---

## 12. Middleware -- Service Suspension

**File:** `app/middleware/serviceSuspension.ts`

### `checkServiceSuspensionMiddleware(request, shopDomain)` (line 11)

```typescript
async function checkServiceSuspensionMiddleware(
  request: LoaderFunctionArgs["request"],
  shopDomain: string,
): Promise<{
  shouldRedirect: boolean;
  redirectUrl?: string;
  suspensionStatus?: any;
}>
```

Checks suspension and determines if redirect is needed. Redirects to `/app/billing` for billing-related suspensions.

### `checkServiceSuspension(shopId: string)` (line 65)

**Redis:** Uses `cacheService.getOrSet(cacheKey, fallbackFn, 300)` with key `suspension:{shopId}` and 5-minute TTL.

**Prisma Queries (inside cache fallback, line 75-98):**
```typescript
Promise.all([
  prisma.shops.findUnique({
    where: { id: shopId },
    select: { id: true, is_active: true, suspended_at: true, suspension_reason: true },
  }),
  prisma.shop_subscriptions.findFirst({
    where: { shop_id: shopId, is_active: true },
    include: {
      billing_cycles: {
        where: { status: "ACTIVE" },
        orderBy: { cycle_number: "desc" },
        take: 1,
      },
    },
  }),
])
```

**Return structure:**
```typescript
{
  isSuspended: boolean,
  reason: string,
  requiresBillingSetup: boolean,
  requiresCapIncrease?: boolean,
  trialCompleted: boolean,
  subscriptionActive: boolean,
  subscriptionPending: boolean,
}
```

**Status logic:**
| Condition | `isSuspended` | `reason` |
|-----------|--------------|----------|
| Shop/subscription not found | `true` | `"shop_not_found"` |
| `shop.is_active === false` | `true` | `shop.suspension_reason` |
| `status === "TRIAL"` | `false` | `"trial_active"` |
| `status === "TRIAL_COMPLETED"` | `true` | `"trial_completed_awaiting_setup"` |
| `status === "PENDING_APPROVAL"` | `true` | `"subscription_pending_approval"` |
| `status === "ACTIVE"` | `false` | `"active"` |
| Default (SUSPENDED/CANCELLED) | `true` | `"subscription_{status}"` |

### `checkServiceSuspensionByDomain(shopDomain: string)` (line 208)

**Prisma Query (line 212-215):**
```typescript
prisma.shops.findUnique({
  where: { shop_domain: shopDomain },
  select: { id: true },
})
```

Then delegates to `checkServiceSuspension(shop.id)`.

### `invalidateSuspensionCache(shopId: string)` (line 243)

**Redis:** Deletes key `suspension:{shopId}`.

---

## 13. Known Bugs & Issues

### Critical

1. **`services/subscription.service.ts` line 6** -- References `prisma.billing_plans` which does not exist in the Prisma schema. Will throw `PrismaClientValidationError` at runtime.

2. **`services/shop.service.ts` line 132** -- `getShopSubscription` queries `shop_subscriptions` with `where: { shop_domain: shopDomain, status: "ACTIVE" }`. The `shop_subscriptions` model does NOT have a `shop_domain` field. Will throw at runtime.

3. **`api.billing.status.tsx` line 22** -- References `prisma.billing_plans.findFirst(...)` which does not exist in the Prisma schema. This entire route will fail.

### Moderate

4. **`services/billing.service.ts` line 297** -- `getBillingSummary` returns `progress_percentage: 0` and `usage_percentage: 0` and `days_remaining: 0` -- all hardcoded, never calculated from actual data.

5. **`services/billing.service.ts` line 204** -- `getCurrentCycleMetrics` hardcodes commission rate at `0.03` (3%) rather than reading from `pricing_tiers.commission_rate`.

6. **`api.billing.setup.tsx` line 218** -- Performs two separate `prisma.shop_subscriptions.update` calls on the same record (lines 215-223 and 226-235). This is not atomic and could leave the record in an inconsistent state if the second update fails.

7. **`api.billing.increase-cap.tsx` line 14** -- Default spending limit is `body.spendingLimit || 1000.0`, meaning a falsy value of `0` would default to `1000`. Should use `body.spendingLimit ?? 1000.0`.

### Minor

8. **`features/dashboard/services/products.service.ts` line 137** -- `revenue` is always hardcoded to `0` with comment "No reliable per-product attribution yet".

9. **`features/dashboard/services/revenue.service.ts` line 199-200** -- `attributed_refunds` and `refund_rate` are hardcoded to `0`.

10. **`webhooks.billing.approaching_cap.tsx`** -- No actual business logic implemented beyond logging. Comment says "Add your warning logic here" (line 43-46).

11. **`api.billing.cancel.tsx` line 108** -- Resets status to `"TRIAL_COMPLETED"` and `is_active: true` after cancellation. This allows cancelled users to remain active while in a `TRIAL_COMPLETED` state, which may not be the intended behavior.

12. **Multiple webhook routes** -- Use `console.error` with emoji characters instead of the `logger` utility (e.g., `webhooks.products.delete.tsx` line 31, `webhooks.collections.create.tsx` line 31).
