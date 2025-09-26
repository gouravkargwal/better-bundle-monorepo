# User Features Documentation

## Overview

User Features provide comprehensive customer analytics and behavioral insights for personalization and customer segmentation. These features are generated from customer data, order history, and behavioral events.

## Data Sources Required

The `UserFeatureGenerator` requires the following data sources:

| Data Source           | Table                           | Purpose                             | Required      |
| --------------------- | ------------------------------- | ----------------------------------- | ------------- |
| **Customer Data**     | `customer_data`                 | Customer demographics, attributes   | ✅ Required   |
| **Orders**            | `order_data` + `line_item_data` | Purchase history, spending patterns | ✅ Required   |
| **Products**          | `product_data`                  | Product categories, vendors         | ✅ Required   |
| **Behavioral Events** | `user_interactions`             | User engagement patterns            | ⚠️ Optional\* |

\*Optional sources provide enhanced features but computation can proceed without them.

## User Features Generated

The `UserFeatures` table contains **40+ computed features** across these categories:

### 💰 Purchase Metrics

- `total_purchases` - Total number of orders
- `total_spent` - Total amount spent
- `avg_order_value` - Average order value
- `lifetime_value` - Customer lifetime value
- `net_lifetime_value` - Lifetime value after refunds

### ⏰ Temporal Features

- `days_since_first_order` - Days since first purchase
- `days_since_last_order` - Days since last purchase
- `avg_days_between_orders` - Average time between orders
- `order_frequency_per_month` - Orders per month

### 🛍️ Product Diversity

- `distinct_products_purchased` - Number of unique products bought
- `distinct_categories_purchased` - Number of unique categories
- `preferred_category` - Most purchased category
- `preferred_vendor` - Most purchased vendor
- `price_point_preference` - Preferred price range (low/medium/high)

### 💸 Discount Behavior

- `orders_with_discount_count` - Orders with discounts
- `discount_sensitivity` - Discount response rate
- `avg_discount_amount` - Average discount amount

### 👤 Customer Attributes

- `customer_state` - Customer state/region
- `is_verified_email` - Email verification status
- `customer_age` - Customer age (if available)
- `has_default_address` - Has default address
- `geographic_region` - Geographic region
- `currency_preference` - Preferred currency

### 🏥 Health & Risk Scores

- `customer_health_score` - Overall customer health (0-100)
- `refunded_orders` - Number of refunded orders
- `refund_rate` - Refund percentage
- `total_refunded_amount` - Total refunded amount
- `refund_risk_score` - Risk of future refunds

### 📊 Customer Demographics

- `customer_email` - Customer email
- `customer_first_name` - First name
- `customer_last_name` - Last name
- `customer_location` - Location data (JSON)
- `customer_tags` - Customer tags (JSON)
- `customer_created_at_shopify` - Shopify creation date
- `customer_last_order_id` - Last order ID
- `customer_metafields` - Custom metafields (JSON)
- `customer_verified_email` - Email verification
- `customer_tax_exempt` - Tax exemption status
- `customer_default_address` - Default address (JSON)
- `customer_addresses` - All addresses (JSON)
- `customer_currency_code` - Currency code
- `customer_locale` - Locale preference

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           USER FEATURE COMPUTATION FLOW                         │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Raw Shopify     │───▶│ GraphQL/REST     │───▶│ Normalization   │
│ Customers API   │    │ API Client       │    │ Service         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Raw Shopify     │───▶│ Order Processing │───▶│ Order           │
│ Orders API      │    │ Service          │    │ Normalization   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ User            │───▶│ Interaction      │───▶│ Behavioral      │
│ Interactions    │    │ Tracking         │    │ Event Storage   │
└─────────────────┘    └──────────────────┘    └─────────────────┘

                                │
                                ▼
                    ┌─────────────────────────┐
                    │     MAIN TABLES         │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ customer_data   │   │
                    │  │ - 381 customers │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ order_data      │   │
                    │  │ - 395 orders    │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ line_item_data  │   │
                    │  │ - 340 items     │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ product_data    │   │
                    │  │ - 350 products  │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ user_interactions│   │
                    │  │ - 0 records*    │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │  UserFeatureGenerator   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Purchase        │   │
                    │  │ Metrics         │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Temporal        │   │
                    │  │ Metrics         │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Product         │   │
                    │  │ Preferences     │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Discount        │   │
                    │  │ Behavior        │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Customer        │   │
                    │  │ Demographics    │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │   FEATURE TABLE         │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ user_features   │   │
                    │  │ - 40+ features  │   │
                    │  │ - 1 record*     │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘

* Current data status from your database
```

## Field Mappings: Table Fields → Features

### Customer Data Fields Used

| Field             | Feature Generated                                 | Purpose                   |
| ----------------- | ------------------------------------------------- | ------------------------- |
| `customer_id`     | All features                                      | Primary identifier        |
| `email`           | `customer_email`                                  | Contact information       |
| `first_name`      | `customer_first_name`                             | Personal information      |
| `last_name`       | `customer_last_name`                              | Personal information      |
| `phone`           | Contact analysis                                  | Communication preferences |
| `verified_email`  | `is_verified_email`, `customer_verified_email`    | Email verification        |
| `tax_exempt`      | `customer_tax_exempt`                             | Tax status                |
| `tags`            | `customer_tags`                                   | Customer categorization   |
| `metafields`      | `customer_metafields`                             | Custom attributes         |
| `default_address` | `customer_default_address`, `has_default_address` | Address information       |
| `addresses`       | `customer_addresses`                              | All addresses             |
| `currency_code`   | `currency_preference`, `customer_currency_code`   | Currency preferences      |
| `locale`          | `customer_locale`                                 | Language preferences      |
| `created_at`      | Customer lifecycle                                | Account age               |
| `updated_at`      | Update patterns                                   | Account activity          |

### Order Data Fields Used

| Field                       | Feature Generated                                  | Purpose                |
| --------------------------- | -------------------------------------------------- | ---------------------- |
| `order_id`                  | Order tracking                                     | Order identification   |
| `customer_id`               | Customer association                               | Customer linking       |
| `total_price`               | `total_spent`, `avg_order_value`, `lifetime_value` | Spending analysis      |
| `subtotal_price`            | Price analysis                                     | Base price calculation |
| `total_tax`                 | Tax analysis                                       | Tax behavior           |
| `total_discounts`           | `avg_discount_amount`, `discount_sensitivity`      | Discount behavior      |
| `currency`                  | Currency analysis                                  | Currency preferences   |
| `financial_status`          | Payment analysis                                   | Payment behavior       |
| `fulfillment_status`        | Fulfillment analysis                               | Order completion       |
| `processed_at`              | Order timing                                       | Processing patterns    |
| `created_at`                | `days_since_first_order`, `days_since_last_order`  | Temporal analysis      |
| `line_item_data.product_id` | `distinct_products_purchased`                      | Product diversity      |
| `line_item_data.quantity`   | Purchase volume                                    | Quantity analysis      |
| `line_item_data.price`      | Price analysis                                     | Price preferences      |

### Product Data Fields Used

| Field          | Feature Generated                                     | Purpose             |
| -------------- | ----------------------------------------------------- | ------------------- |
| `product_id`   | Product association                                   | Product linking     |
| `vendor`       | `preferred_vendor`                                    | Vendor preferences  |
| `product_type` | `preferred_category`, `distinct_categories_purchased` | Category analysis   |
| `price`        | `price_point_preference`                              | Price preferences   |
| `tags`         | Tag analysis                                          | Product preferences |

### User Interaction Fields Used

| Field           | Feature Generated    | Purpose              |
| --------------- | -------------------- | -------------------- |
| `customer_id`   | Customer association | Customer linking     |
| `event_type`    | Engagement analysis  | Interaction patterns |
| `created_at`    | Temporal analysis    | Interaction timing   |
| `view_duration` | Engagement quality   | Interaction depth    |

## Feature Computation Process

### Step 1: Data Collection

```python
# Context data passed to UserFeatureGenerator
context = {
    "orders": [...],            # From order_data + line_item_data
    "customer_data": {...},     # From customer_data table
    "behavioral_events": [...], # From user_interactions table
    "products": [...]           # From product_data table
}
```

### Step 2: Feature Categories Computation

1. **Purchase Metrics** (`_compute_purchase_metrics`)

   - Analyzes order history for spending patterns
   - Calculates total purchases, spending, AOV
   - Computes lifetime value metrics

2. **Temporal Metrics** (`_compute_temporal_metrics`)

   - Analyzes order timing patterns
   - Calculates days since first/last order
   - Computes order frequency and intervals

3. **Product Preferences** (`_compute_product_preferences`)

   - Analyzes purchased products for preferences
   - Identifies preferred categories and vendors
   - Calculates product diversity metrics

4. **Discount Behavior** (`_compute_discount_metrics`)

   - Analyzes discount usage patterns
   - Calculates discount sensitivity
   - Computes average discount amounts

5. **Customer Enhancement** (`_compute_customer_enhancement_features`)

   - Analyzes order data for customer insights
   - Computes customer health scores
   - Calculates refund risk metrics

6. **Demographics** (`_compute_customer_demographic_features`)
   - Extracts customer demographic data
   - Processes location and contact information
   - Analyzes customer attributes

### Step 3: Feature Aggregation

```python
features = {
    # Purchase metrics
    "total_purchases": 15,
    "total_spent": 1250.50,
    "avg_order_value": 83.37,
    "lifetime_value": 1250.50,

    # Temporal features
    "days_since_first_order": 180,
    "days_since_last_order": 7,
    "order_frequency_per_month": 2.5,

    # Product preferences
    "distinct_products_purchased": 25,
    "preferred_category": "Electronics",
    "preferred_vendor": "TechCorp",

    # Health scores
    "customer_health_score": 85,
    "refund_rate": 0.05,
    "refund_risk_score": 0.15,

    # ... 30+ more features
}
```

## Database Schema

### Input Tables (Main Data)

**customer_data**

```sql
CREATE TABLE customer_data (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    customer_id VARCHAR NOT NULL,
    email VARCHAR(255),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(50),
    verified_email BOOLEAN,
    tax_exempt BOOLEAN,
    tags JSON,
    metafields JSON,
    default_address JSON,
    addresses JSON,
    currency_code VARCHAR(10),
    locale VARCHAR(10),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**order_data + line_item_data**

```sql
CREATE TABLE order_data (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    order_id VARCHAR NOT NULL,
    customer_id VARCHAR,
    total_price FLOAT,
    discount_amount FLOAT,
    created_at TIMESTAMP
);

CREATE TABLE line_item_data (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    order_id VARCHAR NOT NULL,
    product_id VARCHAR,
    variant_id VARCHAR,
    title VARCHAR(500),
    quantity INTEGER,
    price FLOAT
);
```

### Output Table (Features)

**user_features**

```sql
CREATE TABLE user_features (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    customer_id VARCHAR NOT NULL,

    -- Purchase metrics
    total_purchases INTEGER DEFAULT 0,
    total_spent FLOAT DEFAULT 0,
    avg_order_value FLOAT DEFAULT 0,
    lifetime_value FLOAT DEFAULT 0,

    -- Temporal features
    days_since_first_order INTEGER,
    days_since_last_order INTEGER,
    order_frequency_per_month FLOAT,

    -- Product diversity
    distinct_products_purchased INTEGER DEFAULT 0,
    preferred_category VARCHAR(100),
    preferred_vendor VARCHAR(255),

    -- Health scores
    customer_health_score INTEGER DEFAULT 0,
    refund_rate FLOAT DEFAULT 0.0,
    net_lifetime_value FLOAT DEFAULT 0.0,

    -- Customer demographics
    customer_email VARCHAR(255),
    customer_first_name VARCHAR(100),
    customer_location JSON,
    customer_tags JSON,

    -- ... 30+ more feature columns

    last_computed_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(shop_id, customer_id)
);
```

## Usage Example

```python
from app.domains.ml.generators.user_feature_generator import UserFeatureGenerator

# Initialize generator
generator = UserFeatureGenerator()

# Prepare context data
context = {
    "orders": order_records,
    "customer_data": customer_record,
    "behavioral_events": interaction_records,
    "products": product_records
}

# Generate features
features = await generator.generate_features(
    shop_id="shop_123",
    customer_id="customer_456",
    context=context
)

# Features dictionary contains 40+ computed features
print(f"Generated {len(features)} features for customer {customer_id}")
```

## Current Status

### ✅ What's Working

- **Data Collection**: 381 customers successfully collected
- **Order Data**: 395 orders with customer associations
- **Product Data**: 350 products for preference analysis

### ⚠️ Current Issues

- **Low Feature Counts**: Only 1 user feature generated instead of 381
- **Missing Interaction Data**: No user_interactions data (0 records)

### 🎯 Expected Results After Fixes

- **User Features**: 381 records (one per customer)
- **Enhanced Features**: Better insights with interaction data

## Performance Considerations

- **Batch Processing**: Features computed in batches of 100-1000 customers
- **Incremental Updates**: Only processes changed data when possible
- **Parallel Processing**: Multiple customers processed concurrently
- **Database Optimization**: Uses bulk upsert operations for efficiency

## Monitoring & Debugging

- **Feature Counts**: Monitor `user_features` table for expected record counts
- **Computation Logs**: Check logs for "Computing user features" messages
- **Data Quality**: Verify input data completeness before feature computation
- **Performance Metrics**: Track computation time and memory usage

---

_Last Updated: 2025-01-26_  
_Version: 1.0_
