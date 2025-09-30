# Feature Computation System Documentation

## Overview

The BetterBundle feature computation system transforms raw Shopify data into machine learning features for recommendation engines and analytics. This document explains the complete data flow from raw data to computed features.

## Data Flow Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Raw Shopify   │───▶│  Normalization   │───▶│  Main Tables    │───▶│ Feature Tables  │
│   Data (API)    │    │   (Canonical)    │    │  (Normalized)   │    │  (ML Features)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘    └─────────────────┘
```

## 1. Product Feature Computation

### Data Sources Required

The `ProductFeatureGenerator` requires the following data sources:

| Data Source           | Table                           | Purpose                              | Required      |
| --------------------- | ------------------------------- | ------------------------------------ | ------------- |
| **Product Data**      | `product_data`                  | Product metadata, pricing, inventory | ✅ Required   |
| **Orders**            | `order_data` + `line_item_data` | Purchase history, revenue data       | ✅ Required   |
| **Behavioral Events** | `user_interactions`             | User engagement (views, cart adds)   | ⚠️ Optional\* |
| **Collections**       | `collection_data`               | Product categorization               | ⚠️ Optional\* |

\*Optional sources provide enhanced features but computation can proceed without them.

### Product Features Generated

The `ProductFeatures` table contains **50+ computed features** across these categories:

#### 📊 Engagement Metrics (30-day)

- `view_count_30d` - Product page views
- `unique_viewers_30d` - Unique users who viewed
- `cart_add_count_30d` - Add to cart events
- `cart_view_count_30d` - Cart page views
- `cart_remove_count_30d` - Remove from cart events
- `purchase_count_30d` - Purchase events
- `unique_purchasers_30d` - Unique buyers

#### 🎯 Conversion Rates

- `view_to_cart_rate` - Views → Cart conversion
- `cart_to_purchase_rate` - Cart → Purchase conversion
- `overall_conversion_rate` - Views → Purchase conversion
- `cart_abandonment_rate` - Cart abandonment rate
- `cart_modification_rate` - Cart modification rate

#### ⏰ Temporal Features

- `last_viewed_at` - Last view timestamp
- `last_purchased_at` - Last purchase timestamp
- `first_purchased_at` - First purchase timestamp
- `days_since_first_purchase` - Days since first sale
- `days_since_last_purchase` - Days since last sale

#### 💰 Pricing & Inventory

- `avg_selling_price` - Average selling price
- `price_variance` - Price variation
- `total_inventory` - Current inventory
- `inventory_turnover` - Inventory turnover rate
- `stock_velocity` - Stock movement speed
- `price_tier` - Price category (low/medium/high)

#### 📝 Content Features

- `variant_complexity` - Number of variants
- `image_richness` - Number of images
- `tag_diversity` - Tag variety score
- `metafield_utilization` - Metafield usage
- `media_richness` - Media content score
- `seo_optimization` - SEO quality score

#### 🎬 Media Features

- `has_video_content` - Contains video
- `has_3d_content` - Contains 3D content
- `media_count` - Total media items
- `has_online_store_url` - Has store URL
- `has_preview_url` - Has preview URL

#### 📈 Performance Scores

- `popularity_score` - Overall popularity (0-100)
- `trending_score` - Trending indicator (0-100)

#### 💸 Refund Metrics

- `refunded_orders` - Number of refunded orders
- `refund_rate` - Refund percentage
- `total_refunded_amount` - Total refunded amount
- `net_revenue` - Revenue after refunds
- `refund_risk_score` - Refund risk indicator

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           PRODUCT FEATURE COMPUTATION FLOW                      │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Raw Shopify     │───▶│ GraphQL/REST     │───▶│ Normalization   │
│ Products API    │    │ API Client       │    │ Service         │
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
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ user_interactions│   │
                    │  │ - 0 records*    │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │  ProductFeatureGenerator │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ 30-Day Metrics  │   │
                    │  │ - Views, Carts  │   │
                    │  │ - Purchases     │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Conversion      │   │
                    │  │ Rates           │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Price &         │   │
                    │  │ Inventory       │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Performance     │   │
                    │  │ Scores          │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │   FEATURE TABLE         │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ product_features│   │
                    │  │ - 50+ features  │   │
                    │  │ - 1 record*     │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘

* Current data status from your database
```

## Field Mappings: Table Fields → Features

### Product Data Fields Used

