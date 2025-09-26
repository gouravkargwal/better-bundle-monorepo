# Interaction Features Documentation

## Overview

Interaction Features analyze customer-product interactions, including view patterns, engagement metrics, and interaction quality scores. These features help understand how customers interact with products and optimize product recommendations.

## Data Sources Required

The `InteractionFeatureGenerator` requires the following data sources:

| Data Source           | Table                           | Purpose                           | Required      |
| --------------------- | ------------------------------- | --------------------------------- | ------------- |
| **User Interactions** | `user_interactions`             | Customer-product interactions     | ✅ Required   |
| **Products**          | `product_data`                  | Product metadata, categories      | ✅ Required   |
| **Customers**         | `customer_data`                 | Customer demographics, attributes | ✅ Required   |
| **Orders**            | `order_data` + `line_item_data` | Purchase history, conversion data | ⚠️ Optional\* |

\*Optional sources provide enhanced features but computation can proceed without them.

## Interaction Features Generated

The `InteractionFeatures` table contains **25+ computed features** across these categories:

### 👀 View & Engagement Metrics

- `total_views` - Total number of product views
- `unique_views` - Number of unique viewing sessions
- `view_duration_avg` - Average view duration
- `view_frequency` - How often customer views this product
- `engagement_score` - Overall engagement score

### 🛒 Shopping Behavior

- `cart_adds` - Number of times added to cart
- `cart_removes` - Number of times removed from cart
- `purchases` - Number of times purchased
- `cart_conversion_rate` - Cart add to purchase conversion
- `view_to_purchase_rate` - View to purchase conversion

### 🔍 Search & Discovery

- `search_views` - Views from search results
- `category_views` - Views from category pages
- `collection_views` - Views from collection pages
- `direct_views` - Direct product page views
- `referral_views` - Views from external referrals

### ⏰ Temporal Patterns

- `first_view_date` - First time product was viewed
- `last_view_date` - Last time product was viewed
- `view_recency` - Days since last view
- `view_consistency` - Consistency of viewing patterns
- `seasonal_view_pattern` - Seasonal viewing patterns

### 📱 Device & Channel

- `mobile_views` - Views from mobile devices
- `desktop_views` - Views from desktop devices
- `tablet_views` - Views from tablet devices
- `preferred_device` - Customer's preferred device
- `channel_preference` - Preferred viewing channel

### 🎯 Interaction Quality

- `interaction_quality_score` - Quality of interactions
- `intent_score` - Purchase intent score
- `loyalty_indicator` - Customer loyalty to product
- `recommendation_score` - Recommendation strength

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       INTERACTION FEATURE COMPUTATION FLOW                      │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ User            │───▶│ Interaction      │───▶│ Interaction     │
│ Interactions    │    │ Tracking         │    │ Storage         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Raw Shopify     │───▶│ Product          │───▶│ Product         │
│ Products API    │    │ Processing       │    │ Normalization   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Raw Shopify     │───▶│ Customer         │───▶│ Customer        │
│ Customers API   │    │ Processing       │    │ Normalization   │
└─────────────────┘    └──────────────────┘    └─────────────────┘

                                │
                                ▼
                    ┌─────────────────────────┐
                    │     MAIN TABLES         │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ user_interactions│   │
                    │  │ - 0 records*    │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ product_data    │   │
                    │  │ - 350 products  │   │
                    │  └─────────────────┘   │
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
                    └─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │ InteractionFeatureGenerator│
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ View &          │   │
                    │  │ Engagement      │   │
                    │  │ Metrics         │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Shopping        │   │
                    │  │ Behavior        │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Search &        │   │
                    │  │ Discovery       │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Temporal        │   │
                    │  │ Patterns        │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Interaction     │   │
                    │  │ Quality         │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │   FEATURE TABLE         │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ interaction_features││
                    │  │ - 25+ features  │   │
                    │  │ - 0 records*    │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘

