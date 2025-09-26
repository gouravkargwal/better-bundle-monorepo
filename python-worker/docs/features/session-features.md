# Session Features Documentation

## Overview

Session Features analyze individual user sessions, including session duration, page views, interactions, and conversion patterns. These features help understand user behavior and optimize the shopping experience.

## Data Sources Required

The `SessionFeatureGenerator` requires the following data sources:

| Data Source           | Table               | Purpose                       | Required      |
| --------------------- | ------------------- | ----------------------------- | ------------- |
| **User Sessions**     | `user_sessions`     | Session data, duration, pages | ✅ Required   |
| **User Interactions** | `user_interactions` | Session events, interactions  | ✅ Required   |
| **Orders**            | `order_data`        | Session conversion data       | ⚠️ Optional\* |

\*Optional sources provide enhanced features but computation can proceed without them.

## Session Features Generated

The `SessionFeatures` table contains **25+ computed features** across these categories:

### ⏱️ Session Duration & Timing

- `session_duration_minutes` - Total session duration in minutes
- `session_start_time` - Session start timestamp
- `session_end_time` - Session end timestamp
- `time_of_day` - Hour of day when session started
- `day_of_week` - Day of week when session started

### 📄 Page & View Metrics

- `total_page_views` - Total number of page views
- `unique_pages_viewed` - Number of unique pages viewed
- `product_pages_viewed` - Number of product pages viewed
- `collection_pages_viewed` - Number of collection pages viewed
- `cart_pages_viewed` - Number of cart page views

### 🛒 Shopping Behavior

- `products_viewed` - Number of products viewed
- `products_added_to_cart` - Number of products added to cart
- `products_removed_from_cart` - Number of products removed from cart
- `cart_abandoned` - Whether cart was abandoned
- `checkout_started` - Whether checkout was started
- `order_completed` - Whether order was completed

### 🎯 Conversion Metrics

- `conversion_rate` - Session conversion rate
- `cart_conversion_rate` - Cart to purchase conversion
- `checkout_conversion_rate` - Checkout to purchase conversion
- `order_value` - Value of order (if completed)

### 🔍 Search & Navigation

- `search_queries_count` - Number of search queries
- `unique_search_queries` - Number of unique search queries
- `navigation_depth` - How deep user navigated
- `bounce_rate` - Whether session was a bounce

### 📱 Device & Technical

- `device_type` - Device type (mobile/desktop/tablet)
- `browser_type` - Browser used
- `referrer_type` - Traffic source type
- `is_returning_visitor` - Whether user is returning

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          SESSION FEATURE COMPUTATION FLOW                       │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ User            │───▶│ Session          │───▶│ Session         │
│ Interactions    │    │ Tracking         │    │ Storage         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Raw Shopify     │───▶│ Order Processing │───▶│ Order           │
│ Orders API      │    │ Service          │    │ Normalization   │
└─────────────────┘    └──────────────────┘    └─────────────────┘

                                │
                                ▼
                    ┌─────────────────────────┐
                    │     MAIN TABLES         │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ user_sessions   │   │
                    │  │ - 0 records*    │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ user_interactions│   │
                    │  │ - 0 records*    │   │
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
                    │  SessionFeatureGenerator│
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Session         │   │
                    │  │ Duration        │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Page & View     │   │
                    │  │ Metrics         │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Shopping        │   │
                    │  │ Behavior        │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Conversion      │   │
                    │  │ Metrics         │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │   FEATURE TABLE         │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ session_features│   │
                    │  │ - 25+ features  │   │
                    │  │ - 0 records*    │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘

* Current data status from your database
```

## Field Mappings: Table Fields → Features

### User Sessions Fields Used

| Field                  | Feature Generated            | Purpose            |
| ---------------------- | ---------------------------- | ------------------ |
| `session_id`           | All features                 | Primary identifier |
| `customer_id`          | Customer association         | Customer linking   |
| `start_time`           | `session_duration_minutes`   | Session duration   |
| `end_time`             | `session_duration_minutes`   | Session duration   |
| `device_type`          | `device_type`                | Device analysis    |
| `browser_type`         | `browser_type`               | Browser analysis   |
| `referrer_type`        | `referrer_type`              | Traffic source     |
| `is_returning_visitor` | `is_returning_visitor`       | Visitor type       |
| `created_at`           | `time_of_day`, `day_of_week` | Temporal analysis  |

### User Interactions Fields Used

| Field           | Feature Generated                                                     | Purpose             |
| --------------- | --------------------------------------------------------------------- | ------------------- |
| `session_id`    | Session association                                                   | Session linking     |
| `event_type`    | `total_page_views`, `product_pages_viewed`, `collection_pages_viewed` | Event counting      |
| `page_type`     | `unique_pages_viewed`, page type distribution                         | Page analysis       |
| `product_id`    | `products_viewed`, `products_added_to_cart`                           | Product interaction |
| `created_at`    | Temporal analysis                                                     | Interaction timing  |
| `view_duration` | Engagement analysis                                                   | Interaction quality |

### Order Data Fields Used

| Field              | Feature Generated                      | Purpose              |
| ------------------ | -------------------------------------- | -------------------- |
| `order_id`         | Order tracking                         | Order identification |
| `customer_id`      | Customer association                   | Customer linking     |
| `total_price`      | `order_value`                          | Order value          |
| `created_at`       | `order_completed`, conversion analysis | Conversion tracking  |
| `financial_status` | Payment analysis                       | Payment status       |

## Feature Computation Process

### Step 1: Data Collection

```python
# Context data passed to SessionFeatureGenerator
context = {
    "shop": {...},              # Shop data
    "order_data": [...],        # From order_data table
    "user_sessions": [...],     # From user_sessions table
    "user_interactions": [...]  # From user_interactions table
}
```

### Step 2: Feature Categories Computation

1. **Session Duration & Timing**

   - Calculates session duration from start/end times
   - Analyzes time patterns (hour, day of week)
   - Computes session timing features

2. **Page & View Metrics**

   - Counts total and unique page views
   - Analyzes page type distribution
   - Computes navigation patterns

3. **Shopping Behavior**

   - Tracks product interactions
   - Monitors cart behavior
   - Analyzes shopping patterns

4. **Conversion Metrics**

   - Calculates conversion rates
   - Tracks funnel progression
   - Computes order values

5. **Search & Navigation**

   - Analyzes search behavior
   - Computes navigation depth
   - Tracks user engagement

6. **Device & Technical**
   - Extracts device information
   - Analyzes traffic sources
   - Computes visitor patterns

### Step 3: Feature Aggregation

```python
features = {
    # Session duration
    "session_duration_minutes": 15.5,
    "time_of_day": 14,
    "day_of_week": 3,

    # Page metrics
    "total_page_views": 8,
    "unique_pages_viewed": 5,
    "product_pages_viewed": 3,

    # Shopping behavior
    "products_viewed": 5,
    "products_added_to_cart": 2,
    "cart_abandoned": False,
    "order_completed": True,

    # Conversion metrics
    "conversion_rate": 1.0,
    "order_value": 89.99,

    # ... 15+ more features
}
```

## Database Schema

### Input Tables (Main Data)

**user_sessions**

```sql
CREATE TABLE user_sessions (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    session_id VARCHAR NOT NULL,
    customer_id VARCHAR,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    device_type VARCHAR(50),
    browser_type VARCHAR(50),
    referrer_type VARCHAR(50),
    is_returning_visitor BOOLEAN,
    created_at TIMESTAMP
);
```

**user_interactions**

```sql
CREATE TABLE user_interactions (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    session_id VARCHAR,
    customer_id VARCHAR,
    event_type VARCHAR(50),
    page_type VARCHAR(50),
    product_id VARCHAR,
    collection_id VARCHAR,
    search_query VARCHAR,
    created_at TIMESTAMP
);
```

### Output Table (Features)

**session_features**

```sql
CREATE TABLE session_features (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    session_id VARCHAR NOT NULL,
    customer_id VARCHAR,

    -- Session duration & timing
    session_duration_minutes FLOAT,
    session_start_time TIMESTAMP,
    session_end_time TIMESTAMP,
    time_of_day INTEGER,
    day_of_week INTEGER,

    -- Page & view metrics
    total_page_views INTEGER DEFAULT 0,
    unique_pages_viewed INTEGER DEFAULT 0,
    product_pages_viewed INTEGER DEFAULT 0,
    collection_pages_viewed INTEGER DEFAULT 0,

    -- Shopping behavior
    products_viewed INTEGER DEFAULT 0,
    products_added_to_cart INTEGER DEFAULT 0,
    products_removed_from_cart INTEGER DEFAULT 0,
    cart_abandoned BOOLEAN DEFAULT FALSE,
    order_completed BOOLEAN DEFAULT FALSE,

    -- Conversion metrics
    conversion_rate FLOAT,
    cart_conversion_rate FLOAT,
    order_value FLOAT,

    -- Search & navigation
    search_queries_count INTEGER DEFAULT 0,
    unique_search_queries INTEGER DEFAULT 0,
    navigation_depth INTEGER DEFAULT 0,
    bounce_rate BOOLEAN DEFAULT FALSE,

    -- Device & technical
    device_type VARCHAR(50),
    browser_type VARCHAR(50),
    referrer_type VARCHAR(50),
    is_returning_visitor BOOLEAN,

    last_computed_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(shop_id, session_id)
);
```

## Usage Example

```python
from app.domains.ml.generators.session_feature_generator import SessionFeatureGenerator

# Initialize generator
generator = SessionFeatureGenerator()

# Prepare context data
context = {
    "shop": shop_data,
    "order_data": order_records,
    "user_sessions": session_records,
    "user_interactions": interaction_records
}

# Generate features
features = await generator.generate_features(
    session_data=session_record,
    context=context
)

# Features dictionary contains 25+ computed features
print(f"Generated {len(features)} features for session {session_id}")
```

## Current Status

### ✅ What's Working

- **Data Collection**: 395 orders available for conversion tracking

### ⚠️ Current Issues

- **No Session Data**: 0 user_sessions records (no session tracking implemented)
- **No Interaction Data**: 0 user_interactions records (no interaction tracking implemented)
- **No Features Generated**: 0 session features (expected - no session data)

### 🎯 Expected Results After Fixes

- **Session Features**: 0 records (expected - no session tracking implemented)
- **Enhanced Features**: Will be available when session tracking is implemented

## Performance Considerations

- **Batch Processing**: Features computed in batches of 100-500 sessions
- **Incremental Updates**: Only processes changed data when possible
- **Parallel Processing**: Multiple sessions processed concurrently
- **Database Optimization**: Uses bulk upsert operations for efficiency

## Monitoring & Debugging

- **Feature Counts**: Monitor `session_features` table for expected record counts
- **Computation Logs**: Check logs for "Computing session features" messages
- **Data Quality**: Verify input data completeness before feature computation
- **Performance Metrics**: Track computation time and memory usage

---

_Last Updated: 2025-01-26_  
_Version: 1.0_
