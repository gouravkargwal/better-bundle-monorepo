# System Overview

## Architecture Overview

The BetterBundle feature computation system transforms raw Shopify data into machine learning features through a multi-stage pipeline.

## Complete Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           BETTERBUNDLE FEATURE COMPUTATION SYSTEM               │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Raw Shopify     │───▶│ GraphQL/REST     │───▶│ Normalization   │
│ Data (API)      │    │ API Client       │    │ Service         │
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
                    │  │ customer_data   │   │
                    │  │ - 381 customers │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ collection_data │   │
                    │  │ - 6 collections │   │
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
                    │  FEATURE GENERATORS     │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ ProductFeature  │   │
                    │  │ Generator       │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ UserFeature     │   │
                    │  │ Generator       │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ CollectionFeature│   │
                    │  │ Generator       │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Other Generators│   │
                    │  │ (5 more types)  │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │   FEATURE TABLES        │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ product_features│   │
                    │  │ - 50+ features  │   │
                    │  │ - 1 record*     │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ user_features   │   │
                    │  │ - 40+ features  │   │
                    │  │ - 1 record*     │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ collection_features│ │
                    │  │ - 30+ features  │   │
                    │  │ - 6 records     │   │
                    │  └─────────────────┘   │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Other Features  │   │
                    │  │ - 0 records*    │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘
                                │
                                ▼
                    ┌─────────────────────────┐
                    │    GORSE SYNC           │
                    │                         │
                    │  ┌─────────────────┐   │
                    │  │ Recommendation  │   │
                    │  │ Engine          │   │
                    │  └─────────────────┘   │
                    └─────────────────────────┘

* Current data status from your database
```

## Processing Modes

### Historical Processing

- **Trigger**: Onboarding analysis, manual triggers
- **Behavior**: Processes ALL available data from the beginning
- **Watermarks**: Reset to start from beginning
- **Batch Size**: Large (1,000-10,000 records)
- **Use Case**: Initial setup, full data refresh

### Incremental Processing

- **Trigger**: Webhooks, scheduled updates
- **Behavior**: Processes only NEW/CHANGED data since last run
- **Watermarks**: Used to track last processed timestamp
- **Batch Size**: Small (100-500 records)
- **Use Case**: Real-time updates, regular maintenance

## Data Sources

### Primary Sources (Required)

- **Products**: Product metadata, pricing, inventory
- **Orders**: Purchase history, revenue data
- **Customers**: Customer information, demographics
- **Collections**: Product categorization

### Secondary Sources (Optional)

- **User Interactions**: Page views, cart events, search queries
- **Sessions**: User session data
- **Behavioral Events**: User behavior patterns

## Feature Categories

### 1. Product Features (50+ features)

- **Engagement**: Views, carts, purchases (30-day)
- **Conversion**: Conversion rates, abandonment
- **Temporal**: Purchase timing, frequency
- **Pricing**: Price analysis, inventory turnover
- **Content**: Variants, images, SEO, media
- **Performance**: Popularity, trending scores
- **Refunds**: Refund rates, risk assessment

### 2. User Features (40+ features)

- **Purchase**: Total spent, order value, frequency
- **Temporal**: Days since orders, frequency patterns
- **Preferences**: Categories, vendors, price points
- **Demographics**: Location, age, verification status
- **Behavior**: Discount sensitivity, refund patterns
- **Health**: Customer health score, risk assessment

### 3. Collection Features (30+ features)

- **Performance**: Product count, engagement
- **Content**: Description, SEO, media
- **Temporal**: Creation, update patterns
- **Product Mix**: Category diversity, price ranges

### 4. Other Features

- **Product Pairs**: Product relationships, co-purchase
- **Sessions**: User session analytics
- **Customer Behavior**: Behavioral patterns
- **Interactions**: User interaction patterns
- **Search Products**: Search performance

## Performance Characteristics

### Batch Processing

- **Historical**: 1,000-10,000 records per batch
- **Incremental**: 100-500 records per batch
- **Parallel**: Multiple products processed concurrently
- **Database**: Bulk upsert operations for efficiency

### Memory Usage

- **Context Data**: Loaded per batch
- **Feature Computation**: In-memory processing
- **Database**: Connection pooling
- **Cleanup**: Automatic garbage collection

### Timing

- **Historical**: 5-15 minutes for full shop
- **Incremental**: 30 seconds to 2 minutes
- **Real-time**: < 10 seconds for single product
- **Scheduled**: Daily/hourly batch processing

## Monitoring & Debugging

### Key Metrics

- **Feature Counts**: Expected vs actual records
- **Processing Time**: Batch processing duration
- **Memory Usage**: Peak memory consumption
- **Error Rates**: Failed computations

### Logging

- **Info**: Processing progress, batch completion
- **Debug**: Feature computation details
- **Warning**: Expected issues (no data available)
- **Error**: Actual problems requiring attention

### Health Checks

- **Data Quality**: Input data completeness
- **Feature Freshness**: Last computation timestamps
- **System Health**: Database connections, memory
- **Performance**: Processing speed, bottlenecks

## Current Issues & Fixes

### ✅ Fixed Issues

- **Collections Field**: Products now get collections data
- **Feature Architecture**: Trigger once for all data types
- **Batch Sizes**: Increased for historical processing
- **Log Verbosity**: Reduced noise from expected warnings

### ⚠️ Remaining Issues

- **Low Feature Counts**: Only 1 product/user feature instead of 350/381
- **Missing Interaction Data**: No user interaction tracking
- **Topic Creation**: Kafka topics not found after creation
- **Timing Warnings**: Async function execution time exceeded

### 🎯 Expected Results

- **Product Features**: 350 records (one per product)
- **User Features**: 381 records (one per customer)
- **Collection Features**: 6 records (already working)
- **Other Features**: 0 records (expected - no interaction data)

---

_Last Updated: 2025-01-26_  
_Version: 1.0_
