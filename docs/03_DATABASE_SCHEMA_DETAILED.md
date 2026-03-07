# BetterBundle Database Schema - Detailed Reference

This document provides an exhaustive reference for every table, column, index, foreign key, and enum in the BetterBundle database. The schema is defined in two places:

- **Prisma schema**: `/better-bundle/prisma/schema.prisma` (Node.js/Remix app)
- **SQLAlchemy models**: `/python-worker/app/core/database/models/` (Python worker)

Both map to the same PostgreSQL database (`betterbundle`).

---

## Table of Contents

1. [Enums](#enums)
2. [shops](#table-shops)
3. [sessions](#table-sessions)
4. [order_data](#table-order_data)
5. [line_item_data](#table-line_item_data)
6. [product_data](#table-product_data)
7. [customer_data](#table-customer_data)
8. [collection_data](#table-collection_data)
9. [raw_orders](#table-raw_orders)
10. [raw_products](#table-raw_products)
11. [raw_customers](#table-raw_customers)
12. [raw_collections](#table-raw_collections)
13. [user_sessions](#table-user_sessions)
14. [user_interactions](#table-user_interactions)
15. [user_identity_links](#table-user_identity_links)
16. [purchase_attributions](#table-purchase_attributions)
17. [subscription_plans](#table-subscription_plans)
18. [pricing_tiers](#table-pricing_tiers)
19. [shop_subscriptions](#table-shop_subscriptions)
20. [billing_cycles](#table-billing_cycles)
21. [commission_records](#table-commission_records)
22. [billing_invoices](#table-billing_invoices)
23. [user_features](#table-user_features)
24. [product_features](#table-product_features)
25. [collection_features](#table-collection_features)
26. [customer_behavior_features](#table-customer_behavior_features)
27. [interaction_features](#table-interaction_features)
28. [session_features](#table-session_features)
29. [product_pair_features](#table-product_pair_features)
30. [search_product_features](#table-search_product_features)
31. [feedback (Gorse)](#table-feedback)
32. [items (Gorse)](#table-items)
33. [users (Gorse)](#table-users)

---

## Enums

### `subscription_plan_type_enum`
| Value | Description |
|-------|-------------|
| `USAGE_BASED` | Usage-based pricing |
| `TIERED` | Tiered pricing |
| `FLAT_RATE` | Flat rate pricing |
| `HYBRID` | Hybrid pricing model |

### `subscription_type_enum`
| Value | Description |
|-------|-------------|
| `TRIAL` | Trial subscription |
| `PAID` | Paid subscription |

### `subscription_status_enum`
| Value | Description |
|-------|-------------|
| `TRIAL` | Trial in progress |
| `PENDING_APPROVAL` | Awaiting approval |
| `TRIAL_COMPLETED` | Trial completed, awaiting billing setup |
| `ACTIVE` | Currently active |
| `SUSPENDED` | Temporarily suspended |
| `CANCELLED` | Cancelled by user/system |
| `EXPIRED` | Naturally expired |

### `billing_cycle_status_enum`
| Value | Description |
|-------|-------------|
| `ACTIVE` | Current billing cycle |
| `COMPLETED` | Cycle ended normally |
| `CANCELLED` | Cycle cancelled (subscription ended) |
| `SUSPENDED` | Cycle suspended |

### `billing_phase_enum`
| Value | Description |
|-------|-------------|
| `TRIAL` | Trial phase |
| `PAID` | Paid phase |

### `commission_status_enum`
| Value | Description |
|-------|-------------|
| `TRIAL_PENDING` | Tracked during trial, not charged |
| `TRIAL_COMPLETED` | Trial ended, moved to paid phase |
| `PENDING` | Ready to be sent to Shopify |
| `RECORDED` | Successfully sent to Shopify |
| `INVOICED` | Included in monthly invoice |
| `REJECTED` | Cap reached, could not charge |
| `FAILED` | Failed to send to Shopify |
| `CAPPED` | Partial charge due to cap |

### `charge_type_enum`
| Value | Description |
|-------|-------------|
| `FULL` | Full commission charged |
| `PARTIAL` | Partial due to cap |
| `OVERFLOW_ONLY` | Only overflow tracked |
| `TRIAL` | During trial period |
| `REJECTED` | Not charged |

### `invoice_status_enum`
| Value | Description |
|-------|-------------|
| `DRAFT` | Draft invoice |
| `PENDING` | Pending payment |
| `PAID` | Invoice paid |
| `OVERDUE` | Payment overdue |
| `CANCELLED` | Invoice cancelled |
| `REFUNDED` | Invoice refunded |
| `FAILED` | Payment failed |

### `trial_status_enum`
| Value | Description |
|-------|-------------|
| `ACTIVE` | Trial in progress |
| `COMPLETED` | Trial completed (threshold reached) |
| `EXPIRED` | Trial expired (time limit reached) |
| `CANCELLED` | Trial cancelled |

### `shopify_subscription_status_enum`
| Value | Description |
|-------|-------------|
| `PENDING` | Awaiting merchant approval |
| `ACTIVE` | Active and billing |
| `DECLINED` | Merchant declined |
| `CANCELLED` | Cancelled |
| `EXPIRED` | Expired |

### `adjustment_reason_enum`
| Value | Description |
|-------|-------------|
| `CAP_INCREASE` | User requested cap increase |
| `PLAN_UPGRADE` | Upgraded to higher tier |
| `ADMIN_ADJUSTMENT` | Admin adjustment |
| `PROMOTION` | Promotional adjustment |
| `DISPUTE_RESOLUTION` | Dispute resolution |

### Python-only Enums (SQLAlchemy)

#### `RawSourceType`
| Value |
|-------|
| `webhook` |
| `backfill` |

#### `RawDataFormat`
| Value |
|-------|
| `rest` |
| `graphql` |

#### `BillingPlanType` (legacy)
| Value |
|-------|
| `revenue_share` |
| `performance_tier` |
| `hybrid` |
| `usage_based` |

#### `BillingPlanStatus` (legacy)
| Value |
|-------|
| `active` |
| `inactive` |
| `suspended` |
| `trial` |

#### `BillingCycle` (legacy enum, not the table)
| Value |
|-------|
| `monthly` |
| `quarterly` |
| `annually` |

#### `ExtensionType`
| Value | Description |
|-------|-------------|
| `apollo` | Apollo extension |
| `atlas` | Atlas extension |
| `phoenix` | Phoenix extension |
| `venus` | Venus extension |
| `mercury` | Shopify Plus checkout extensions |

#### `AppBlockTarget`
| Value |
|-------|
| `customer_account_order_status_block_render` |
| `customer_account_order_index_block_render` |
| `customer_account_profile_block_render` |
| `checkout_post_purchase` |
| `theme_app_extension` |
| `web_pixel_extension` |

---

## Table: `shops`

**Description**: Core table representing Shopify stores installed with BetterBundle.

**Services that read/write**:
- **Write**: Remix app (onboarding, webhook handlers), Python worker (shop status updates, suspension)
- **Read**: Both Remix app and Python worker (all Kafka consumers, recommendation service, billing)

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | VarChar (PK) | No | `gen_random_uuid()` | Primary Key |
| `shop_domain` | VarChar(255) | No | - | Unique (`shop_domain_unique`) |
| `custom_domain` | VarChar(255) | Yes | - | - |
| `access_token` | VarChar(1000) | No | - | - |
| `plan_type` | VarChar(50) | No | `'Free'` | - |
| `currency_code` | VarChar(10) | Yes | - | - |
| `money_format` | VarChar(100) | Yes | - | - |
| `is_active` | Boolean | No | `true` | - |
| `onboarding_completed` | Boolean | No | `false` | - |
| `shopify_plus` | Boolean | No | `false` | - |
| `suspended_at` | Timestamptz(6) | Yes | - | - |
| `suspension_reason` | VarChar(255) | Yes | - | - |
| `service_impact` | VarChar(50) | Yes | - | Values: `suspended`, `active`, `limited` |
| `email` | VarChar(255) | Yes | - | - |
| `last_analysis_at` | Timestamptz(6) | Yes | - | - |
| `created_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |
| `updated_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |

**Indexes**:
| Name | Columns | Unique |
|------|---------|--------|
| `shop_domain_unique` | `shop_domain` | Yes |
| `ix_shops_is_active` | `is_active` | No |
| `ix_shops_last_analysis_at` | `last_analysis_at` | No |
| `ix_shops_plan_type` | `plan_type` | No |
| `ix_shops_shop_domain` | `shop_domain` | No |
| `ix_shops_shopify_plus` | `shopify_plus` | No |

**Relationships (has many)**:
`collection_data`, `collection_features`, `commission_records`, `customer_behavior_features`, `customer_data`, `interaction_features`, `order_data`, `product_data`, `product_features`, `product_pair_features`, `purchase_attributions`, `raw_collections`, `raw_customers`, `raw_orders`, `raw_products`, `search_product_features`, `session_features`, `shop_subscriptions`, `user_features`, `user_identity_links`, `user_interactions`, `user_sessions`

---

## Table: `sessions`

**Description**: Shopify app sessions for Remix authentication. Uses camelCase column names for Remix/Shopify compatibility.

**Services that read/write**:
- **Write**: Remix app (authentication flow)
- **Read**: Remix app (session validation)

| Column (DB name) | Type | Nullable | Default | Constraints |
|-------------------|------|----------|---------|-------------|
| `id` | VarChar (PK) | No | - | Primary Key |
| `shop` | VarChar | No | - | - |
| `state` | VarChar | No | - | - |
| `isOnline` | Boolean | No | - | - |
| `scope` | VarChar(500) | Yes | - | - |
| `expires` | Timestamptz(6) | Yes | - | - |
| `accessToken` | VarChar(1000) | No | - | - |
| `userId` | BigInt | Yes | - | - |
| `firstName` | VarChar(100) | Yes | - | - |
| `lastName` | VarChar(100) | Yes | - | - |
| `email` | VarChar(255) | Yes | - | - |
| `accountOwner` | Boolean | No | - | - |
| `locale` | VarChar(10) | Yes | - | - |
| `collaborator` | Boolean | Yes | - | - |
| `emailVerified` | Boolean | Yes | - | - |
| `createdAt` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |
| `updatedAt` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |

**Indexes**:
| Name | Columns | Unique |
|------|---------|--------|
| `ix_sessions_expires` | `expires` | No |
| `ix_sessions_shop` | `shop` | No |

---

## Table: `order_data`

**Description**: Normalized Shopify order data for analytics and ML.

**Services that read/write**:
- **Write**: Python worker (data collection consumer, normalization consumer)
- **Read**: Python worker (purchase attribution consumer, feature computation, billing), Remix app (dashboard, analytics)

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | VarChar (PK) | No | `gen_random_uuid()` | Primary Key |
| `shop_id` | VarChar | No | - | FK -> `shops.id` |
| `order_id` | VarChar | No | - | - |
| `order_name` | VarChar(100) | Yes | - | - |
| `customer_id` | VarChar(100) | Yes | - | - |
| `customer_phone` | VarChar(50) | Yes | - | - |
| `customer_display_name` | VarChar(255) | Yes | - | - |
| `customer_state` | VarChar(50) | Yes | - | - |
| `customer_verified_email` | Boolean | Yes | `false` | - |
| `customer_default_address` | Json | Yes | `{}` | - |
| `total_amount` | Float | No | `0.0` | - |
| `subtotal_amount` | Float | Yes | `0.0` | - |
| `total_tax_amount` | Float | Yes | `0.0` | - |
| `total_shipping_amount` | Float | Yes | `0.0` | - |
| `total_refunded_amount` | Float | Yes | `0.0` | - |
| `total_outstanding_amount` | Float | Yes | `0.0` | - |
| `order_date` | Timestamptz(6) | No | - | - |
| `processed_at` | Timestamptz(6) | Yes | - | - |
| `cancelled_at` | Timestamptz(6) | Yes | - | - |
| `cancel_reason` | VarChar(500) | Yes | `''` | - |
| `order_locale` | VarChar(10) | Yes | `'en'` | - |
| `currency_code` | VarChar(10) | Yes | `'USD'` | - |
| `presentment_currency_code` | VarChar(10) | Yes | `'USD'` | - |
| `confirmed` | Boolean | No | `false` | - |
| `test` | Boolean | No | `false` | - |
| `financial_status` | VarChar(50) | Yes | - | - |
| `fulfillment_status` | VarChar(50) | Yes | - | - |
| `order_status` | VarChar(50) | Yes | - | - |
| `tags` | Json | Yes | `[]` | - |
| `note` | Text | Yes | `''` | - |
| `note_attributes` | Json | Yes | `[]` | - |
| `shipping_address` | Json | Yes | `{}` | - |
| `billing_address` | Json | Yes | `{}` | - |
| `discount_applications` | Json | Yes | `[]` | - |
| `metafields` | Json | Yes | `[]` | - |
| `fulfillments` | Json | Yes | `[]` | - |
| `transactions` | Json | Yes | `[]` | - |
| `extras` | Json | Yes | `{}` | - |
| `created_at` | Timestamptz(6) | Yes | - | - |
| `updated_at` | Timestamptz(6) | Yes | - | - |

**Foreign Keys**:
| Column | References | On Delete | On Update |
|--------|-----------|-----------|-----------|
| `shop_id` | `shops.id` | NoAction | NoAction |

**Indexes**:
| Name | Columns | Unique |
|------|---------|--------|
| `ix_order_data_created_at` | `created_at` | No |
| `ix_order_data_currency_code` | `currency_code` | No |
| `ix_order_data_customer_id` | `customer_id` | No |
| `ix_order_data_customer_state` | `customer_state` | No |
| `ix_order_data_financial_status` | `financial_status` | No |
| `ix_order_data_fulfillment_status` | `fulfillment_status` | No |
| `ix_order_data_order_date` | `order_date` | No |
| `ix_order_data_order_id` | `order_id` | No |
| `ix_order_data_order_status` | `order_status` | No |
| `ix_order_data_shop_id` | `shop_id` | No |
| `ix_order_data_total_amount` | `total_amount` | No |
| `ix_order_data_updated_at` | `updated_at` | No |

---

## Table: `line_item_data`

**Description**: Individual line items belonging to orders.

**Services that read/write**:
- **Write**: Python worker (normalization consumer)
- **Read**: Python worker (purchase attribution consumer, feature computation)

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | VarChar (PK) | No | `gen_random_uuid()` | Primary Key |
| `order_id` | VarChar | No | - | FK -> `order_data.id` |
| `product_id` | VarChar | Yes | - | - |
| `variant_id` | VarChar | Yes | - | - |
| `title` | VarChar | Yes | - | - |
| `quantity` | Int | No | - | - |
| `price` | Float | No | - | - |
| `original_unit_price` | Float | Yes | - | - |
| `discounted_unit_price` | Float | Yes | - | - |
| `currency_code` | VarChar(10) | Yes | - | - |
| `variant_data` | Json | Yes | `{}` | - |
| `properties` | Json | Yes | `{}` | - |
| `created_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |
| `updated_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |

**Foreign Keys**:
| Column | References | On Delete | On Update |
|--------|-----------|-----------|-----------|
| `order_id` | `order_data.id` | NoAction | NoAction |

---

## Table: `product_data`

**Description**: Normalized Shopify product data for recommendations and ML.

**Services that read/write**:
- **Write**: Python worker (data collection consumer, normalization consumer)
- **Read**: Python worker (recommendation engine, feature computation), Remix app (dashboard)

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | VarChar (PK) | No | `gen_random_uuid()` | Primary Key |
| `shop_id` | VarChar | No | - | FK -> `shops.id` |
| `product_id` | VarChar | No | - | - |
| `title` | VarChar(500) | No | - | - |
| `handle` | VarChar(255) | No | - | - |
| `description` | Text | Yes | - | - |
| `product_type` | VarChar(100) | Yes | `''` | - |
| `vendor` | VarChar(255) | Yes | `''` | - |
| `tags` | Json | Yes | `[]` | - |
| `status` | VarChar | Yes | `'ACTIVE'` | - |
| `total_inventory` | Int | Yes | `0` | - |
| `price` | Float | No | `0.0` | - |
| `compare_at_price` | Float | Yes | `0.0` | - |
| `price_range` | Json | Yes | `{}` | - |
| `collections` | Json | Yes | `[]` | - |
| `seo_title` | VarChar(500) | Yes | - | - |
| `seo_description` | Text | Yes | - | - |
| `template_suffix` | VarChar(100) | Yes | - | - |
| `variants` | Json | Yes | `[]` | - |
| `images` | Json | Yes | `[]` | - |
| `media` | Json | Yes | `[]` | - |
| `options` | Json | Yes | `[]` | - |
| `metafields` | Json | Yes | `[]` | - |
| `extras` | Json | Yes | `{}` | - |
| `is_active` | Boolean | No | `true` | - |
| `created_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |
| `updated_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |

**Indexes**:
| Name | Columns | Unique |
|------|---------|--------|
| `ix_product_data_is_active` | `is_active` | No |
| `ix_product_data_price` | `price` | No |
| `ix_product_data_product_id` | `product_id` | No |
| `ix_product_data_product_type` | `product_type` | No |
| `ix_product_data_shop_id` | `shop_id` | No |
| `ix_product_data_status` | `status` | No |
| `ix_product_data_total_inventory` | `total_inventory` | No |
| `ix_product_data_vendor` | `vendor` | No |

---

## Table: `customer_data`

**Description**: Normalized Shopify customer data.

**Services that read/write**:
- **Write**: Python worker (data collection consumer, normalization consumer)
- **Read**: Python worker (feature computation, customer linking)

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | VarChar (PK) | No | `gen_random_uuid()` | Primary Key |
| `shop_id` | VarChar | No | - | FK -> `shops.id` |
| `customer_id` | VarChar | No | - | - |
| `first_name` | VarChar(100) | Yes | - | - |
| `last_name` | VarChar(100) | Yes | - | - |
| `total_spent` | Float | No | `0.0` | - |
| `order_count` | Int | No | `0` | - |
| `last_order_date` | Timestamptz(6) | Yes | - | - |
| `last_order_id` | VarChar(100) | Yes | - | - |
| `verified_email` | Boolean | No | `false` | - |
| `tax_exempt` | Boolean | No | `false` | - |
| `customer_locale` | VarChar(10) | Yes | `'en'` | - |
| `tags` | Json | Yes | `[]` | - |
| `state` | VarChar(50) | Yes | `''` | - |
| `default_address` | Json | Yes | `{}` | - |
| `is_active` | Boolean | No | `true` | - |
| `created_at` | Timestamptz(6) | Yes | - | - |
| `updated_at` | Timestamptz(6) | Yes | - | - |
| `extras` | Json | Yes | `{}` | - |

**Indexes**:
| Name | Columns | Unique |
|------|---------|--------|
| `ix_customer_data_created_at` | `created_at` | No |
| `ix_customer_data_customer_id` | `customer_id` | No |
| `ix_customer_data_last_order_date` | `last_order_date` | No |
| `ix_customer_data_shop_id` | `shop_id` | No |
| `ix_customer_data_state` | `state` | No |
| `ix_customer_data_total_spent` | `total_spent` | No |
| `ix_customer_data_updated_at` | `updated_at` | No |
| `ix_customer_data_verified_email` | `verified_email` | No |

---

## Table: `collection_data`

**Description**: Normalized Shopify collection data.

**Services that read/write**:
- **Write**: Python worker (data collection consumer, normalization consumer)
- **Read**: Python worker (feature computation, recommendation engine)

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | VarChar (PK) | No | `gen_random_uuid()` | Primary Key |
| `shop_id` | VarChar | No | - | FK -> `shops.id` |
| `collection_id` | VarChar | No | - | - |
| `title` | VarChar(500) | No | - | - |
| `handle` | VarChar(255) | No | - | - |
| `description` | Text | Yes | `''` | - |
| `template_suffix` | VarChar(100) | Yes | `''` | - |
| `seo_title` | VarChar(500) | Yes | `''` | - |
| `seo_description` | Text | Yes | `''` | - |
| `image_url` | VarChar(1000) | Yes | - | - |
| `image_alt` | VarChar(500) | Yes | - | - |
| `product_count` | Int | No | `0` | - |
| `is_automated` | Boolean | No | `false` | - |
| `is_active` | Boolean | No | `true` | - |
| `metafields` | Json | Yes | `[]` | - |
| `products` | Json | Yes | `[]` | - |
| `extras` | Json | Yes | `{}` | - |
| `created_at` | Timestamptz(6) | Yes | - | - |
| `updated_at` | Timestamptz(6) | Yes | - | - |

**Indexes**:
| Name | Columns | Unique |
|------|---------|--------|
| `ix_collection_data_collection_id` | `collection_id` | No |
| `ix_collection_data_created_at` | `created_at` | No |
| `ix_collection_data_handle` | `handle` | No |
| `ix_collection_data_is_automated` | `is_automated` | No |
| `ix_collection_data_product_count` | `product_count` | No |
| `ix_collection_data_shop_id` | `shop_id` | No |
| `ix_collection_data_title` | `title` | No |
| `ix_collection_data_updated_at` | `updated_at` | No |

---

## Table: `raw_orders`

**Description**: Raw order payloads from Shopify webhooks/API for audit and reprocessing.

**Services that read/write**:
- **Write**: Python worker (data collection consumer)
- **Read**: Python worker (normalization consumer)

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | VarChar (PK) | No | `gen_random_uuid()` | Primary Key |
| `shop_id` | VarChar | No | - | FK -> `shops.id` |
| `payload` | Json | No | - | - |
| `extracted_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |
| `shopify_id` | VarChar(100) | Yes | - | - |
| `shopify_created_at` | Timestamptz(6) | Yes | - | - |
| `shopify_updated_at` | Timestamptz(6) | Yes | - | - |
| `source` | VarChar | Yes | `'webhook'` | Values: `webhook`, `backfill` |
| `format` | VarChar | Yes | `'rest'` | Values: `rest`, `graphql` |
| `received_at` | Timestamptz(6) | Yes | `timezone('UTC', CURRENT_TIMESTAMP)` | - |
| `created_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |
| `updated_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |

**Indexes**:
| Name | Columns | Unique |
|------|---------|--------|
| `ix_raw_order_shop_id_shopify_id` | `shop_id`, `shopify_id` | No |
| `ix_raw_order_shop_id_shopify_updated_at` | `shop_id`, `shopify_updated_at` | No |
| `ix_raw_order_shop_id_shopify_created_at` | `shop_id`, `shopify_created_at` | No |
| `ix_raw_order_shop_id_source` | `shop_id`, `source` | No |
| `ix_raw_order_shop_id_format` | `shop_id`, `format` | No |
| `ix_raw_orders_format` | `format` | No |
| `ix_raw_orders_shop_id` | `shop_id` | No |
| `ix_raw_orders_source` | `source` | No |

The tables `raw_products`, `raw_customers`, and `raw_collections` have an identical structure (same columns, same pattern of indexes with the respective prefix name). They differ only in their table names and index names:

- **`raw_products`**: `ix_raw_product_*` indexes
- **`raw_customers`**: `ix_raw_customer_*` indexes
- **`raw_collections`**: `ix_raw_collection_*` indexes

---

## Table: `user_sessions`

**Description**: Tracks end-user browsing sessions on the storefront for attribution.

**Services that read/write**:
- **Write**: Python worker (interaction service, session creation from extensions)
- **Read**: Python worker (purchase attribution consumer, customer linking consumer, feature computation)

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | VarChar (PK) | No | `gen_random_uuid()` | Primary Key |
| `shop_id` | VarChar | No | - | FK -> `shops.id` |
| `customer_id` | VarChar | Yes | - | - |
| `browser_session_id` | VarChar(255) | Yes | - | - |
| `status` | VarChar(50) | No | `'active'` | - |
| `client_id` | VarChar | Yes | - | Shopify client ID for cross-device |
| `last_active` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |
| `expires_at` | Timestamptz(6) | Yes | - | - |
| `user_agent` | VarChar | Yes | - | - |
| `ip_address` | VarChar(45) | Yes | - | - |
| `referrer` | VarChar | Yes | - | - |
| `extensions_used` | Json | No | `[]` | - |
| `total_interactions` | Int | No | `0` | - |
| `created_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |
| `updated_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |

**Indexes (including partial indexes)**:
| Name | Columns | Unique | Notes |
|------|---------|--------|-------|
| `ix_active_by_customer` | `shop_id`, `customer_id`, `status`, `expires_at` | No | Partial: `WHERE customer_id IS NOT NULL AND status = 'active'` |
| `ix_active_by_client_id` | `shop_id`, `client_id`, `status`, `expires_at` | No | Partial: `WHERE client_id IS NOT NULL AND status = 'active'` |
| `ix_active_by_browser_session` | `shop_id`, `browser_session_id`, `status`, `expires_at` | No | Partial: `WHERE browser_session_id IS NOT NULL AND status = 'active'` |
| `ix_shop_id` | `shop_id` | No | - |
| `ix_customer_id` | `customer_id` | No | - |
| `ix_status` | `status` | No | - |
| `ix_expires_at` | `expires_at` | No | - |
| `ix_shop_status` | `shop_id`, `status` | No | - |
| `ix_created_at` | `created_at` | No | - |

---

## Table: `user_interactions`

**Description**: Individual user interactions with BetterBundle extensions on the storefront.

**Services that read/write**:
- **Write**: Python worker (interaction service from extension API calls)
- **Read**: Python worker (purchase attribution, customer linking, feature computation)

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | VarChar (PK) | No | `gen_random_uuid()` | Primary Key |
| `shop_id` | VarChar | No | - | FK -> `shops.id` |
| `customer_id` | VarChar | Yes | - | - |
| `session_id` | VarChar(255) | No | - | FK -> `user_sessions.id` |
| `extension_type` | VarChar(50) | No | - | Values: `apollo`, `phoenix`, `venus`, `mercury`, `atlas` |
| `interaction_type` | VarChar(50) | No | - | - |
| `interaction_metadata` | Json | No | `{}` | - |
| `created_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |
| `updated_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |

**Indexes**:
| Name | Columns | Unique |
|------|---------|--------|
| `ix_user_interaction_session_id` | `session_id` | No |
| `ix_user_interaction_customer_id` | `customer_id` | No |
| `ix_user_interaction_shop_id` | `shop_id` | No |
| `ix_user_interaction_extension_type` | `extension_type` | No |
| `ix_user_interaction_interaction_type` | `interaction_type` | No |
| `ix_user_interaction_created_at` | `created_at` | No |
| `ix_user_interaction_shop_id_extension_type` | `shop_id`, `extension_type` | No |
| `ix_user_interaction_shop_id_interaction_type` | `shop_id`, `interaction_type` | No |
| `ix_user_interaction_shop_id_customer_id_created_at` | `shop_id`, `customer_id`, `created_at` | No |

---

## Table: `user_identity_links`

**Description**: Cross-session customer identity resolution linking identifiers to customer IDs.

**Services that read/write**:
- **Write**: Python worker (customer linking consumer)
- **Read**: Python worker (cross-session linking service)

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | VarChar (PK) | No | `gen_random_uuid()` | Primary Key |
| `shop_id` | VarChar | No | - | FK -> `shops.id` |
| `identifier` | VarChar | No | - | - |
| `identifier_type` | VarChar | No | - | - |
| `customer_id` | VarChar | No | - | - |
| `linked_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |
| `created_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |
| `updated_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |

**Indexes**:
| Name | Columns | Unique |
|------|---------|--------|
| `ix_user_identity_link_shop_id_identifier_customer_id` | `shop_id`, `identifier`, `customer_id` | Yes |
| `ix_user_identity_link_shop_id_identifier` | `shop_id`, `identifier` | No |
| `ix_user_identity_link_shop_id_customer_id` | `shop_id`, `customer_id` | No |
| `ix_user_identity_link_identifier` | `identifier` | No |
| `ix_user_identity_link_customer_id` | `customer_id` | No |
| `ix_user_identity_link_identifier_type` | `identifier_type` | No |

---

## Table: `purchase_attributions`

**Description**: Revenue attribution connecting orders to sessions and extensions.

**Services that read/write**:
- **Write**: Python worker (purchase attribution consumer via BillingServiceV2)
- **Read**: Python worker (commission calculation, billing), Remix app (analytics dashboard)

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | VarChar (PK) | No | `gen_random_uuid()` | Primary Key |
| `shop_id` | VarChar | No | - | FK -> `shops.id` |
| `customer_id` | VarChar | Yes | - | - |
| `session_id` | VarChar(255) | No | - | FK -> `user_sessions.id` |
| `order_id` | VarChar(255) | No | - | - |
| `contributing_extensions` | Json | No | - | - |
| `attribution_weights` | Json | No | - | - |
| `total_revenue` | Decimal(10,2) | No | - | - |
| `attributed_revenue` | Json | No | - | - |
| `total_interactions` | Int | No | - | - |
| `interactions_by_extension` | Json | No | - | - |
| `purchase_at` | Timestamptz(6) | No | - | - |
| `attribution_algorithm` | VarChar(50) | No | `'multi_touch'` | - |
| `metadata` | Json | No | `{}` | - |
| `created_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |
| `updated_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |

**Indexes**:
| Name | Columns | Unique |
|------|---------|--------|
| `ix_purchase_attribution_shop_id_order_id` | `shop_id`, `order_id` | Yes |
| `ix_purchase_attribution_session_id` | `session_id` | No |
| `ix_purchase_attribution_order_id` | `order_id` | No |
| `ix_purchase_attribution_customer_id` | `customer_id` | No |
| `ix_purchase_attribution_shop_id` | `shop_id` | No |
| `ix_purchase_attribution_purchase_at` | `purchase_at` | No |
| `ix_purchase_attribution_shop_id_purchase_at` | `shop_id`, `purchase_at` | No |
| `ix_purchase_attribution_shop_id_customer_id_purchase_at` | `shop_id`, `customer_id`, `purchase_at` | No |

---

## Table: `subscription_plans`

**Description**: Master table defining available subscription plans (admin-controlled templates).

**Services that read/write**:
- **Write**: Admin panel (Django admin)
- **Read**: Remix app (plan selection), Python worker (billing service)

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | VarChar (PK) | No | `gen_random_uuid()` | Primary Key |
| `name` | VarChar(100) | No | - | Unique (`ix_subscription_plans_name`) |
| `description` | Text | Yes | - | - |
| `plan_type` | `subscription_plan_type_enum` | No | - | - |
| `is_active` | Boolean | No | `true` | - |
| `is_default` | Boolean | No | `false` | - |
| `default_commission_rate` | VarChar(10) | Yes | - | e.g., `"0.03"` for 3% |
| `plan_metadata` | Text | Yes | - | JSON string |
| `effective_from` | Timestamptz(6) | No | - | - |
| `effective_to` | Timestamptz(6) | Yes | - | - |
| `created_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |
| `updated_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |

**Indexes**:
| Name | Columns | Unique |
|------|---------|--------|
| `ix_subscription_plans_name` | `name` | Yes |
| `ix_subscription_plan_name` | `name` | No |
| `ix_subscription_plan_type` | `plan_type` | No |
| `ix_subscription_plan_active` | `is_active` | No |
| `ix_subscription_plan_default` | `is_default` | No |
| `ix_subscription_plan_effective` | `effective_from`, `effective_to` | No |

---

## Table: `pricing_tiers`

**Description**: Pricing configuration per subscription plan per currency.

**Services that read/write**:
- **Write**: Admin panel
- **Read**: Remix app (billing flow), Python worker (commission calculation)

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | VarChar (PK) | No | `gen_random_uuid()` | Primary Key |
| `subscription_plan_id` | VarChar(255) | No | - | FK -> `subscription_plans.id` (CASCADE) |
| `currency` | VarChar(3) | No | - | ISO 4217 |
| `trial_threshold_amount` | Decimal(10,2) | No | - | Revenue threshold to complete trial |
| `commission_rate` | Decimal(5,4) | No | `0.03` | e.g., 0.03 for 3% |
| `is_active` | Boolean | No | `true` | - |
| `is_default` | Boolean | No | `false` | - |
| `minimum_charge` | Decimal(10,2) | Yes | - | Minimum per billing cycle |
| `proration_enabled` | Boolean | No | `true` | - |
| `tier_metadata` | VarChar(1000) | Yes | - | JSON string |
| `effective_from` | Timestamptz(6) | No | - | - |
| `effective_to` | Timestamptz(6) | Yes | - | - |
| `created_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |
| `updated_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |

**Indexes**:
| Name | Columns | Unique |
|------|---------|--------|
| `ix_pricing_tier_unique_default` | `subscription_plan_id`, `currency`, `is_default` | Yes |
| `ix_pricing_tier_plan_currency` | `subscription_plan_id`, `currency` | No |
| `ix_pricing_tier_currency` | `currency` | No |
| `ix_pricing_tier_active` | `is_active` | No |
| `ix_pricing_tier_default` | `is_default` | No |
| `ix_pricing_tier_effective` | `effective_from`, `effective_to` | No |

---

## Table: `shop_subscriptions`

**Description**: Unified subscription records per shop. Multiple records possible (trial + paid), only one active.

**Services that read/write**:
- **Write**: Remix app (subscription creation), Python worker (billing service, Shopify usage consumer)
- **Read**: Both services (billing checks, commission calculation)

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | VarChar (PK) | No | `gen_random_uuid()` | Primary Key |
| `shop_id` | VarChar | No | - | FK -> `shops.id` |
| `subscription_type` | `subscription_type_enum` | No | `TRIAL` | - |
| `status` | `subscription_status_enum` | No | `ACTIVE` | - |
| `subscription_plan_id` | VarChar(255) | No | - | FK -> `subscription_plans.id` (RESTRICT) |
| `pricing_tier_id` | VarChar(255) | No | - | FK -> `pricing_tiers.id` (RESTRICT) |
| `trial_threshold_override` | Decimal(10,2) | Yes | - | - |
| `trial_duration_days` | Int | Yes | - | - |
| `user_chosen_cap_amount` | Decimal(10,2) | Yes | - | - |
| `auto_renew` | Boolean | No | `true` | - |
| `shopify_subscription_id` | VarChar(255) | Yes | - | Shopify GID |
| `shopify_line_item_id` | VarChar(255) | Yes | - | - |
| `shopify_status` | VarChar(50) | Yes | - | - |
| `confirmation_url` | Text | Yes | - | - |
| `started_at` | Timestamptz(6) | No | - | - |
| `completed_at` | Timestamptz(6) | Yes | - | - |
| `cancelled_at` | Timestamptz(6) | Yes | - | - |
| `expires_at` | Timestamptz(6) | Yes | - | - |
| `is_active` | Boolean | No | `true` | - |
| `shop_subscription_metadata` | JSONB | Yes | - | - |
| `created_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |
| `updated_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |

**Indexes**:
| Name | Columns | Unique |
|------|---------|--------|
| `ix_shop_subscriptions_shop_id` | `shop_id` | No |
| `ix_shop_subscriptions_status` | `status` | No |
| `ix_shop_subscriptions_is_active` | `is_active` | No |
| `ix_shop_subscriptions_subscription_plan_id` | `subscription_plan_id` | No |
| `ix_shop_subscriptions_pricing_tier_id` | `pricing_tier_id` | No |
| `ix_shop_subscriptions_subscription_type` | `subscription_type` | No |
| `ix_shop_subscriptions_shopify_subscription_id` | `shopify_subscription_id` | No |
| `ix_shop_subscriptions_started_at` | `started_at` | No |
| `ix_shop_subscriptions_completed_at` | `completed_at` | No |
| `ix_shop_subscriptions_cancelled_at` | `cancelled_at` | No |
| `ix_shop_subscriptions_expires_at` | `expires_at` | No |

---

## Table: `billing_cycles`

**Description**: 30-day billing periods per shop subscription. Tracks usage against caps.

**Services that read/write**:
- **Write**: Python worker (billing service, Shopify usage consumer)
- **Read**: Python worker (commission calculation), Remix app (billing dashboard)

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | VarChar (PK) | No | `gen_random_uuid()` | Primary Key |
| `shop_subscription_id` | VarChar(255) | No | - | FK -> `shop_subscriptions.id` (CASCADE) |
| `cycle_number` | Int | No | - | - |
| `start_date` | Timestamptz(6) | No | - | - |
| `end_date` | Timestamptz(6) | No | - | - |
| `initial_cap_amount` | Decimal(10,2) | No | - | Cap at cycle start |
| `current_cap_amount` | Decimal(10,2) | No | - | Current cap (after adjustments) |
| `usage_amount` | Decimal(10,2) | No | `0.00` | Total usage in this cycle |
| `commission_count` | Int | No | `0` | Number of commissions |
| `status` | `billing_cycle_status_enum` | No | `ACTIVE` | - |
| `activated_at` | Timestamptz(6) | Yes | - | - |
| `completed_at` | Timestamptz(6) | Yes | - | - |
| `cancelled_at` | Timestamptz(6) | Yes | - | - |
| `cycle_metadata` | VarChar(1000) | Yes | - | JSON string |
| `created_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |
| `updated_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |

**Indexes**:
| Name | Columns | Unique |
|------|---------|--------|
| `ix_billing_cycle_unique_active` | `shop_subscription_id`, `status` | Yes |
| `ix_billing_cycle_active` | `shop_subscription_id`, `status` | No |
| `ix_billing_cycle_dates` | `start_date`, `end_date` | No |
| `ix_billing_cycle_number` | `cycle_number` | No |
| `ix_billing_cycle_status` | `status` | No |
| `ix_billing_cycle_subscription` | `shop_subscription_id` | No |

---

## Table: `commission_records`

**Description**: Individual commission records for each purchase attribution. Tracks trial and paid phases.

**Services that read/write**:
- **Write**: Python worker (purchase attribution consumer, Shopify usage consumer, commission service)
- **Read**: Python worker (billing, reprocessing), Remix app (billing dashboard)

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | VarChar(255) (PK) | No | `uuid4()` | Primary Key |
| `shop_id` | VarChar(255) | No | - | FK -> `shops.id` (CASCADE) |
| `purchase_attribution_id` | VarChar(255) | No | - | FK -> `purchase_attributions.id` (CASCADE), Unique |
| `billing_cycle_id` | VarChar(255) | Yes | - | FK -> `billing_cycles.id` (SET NULL) |
| `order_id` | VarChar(255) | No | - | - |
| `order_date` | Timestamptz(6) | No | - | - |
| `attributed_revenue` | Decimal(10,2) | No | - | - |
| `commission_rate` | Decimal(5,4) | No | `0.03` | - |
| `commission_earned` | Decimal(10,2) | No | - | Full commission amount |
| `commission_charged` | Decimal(10,2) | No | `0` | Actual charged to Shopify |
| `commission_overflow` | Decimal(10,2) | No | `0` | Amount couldn't charge due to cap |
| `billing_cycle_start` | Timestamptz(6) | Yes | - | - |
| `billing_cycle_end` | Timestamptz(6) | Yes | - | - |
| `cycle_usage_before` | Decimal(10,2) | No | `0` | - |
| `cycle_usage_after` | Decimal(10,2) | No | `0` | - |
| `capped_amount` | Decimal(10,2) | No | - | Max chargeable in cycle |
| `trial_accumulated` | Decimal(10,2) | No | `0` | - |
| `billing_phase` | `billing_phase_enum` | No | `TRIAL` | - |
| `status` | `commission_status_enum` | No | `TRIAL_PENDING` | - |
| `charge_type` | `charge_type_enum` | No | `TRIAL` | - |
| `shopify_usage_record_id` | VarChar(255) | Yes | - | Unique |
| `shopify_recorded_at` | Timestamptz(6) | Yes | - | - |
| `shopify_response` | Json | Yes | - | - |
| `currency` | VarChar(3) | No | `'USD'` | ISO 4217 |
| `notes` | Text | Yes | - | - |
| `commission_metadata` | Json | Yes | `{}` | - |
| `error_count` | Int | No | `0` | - |
| `last_error` | Text | Yes | - | - |
| `last_error_at` | Timestamptz(6) | Yes | - | - |
| `deleted_at` | Timestamptz(6) | Yes | - | Soft delete |
| `created_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |
| `updated_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |

**Indexes**:
| Name | Columns | Unique |
|------|---------|--------|
| `ix_commission_records_purchase_attribution_id` | `purchase_attribution_id` | Yes |
| `ix_commission_records_shopify_usage_record_id` | `shopify_usage_record_id` | Yes |
| `idx_commission_shop_cycle` | `shop_id`, `billing_cycle_start`, `billing_cycle_end` | No |
| `idx_commission_shop_phase_status` | `shop_id`, `billing_phase`, `status` | No |
| `idx_commission_status_created` | `status`, `created_at` | No |
| `idx_commission_shopify_record` | `shopify_usage_record_id` | No |
| `ix_commission_records_billing_cycle_id` | `billing_cycle_id` | No |
| `ix_commission_records_billing_phase` | `billing_phase` | No |
| `ix_commission_records_deleted_at` | `deleted_at` | No |
| `ix_commission_records_order_date` | `order_date` | No |
| `ix_commission_records_order_id` | `order_id` | No |
| `ix_commission_records_shop_id` | `shop_id` | No |
| `ix_commission_records_status` | `status` | No |

---

## Table: `billing_invoices`

**Description**: Shopify billing invoices received via webhooks (SQLAlchemy model only, not in Prisma schema).

**Services that read/write**:
- **Write**: Python worker (billing webhook handlers)
- **Read**: Python worker (invoice tracking)

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `id` | VarChar (PK) | No | `gen_random_uuid()` | Primary Key |
| `shop_subscription_id` | VarChar(255) | No | - | FK -> `shop_subscriptions.id` (CASCADE) |
| `shopify_invoice_id` | VarChar(255) | No | - | Unique |
| `invoice_number` | VarChar(100) | Yes | - | - |
| `amount_due` | Decimal(10,2) | No | `0.00` | - |
| `amount_paid` | Decimal(10,2) | No | `0.00` | - |
| `total_amount` | Decimal(10,2) | No | `0.00` | - |
| `currency` | VarChar(3) | No | `'USD'` | - |
| `invoice_date` | Timestamptz(6) | No | - | - |
| `due_date` | Timestamptz(6) | Yes | - | - |
| `paid_at` | Timestamptz(6) | Yes | - | - |
| `status` | `invoice_status_enum` | No | `PENDING` | - |
| `description` | Text | Yes | - | - |
| `line_items` | JSON | Yes | - | - |
| `shopify_response` | JSON | Yes | - | - |
| `payment_method` | VarChar(100) | Yes | - | - |
| `payment_reference` | VarChar(255) | Yes | - | - |
| `failure_reason` | VarChar(500) | Yes | - | - |
| `created_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |
| `updated_at` | Timestamptz(6) | No | `timezone('UTC', CURRENT_TIMESTAMP)` | - |

---

## Feature Tables

The following tables store computed ML features. They all follow a similar pattern: they belong to a shop, have a `last_computed_at` timestamp, and use composite unique indexes.

### Table: `user_features`

**Services**: Written by Python worker (feature computation consumer). Read by Python worker (recommendation engine, Gorse sync).

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `id` | VarChar (PK) | No | `gen_random_uuid()` |
| `shop_id` | VarChar | No | FK -> `shops.id` |
| `customer_id` | VarChar | Yes | - |
| `total_purchases` | Int | No | `0` |
| `total_interactions` | Int | No | `0` |
| `lifetime_value` | Float | No | `0` |
| `avg_order_value` | Float | No | `0` |
| `purchase_frequency_score` | Float | No | `0` |
| `interaction_diversity_score` | Float | No | `0` |
| `days_since_last_purchase` | Int | Yes | - |
| `recency_score` | Float | No | `0` |
| `conversion_rate` | Float | No | `0` |
| `primary_category` | VarChar(100) | Yes | - |
| `category_diversity` | Int | No | `0` |
| `user_lifecycle_stage` | VarChar(100) | Yes | - |
| `churn_risk_score` | Float | No | `1.0` |
| `last_computed_at` | Timestamptz(6) | No | - |
| `created_at` / `updated_at` | Timestamptz(6) | No | UTC timestamp |

**Key Indexes**: `ix_user_features_shop_id_customer_id` (unique composite)

### Table: `product_features`

| Column | Type | Nullable |
|--------|------|----------|
| `id`, `shop_id`, `product_id` | VarChar | No/No/Yes |
| `interaction_volume_score`, `purchase_velocity_score`, `engagement_quality_score` | Float | No |
| `price_tier` | VarChar(20) | No |
| `revenue_potential_score`, `conversion_efficiency`, `activity_recency_score` | Float | No |
| `days_since_last_purchase` | Int | Yes |
| `trending_momentum`, `inventory_health_score` | Float | No |
| `product_lifecycle_stage` | VarChar(100) | No |
| `product_category` | VarChar(100) | Yes |
| `last_computed_at` | Timestamptz(6) | No |

**Key Index**: `ix_product_features_shop_id_product_id` (unique). 11 additional composite indexes on `(shop_id, <score>)`.

### Table: `collection_features`

| Column | Type | Nullable |
|--------|------|----------|
| `id`, `shop_id`, `collection_id` | VarChar | No/No/No |
| `collection_engagement_score`, `collection_conversion_rate`, `collection_popularity_score` | Float | No |
| `avg_product_value` | Float | Yes |
| `collection_revenue_potential`, `product_diversity_score`, `collection_recency_score` | Float | No |
| `collection_size_tier` | VarChar(100) | No |
| `days_since_last_interaction` | Int | Yes |
| `is_curated_collection` | Boolean | No |
| `last_computed_at` | Timestamptz(6) | No |

**Key Index**: `ix_collection_features_shop_id_collection_id` (unique)

### Table: `customer_behavior_features`

| Column | Type | Nullable |
|--------|------|----------|
| `id`, `shop_id`, `customer_id` | VarChar | No/No/Yes |
| `user_lifecycle_stage` | VarChar(100) | Yes |
| `purchase_frequency_score`, `interaction_diversity_score` | Float | No |
| `category_diversity` | Int | No |
| `primary_category` | VarChar(100) | Yes |
| `conversion_rate`, `avg_order_value`, `lifetime_value`, `recency_score`, `churn_risk_score` | Float | No |
| `total_interactions` | Int | No |
| `days_since_last_purchase` | Int | Yes |
| `last_computed_at` | Timestamptz(6) | No |

**Key Index**: `ix_cb_features_shop_cust` (unique on `shop_id`, `customer_id`). 13 additional composite indexes.

### Table: `interaction_features`

| Column | Type | Nullable |
|--------|------|----------|
| `id`, `shop_id`, `customer_id`, `product_id` | VarChar | No/No/Yes/Yes |
| `interaction_strength_score`, `customer_product_affinity`, `engagement_progression_score` | Float | No |
| `conversion_likelihood`, `purchase_intent_score`, `interaction_recency_score` | Float | No |
| `relationship_maturity` | VarChar(100) | No |
| `interaction_frequency_score`, `customer_product_loyalty`, `total_interaction_value` | Float | No |
| `last_computed_at` | Timestamptz(6) | No |

**Key Index**: `ix_int_features_shop_cust_prod` (unique on `shop_id`, `customer_id`, `product_id`). 8 additional composite indexes.

### Table: `session_features`

| Column | Type | Nullable |
|--------|------|----------|
| `id`, `shop_id`, `customer_id`, `session_id` | VarChar | No/No/Yes/No |
| `session_duration_minutes`, `interaction_count`, `unique_products_viewed` | Int | No |
| `interaction_intensity`, `browse_depth_score`, `purchase_intent_score`, `session_value` | Float | No |
| `conversion_funnel_stage`, `session_type`, `traffic_source` | VarChar(100) | No |
| `bounce_session`, `returning_visitor` | Boolean | No |
| `last_computed_at` | Timestamptz(6) | No |

**Key Indexes**: `ix_session_features_session_id` (unique), `ix_session_features_shop_id_session_id` (unique)

### Table: `product_pair_features`

| Column | Type | Nullable |
|--------|------|----------|
| `id`, `shop_id`, `product_id`, `product_id1`, `product_id2` | VarChar | No/No/Yes/No/No |
| `co_purchase_strength`, `co_engagement_score`, `pair_affinity_score` | Float | No |
| `total_pair_revenue`, `pair_frequency_score`, `pair_recency_score`, `cross_sell_potential` | Float | No |
| `days_since_last_co_occurrence` | Int | Yes |
| `pair_confidence_level` | VarChar(100) | No |
| `last_computed_at` | Timestamptz(6) | No |

**Key Index**: `ix_pp_features_shop_p1_p2` (unique on `shop_id`, `product_id1`, `product_id2`). 11 additional composite indexes.

### Table: `search_product_features`

| Column | Type | Nullable |
|--------|------|----------|
| `id`, `shop_id`, `product_id` | VarChar | No/No/Yes |
| `search_query` | VarChar(500) | No |
| `search_click_rate`, `search_conversion_rate`, `search_relevance_score` | Float | No |
| `total_search_interactions`, `search_to_purchase_count` | Int | No |
| `days_since_last_search_interaction` | Int | Yes |
| `search_recency_score`, `semantic_match_score` | Float | No |
| `search_intent_alignment` | VarChar(100) | No |
| `last_computed_at` | Timestamptz(6) | No |

**Key Index**: `ix_sp_features_shop_query_prod` (unique on `shop_id`, `search_query`, `product_id`)

---

## Gorse Tables

These tables are managed by the Gorse recommendation engine and share the same PostgreSQL database.

### Table: `feedback`

| Column | Type | Nullable | Default | Constraints |
|--------|------|----------|---------|-------------|
| `feedback_type` | VarChar(256) | No | - | Composite PK |
| `user_id` | VarChar(256) | No | - | Composite PK |
| `item_id` | VarChar(256) | No | - | Composite PK |
| `time_stamp` | Timestamptz(6) | No | - | - |
| `comment` | String | No | `''` | - |

**Indexes**: `item_id_index` on `item_id`, `user_id_index` on `user_id`

### Table: `items`

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `item_id` | VarChar(256) (PK) | No | - |
| `is_hidden` | Boolean | No | `false` |
| `categories` | Json | No | `'[]'` |
| `time_stamp` | Timestamptz(6) | No | - |
| `labels` | Json | No | `'[]'` |
| `comment` | String | No | `''` |

### Table: `users`

| Column | Type | Nullable | Default |
|--------|------|----------|---------|
| `user_id` | VarChar(256) (PK) | No | - |
| `labels` | Json | No | `'[]'` |
| `subscribe` | Json | No | `'[]'` |
| `comment` | String | No | `''` |

---

## Entity Relationship Summary

```
shops (1) ---> (N) order_data ---> (N) line_item_data
shops (1) ---> (N) product_data
shops (1) ---> (N) customer_data
shops (1) ---> (N) collection_data
shops (1) ---> (N) raw_orders / raw_products / raw_customers / raw_collections
shops (1) ---> (N) user_sessions ---> (N) user_interactions
                                  ---> (N) purchase_attributions ---> (1) commission_records
shops (1) ---> (N) user_identity_links
shops (1) ---> (N) shop_subscriptions ---> (N) billing_cycles ---> (N) commission_records
                                       ---> (1) subscription_plans ---> (N) pricing_tiers
shops (1) ---> (N) [all feature tables]
shops (1) ---> (N) commission_records
```
