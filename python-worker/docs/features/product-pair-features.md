# Product Pair Features Documentation

## Overview

Product Pair Features analyze relationships between products, including co-purchase patterns, product associations, and cross-selling opportunities. These features help identify which products are frequently bought together and optimize product recommendations.

## Data Sources Required

The `ProductPairFeatureGenerator` requires the following data sources:

| Data Source           | Table                           | Purpose                      | Required      |
| --------------------- | ------------------------------- | ---------------------------- | ------------- |
| **Orders**            | `order_data` + `line_item_data` | Co-purchase patterns         | ✅ Required   |
| **Products**          | `product_data`                  | Product metadata, categories | ✅ Required   |
| **Behavioral Events** | `user_interactions`             | Product view patterns        | ⚠️ Optional\* |

\*Optional sources provide enhanced features but computation can proceed without them.

## Product Pair Features Generated

The `ProductPairFeatures` table contains **20+ computed features** across these categories:

### 🔗 Association Metrics

- `co_purchase_count` - Number of times products bought together
- `co_purchase_frequency` - Frequency of co-purchases
- `support` - Support value for association rule
- `confidence` - Confidence in association rule
- `lift` - Lift value for association rule

### 📊 Product Similarity

- `category_similarity` - Category overlap between products
- `vendor_similarity` - Vendor overlap between products
- `price_similarity` - Price range similarity
- `tag_similarity` - Tag overlap between products

### 🎯 Cross-Sell Potential

- `cross_sell_score` - Cross-selling potential (0-100)
- `recommendation_strength` - Recommendation strength score
- `complementary_score` - How complementary the products are

### ⏰ Temporal Patterns

- `first_co_purchase_date` - First time products bought together
- `last_co_purchase_date` - Last time products bought together
- `co_purchase_trend` - Trend in co-purchase frequency

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        PRODUCT PAIR FEATURE COMPUTATION FLOW                    │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Raw Shopify     │───▶│ Order Processing │───▶│ Order           │
│ Orders API      │    │ Service          │    │ Normalization   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Raw Shopify     │───▶│ Product          │───▶│ Product         │
│ Products API    │    │ Processing       │    │ Normalization   │
└─────────────────┘    └──────────────────┘    └─────────────────┘

                                │
                                ▼
                    ┌─────────────────────────┐
                    │     MAIN TABLES         │
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
                    └─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │ ProductPairFeatureGenerator│
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Co-purchase     │   │
                    │  │ Analysis        │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Association     │   │
                    │  │ Rules           │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Similarity      │   │
                    │  │ Metrics         │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Cross-sell      │   │
                    │  │ Scoring         │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │   FEATURE TABLE         │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ product_pair_features││
                    │  │ - 20+ features  │   │
                    │  │ - Variable count│   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘
```

## Field Mappings: Table Fields → Features

### Order Data Fields Used

| Field                       | Feature Generated                                                      | Purpose              |
| --------------------------- | ---------------------------------------------------------------------- | -------------------- |
| `order_id`                  | Order grouping                                                         | Order identification |
| `customer_id`               | Customer analysis                                                      | Customer linking     |
| `created_at`                | `first_co_purchase_date`, `last_co_purchase_date`, `co_purchase_trend` | Temporal analysis    |
| `line_item_data.product_id` | Product association                                                    | Product linking      |
| `line_item_data.quantity`   | Purchase volume                                                        | Quantity analysis    |
| `line_item_data.price`      | Price analysis                                                         | Price tracking       |

### Product Data Fields Used

| Field          | Feature Generated     | Purpose                |
| -------------- | --------------------- | ---------------------- |
| `product_id`   | Product association   | Product linking        |
| `vendor`       | `vendor_similarity`   | Vendor comparison      |
| `product_type` | `category_similarity` | Category comparison    |
| `price`        | `price_similarity`    | Price comparison       |
| `tags`         | `tag_similarity`      | Tag comparison         |
| `title`        | Product analysis      | Product identification |
| `description`  | Content analysis      | Product content        |

### User Interaction Fields Used

| Field        | Feature Generated   | Purpose              |
| ------------ | ------------------- | -------------------- |
| `product_id` | Product association | Product linking      |
| `event_type` | Co-view analysis    | Interaction patterns |
| `created_at` | Temporal analysis   | Interaction timing   |
| `user_id`    | User analysis       | User behavior        |

## Feature Computation Process

### Step 1: Data Collection

```python
# Context data passed to ProductPairFeatureGenerator
context = {
    "orders": [...],            # From order_data + line_item_data
    "products": [...],          # From product_data table
    "behavioral_events": [...]  # From user_interactions table
}
```

### Step 2: Feature Categories Computation

1. **Co-purchase Analysis**

   - Analyzes order data for products bought together
   - Calculates co-purchase frequency and patterns
   - Identifies strong product associations

2. **Association Rules**

   - Computes support, confidence, and lift values
   - Identifies meaningful product relationships
   - Filters out weak associations

3. **Similarity Metrics**

   - Analyzes product metadata for similarities
   - Computes category, vendor, price, and tag overlap
   - Calculates similarity scores

4. **Cross-sell Scoring**
   - Combines co-purchase and similarity data
   - Computes cross-sell potential scores
   - Identifies complementary products

### Step 3: Feature Aggregation

```python
features = {
    # Association metrics
    "co_purchase_count": 15,
    "co_purchase_frequency": 0.08,
    "support": 0.05,
    "confidence": 0.75,
    "lift": 2.5,

    # Similarity metrics
    "category_similarity": 0.8,
    "vendor_similarity": 0.0,
    "price_similarity": 0.6,

    # Cross-sell potential
    "cross_sell_score": 85.5,
    "recommendation_strength": 0.9,
    "complementary_score": 0.7,

    # ... 10+ more features
}
```

## Database Schema

### Input Tables (Main Data)

**order_data + line_item_data**

```sql
CREATE TABLE order_data (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    order_id VARCHAR NOT NULL,
    customer_id VARCHAR,
    created_at TIMESTAMP
);

