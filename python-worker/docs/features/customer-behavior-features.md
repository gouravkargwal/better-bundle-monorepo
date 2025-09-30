# Customer Behavior Features Documentation

## Overview

Customer Behavior Features analyze customer behavioral patterns, including purchase behavior, engagement patterns, and behavioral segmentation. These features help understand customer preferences and predict future behavior.

## Data Sources Required

The `CustomerBehaviorFeatureGenerator` requires the following data sources:

| Data Source               | Table                   | Purpose                           | Required    |
| ------------------------- | ----------------------- | --------------------------------- | ----------- |
| **Customers**             | `customer_data`         | Customer demographics, attributes | ✅ Required |
| **User Interactions**     | `user_interactions`     | User engagement patterns          | ✅ Required |
| **User Sessions**         | `user_sessions`         | Session data, behavior patterns   | ✅ Required |
| **Purchase Attributions** | `purchase_attributions` | Purchase behavior analysis        | ✅ Required |

## Customer Behavior Features Generated

The `CustomerBehaviorFeatures` table contains **30+ computed features** across these categories:

### 🛒 Purchase Behavior

- `total_purchases` - Total number of purchases
- `avg_purchase_value` - Average purchase value
- `purchase_frequency` - Purchase frequency per month
- `purchase_consistency` - Consistency of purchase patterns
- `seasonal_purchase_pattern` - Seasonal buying patterns

### 👀 Engagement Behavior

- `total_sessions` - Total number of sessions
- `avg_session_duration` - Average session duration
- `page_views_per_session` - Average page views per session
- `engagement_score` - Overall engagement score
- `bounce_rate` - Session bounce rate

### 🔍 Search & Discovery

- `search_frequency` - How often customer searches
- `search_query_diversity` - Diversity of search queries
- `product_discovery_method` - How customer discovers products
- `category_exploration` - Category exploration behavior

### 🛍️ Shopping Patterns

- `cart_abandonment_rate` - Cart abandonment frequency
- `checkout_completion_rate` - Checkout completion rate
- `product_comparison_behavior` - Product comparison patterns
- `impulse_purchase_tendency` - Tendency for impulse purchases

### 📱 Device & Channel Behavior

- `preferred_device` - Preferred device type
- `channel_preference` - Preferred shopping channel
- `mobile_usage_pattern` - Mobile usage patterns
- `desktop_usage_pattern` - Desktop usage patterns

### ⏰ Temporal Behavior

- `preferred_shopping_time` - Preferred time to shop
- `shopping_day_preference` - Preferred days to shop
- `seasonal_behavior` - Seasonal shopping patterns
- `loyalty_trend` - Customer loyalty trend

### 🎯 Behavioral Segmentation

- `customer_segment` - Behavioral customer segment
- `risk_score` - Customer risk assessment
- `lifetime_value_prediction` - Predicted lifetime value
- `churn_probability` - Probability of churning

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    CUSTOMER BEHAVIOR FEATURE COMPUTATION FLOW                   │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Raw Shopify     │───▶│ Customer         │───▶│ Customer        │
│ Customers API   │    │ Processing       │    │ Normalization   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ User            │───▶│ Interaction      │───▶│ Behavioral      │
│ Interactions    │    │ Tracking         │    │ Event Storage   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ User            │───▶│ Session          │───▶│ Session         │
│ Sessions        │    │ Tracking         │    │ Storage         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Purchase        │───▶│ Attribution      │───▶│ Attribution     │
│ Attributions    │    │ Analysis         │    │ Storage         │
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
                    │  │ user_interactions│   │
                    │  │ - 0 records*    │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ user_sessions   │   │
                    │  │ - 0 records*    │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ purchase_attributions││
                    │  │ - 0 records*    │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │ CustomerBehaviorFeatureGenerator│
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Purchase        │   │
                    │  │ Behavior        │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Engagement      │   │
                    │  │ Behavior        │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Search &        │   │
                    │  │ Discovery       │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Shopping        │   │
                    │  │ Patterns        │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Behavioral      │   │
                    │  │ Segmentation    │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │   FEATURE TABLE         │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ customer_behavior_features││
                    │  │ - 30+ features  │   │
                    │  │ - 0 records*    │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘

