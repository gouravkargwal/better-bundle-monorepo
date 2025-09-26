# Search Product Features Documentation

## Overview

Search Product Features analyze the relationship between search queries and product performance, including search-to-purchase conversion rates, search relevance scores, and search behavior patterns. These features help optimize search functionality and product discoverability.

## Data Sources Required

The `SearchProductFeatureGenerator` requires the following data sources:

| Data Source           | Table                           | Purpose                            | Required      |
| --------------------- | ------------------------------- | ---------------------------------- | ------------- |
| **User Interactions** | `user_interactions`             | Search queries, product views      | ✅ Required   |
| **Products**          | `product_data`                  | Product metadata, search relevance | ✅ Required   |
| **Orders**            | `order_data` + `line_item_data` | Purchase history, conversion data  | ⚠️ Optional\* |

\*Optional sources provide enhanced features but computation can proceed without them.

## Search Product Features Generated

The `SearchProductFeatures` table contains **20+ computed features** across these categories:

### 🔍 Search Performance

- `search_query` - The search query string
- `product_id` - The product being analyzed
- `search_impressions` - Number of times product appeared in search
- `search_clicks` - Number of clicks from search results
- `search_views` - Number of product page views from search
- `click_through_rate` - CTR from search results
- `search_to_view_rate` - Search to view conversion rate

### 🛒 Conversion Metrics

- `search_to_cart_rate` - Search to cart add conversion
- `search_to_purchase_rate` - Search to purchase conversion
- `search_revenue` - Revenue generated from search
- `search_conversion_value` - Average conversion value from search

### 📊 Search Relevance

- `search_relevance_score` - How relevant product is to query
- `query_product_match_score` - Query-product matching score
- `semantic_similarity` - Semantic similarity between query and product
- `keyword_coverage` - Keyword coverage in product data

### ⏰ Temporal Patterns

- `first_search_date` - First time product appeared in search
- `last_search_date` - Last time product appeared in search
- `search_frequency` - How often product appears in search
- `search_trend` - Trend in search performance
- `seasonal_search_pattern` - Seasonal search patterns

### 🎯 Search Behavior

- `query_length` - Length of search query
- `query_complexity` - Complexity of search query
- `search_intent` - Inferred search intent
- `product_rank_position` - Average rank position in search
- `search_competition_score` - Competition level for query

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      SEARCH PRODUCT FEATURE COMPUTATION FLOW                    │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ User            │───▶│ Search           │───▶│ Search          │
│ Interactions    │    │ Tracking         │    │ Storage         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Raw Shopify     │───▶│ Product          │───▶│ Product         │
│ Products API    │    │ Processing       │    │ Normalization   │
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
                    │  │ order_data      │   │
                    │  │ - 395 orders    │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ line_item_data  │   │
                    │  │ - 340 items     │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │ SearchProductFeatureGenerator│
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Search          │   │
                    │  │ Performance     │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Conversion      │   │
                    │  │ Metrics         │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Search          │   │
                    │  │ Relevance       │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Temporal        │   │
                    │  │ Patterns        │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Search          │   │
                    │  │ Behavior        │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │   FEATURE TABLE         │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ search_product_features││
                    │  │ - 20+ features  │   │
                    │  │ - 0 records*    │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘

* Current data status from your database
```

## Field Mappings: Table Fields → Features

### User Interactions Fields Used

| Field           | Feature Generated                                           | Purpose             |
| --------------- | ----------------------------------------------------------- | ------------------- |
| `search_query`  | All features                                                | Primary identifier  |
| `product_id`    | Product association                                         | Product linking     |
| `event_type`    | `search_impressions`, `search_clicks`, `search_views`       | Event counting      |
| `created_at`    | `first_search_date`, `last_search_date`, `search_frequency` | Temporal analysis   |
| `user_id`       | User analysis                                               | User identification |
| `device_type`   | Device analysis                                             | Device preferences  |
| `referrer_type` | Traffic source analysis                                     | Traffic source      |
| `view_duration` | Engagement analysis                                         | Interaction quality |

### Product Data Fields Used

| Field          | Feature Generated                                  | Purpose              |
| -------------- | -------------------------------------------------- | -------------------- |
| `product_id`   | Product association                                | Product linking      |
| `title`        | `query_product_match_score`, `semantic_similarity` | Content matching     |
| `description`  | `query_product_match_score`, `semantic_similarity` | Content matching     |
| `tags`         | `keyword_coverage`, `semantic_similarity`          | Tag matching         |
| `vendor`       | Vendor analysis                                    | Vendor information   |
| `product_type` | Category analysis                                  | Category information |
| `price`        | Price analysis                                     | Price information    |
| `handle`       | URL analysis                                       | URL information      |

### Order Data Fields Used

| Field                       | Feature Generated                           | Purpose              |
| --------------------------- | ------------------------------------------- | -------------------- |
| `order_id`                  | Order tracking                              | Order identification |
| `customer_id`               | Customer association                        | Customer linking     |
| `total_price`               | `search_revenue`, `search_conversion_value` | Revenue analysis     |
| `created_at`                | Conversion analysis                         | Conversion tracking  |
| `line_item_data.product_id` | Product association                         | Product linking      |
| `line_item_data.price`      | Revenue analysis                            | Revenue calculation  |

## Feature Computation Process

### Step 1: Data Collection

```python
# Context data passed to SearchProductFeatureGenerator
context = {
    "shop": {...},              # Shop data
    "behavioral_events": [...], # From user_interactions table
    "products": [...],          # From product_data table
    "orders": [...]             # From order_data + line_item_data
}
```

### Step 2: Feature Categories Computation

1. **Search Performance Analysis**

   - Analyzes search interactions for performance metrics
   - Calculates impressions, clicks, and views
   - Computes click-through rates

2. **Conversion Metrics Analysis**

   - Tracks search-to-purchase conversion
   - Calculates conversion rates and revenue
   - Computes conversion values

3. **Search Relevance Analysis**

   - Analyzes query-product matching
   - Calculates relevance scores
   - Computes semantic similarity

4. **Temporal Pattern Analysis**

   - Analyzes search patterns over time
   - Calculates search frequency and trends
   - Computes seasonal patterns

5. **Search Behavior Analysis**
   - Analyzes query characteristics
   - Calculates search intent and complexity
   - Computes competition scores

### Step 3: Feature Aggregation

```python
features = {
    # Search performance
    "search_query": "wireless headphones",
    "product_id": "prod_123",
    "search_impressions": 150,
    "search_clicks": 25,
    "search_views": 20,
    "click_through_rate": 0.17,
    "search_to_view_rate": 0.8,

    # Conversion metrics
    "search_to_cart_rate": 0.15,
    "search_to_purchase_rate": 0.05,
    "search_revenue": 89.99,
    "search_conversion_value": 89.99,

    # Search relevance
    "search_relevance_score": 0.85,
    "query_product_match_score": 0.9,
    "semantic_similarity": 0.8,
    "keyword_coverage": 0.75,

    # Temporal patterns
    "first_search_date": "2025-01-01",
    "last_search_date": "2025-01-25",
    "search_frequency": 0.3,
    "search_trend": 0.1,

    # Search behavior
    "query_length": 18,
    "query_complexity": 0.6,
    "search_intent": "purchase",
    "product_rank_position": 3.5,
    "search_competition_score": 0.7,

    # ... 5+ more features
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
    search_query VARCHAR(500),
    page_type VARCHAR(50),
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
    description TEXT,
    tags JSON,
    vendor VARCHAR(255),
    product_type VARCHAR(100),
    created_at TIMESTAMP
);
```

### Output Table (Features)

**search_product_features**

```sql
CREATE TABLE search_product_features (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    search_query VARCHAR(500) NOT NULL,
    product_id VARCHAR NOT NULL,

    -- Search performance
    search_impressions INTEGER DEFAULT 0,
    search_clicks INTEGER DEFAULT 0,
    search_views INTEGER DEFAULT 0,
    click_through_rate FLOAT,
    search_to_view_rate FLOAT,

    -- Conversion metrics
    search_to_cart_rate FLOAT,
    search_to_purchase_rate FLOAT,
    search_revenue FLOAT,
    search_conversion_value FLOAT,

    -- Search relevance
    search_relevance_score FLOAT,
    query_product_match_score FLOAT,
    semantic_similarity FLOAT,
    keyword_coverage FLOAT,

    -- Temporal patterns
    first_search_date TIMESTAMP,
    last_search_date TIMESTAMP,
    search_frequency FLOAT,
    search_trend FLOAT,
    seasonal_search_pattern FLOAT,

    -- Search behavior
    query_length INTEGER,
    query_complexity FLOAT,
    search_intent VARCHAR(50),
    product_rank_position FLOAT,
    search_competition_score FLOAT,

    last_computed_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(shop_id, search_query, product_id)
);
```

## Usage Example

```python
from app.domains.ml.generators.search_product_feature_generator import SearchProductFeatureGenerator

# Initialize generator
generator = SearchProductFeatureGenerator()

# Prepare context data
context = {
    "shop": shop_data,
    "behavioral_events": interaction_records,
    "products": product_records,
    "orders": order_records
}

# Generate features
features = await generator.generate_features(
    search_product_data={"searchQuery": "wireless headphones", "productId": "prod_123"},
    context=context
)

# Features dictionary contains 20+ computed features
print(f"Generated {len(features)} features for search-product combination")
```

## Current Status

### ✅ What's Working

- **Data Collection**: 350 products available for search analysis

### ⚠️ Current Issues

- **No Search Data**: 0 user_interactions records (no search tracking implemented)
- **No Features Generated**: 0 search product features (expected - no search data)

### 🎯 Expected Results After Fixes

- **Search Product Features**: 0 records (expected - no search data available)
- **Enhanced Features**: Will be available when search tracking is implemented

## Performance Considerations

- **Batch Processing**: Features computed in batches of 100-500 search-product pairs
- **Incremental Updates**: Only processes changed data when possible
- **Parallel Processing**: Multiple search-product pairs processed concurrently
- **Database Optimization**: Uses bulk upsert operations for efficiency

## Monitoring & Debugging

- **Feature Counts**: Monitor `search_product_features` table for expected record counts
- **Computation Logs**: Check logs for "Computing search-product features" messages
- **Data Quality**: Verify input data completeness before feature computation
- **Performance Metrics**: Track computation time and memory usage

---

_Last Updated: 2025-01-26_  
_Version: 1.0_
