# BetterBundle — Complete System Workflow Documentation

> Generated for unit test planning. Maps every user flow, service, API, consumer, and data pipeline.

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [User-Facing Flows](#2-user-facing-flows)
3. [Remix App — Routes, Services, Webhooks](#3-remix-app)
4. [Python Worker — APIs, Consumers, Services](#4-python-worker)
5. [ML & Recommendation Pipeline](#5-ml--recommendation-pipeline)
6. [Billing Pipeline (End-to-End)](#6-billing-pipeline)
7. [Data Pipeline (Collection → Features)](#7-data-pipeline)
8. [Kafka Topic Map](#8-kafka-topic-map)
9. [Database Schema Summary](#9-database-schema-summary)
10. [Shopify Extensions](#10-shopify-extensions)
11. [Infrastructure](#11-infrastructure)

---

## 1. System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    SHOPIFY STOREFRONT                            │
│  Extensions: Atlas(pixel) Phoenix(theme) Mercury(checkout)      │
│              Apollo(post-purchase) Venus(customer-account)       │
└──────────┬────────────────────────────┬─────────────────────────┘
           │ Webhooks                   │ Extension API calls
           ▼                            ▼
┌─────────────────────┐      ┌─────────────────────────┐
│   REMIX APP (3000)  │      │  PYTHON WORKER (8000)   │
│   - Admin UI        │      │  - REST API             │
│   - Webhook handler │      │  - Kafka consumers (7)  │
│   - Billing setup   │─────>│  - ML pipeline          │
│   - Shopify OAuth   │Kafka │  - Billing engine       │
└─────────┬───────────┘      └───────────┬─────────────┘
          │                              │
    ┌─────┴─────┬──────────┬─────────────┤
    ▼           ▼          ▼             ▼
┌────────┐ ┌───────┐ ┌─────────┐ ┌──────────┐
│Postgres│ │ Redis │ │  Kafka  │ │  Gorse   │
│  (17)  │ │(7.2)  │ │ (KRaft) │ │  (ML)    │
└────────┘ └───────┘ └─────────┘ └──────────┘
```

### Services Summary

| Service | Port | Purpose |
|---------|------|---------|
| Remix App | 3000 | Shopify embedded admin app, webhook receiver |
| Python Worker | 8000 | FastAPI backend, Kafka consumers, ML, billing |
| PostgreSQL | 5432 | Primary database (37+ tables) |
| Redis | 6379 | Cache, sessions, recommendation cache |
| Kafka | 9092 | Event streaming (11 topics, 7 consumers) |
| Gorse | 8086/8088 | Recommendation engine (collaborative filtering) |
| Django Admin | 8003 | Backoffice admin panel |
| Nginx Proxy | 80/443 | Reverse proxy, SSL termination |
| Grafana | 3001 | Monitoring dashboards |
| Loki | 3100 | Log aggregation |

---

## 2. User-Facing Flows

### Flow 1: Merchant Installs App

```
1. Merchant clicks "Install" on Shopify App Store
2. → /auth/login (OAuth initiation)
3. → /auth/* (OAuth callback, session created)
4. → /app (layout loads, checks onboarding status)
5. → /app/onboarding (if not onboarded)
6. Merchant completes onboarding wizard:
   a. createShopAndSetOnboardingCompleted() → upserts shops record
   b. createShopSubscription() → creates shop_subscriptions (TRIAL)
   c. markOnboardingCompleted() → shops.onboarding_completed = true
   d. activateAtlasWebPixel() → Shopify GraphQL webPixelCreate
   e. Kafka → data-collection-jobs: "initial_data_collection"
7. → /app/overview (main dashboard)
```

### Flow 2: Customer Browses Store (Extension Tracking)

```
1. Atlas web pixel loads on every storefront page
2. Captures: page_view, product_view, add_to_cart, checkout_start
3. → POST /api/auth/generate-token (JWT for shop)
4. → POST /api/session/get-or-create-session (creates UserSession)
5. → POST /api/interaction/track (creates UserInteraction per event)
6. Phoenix/Mercury/Venus show recommendations:
   → POST /api/recommendation/get (fetches from Gorse + FBT + fallbacks)
7. Customer interactions tracked → Kafka → customer-linking-jobs
```

### Flow 3: Order Placed → Attribution → Commission

```
1. Customer completes purchase on Shopify
2. Shopify fires orders/paid webhook
3. → Remix webhook handler → Kafka [shopify-events]: "order_paid"
4. → DataCollectionConsumer: fetches order via GraphQL, stores raw
5. → Kafka [normalization-jobs]: "normalize_data"
6. → NormalizationConsumer: normalizes into order_data + line_item_data
7. → Kafka [purchase-attribution-jobs]: "purchase_ready_for_attribution"
8. → PurchaseAttributionConsumer:
   a. Loads OrderData + LineItemData
   b. Checks for tracking data (line item properties, metafields, interactions)
   c. If tracking found → BillingServiceV2.process_purchase_attribution()
   d. Creates PurchaseAttribution record
   e. Creates CommissionRecord (TRIAL or PAID phase)
   f. If PAID + commission_charged > 0 → Kafka [shopify-usage-events]: "record_usage"
9. → ShopifyUsageConsumer:
   a. CommissionServiceV2.record_commission_to_shopify()
   b. Shopify GraphQL appUsageRecordCreate
   c. Commission status → RECORDED
   d. BillingCycle.usage_amount incremented atomically
```

### Flow 4: Trial → Paid Transition

```
1. Trial commissions accumulate in commission_records (billing_phase=TRIAL)
2. Merchant visits /app/billing
3. BillingService.getBillingState():
   - Aggregates trial revenue from commission_records
   - Compares against pricing_tier.trial_threshold_amount
4. If revenue >= threshold → UI shows "trial_completed"
5. Merchant enters monthly cap → POST /api/billing/setup:
   a. Validates trial threshold reached
   b. Shopify GraphQL appSubscriptionCreate (usage-based pricing)
   c. Returns confirmationUrl
6. Merchant approves charge in Shopify
7. Shopify fires APP_SUBSCRIPTIONS_UPDATE webhook (status: ACTIVE)
8. → webhooks.billing.subscription_update handler:
   a. Updates shop_subscriptions → PAID/ACTIVE
   b. Creates billing_cycles (cycle_number=1, 30 days)
   c. Reactivates shop
```

### Flow 5: Cap Hit → Increase → Reprocess

```
1. Commission earned but remaining_cap <= 0
2. CommissionServiceV2._calculate_charge_amounts():
   - commission_charged = 0, commission_overflow = full amount
   - charge_type = REJECTED, status = REJECTED
3. Shop subscription set to SUSPENDED
4. Merchant visits /app/billing → sees rejected amount
5. POST /api/billing/increase-cap:
   a. Shopify GraphQL appSubscriptionLineItemUpdate (new cap)
   b. Updates billing_cycles.current_cap_amount
   c. Kafka [shopify-usage-events]: "cap_increase"
6. → ShopifyUsageConsumer._handle_cap_increase():
   a. Loads REJECTED + PENDING commissions for the cycle
   b. Recalculates charge against new remaining cap
   c. Re-records to Shopify via appUsageRecordCreate
   d. Reactivates subscription SUSPENDED → ACTIVE
```

### Flow 6: Cancellation

```
1. Merchant clicks cancel → POST /api/billing/cancel:
   a. Shopify GraphQL appSubscriptionCancel
   b. Sets status = TRIAL_COMPLETED, is_active = true
2. Simultaneously, Shopify fires APP_SUBSCRIPTIONS_UPDATE (CANCELLED):
   a. Sets status = CANCELLED, is_active = false
   b. Suspends shop (suspension_reason = subscription_cancelled)
3. RACE CONDITION: Final state depends on execution order
```

### Flow 7: Recommendation Request (Storefront)

```
1. Extension calls POST /api/recommendation/get
2. JWT validated → shop resolved
3. Context determined (product_page, homepage, cart, checkout, collection)
4. Pipeline:
   a. Category detection (from product_type or collection)
   b. User ID resolution (customer_id, client_id, session)
   c. Exclusion computation (purchased products, cart items, time decay)
   d. Cache check (Redis, currently disabled)
   e. Smart selection (probe recommendation types in priority order)
   f. Fetch from Gorse API (or FBT for checkout)
   g. Enrich with ProductData (title, images, price, variants)
   h. Filter unavailable/excluded products
   i. Return enriched recommendations
5. Smart selection priority by context:
   - product_page: item_neighbors → FBT → user_neighbors → user_recs → popular
   - homepage: recently_viewed → user_recs → popular → latest
   - cart: item_neighbors → FBT → user_recs → popular
   - checkout: FBT only
   - collection: item_neighbors → popular_category → user_recs → popular
```

---

## 3. Remix App

### Routes

#### Pages (GET loaders)

| Route | URL | Auth | Purpose |
|-------|-----|------|---------|
| `_index` | `/` | None | Landing page |
| `auth.login` | `/auth/login` | None | Shopify OAuth login |
| `auth.$` | `/auth/*` | OAuth | OAuth callback |
| `app` | `/app` (layout) | `authenticate.admin` | Main layout with nav |
| `app._index` | `/app` | Inherited | Redirects to overview or onboarding |
| `app.onboarding` | `/app/onboarding` | Inherited | Onboarding wizard |
| `app.overview` | `/app/overview` | Inherited | Main dashboard with KPIs |
| `app.dashboard` | `/app/dashboard` (layout) | Inherited | Dashboard with date picker |
| `app.dashboard.revenue` | `/app/dashboard/revenue` | Inherited | Revenue metrics tab |
| `app.dashboard.performance` | `/app/dashboard/performance` | Inherited | Conversion metrics tab |
| `app.dashboard.products` | `/app/dashboard/products` | Inherited | Product-level analytics |
| `app.dashboard.activity` | `/app/dashboard/activity` | Inherited | Activity timeline |
| `app.billing` | `/app/billing` (layout) | Inherited | Billing status + tabs |
| `app.billing.cycles` | `/app/billing/cycles` | Inherited | Billing cycles list |
| `app.billing.invoices` | `/app/billing/invoices` | Inherited | Usage records / invoices |
| `app.extensions` | `/app/extensions` | Inherited | Extension manager |
| `app.help` | `/app/help` | Inherited | Help page |
| `privacy-policy` | `/privacy-policy` | None | Privacy policy |

#### API Endpoints (POST actions)

| Route | URL | Method | Purpose |
|-------|-----|--------|---------|
| `api.billing.setup` | `/api/billing/setup` | POST | Create Shopify usage subscription |
| `api.billing.activate` | `/api/billing/activate` | POST | Manual subscription activation |
| `api.billing.cancel` | `/api/billing/cancel` | POST | Cancel subscription |
| `api.billing.increase-cap` | `/api/billing/increase-cap` | POST | Increase billing cap |
| `api.billing.status` | `/api/billing/status` | GET | Billing status (BROKEN: uses deleted model) |
| `api.sign-changeset` | `/api/sign-changeset` | POST | Sign JWT for extensions |

#### Webhook Handlers

| Route | Shopify Topic | Kafka Topic | Event Type |
|-------|---------------|-------------|------------|
| `webhooks.orders.paid` | ORDERS_PAID | shopify-events | order_paid |
| `webhooks.orders.updated` | ORDERS_UPDATED | shopify-events | order_updated |
| `webhooks.products.create` | PRODUCTS_CREATE | shopify-events | product_created |
| `webhooks.products.update` | PRODUCTS_UPDATE | shopify-events | product_updated |
| `webhooks.products.delete` | PRODUCTS_DELETE | shopify-events | product_deleted |
| `webhooks.collections.create` | COLLECTIONS_CREATE | shopify-events | collection_created |
| `webhooks.collections.update` | COLLECTIONS_UPDATE | shopify-events | collection_updated |
| `webhooks.collections.delete` | COLLECTIONS_DELETE | shopify-events | collection_deleted |
| `webhooks.customers.create` | CUSTOMERS_CREATE | shopify-events | customer_created |
| `webhooks.customers.update` | CUSTOMERS_UPDATE | shopify-events | customer_updated |
| `webhooks.refunds.create` | REFUNDS_CREATE | shopify-events | refund_created |
| `webhooks.inventory_levels.update` | INVENTORY_LEVELS_UPDATE | shopify-events | inventory_updated |
| `webhooks.billing.subscription_update` | APP_SUBSCRIPTIONS_UPDATE | (direct DB) | Activates/cancels subscription |
| `webhooks.billing.approaching_cap` | APP_SUBSCRIPTIONS_APPROACHING_CAPPED_AMOUNT | (log only) | Cap warning |
| `webhooks.billing.billing_failed` | (billing failed) | (direct DB) | BROKEN: uses deleted model |
| `webhooks.billing.billing_success` | (billing success) | (direct DB) | BROKEN: uses deleted model |
| `webhooks.app.uninstalled` | APP_UNINSTALLED | access-control | App uninstall cleanup |
| `webhooks.gdpr.*` | GDPR compliance | (log only) | Data request/redact |

### Services

| Service | File | Key Functions |
|---------|------|---------------|
| ShopService | `services/shop.service.ts` | getShop, getShopInfoFromShopify, createShopAndSetOnboardingCompleted, activateAtlasWebPixel, deactivateShopBilling |
| BillingService (root) | `services/billing.service.ts` | getTrialRevenueData, getUsageRevenueData, getCurrentCycleMetrics, getBillingSummary, createShopSubscription, activateSubscription, increaseBillingCycleCap, reactivateShopIfSuspended |
| BillingService (feature) | `features/billing/services/billing.service.ts` | getBillingState, getTrialRevenue, getShopifySubscriptionStatus, getCommissionBreakdown |
| PricingTierService | `services/pricing-tier.service.ts` | getPricingTierConfig |
| OnboardingService | `features/onboarding/services/onboarding.service.ts` | getOnboardingData, completeOnboarding |
| OverviewService | `features/overview/services/overview.service.ts` | getOverviewData |
| KafkaProducerService | `services/kafka/kafka-producer.service.ts` | publishShopifyEvent, publishDataJobEvent, publishShopifyUsageEvent, publishAccessControlEvent |
| RedisService | `services/redis.service.ts` | get, set, del, getOrSet |
| SuspensionMiddleware | `middleware/serviceSuspension.ts` | checkServiceSuspension, invalidateSuspensionCache |

---

## 4. Python Worker

### API Endpoints

| Prefix | File | Endpoints |
|--------|------|-----------|
| `/api/v1/recommendations` | `api/v1/recommendations.py` | POST / — Main recommendation endpoint (JWT auth) |
| `/api/v1/gorse` | `api/v1/unified_gorse.py` | POST /sync, GET /status/{shop_id}, POST /train/{shop_id} |
| `/api/v1/data-collection` | `api/v1/data_collection.py` | POST /trigger, GET /status/{shop_id} |
| `/api/v1/attribution` | `api/v1/attribution_backfill.py` | POST /retrigger, POST /shop-wide, GET /status/{shop_id} |
| `/api/v1/customer-linking` | `api/v1/customer_linking.py` | POST /shops/{id}/backfill, GET /shops/{id}/stats |
| `/api/v1/fbt` | `api/v1/fbt_status.py` | GET /status/{shop_id}, POST /train/{shop_id}, GET /test/{shop_id} |
| `/api/v1/record-matching` | `api/v1/record_matching.py` | GET /shopify-usage-records/{shop_id} |
| `/api/billing` | `domains/billing/api/billing_api.py` | POST /process, GET /status, POST /shop/{id}/process, POST /shop/{id}/retrigger-commissions, POST /shop/reprocess-rejected-commissions |
| `/api/v1/auth` | `api/v1/auth.py` | POST /shop-token, POST /validate-token, POST /refresh-token, GET /token-info |
| `/api/auth` | `routes/auth_routes.py` | POST /generate-token, POST /refresh-token |
| `/api/session` | `routes/session_routes.py` | POST /get-or-create-session, POST /get-session-and-recommendations |
| `/api/interaction` | `routes/interaction_routes.py` | POST /track |
| `/api/recommendation` | `routes/recommendation_routes.py` | POST /get, POST /get-with-session |
| `/logs` | `api/v1/logs.py` | POST /logs (forward to Loki) |
| `/health` | `main.py` | GET /health, GET /health/redis |

### Kafka Consumers (7)

| Consumer | Topic(s) | Group ID | Event Types |
|----------|----------|----------|-------------|
| DataCollectionConsumer | shopify-events, data-collection-jobs | data-collection-processors | order_paid, product_updated, data_collection, etc. |
| NormalizationConsumer | normalization-jobs | normalization-processors | normalize_data |
| FeatureComputationConsumer | feature-computation-jobs | feature-computation-processors | features_ready=False |
| CustomerLinkingConsumer | customer-linking-jobs | customer-linking-processors | customer_linking, cross_session_linking, backfill_interactions |
| PurchaseAttributionConsumer | purchase-attribution-jobs | purchase-attribution-processors | purchase_ready_for_attribution |
| BillingConsumer | billing-events | billing-processors | (STUB — logs only, no processing) |
| ShopifyUsageConsumer | shopify-usage-events | shopify-usage-processors | record_usage, cap_increase, reprocess_rejected_commissions |

### Domain Services

| Domain | Service | Purpose |
|--------|---------|---------|
| **shopify** | ShopifyDataCollectionService | Fetches data from Shopify GraphQL API |
| **shopify** | NormalizationService | Normalizes raw data into canonical models |
| **ml** | FeatureEngineeringService | Orchestrates 8 feature generators |
| **ml** | UnifiedGorseService | Syncs features to Gorse, triggers training |
| **billing** | BillingServiceV2 | Processes purchase attribution, routes to trial/paid |
| **billing** | CommissionServiceV2 | Creates commission records, records to Shopify |
| **billing** | ShopifyUsageBillingServiceV2 | Shopify GraphQL appUsageRecordCreate |
| **billing** | BillingSchedulerService | Monthly billing processing |
| **analytics** | UnifiedSessionService | Session create/update/expire |
| **analytics** | AnalyticsTrackingService | User interaction recording |
| **analytics** | CrossSessionLinkingService | Links sessions across devices |

---

## 5. ML & Recommendation Pipeline

### Three-Layer FBT Architecture

```
Layer 1: FP-Growth (association rules)
  - mlxtend library, min_support=0.01, min_confidence=0.30, min_lift=1.5
  - 90-day transaction window, recency weighting
  - Cached in Redis (24h TTL)

Layer 2: Business Rules Filter
  - Price range (20-150% of cart avg)
  - Category affinity boosting
  - Inventory filtering
  - Margin optimization

Layer 3: Product Embeddings (Word2Vec)
  - Skip-gram, 200 dimensions, window=3, 180-day history
  - Cosine similarity boosting (>0.8: 1.3x, >0.6: 1.2x, >0.4: 1.1x)
```

### Feature Generators (8)

| Generator | Input Tables | Output Table | Key Features |
|-----------|-------------|--------------|--------------|
| UserFeatureGenerator | order_data, user_interactions | user_features | lifetime_value, churn_risk, purchase_frequency |
| ProductFeatureGenerator | product_data, user_interactions, order_data | product_features | trending_momentum, engagement_quality, conversion_efficiency |
| CollectionFeatureGenerator | collection_data, user_interactions | collection_features | engagement_score, conversion_rate, popularity |
| InteractionFeatureGenerator | user_interactions | interaction_features | customer_product_affinity, purchase_intent, loyalty |
| SessionFeatureGenerator | user_sessions, user_interactions | session_features | funnel_stage, browse_depth, intent_score |
| ProductPairFeatureGenerator | order_data, line_item_data | product_pair_features | co_purchase_strength, cross_sell_potential |
| SearchProductFeatureGenerator | user_interactions | search_product_features | search_conversion_rate, relevance_score |
| CustomerBehaviorFeatureGenerator | customer_data, order_data | customer_behavior_features | lifecycle_stage, churn_risk |

### Gorse Integration

- **5 Transformers**: User, Item, Feedback, Collection, Interaction
- **28+ feedback types** with confidence weights
- **60-day temporal decay** half-life
- **Multi-tenancy**: All IDs prefixed `shop_{shop_id}_{entity_id}`
- **Ranking model**: Factorization Machines (64 factors, 40 epochs)

### Recommendation Contexts & Priority Chains

| Context | Priority Chain |
|---------|---------------|
| product_page | item_neighbors → FBT → user_neighbors → user_recs → popular_category |
| homepage | recently_viewed → user_recs → popular → latest |
| cart | item_neighbors → FBT → user_recs → popular |
| checkout | FBT only |
| collection | item_neighbors → popular_category → user_recs → popular |

---

## 6. Billing Pipeline

### State Machine

```
TRIAL → PENDING_APPROVAL → (Shopify charge created) → SUSPENDED
  → (merchant approves) → ACTIVE → (cap hit) → SUSPENDED
  → (cap increased) → ACTIVE
  → (cancelled) → CANCELLED / TRIAL_COMPLETED
```

### Commission Flow

```
PurchaseAttribution created
  ↓
CommissionServiceV2.create_commission_record()
  ↓
Calculate: commission_earned = total_revenue × commission_rate
  ↓
Check cap: remaining_cap = current_cap_amount - usage_amount
  ↓
┌─ remaining_cap > 0 ──→ charge = min(earned, remaining) ──→ PENDING
│                         overflow = earned - charge
│                         type = FULL or PARTIAL
│
└─ remaining_cap ≤ 0 ──→ charge = 0, overflow = earned ──→ REJECTED
                          type = REJECTED
  ↓ (if PENDING + charged > 0)
Kafka [shopify-usage-events]: "record_usage"
  ↓
ShopifyUsageConsumer → record_commission_to_shopify()
  ↓
Shopify GraphQL: appUsageRecordCreate
  ↓
┌─ Success ──→ status = RECORDED, billing_cycle.usage_amount += charged
└─ Cap exceeded ──→ status = REJECTED, shop SUSPENDED
```

### Known Billing Bugs

| # | Bug | Impact |
|---|-----|--------|
| 1 | cap_increase handler signature mismatch (TypeError) | Rejected commissions never reprocessed |
| 2 | Commission creation errors swallowed (no raise) | Attribution saved, commission lost |
| 3 | No billing cycle rotation after 30 days | Billing breaks after first cycle |
| 4 | purchase_attribution_repository never initialized | Trial logging crashes |
| 5 | Inconsistent trial revenue calculation (2 methods) | Trial completes at wrong threshold |
| 6 | Kafka publish failure → commission PENDING forever | No retry mechanism |
| 7 | Shopify recording failure → commission rolled back | Data lost, no recovery |
| 8 | Orders without session_id skip billing | Attributed revenue not billed |
| 9 | Webhook finds wrong subscription (no is_active filter) | Activation on wrong record |
| 10 | Cancellation race condition (API vs webhook) | Unpredictable final state |
| 11 | 4 routes reference deleted models (billing_plans, billing_invoices) | Runtime crashes |
| 12 | shop.service queries non-existent fields | Runtime crashes |
| 13 | Manual activation doesn't create billing cycle | Commissions have no cycle |
| 14 | returnUrl uses full domain instead of store handle | Broken redirect after approval |
| 15 | EventPublisher leak (created per commission, never closed) | Connection exhaustion |
| 16 | billing_consumer is a stub | Billing events silently dropped |
| 17 | Hardcoded 3% commission in dashboard | Wrong numbers if rate changes |

---

## 7. Data Pipeline

```
Shopify Webhook
  │
  ▼
Remix webhook handler
  │ publishes to Kafka
  ▼
[shopify-events] ──→ DataCollectionConsumer
  │                    │
  │ (for new entities)  │ (fetches full data via GraphQL)
  │                    ▼
  │              Raw tables (raw_orders, raw_products, etc.)
  │                    │
  │                    ▼ publishes to Kafka
  │              [normalization-jobs]
  │                    │
  │                    ▼
  │              NormalizationConsumer
  │                    │
  │                    ▼
  │              Normalized tables (order_data, product_data, etc.)
  │                    │
  │              ┌─────┴─────┐
  │              ▼           ▼
  │   [feature-computation] [purchase-attribution-jobs]
  │              │           │
  │              ▼           ▼
  │   FeatureComputation  PurchaseAttribution
  │   Consumer            Consumer
  │              │           │
  │              ▼           ▼
  │   8 Feature tables    purchase_attributions
  │              │        + commission_records
  │              ▼           │
  │   Gorse sync &          ▼
  │   training         [shopify-usage-events]
  │                          │
  │                          ▼
  │                    ShopifyUsageConsumer
  │                    → appUsageRecordCreate
  │
  ▼ (for orders with FBT retraining)
FPGrowthEngine.train_fp_growth_model()
```

---

## 8. Kafka Topic Map

| Topic | Partitions | Retention | Producers | Consumers |
|-------|-----------|-----------|-----------|-----------|
| `shopify-events` | 6 | 7 days | Remix webhooks | DataCollectionConsumer |
| `data-collection-jobs` | 4 | 3 days | Remix onboarding, Python | DataCollectionConsumer |
| `normalization-jobs` | 4 | 3 days | DataCollectionConsumer | NormalizationConsumer |
| `feature-computation-jobs` | 2 | 1 day | NormalizationConsumer, CustomerLinking | FeatureComputationConsumer |
| `customer-linking-jobs` | 4 | 3 days | InteractionTracking | CustomerLinkingConsumer |
| `purchase-attribution-jobs` | 6 | 3 days | NormalizationConsumer, API backfill | PurchaseAttributionConsumer |
| `shopify-usage-events` | 4 | 3 days | CommissionServiceV2, Remix cap-increase | ShopifyUsageConsumer |
| `billing-events` | 4 | 3 days | CommissionServiceV2 | BillingConsumer (STUB) |
| `access-control` | 6 | 7 days | Remix app.uninstalled | (no consumer) |
| `ml-training` | 2 | 1 day | (event publisher) | (no dedicated consumer) |
| `analytics-events` | -- | -- | (event publisher) | (no dedicated consumer) |

---

## 9. Database Schema Summary

### Core Tables (37+)

**Shop & Config:** shops, sessions, subscription_plans, pricing_tiers, shop_subscriptions

**Billing:** billing_cycles, commission_records, purchase_attributions

**Shopify Data:** product_data, order_data, line_item_data, customer_data, collection_data

**Raw Data:** raw_orders, raw_products, raw_customers, raw_collections

**Analytics:** user_sessions, user_interactions, user_identity_links

**ML Features:** user_features, product_features, collection_features, interaction_features, session_features, product_pair_features, search_product_features, customer_behavior_features

### Key Enums

| Enum | Values |
|------|--------|
| subscription_status | TRIAL, PENDING_APPROVAL, TRIAL_COMPLETED, ACTIVE, SUSPENDED, CANCELLED, EXPIRED |
| billing_phase | TRIAL, PAID |
| commission_status | TRIAL_PENDING, TRIAL_COMPLETED, PENDING, RECORDED, INVOICED, REJECTED, FAILED, CAPPED |
| charge_type | FULL, PARTIAL, OVERFLOW_ONLY, TRIAL, REJECTED |
| billing_cycle_status | ACTIVE, COMPLETED, CANCELLED, SUSPENDED |

---

## 10. Shopify Extensions

| Extension | Type | Purpose | Storefront Location |
|-----------|------|---------|-------------------|
| **Atlas** | Web Pixel | Behavioral tracking (page views, product views, cart, checkout) | Every page (invisible) |
| **Phoenix** | Theme App Extension | Product recommendation blocks | Product page, Homepage, Cart, Collection |
| **Mercury** | Checkout UI Extension | Checkout recommendations with add-to-cart | Checkout page |
| **Apollo** | Post-Purchase Extension | Post-purchase upsell recommendations | Thank you page |
| **Venus** | Customer Account UI Extension | Personalized recommendations | Order status, Order index, Profile |

### Extension → API Flow

```
All extensions:
  1. Get JWT token via /api/auth/generate-token or /api/sign-changeset
  2. Create/get session via /api/session/get-or-create-session
  3. Fetch recommendations via /api/recommendation/get
  4. Track interactions via /api/interaction/track

Mercury (checkout) additionally:
  - Writes metafields: bb_recommendation/{extension, session_id, context, products, source}
  - These metafields become order metafields → used for attribution

Apollo (post-purchase) additionally:
  - Uses combined /api/session/get-session-and-recommendations endpoint
```

---

## 11. Infrastructure

### Docker Compose Resources (Production)

| Service | CPU | Memory | Notes |
|---------|-----|--------|-------|
| Python Worker | 2.0 | 2GB | Heaviest processing |
| Gorse | 2.0 | 2GB | ML model training |
| Remix App | 1.0 | 1GB | Frontend + webhooks |
| Kafka | 1.0 | 1GB | Event streaming |
| Django Admin | 1.0 | 1GB | Backoffice |
| PostgreSQL | 1.0 | 512MB | **Undersized** — should be 2-4GB |
| Loki | 0.5 | 512MB | Log aggregation |
| Redis | 0.5 | 256MB | Cache |
| Grafana | 0.5 | 256MB | Dashboards |
| Kafka UI | 0.5 | 256MB | Monitoring |
| Rest Proxy | 0.5 | 256MB | Kafka REST |
| Nginx | 0.5 | 256MB | Reverse proxy |
| Promtail | 0.25 | 128MB | Log forwarder |
| **Total** | **10.25** | **9.38GB** | Oracle Cloud: 4 OCPU / 24GB |

### Gorse Configuration Highlights

- Collaborative filtering: 90% recall, 200 fit epochs
- Ranking: Factorization Machines, 64 factors, 40 epochs
- Offline refresh: Every 8h
- Cache: 100K items, 4h expiry
- Feedback: 7 positive types, 7 read types, 7 negative types
- Online fallback: collaborative → item_based → user_based → popular → latest

### Shopify Scopes (Production)

```
read_custom_pixels, read_customer_data_erasure, read_customer_events,
read_customers, read_draft_orders, read_files, read_inventory,
read_metaobject_definitions, read_metaobjects, read_order_edits,
read_orders, read_pixels, read_products, read_publications,
read_returns, write_custom_pixels, write_customer_data_erasure,
write_metaobject_definitions, write_metaobjects, write_pixels,
write_returns
```
