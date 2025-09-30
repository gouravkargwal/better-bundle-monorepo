# Data Sources Documentation

## Overview

This document provides a comprehensive overview of all data sources used in the BetterBundle feature computation system, including their purposes, schemas, and relationships.

## Data Source Categories

### 1. Raw Data Sources (Shopify API)

#### Products API

- **Purpose**: Product catalog, pricing, inventory, variants
- **Data Types**: Products, variants, images, collections, metafields
- **Update Frequency**: Real-time via webhooks, batch via GraphQL
- **Volume**: 350 products in current dataset

#### Orders API

- **Purpose**: Purchase history, customer orders, line items
- **Data Types**: Orders, line items, customers, shipping, payments
- **Update Frequency**: Real-time via webhooks
- **Volume**: 395 orders, 340 line items in current dataset

#### Customers API

- **Purpose**: Customer information, demographics, addresses
- **Data Types**: Customer profiles, addresses, metafields
- **Update Frequency**: Real-time via webhooks
- **Volume**: 381 customers in current dataset

#### Collections API

- **Purpose**: Product categorization, collection management
- **Data Types**: Collections, product associations, metafields
- **Update Frequency**: Real-time via webhooks
- **Volume**: 6 collections in current dataset

### 2. Normalized Data Sources (Main Tables)

#### product_data

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
    status VARCHAR(50),
    tags JSON,
    price FLOAT,
    compare_at_price FLOAT,
    total_inventory INTEGER,
    is_active BOOLEAN,
    variants JSON,
    images JSON,
    media JSON,
    options JSON,
    collections JSON,  -- Collection IDs
    seo_title VARCHAR(500),
    seo_description TEXT,
    template_suffix VARCHAR(100),
    metafields JSON,
    extras JSON,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

#### customer_data

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

#### collection_data

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

#### order_data

```sql
CREATE TABLE order_data (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    order_id VARCHAR NOT NULL,
    customer_id VARCHAR,
    total_price FLOAT,
    subtotal_price FLOAT,
    total_tax FLOAT,
    total_discounts FLOAT,
    currency VARCHAR(10),
    financial_status VARCHAR(50),
    fulfillment_status VARCHAR(50),
    processed_at TIMESTAMP,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

#### line_item_data

```sql
CREATE TABLE line_item_data (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    order_id VARCHAR NOT NULL,
    product_id VARCHAR,
    variant_id VARCHAR,
    title VARCHAR(500),
    quantity INTEGER,
    price FLOAT,
    total_discount FLOAT,
    vendor VARCHAR(255),
    product_type VARCHAR(100),
    created_at TIMESTAMP
);
```

### 3. Behavioral Data Sources (Not Yet Implemented)

#### user_interactions

```sql
CREATE TABLE user_interactions (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    customer_id VARCHAR,
    session_id VARCHAR,
    product_id VARCHAR,
    collection_id VARCHAR,
    event_type VARCHAR(50),  -- 'view', 'cart_add', 'cart_remove', 'purchase', 'search'
    page_type VARCHAR(50),   -- 'product', 'collection', 'search', 'cart'
    search_query VARCHAR(500),
    device_type VARCHAR(50),
    browser_type VARCHAR(50),
    referrer_type VARCHAR(50),
    view_duration FLOAT,
    created_at TIMESTAMP
);
```

#### user_sessions

```sql
CREATE TABLE user_sessions (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    customer_id VARCHAR,
    session_id VARCHAR NOT NULL,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    device_type VARCHAR(50),
    browser_type VARCHAR(50),
    referrer_type VARCHAR(50),
    is_returning_visitor BOOLEAN,
    created_at TIMESTAMP
);
```

#### purchase_attributions

```sql
CREATE TABLE purchase_attributions (
    id VARCHAR PRIMARY KEY,
    shop_id VARCHAR NOT NULL,
    customer_id VARCHAR,
    order_id VARCHAR,
    attribution_source VARCHAR(100),
    attribution_medium VARCHAR(100),
    attribution_campaign VARCHAR(100),
    attribution_content VARCHAR(100),
    attribution_term VARCHAR(100),
    created_at TIMESTAMP
);
```

## Data Relationships

### Primary Relationships

```
Shop (1) ──→ (N) Products
Shop (1) ──→ (N) Customers
Shop (1) ──→ (N) Collections
Shop (1) ──→ (N) Orders