* Current data status from your database
```

## Field Mappings: Table Fields → Features

### Customer Data Fields Used

| Field             | Feature Generated       | Purpose                 |
| ----------------- | ----------------------- | ----------------------- |
| `customer_id`     | All features            | Primary identifier      |
| `email`           | Customer identification | Customer linking        |
| `first_name`      | Customer identification | Customer linking        |
| `created_at`      | Customer lifecycle      | Account age             |
| `updated_at`      | Update patterns         | Account activity        |
| `tags`            | Customer segmentation   | Customer categorization |
| `metafields`      | Custom attributes       | Customer attributes     |
| `default_address` | Location analysis       | Geographic preferences  |
| `currency_code`   | Currency preferences    | Currency analysis       |
| `locale`          | Language preferences    | Language analysis       |

### User Interactions Fields Used

| Field           | Feature Generated                                    | Purpose             |
| --------------- | ---------------------------------------------------- | ------------------- |
| `customer_id`   | Customer association                                 | Customer linking    |
| `event_type`    | `search_frequency`, `search_query_diversity`         | Search behavior     |
| `page_type`     | `product_discovery_method`, `category_exploration`   | Discovery patterns  |
| `product_id`    | Product interaction analysis                         | Product preferences |
| `created_at`    | `preferred_shopping_time`, `shopping_day_preference` | Temporal behavior   |
| `view_duration` | `engagement_score`, `bounce_rate`                    | Engagement quality  |
| `device_type`   | `preferred_device`, `mobile_usage_pattern`           | Device preferences  |

### User Sessions Fields Used

| Field           | Feature Generated                                    | Purpose                |
| --------------- | ---------------------------------------------------- | ---------------------- |
| `customer_id`   | Customer association                                 | Customer linking       |
| `session_id`    | Session tracking                                     | Session identification |
| `start_time`    | `total_sessions`, `avg_session_duration`             | Session metrics        |
| `end_time`      | `avg_session_duration`                               | Session duration       |
| `device_type`   | `preferred_device`, `desktop_usage_pattern`          | Device preferences     |
| `browser_type`  | Browser preferences                                  | Browser analysis       |
| `referrer_type` | `channel_preference`                                 | Traffic source         |
| `created_at`    | `preferred_shopping_time`, `shopping_day_preference` | Temporal behavior      |

### Purchase Attributions Fields Used

| Field               | Feature Generated          | Purpose              |
| ------------------- | -------------------------- | -------------------- |
| `customer_id`       | Customer association       | Customer linking     |
| `order_id`          | Order tracking             | Order identification |
| `product_id`        | Product association        | Product linking      |
| `attribution_type`  | `product_discovery_method` | Discovery analysis   |
| `attribution_value` | Attribution analysis       | Attribution tracking |
| `created_at`        | Temporal analysis          | Attribution timing   |

## Feature Computation Process

### Step 1: Data Collection

```python
# Context data passed to CustomerBehaviorFeatureGenerator
context = {
    "shop": {...},                    # Shop data
    "user_interactions": [...],       # From user_interactions table
    "user_sessions": [...],           # From user_sessions table
    "purchase_attributions": [...]    # From purchase_attributions table
}
```

### Step 2: Feature Categories Computation

1. **Purchase Behavior Analysis**

   - Analyzes purchase history for patterns
   - Calculates purchase frequency and consistency
   - Computes seasonal purchase patterns

2. **Engagement Behavior Analysis**

   - Analyzes session data for engagement patterns
   - Calculates session duration and frequency
   - Computes engagement scores

3. **Search & Discovery Analysis**

   - Analyzes search behavior patterns
   - Calculates search frequency and diversity
   - Computes product discovery methods

4. **Shopping Pattern Analysis**

   - Analyzes shopping behavior patterns
   - Calculates cart abandonment and completion rates
   - Computes shopping preferences

5. **Device & Channel Analysis**

   - Analyzes device and channel preferences
   - Calculates usage patterns across devices
   - Computes channel preferences

6. **Temporal Behavior Analysis**

   - Analyzes time-based behavior patterns
   - Calculates preferred shopping times
   - Computes seasonal behavior patterns

7. **Behavioral Segmentation**
   - Combines all behavioral data
   - Calculates customer segments
   - Computes risk and loyalty scores

### Step 3: Feature Aggregation

```python
features = {
    # Purchase behavior
    "total_purchases": 15,
    "avg_purchase_value": 89.99,
    "purchase_frequency": 2.5,
    "purchase_consistency": 0.8,

    # Engagement behavior
    "total_sessions": 45,
    "avg_session_duration": 12.5,
    "engagement_score": 75.5,
    "bounce_rate": 0.2,

    # Search & discovery
    "search_frequency": 0.3,
    "search_query_diversity": 0.7,
    "product_discovery_method": "search",

    # Shopping patterns
    "cart_abandonment_rate": 0.3,
    "checkout_completion_rate": 0.7,
    "impulse_purchase_tendency": 0.4,

    # Behavioral segmentation
    "customer_segment": "loyal_customer",
    "risk_score": 0.2,
    "churn_probability": 0.1,

    # ... 20+ more features
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
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**user_interactions**

```sql
CREATE TABLE user_interactions (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    customer_id VARCHAR,
    event_type VARCHAR(50),
    page_type VARCHAR(50),
    product_id VARCHAR,
    search_query VARCHAR,
    created_at TIMESTAMP
);
```

**user_sessions**

```sql
CREATE TABLE user_sessions (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    customer_id VARCHAR,
    session_id VARCHAR NOT NULL,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    device_type VARCHAR(50),
    created_at TIMESTAMP
);
```

**purchase_attributions**

```sql
CREATE TABLE purchase_attributions (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    customer_id VARCHAR,
    order_id VARCHAR,
    attribution_source VARCHAR(100),
    attribution_medium VARCHAR(100),
    created_at TIMESTAMP
);
```

### Output Table (Features)

**customer_behavior_features**

```sql
CREATE TABLE customer_behavior_features (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    customer_id VARCHAR NOT NULL,

    -- Purchase behavior
    total_purchases INTEGER DEFAULT 0,
    avg_purchase_value FLOAT,
    purchase_frequency FLOAT,
    purchase_consistency FLOAT,
    seasonal_purchase_pattern FLOAT,

    -- Engagement behavior
    total_sessions INTEGER DEFAULT 0,
    avg_session_duration FLOAT,
    page_views_per_session FLOAT,
    engagement_score FLOAT,
    bounce_rate FLOAT,

    -- Search & discovery
    search_frequency FLOAT,
    search_query_diversity FLOAT,
    product_discovery_method VARCHAR(50),
    category_exploration FLOAT,

    -- Shopping patterns
    cart_abandonment_rate FLOAT,
    checkout_completion_rate FLOAT,
    product_comparison_behavior FLOAT,
    impulse_purchase_tendency FLOAT,

    -- Device & channel behavior
    preferred_device VARCHAR(50),
    channel_preference VARCHAR(50),
    mobile_usage_pattern FLOAT,
    desktop_usage_pattern FLOAT,

    -- Temporal behavior
    preferred_shopping_time INTEGER,
    shopping_day_preference INTEGER,
    seasonal_behavior FLOAT,
    loyalty_trend FLOAT,

    -- Behavioral segmentation
    customer_segment VARCHAR(50),
    risk_score FLOAT,
    lifetime_value_prediction FLOAT,
    churn_probability FLOAT,

    last_computed_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(shop_id, customer_id)
);
```

## Usage Example

```python
from app.domains.ml.generators.customer_behavior_feature_generator import CustomerBehaviorFeatureGenerator

# Initialize generator
generator = CustomerBehaviorFeatureGenerator()

# Prepare context data
context = {
    "shop": shop_data,
    "user_interactions": interaction_records,
    "user_sessions": session_records,
    "purchase_attributions": attribution_records
}

# Generate features
features = await generator.generate_features(
    customer=customer_record,
    context=context
)

# Features dictionary contains 30+ computed features
print(f"Generated {len(features)} features for customer {customer_id}")
```

## Current Status

### ✅ What's Working

- **Data Collection**: 381 customers available for analysis

### ⚠️ Current Issues

- **No Interaction Data**: 0 user_interactions records (no interaction tracking implemented)
- **No Session Data**: 0 user_sessions records (no session tracking implemented)
- **No Attribution Data**: 0 purchase_attributions records (no attribution tracking implemented)
- **No Features Generated**: 0 customer behavior features (expected - no behavioral data)

### 🎯 Expected Results After Fixes

- **Customer Behavior Features**: 0 records (expected - no behavioral data available)
- **Enhanced Features**: Will be available when behavioral tracking is implemented

## Performance Considerations

- **Batch Processing**: Features computed in batches of 100-500 customers
- **Incremental Updates**: Only processes changed data when possible
- **Parallel Processing**: Multiple customers processed concurrently
- **Database Optimization**: Uses bulk upsert operations for efficiency

## Monitoring & Debugging

- **Feature Counts**: Monitor `customer_behavior_features` table for expected record counts
- **Computation Logs**: Check logs for "Computing customer behavior features" messages
- **Data Quality**: Verify input data completeness before feature computation
- **Performance Metrics**: Track computation time and memory usage

---

_Last Updated: 2025-01-26_  
_Version: 1.0_