| Field             | Feature Generated                              | Purpose                |
| ----------------- | ---------------------------------------------- | ---------------------- |
| `product_id`      | All features                                   | Primary identifier     |
| `title`           | `content_richness_score`                       | Title length analysis  |
| `description`     | `description_length`, `content_richness_score` | Content analysis       |
| `price`           | `avg_selling_price`, `price_tier`              | Pricing analysis       |
| `total_inventory` | `total_inventory`, `inventory_turnover`        | Inventory metrics      |
| `variants`        | `variant_complexity`                           | Product complexity     |
| `images`          | `image_richness`, `media_count`                | Media analysis         |
| `tags`            | `tag_diversity`                                | Tag variety            |
| `metafields`      | `metafield_utilization`                        | Metadata usage         |
| `collections`     | Collection association                         | Collection membership  |
| `created_at`      | `product_age`                                  | Product lifecycle      |
| `updated_at`      | `last_updated_days`, `update_frequency`        | Update patterns        |
| `status`          | `status_stability`                             | Status consistency     |
| `vendor`          | Vendor analysis                                | Vendor performance     |
| `product_type`    | Category analysis                              | Product categorization |

### Order Data Fields Used

| Field                       | Feature Generated                         | Purpose                |
| --------------------------- | ----------------------------------------- | ---------------------- |
| `order_id`                  | Purchase tracking                         | Order identification   |
| `customer_id`               | `unique_purchasers_30d`                   | Customer analysis      |
| `total_price`               | `avg_selling_price`, `net_revenue`        | Revenue analysis       |
| `created_at`                | `purchase_count_30d`, `last_purchased_at` | Temporal analysis      |
| `financial_status`          | Refund analysis                           | Payment status         |
| `line_item_data.product_id` | Product association                       | Product linking        |
| `line_item_data.quantity`   | Purchase volume                           | Quantity analysis      |
| `line_item_data.price`      | Price analysis                            | Selling price tracking |

### User Interaction Fields Used

| Field           | Feature Generated                      | Purpose             |
| --------------- | -------------------------------------- | ------------------- |
| `product_id`    | Product association                    | Product linking     |
| `event_type`    | `view_count_30d`, `cart_add_count_30d` | Event counting      |
| `created_at`    | `last_viewed_at`, temporal metrics     | Time analysis       |
| `user_id`       | `unique_viewers_30d`                   | User analysis       |
| `view_duration` | Engagement analysis                    | Interaction quality |

### Collection Data Fields Used

| Field           | Feature Generated      | Purpose            |
| --------------- | ---------------------- | ------------------ |
| `collection_id` | Collection association | Collection linking |
| `product_count` | Collection size        | Collection metrics |

### Feature Computation Process

#### Step 1: Data Collection

```python
# Context data passed to ProductFeatureGenerator
context = {
    "product_data": {...},      # From product_data table
    "orders": [...],            # From order_data + line_item_data
    "behavioral_events": [...], # From user_interactions table
    "collections": [...]        # From collection_data table
}
```

#### Step 2: Feature Categories Computation

1. **30-Day Metrics** (`_compute_30day_metrics`)

   - Analyzes behavioral events for last 30 days
   - Counts views, cart adds, purchases
   - Calculates unique user metrics

2. **Conversion Metrics** (`_compute_conversion_metrics`)

   - Computes conversion rates from 30-day metrics
   - Calculates abandonment rates
   - Determines funnel performance

3. **Temporal Metrics** (`_compute_temporal_metrics`)

   - Analyzes order history for timing patterns
   - Calculates days since first/last purchase
   - Tracks purchase frequency

4. **Price & Inventory** (`_compute_price_inventory_metrics`)

   - Analyzes order data for pricing patterns
   - Calculates average selling price
   - Computes inventory turnover

5. **Metadata Scores** (`_compute_metadata_scores`)

   - Analyzes product metadata (variants, images, tags)
   - Computes content richness scores
   - Evaluates SEO optimization

6. **Performance Scores** (`_compute_popularity_trending_scores`)

   - Combines engagement and temporal metrics
   - Calculates popularity score (0-100)
   - Determines trending score (0-100)

7. **Refund Metrics** (`_compute_refund_metrics`)
   - Analyzes refund data from orders
   - Calculates refund rates and amounts
   - Computes refund risk scores

#### Step 3: Feature Aggregation

```python
features = {
    # 30-day engagement metrics
    "view_count_30d": 150,
    "unique_viewers_30d": 45,
    "cart_add_count_30d": 12,
    "purchase_count_30d": 3,

    # Conversion rates
    "view_to_cart_rate": 0.08,  # 12/150
    "cart_to_purchase_rate": 0.25,  # 3/12
    "overall_conversion_rate": 0.02,  # 3/150

    # Performance scores
    "popularity_score": 75.5,
    "trending_score": 82.3,

    # ... 40+ more features
}
```