* Current data status from your database
```

## Field Mappings: Table Fields → Features

### User Interactions Fields Used

| Field           | Feature Generated                                   | Purpose             |
| --------------- | --------------------------------------------------- | ------------------- |
| `customer_id`   | Customer association                                | Customer linking    |
| `product_id`    | Product association                                 | Product linking     |
| `event_type`    | `total_views`, `cart_adds`, `cart_removes`          | Event counting      |
| `created_at`    | `first_view_date`, `last_view_date`, `view_recency` | Temporal analysis   |
| `view_duration` | `view_duration_avg`, `engagement_score`             | Engagement quality  |
| `page_type`     | `search_views`, `category_views`, `direct_views`    | Discovery analysis  |
| `device_type`   | `mobile_views`, `desktop_views`, `preferred_device` | Device preferences  |
| `referrer_type` | `channel_preference`                                | Traffic source      |
| `user_id`       | User analysis                                       | User identification |

### Product Data Fields Used

| Field          | Feature Generated      | Purpose              |
| -------------- | ---------------------- | -------------------- |
| `product_id`   | Product association    | Product linking      |
| `title`        | Product identification | Product details      |
| `price`        | Price analysis         | Price information    |
| `vendor`       | Vendor analysis        | Vendor information   |
| `product_type` | Category analysis      | Category information |
| `tags`         | Tag analysis           | Product tags         |

### Customer Data Fields Used

| Field         | Feature Generated       | Purpose                 |
| ------------- | ----------------------- | ----------------------- |
| `customer_id` | Customer association    | Customer linking        |
| `email`       | Customer identification | Customer details        |
| `first_name`  | Customer identification | Customer details        |
| `created_at`  | Customer lifecycle      | Account age             |
| `tags`        | Customer segmentation   | Customer categorization |

### Order Data Fields Used

| Field                       | Feature Generated                      | Purpose              |
| --------------------------- | -------------------------------------- | -------------------- |
| `order_id`                  | Order tracking                         | Order identification |
| `customer_id`               | Customer association                   | Customer linking     |
| `total_price`               | `order_value`                          | Order value          |
| `created_at`                | `order_completed`, conversion analysis | Conversion tracking  |
| `line_item_data.product_id` | Product association                    | Product linking      |
| `line_item_data.quantity`   | Purchase volume                        | Quantity analysis    |

## Feature Computation Process

### Step 1: Data Collection

```python
# Context data passed to InteractionFeatureGenerator
context = {
    "shop": {...},              # Shop data
    "orders": [...],            # From order_data + line_item_data
    "behavioral_events": [...], # From user_interactions table
    "products": [...],          # From product_data table
    "customers": [...]          # From customer_data table
}
```

### Step 2: Feature Categories Computation

1. **View & Engagement Analysis**

   - Analyzes interaction data for view patterns
   - Calculates view duration and frequency
   - Computes engagement scores

2. **Shopping Behavior Analysis**

   - Tracks cart adds, removes, and purchases
   - Calculates conversion rates
   - Computes shopping behavior patterns

3. **Search & Discovery Analysis**

   - Analyzes how customers discover products
   - Calculates view sources (search, category, etc.)
   - Computes discovery patterns

4. **Temporal Pattern Analysis**

   - Analyzes viewing patterns over time
   - Calculates recency and consistency
   - Computes seasonal patterns

5. **Device & Channel Analysis**

   - Analyzes device preferences
   - Calculates channel usage patterns
   - Computes device-specific behavior

6. **Interaction Quality Analysis**
   - Combines all interaction data
   - Calculates interaction quality scores
   - Computes intent and loyalty indicators

### Step 3: Feature Aggregation

```python
features = {
    # View & engagement
    "total_views": 25,
    "unique_views": 15,
    "view_duration_avg": 45.5,
    "engagement_score": 75.5,

    # Shopping behavior
    "cart_adds": 3,
    "cart_removes": 1,
    "purchases": 1,
    "cart_conversion_rate": 0.33,
    "view_to_purchase_rate": 0.04,

    # Search & discovery
    "search_views": 10,
    "category_views": 8,
    "direct_views": 7,

    # Temporal patterns
    "first_view_date": "2025-01-01",
    "last_view_date": "2025-01-25",
    "view_recency": 1,
    "view_consistency": 0.8,

    # Device & channel
    "mobile_views": 15,
    "desktop_views": 10,
    "preferred_device": "mobile",

    # Interaction quality
    "interaction_quality_score": 82.5,
    "intent_score": 0.7,
    "recommendation_score": 0.8,

    # ... 10+ more features
}
```

## Database Schema

### Input Tables (Main Data)

**user_interactions**

```sql
CREATE TABLE user_interactions (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    customer_id VARCHAR,
    product_id VARCHAR,
    event_type VARCHAR(50),
    page_type VARCHAR(50),
    device_type VARCHAR(50),
    referrer_type VARCHAR(50),
    view_duration FLOAT,
    created_at TIMESTAMP
);
```

**product_data**

```sql
CREATE TABLE product_data (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    product_id VARCHAR NOT NULL,
    title VARCHAR(500) NOT NULL,
    price FLOAT,
    vendor VARCHAR(255),
    product_type VARCHAR(100),
    created_at TIMESTAMP
);
```

**customer_data**

```sql
CREATE TABLE customer_data (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    customer_id VARCHAR NOT NULL,
    email VARCHAR(255),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    created_at TIMESTAMP
);
```

### Output Table (Features)

**interaction_features**

```sql
CREATE TABLE interaction_features (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    customer_id VARCHAR NOT NULL,
    product_id VARCHAR NOT NULL,

    -- View & engagement metrics
    total_views INTEGER DEFAULT 0,
    unique_views INTEGER DEFAULT 0,
    view_duration_avg FLOAT,
    view_frequency FLOAT,
    engagement_score FLOAT,

    -- Shopping behavior
    cart_adds INTEGER DEFAULT 0,
    cart_removes INTEGER DEFAULT 0,
    purchases INTEGER DEFAULT 0,
    cart_conversion_rate FLOAT,
    view_to_purchase_rate FLOAT,

    -- Search & discovery
    search_views INTEGER DEFAULT 0,
    category_views INTEGER DEFAULT 0,
    collection_views INTEGER DEFAULT 0,
    direct_views INTEGER DEFAULT 0,
    referral_views INTEGER DEFAULT 0,

    -- Temporal patterns
    first_view_date TIMESTAMP,
    last_view_date TIMESTAMP,
    view_recency INTEGER,
    view_consistency FLOAT,
    seasonal_view_pattern FLOAT,

    -- Device & channel
    mobile_views INTEGER DEFAULT 0,
    desktop_views INTEGER DEFAULT 0,
    tablet_views INTEGER DEFAULT 0,
    preferred_device VARCHAR(50),
    channel_preference VARCHAR(50),

    -- Interaction quality
    interaction_quality_score FLOAT,
    intent_score FLOAT,
    loyalty_indicator FLOAT,
    recommendation_score FLOAT,

    last_computed_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(shop_id, customer_id, product_id)
);
```

## Usage Example

```python
from app.domains.ml.generators.interaction_feature_generator import InteractionFeatureGenerator

