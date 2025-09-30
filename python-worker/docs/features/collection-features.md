# Collection Features Documentation

## Overview

Collection Features provide comprehensive analytics for product collections, including performance metrics, engagement data, and content quality scores. These features help optimize collection strategies and improve product discoverability.

## Data Sources Required

The `CollectionFeatureGenerator` requires the following data sources:

| Data Source           | Table                           | Purpose                          | Required      |
| --------------------- | ------------------------------- | -------------------------------- | ------------- |
| **Collection Data**   | `collection_data`               | Collection metadata, content     | ✅ Required   |
| **Products**          | `product_data`                  | Products in collections          | ✅ Required   |
| **Orders**            | `order_data` + `line_item_data` | Purchase history, revenue data   | ⚠️ Optional\* |
| **Behavioral Events** | `user_interactions`             | User engagement with collections | ⚠️ Optional\* |

\*Optional sources provide enhanced features but computation can proceed without them.

## Collection Features Generated

The `CollectionFeatures` table contains **30+ computed features** across these categories:

### 📊 Basic Metrics

- `product_count` - Number of products in collection
- `is_automated` - Whether collection is automated or manual

### 👀 Engagement Metrics (30-day)

- `view_count_30d` - Collection page views
- `unique_viewers_30d` - Unique users who viewed collection

### 🎯 Performance Metrics

- `click_through_rate` - CTR from collection to products
- `bounce_rate` - Bounce rate for collection pages
- `avg_product_price` - Average price of products in collection
- `min_product_price` - Minimum product price
- `max_product_price` - Maximum product price
- `price_range` - Price range (max - min)
- `price_variance` - Price variation within collection
- `conversion_rate` - Collection to purchase conversion
- `revenue_contribution` - Revenue generated from collection

### 🏆 Top Performers

- `top_products` - Top performing products (JSON array)
- `top_vendors` - Top performing vendors (JSON array)

### 📈 Quality Scores

- `performance_score` - Overall performance score (0-100)
- `seo_score` - SEO optimization score (0-100)
- `image_score` - Image quality score (0-100)

### 🔧 Enhanced Features

- `handle_quality` - URL handle quality score
- `template_score` - Template usage score
- `seo_optimization_score` - SEO optimization level
- `collection_age` - Days since collection creation
- `update_frequency` - How often collection is updated
- `lifecycle_stage` - Collection lifecycle stage
- `maturity_score` - Collection maturity indicator

### 📝 Content Features

- `handle` - Collection handle/URL
- `template_suffix` - Custom template used
- `last_updated_days` - Days since last update
- `metafield_count` - Number of metafields
- `metafield_utilization` - Metafield usage score
- `extras_count` - Number of extra fields
- `extras_utilization` - Extra fields usage score

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        COLLECTION FEATURE COMPUTATION FLOW                      │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Raw Shopify     │───▶│ GraphQL/REST     │───▶│ Normalization   │
│ Collections API │    │ API Client       │    │ Service         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Raw Shopify     │───▶│ Product          │───▶│ Product         │
│ Products API    │    │ Processing       │    │ Normalization   │
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
                    │  │ collection_data │   │
                    │  │ - 6 collections │   │
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
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ user_interactions│   │
                    │  │ - 0 records*    │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │ CollectionFeatureGenerator│
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Basic           │   │
                    │  │ Collection      │   │
                    │  │ Features        │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Engagement      │   │
                    │  │ Metrics         │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Product         │   │
                    │  │ Metrics         │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Performance     │   │
                    │  │ Metrics         │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ SEO & Image     │   │
                    │  │ Scores          │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │   FEATURE TABLE         │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ collection_features│ │
                    │  │ - 30+ features  │   │
                    │  │ - 6 records     │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘

* Current data status from your database
```

## Field Mappings: Table Fields → Features

### Collection Data Fields Used

| Field             | Feature Generated                          | Purpose                |
| ----------------- | ------------------------------------------ | ---------------------- |
| `collection_id`   | All features                               | Primary identifier     |
| `title`           | Content analysis                           | Collection title       |
| `handle`          | `handle_quality`, `handle`                 | URL quality analysis   |
| `description`     | Content analysis                           | Collection description |
| `template_suffix` | `template_score`, `template_suffix`        | Template usage         |
| `seo_title`       | `seo_score`, `seo_optimization_score`      | SEO analysis           |
| `seo_description` | `seo_score`, `seo_optimization_score`      | SEO analysis           |
| `image_url`       | `image_score`                              | Image presence         |
| `image_alt`       | `image_score`                              | Image optimization     |
| `product_count`   | `product_count`                            | Collection size        |
| `is_automated`    | `is_automated`                             | Automation status      |
| `is_active`       | Status analysis                            | Collection status      |
| `metafields`      | `metafield_count`, `metafield_utilization` | Metadata analysis      |
| `extras`          | `extras_count`, `extras_utilization`       | Extra fields analysis  |
| `created_at`      | `collection_age`                           | Collection lifecycle   |
| `updated_at`      | `last_updated_days`, `update_frequency`    | Update patterns        |

### Product Data Fields Used

| Field         | Feature Generated                                                                              | Purpose               |
| ------------- | ---------------------------------------------------------------------------------------------- | --------------------- |
| `product_id`  | Product association                                                                            | Product linking       |
| `price`       | `avg_product_price`, `min_product_price`, `max_product_price`, `price_range`, `price_variance` | Price analysis        |
| `vendor`      | `top_vendors`                                                                                  | Vendor analysis       |
| `title`       | `top_products`                                                                                 | Product analysis      |
| `collections` | Collection association                                                                         | Collection membership |

### Order Data Fields Used

| Field                       | Feature Generated      | Purpose              |
| --------------------------- | ---------------------- | -------------------- |
| `order_id`                  | Order tracking         | Order identification |
| `total_price`               | `revenue_contribution` | Revenue analysis     |
| `created_at`                | Temporal analysis      | Order timing         |
| `line_item_data.product_id` | Product association    | Product linking      |
| `line_item_data.price`      | Revenue analysis       | Revenue calculation  |

### User Interaction Fields Used

| Field           | Feature Generated                      | Purpose             |
| --------------- | -------------------------------------- | ------------------- |
| `collection_id` | Collection association                 | Collection linking  |
| `event_type`    | `view_count_30d`, `unique_viewers_30d` | Engagement analysis |
| `created_at`    | Temporal analysis                      | Interaction timing  |
| `user_id`       | `unique_viewers_30d`                   | User analysis       |

## Feature Computation Process

### Step 1: Data Collection

```python
# Context data passed to CollectionFeatureGenerator
context = {
    "shop": {...},              # Shop data
    "products": [...],          # From product_data table
    "behavioral_events": [...], # From user_interactions table
    "order_data": [...]         # From order_data + line_item_data
}
```

### Step 2: Feature Categories Computation

1. **Basic Collection Features** (`_compute_basic_collection_features`)

   - Extracts collection metadata
   - Calculates product count
   - Determines automation status

2. **Engagement Metrics** (`_compute_engagement_metrics`)

   - Analyzes behavioral events for collection views
   - Calculates unique viewers
   - Computes engagement rates

3. **Product Metrics** (`_compute_product_metrics`)

   - Analyzes products within collection
   - Calculates price statistics
   - Computes product diversity metrics

4. **Performance Metrics** (`_compute_performance_metrics`)

   - Analyzes order data for collection performance
   - Calculates conversion rates
   - Computes revenue contribution

5. **SEO Score** (`_compute_seo_score`)

   - Evaluates SEO optimization
   - Analyzes title and description quality
   - Computes SEO score (0-100)

6. **Image Score** (`_compute_image_score`)

   - Evaluates image quality and presence
   - Analyzes image optimization
   - Computes image score (0-100)

7. **Collection Metadata** (`_compute_collection_metadata_features`)

   - Analyzes collection metadata
   - Computes handle quality
   - Evaluates template usage

8. **Lifecycle Features** (`_compute_collection_lifecycle_features`)

   - Calculates collection age
   - Computes update frequency
   - Determines lifecycle stage

9. **Performance Score** (`_compute_performance_score`)
   - Combines all metrics into composite score
   - Calculates overall performance (0-100)

### Step 3: Feature Aggregation

```python
features = {
    # Basic metrics
    "product_count": 25,
    "is_automated": False,

    # Engagement metrics
    "view_count_30d": 150,
    "unique_viewers_30d": 45,

    # Performance metrics
    "avg_product_price": 89.99,
    "price_range": 150.00,
    "conversion_rate": 0.08,
    "revenue_contribution": 1250.50,

    # Quality scores
    "performance_score": 75.5,
    "seo_score": 82,
    "image_score": 78,

    # Enhanced features
    "collection_age": 180,
    "update_frequency": 0.5,
    "lifecycle_stage": "mature",

    # ... 20+ more features
}
```

## Database Schema

### Input Tables (Main Data)

**collection_data**

```sql
CREATE TABLE collection_data (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    collection_id VARCHAR NOT NULL,
    title VARCHAR(500) NOT NULL,
    handle VARCHAR(255) NOT NULL,
    description TEXT,
    template_suffix VARCHAR(100),
    seo_title VARCHAR(500),
    seo_description TEXT,
    image_url VARCHAR(1000),
    image_alt VARCHAR(500),
    product_count INTEGER DEFAULT 0,
    is_automated BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    metafields JSON,
    extras JSON,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**product_data** (for products in collections)

```sql
CREATE TABLE product_data (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    product_id VARCHAR NOT NULL,
    title VARCHAR(500) NOT NULL,
    price FLOAT,
    vendor VARCHAR(255),
    product_type VARCHAR(100),
    collections JSON,  -- Collection IDs this product belongs to
    -- ... other product fields
);
```

### Output Table (Features)

**collection_features**

```sql
CREATE TABLE collection_features (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    collection_id VARCHAR NOT NULL,

    -- Basic metrics
    product_count INTEGER DEFAULT 0,
    is_automated BOOLEAN DEFAULT FALSE,

    -- Engagement metrics
    view_count_30d INTEGER DEFAULT 0,
    unique_viewers_30d INTEGER DEFAULT 0,

    -- Performance metrics
    click_through_rate FLOAT,
    bounce_rate FLOAT,
    avg_product_price FLOAT,
    conversion_rate FLOAT,
    revenue_contribution FLOAT,

    -- Quality scores
    performance_score FLOAT DEFAULT 0,
    seo_score INTEGER DEFAULT 0,
    image_score INTEGER DEFAULT 0,

    -- Enhanced features
    collection_age INTEGER,
    update_frequency FLOAT,
    lifecycle_stage VARCHAR(50),
    maturity_score FLOAT,

    -- Content features
    handle VARCHAR(255),
    template_suffix VARCHAR(100),
    metafield_count INTEGER DEFAULT 0,
    extras_count INTEGER DEFAULT 0,

    -- ... 20+ more feature columns

    last_computed_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(shop_id, collection_id)
);
```

## Usage Example

```python
from app.domains.ml.generators.collection_feature_generator import CollectionFeatureGenerator

# Initialize generator
generator = CollectionFeatureGenerator()

# Prepare context data
context = {
    "shop": shop_data,
    "products": product_records,
    "behavioral_events": interaction_records,
    "order_data": order_records
}

# Generate features
features = await generator.generate_features(
    collection=collection_record,
    context=context
)

# Features dictionary contains 30+ computed features
print(f"Generated {len(features)} features for collection {collection_id}")
```

## Current Status

### ✅ What's Working

- **Data Collection**: 6 collections successfully collected
- **Product Data**: 350 products with collection associations
- **Feature Generation**: 6 collection features generated correctly
- **Collections Fix**: Products now get collections data (fixed in this session)

### ⚠️ Current Issues

- **Missing Interaction Data**: No user_interactions data (0 records)
- **Limited Engagement Metrics**: No view/click data available

### 🎯 Expected Results After Fixes

- **Collection Features**: 6 records (already working correctly)
- **Enhanced Features**: Better engagement metrics with interaction data

## Performance Considerations

- **Batch Processing**: Features computed in batches of 10-50 collections
- **Incremental Updates**: Only processes changed data when possible
- **Parallel Processing**: Multiple collections processed concurrently
- **Database Optimization**: Uses bulk upsert operations for efficiency

## Monitoring & Debugging

- **Feature Counts**: Monitor `collection_features` table for expected record counts
- **Computation Logs**: Check logs for "Computing features for collection" messages
- **Data Quality**: Verify input data completeness before feature computation
- **Performance Metrics**: Track computation time and memory usage

---

_Last Updated: 2025-01-26_  
_Version: 1.0_