### Database Schema

#### Input Tables (Main Data)

**product_data**

```sql
CREATE TABLE product_data (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    product_id VARCHAR NOT NULL,
    title VARCHAR(500) NOT NULL,
    handle VARCHAR(255) NOT NULL,
    description TEXT,
    vendor VARCHAR(255),
    product_type VARCHAR(100),
    price FLOAT,
    total_inventory INTEGER,
    variants JSON,
    images JSON,
    collections JSON,  -- Collection IDs
    tags JSON,
    metafields JSON,
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
    created_at TIMESTAMP
);

CREATE TABLE line_item_data (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    order_id VARCHAR NOT NULL,
    product_id VARCHAR,  -- Links to product_data.product_id
    variant_id VARCHAR,
    title VARCHAR(500),
    quantity INTEGER,
    price FLOAT
);
```

**user_interactions** (Optional)

```sql
CREATE TABLE user_interactions (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    product_id VARCHAR,
    event_type VARCHAR,  -- 'view', 'cart_add', 'cart_remove', 'purchase'
    user_id VARCHAR,
    created_at TIMESTAMP
);
```

#### Output Table (Features)

**product_features**

```sql
CREATE TABLE product_features (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    product_id VARCHAR NOT NULL,

    -- Engagement metrics (30-day)
    view_count_30d INTEGER DEFAULT 0,
    unique_viewers_30d INTEGER DEFAULT 0,
    cart_add_count_30d INTEGER DEFAULT 0,
    purchase_count_30d INTEGER DEFAULT 0,

    -- Conversion rates
    view_to_cart_rate FLOAT,
    cart_to_purchase_rate FLOAT,
    overall_conversion_rate FLOAT,

    -- Performance scores
    popularity_score FLOAT DEFAULT 0,
    trending_score FLOAT DEFAULT 0,

    -- Refund metrics
    refund_rate FLOAT DEFAULT 0.0,
    net_revenue FLOAT DEFAULT 0.0,

    -- ... 40+ more feature columns

    last_computed_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(shop_id, product_id)
);
```

### Usage Example

```python
from app.domains.ml.generators.product_feature_generator import ProductFeatureGenerator

# Initialize generator
generator = ProductFeatureGenerator()

# Prepare context data
context = {
    "product_data": product_record,
    "orders": order_records,
    "behavioral_events": interaction_records,
    "collections": collection_records
}

# Generate features
features = await generator.generate_features(
    shop_id="shop_123",
    product_id="product_456",
    context=context
)

# Features dictionary contains 50+ computed features
print(f"Generated {len(features)} features for product {product_id}")
```

### Performance Considerations

- **Batch Processing**: Features are computed in batches of 100-1000 products
- **Incremental Updates**: Only processes changed data when possible
- **Parallel Processing**: Multiple products processed concurrently
- **Database Optimization**: Uses bulk upsert operations for efficiency

### Monitoring & Debugging

- **Feature Counts**: Monitor `product_features` table for expected record counts
- **Computation Logs**: Check logs for "Computing product features" messages
- **Data Quality**: Verify input data completeness before feature computation
- **Performance Metrics**: Track computation time and memory usage

## Current Status & Issues

### ✅ What's Working

- **Data Collection**: 350 products, 395 orders, 340 line items successfully collected
- **Normalization**: Raw data properly normalized into main tables
- **Collections Fix**: Products now get collections data (fixed in this session)

### ⚠️ Current Issues

- **Low Feature Counts**: Only 1 product feature generated instead of 350
- **Missing Interaction Data**: No user_interactions data (0 records)
- **Feature Computation**: Not processing all available data

### 🔧 Root Causes

1. **Architecture Change**: Feature computation was triggered separately for each data type
2. **Batch Size**: Small batch sizes (100-300) instead of processing all data
3. **Missing Data**: No user interaction tracking implemented yet

### 🎯 Expected Results After Fixes

- **Product Features**: 350 records (one per product)
- **User Features**: 381 records (one per customer)
- **Collection Features**: 6 records (already working)
- **Other Features**: 0 records (expected - no interaction data)

---

## Next: User Features, Collection Features, and More

This document covers **Product Features** in detail. The system also generates:

- **User Features** (Customer analytics)
- **Collection Features** (Collection performance)
- **Product Pair Features** (Product relationships)
- **Session Features** (User session analytics)
- **Customer Behavior Features** (Behavioral patterns)
- **Interaction Features** (User interaction patterns)
- **Search Product Features** (Search performance)

Each feature type follows a similar pattern but uses different input data and generates different output features.

---

_Last Updated: 2025-01-26_
_Version: 1.0_