Customer (1) ──→ (N) Orders
Order (1) ──→ (N) Line Items
Product (1) ──→ (N) Line Items
Collection (N) ──→ (N) Products
```

### Feature Computation Dependencies

```
Product Features:
├── product_data (required)
├── order_data + line_item_data (required)
├── user_interactions (optional)
└── collection_data (optional)

User Features:
├── customer_data (required)
├── order_data + line_item_data (required)
├── product_data (required)
└── user_interactions (optional)

Collection Features:
├── collection_data (required)
├── product_data (required)
├── order_data + line_item_data (optional)
└── user_interactions (optional)

Product Pair Features:
├── order_data + line_item_data (required)
├── product_data (required)
└── user_interactions (optional)

Session Features:
├── user_sessions (required)
├── user_interactions (required)
└── order_data (optional)

Customer Behavior Features:
├── customer_data (required)
├── user_interactions (required)
├── user_sessions (required)
└── purchase_attributions (required)

Interaction Features:
├── user_interactions (required)
├── product_data (required)
├── customer_data (required)
└── order_data + line_item_data (optional)

Search Product Features:
├── user_interactions (required)
├── product_data (required)
└── order_data + line_item_data (optional)
```

## Data Quality & Validation

### Required Fields

- **product_data**: product_id, title, handle, shop_id
- **customer_data**: customer_id, shop_id
- **collection_data**: collection_id, title, handle, shop_id
- **order_data**: order_id, shop_id
- **line_item_data**: order_id, shop_id

### Data Validation Rules

- **Unique Constraints**: product_id per shop, customer_id per shop, collection_id per shop
- **Foreign Key Constraints**: line_item_data.product_id → product_data.product_id
- **Data Types**: Proper JSON handling for arrays and objects
- **Timestamps**: Valid ISO format timestamps

### Data Completeness

- **Products**: 350/350 (100% complete)
- **Customers**: 381/381 (100% complete)
- **Collections**: 6/6 (100% complete)
- **Orders**: 395/395 (100% complete)
- **Line Items**: 340/340 (100% complete)
- **User Interactions**: 0/0 (not implemented)
- **User Sessions**: 0/0 (not implemented)
- **Purchase Attributions**: 0/0 (not implemented)

## Data Processing Pipeline

### 1. Data Collection

```
Shopify API → GraphQL/REST Client → Raw Data Storage
```

### 2. Normalization

```
Raw Data → Canonical Models → Main Tables
```

### 3. Feature Computation

```
Main Tables → Feature Generators → Feature Tables
```

### 4. ML Integration

```
Feature Tables → Gorse Sync → Recommendation Engine
```

## Performance Considerations

### Data Volume

- **Current**: ~1,500 records across all tables
- **Expected Growth**: 10x-100x with full interaction tracking
- **Storage**: ~100MB current, ~1-10GB with full data

### Processing Speed

- **Normalization**: 1-5 seconds per batch
- **Feature Computation**: 10-60 seconds per batch
- **Gorse Sync**: 5-30 seconds per batch

### Optimization Strategies

- **Batch Processing**: Process data in batches of 100-1000 records
- **Parallel Processing**: Multiple records processed concurrently
- **Incremental Updates**: Only process changed data
- **Database Indexing**: Optimized indexes for common queries

## Monitoring & Maintenance

### Data Quality Monitoring

- **Completeness**: Monitor for missing required fields
- **Consistency**: Validate foreign key relationships
- **Freshness**: Track data update timestamps
- **Accuracy**: Validate data against Shopify API

### Performance Monitoring

- **Processing Time**: Track normalization and feature computation time
- **Memory Usage**: Monitor memory consumption during processing
- **Database Performance**: Track query execution times
- **Error Rates**: Monitor failed processing attempts

### Maintenance Tasks

- **Data Cleanup**: Remove old or invalid data
- **Index Optimization**: Rebuild indexes for performance
- **Storage Management**: Archive old data if needed
- **Backup & Recovery**: Regular backups of critical data

---

_Last Updated: 2025-01-26_  
_Version: 1.0_