CREATE TABLE line_item_data (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    order_id VARCHAR NOT NULL,
    product_id VARCHAR,
    variant_id VARCHAR,
    quantity INTEGER,
    price FLOAT
);
```

### Output Table (Features)

**product_pair_features**

```sql
CREATE TABLE product_pair_features (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    product_id_1 VARCHAR NOT NULL,
    product_id_2 VARCHAR NOT NULL,

    -- Association metrics
    co_purchase_count INTEGER DEFAULT 0,
    co_purchase_frequency FLOAT,
    support FLOAT,
    confidence FLOAT,
    lift FLOAT,

    -- Similarity metrics
    category_similarity FLOAT,
    vendor_similarity FLOAT,
    price_similarity FLOAT,
    tag_similarity FLOAT,

    -- Cross-sell potential
    cross_sell_score FLOAT DEFAULT 0,
    recommendation_strength FLOAT,
    complementary_score FLOAT,

    -- Temporal patterns
    first_co_purchase_date TIMESTAMP,
    last_co_purchase_date TIMESTAMP,
    co_purchase_trend FLOAT,

    last_computed_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(shop_id, product_id_1, product_id_2)
);
```

## Usage Example

```python
from app.domains.ml.generators.product_pair_feature_generator import ProductPairFeatureGenerator

# Initialize generator
generator = ProductPairFeatureGenerator()

# Prepare context data
context = {
    "orders": order_records,
    "products": product_records,
    "behavioral_events": interaction_records
}

# Generate features for product pair
features = await generator.generate_features(
    product_pair_data={"product_id_1": "prod_123", "product_id_2": "prod_456"},
    context=context
)

# Features dictionary contains 20+ computed features
print(f"Generated {len(features)} features for product pair")
```

## Current Status

### ✅ What's Working

- **Data Collection**: 395 orders, 340 line items available
- **Product Data**: 350 products for pair analysis

### ⚠️ Current Issues

- **No Features Generated**: 0 product pair features (expected - requires analysis)
- **Missing Interaction Data**: No user_interactions data (0 records)

### 🎯 Expected Results After Fixes

- **Product Pair Features**: Variable count based on co-purchase patterns
- **Enhanced Features**: Better insights with interaction data

## Performance Considerations

- **Batch Processing**: Features computed in batches of 100-500 pairs
- **Incremental Updates**: Only processes changed data when possible
- **Parallel Processing**: Multiple pairs processed concurrently
- **Database Optimization**: Uses bulk upsert operations for efficiency

## Monitoring & Debugging

- **Feature Counts**: Monitor `product_pair_features` table for expected record counts
- **Computation Logs**: Check logs for "Computing product pair features" messages
- **Data Quality**: Verify input data completeness before feature computation
- **Performance Metrics**: Track computation time and memory usage

---

_Last Updated: 2025-01-26_  
_Version: 1.0_