# Initialize generator
generator = InteractionFeatureGenerator()

# Prepare context data
context = {
    "shop": shop_data,
    "orders": order_records,
    "behavioral_events": interaction_records,
    "products": product_records,
    "customers": customer_records
}

# Generate features
features = await generator.generate_features(
    customer_product_data={"customer_id": "cust_123", "product_id": "prod_456"},
    context=context
)

# Features dictionary contains 25+ computed features
print(f"Generated {len(features)} features for customer-product interaction")
```

## Current Status

### ✅ What's Working

- **Data Collection**: 350 products, 381 customers available for analysis

### ⚠️ Current Issues

- **No Interaction Data**: 0 user_interactions records (no interaction tracking implemented)
- **No Features Generated**: 0 interaction features (expected - no interaction data)

### 🎯 Expected Results After Fixes

- **Interaction Features**: 0 records (expected - no interaction data available)
- **Enhanced Features**: Will be available when interaction tracking is implemented

## Performance Considerations

- **Batch Processing**: Features computed in batches of 100-500 interactions
- **Incremental Updates**: Only processes changed data when possible
- **Parallel Processing**: Multiple interactions processed concurrently
- **Database Optimization**: Uses bulk upsert operations for efficiency

## Monitoring & Debugging

- **Feature Counts**: Monitor `interaction_features` table for expected record counts
- **Computation Logs**: Check logs for "Computing interaction features" messages
- **Data Quality**: Verify input data completeness before feature computation
- **Performance Metrics**: Track computation time and memory usage

---

_Last Updated: 2025-01-26_  
_Version: 1.0_
