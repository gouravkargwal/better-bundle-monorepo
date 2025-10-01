# Product Features Guide

## Overview

This guide explains how product features are calculated in the BetterBundle system. Product features are ML-ready metrics that help understand product performance, customer behavior, and business insights.

## What Are Product Features?

Product features are calculated metrics that describe:

- **How customers interact** with products (views, cart adds, purchases)
- **How well products convert** (conversion rates, funnels)
- **Business performance** (revenue, inventory, pricing)
- **Content quality** (SEO, media, metadata)

## Data Sources

Product features are calculated using these data sources:

### 1. **Product Data** (from Shopify)

```json
{
  "product_id": "123456789",
  "title": "Amazing T-Shirt",
  "price": 29.99,
  "total_inventory": 100,
  "variants": [...],
  "images": [...],
  "tags": ["clothing", "summer"],
  "description": "High quality cotton t-shirt"
}
```

### 2. **Order Data** (from Shopify)

```json
{
  "order_id": "987654321",
  "customer_id": "customer_123",
  "line_items": [
    {
      "product_id": "123456789",
      "quantity": 2,
      "price": 29.99
    }
  ],
  "created_at": "2023-01-15T10:30:00Z"
}
```

### 3. **User Interactions** (from tracking events)

```json
{
  "interactionType": "product_viewed",
  "customer_id": "customer_123",
  "product_id": "123456789",
  "created_at": "2023-01-15T10:00:00Z",
  "metadata": {
    "productVariant": {
      "product": {
        "id": "123456789"
      }
    }
  }
}
```

## Feature Categories

### 1. **Engagement Metrics** (30-day window)

These metrics track how customers interact with products:

| Feature                 | Description                           | Data Source       | Calculation                             |
| ----------------------- | ------------------------------------- | ----------------- | --------------------------------------- |
| `view_count_30d`        | Number of product views               | User Interactions | Count `product_viewed` events           |
| `unique_viewers_30d`    | Number of unique customers who viewed | User Interactions | Count unique `customer_id` in views     |
| `cart_add_count_30d`    | Number of times added to cart         | User Interactions | Count `product_added_to_cart` events    |
| `cart_view_count_30d`   | Number of cart views                  | User Interactions | Count `cart_viewed` events              |
| `purchase_count_30d`    | Number of purchases                   | Orders            | Sum `quantity` from line items          |
| `unique_purchasers_30d` | Number of unique buyers               | Orders            | Count unique `customer_id` in purchases |

**Example Calculation:**

```python
# For product "123456789" in last 30 days
view_count_30d = 150        # 150 people viewed this product
unique_viewers_30d = 120    # 120 unique customers viewed it
cart_add_count_30d = 45     # 45 times added to cart
purchase_count_30d = 12     # 12 units sold
```

### 2. **Conversion Metrics**

These metrics measure how well products convert customers:

| Feature                   | Description                          | Formula                     |
| ------------------------- | ------------------------------------ | --------------------------- |
| `view_to_cart_rate`       | % of viewers who add to cart         | `cart_adds / views`         |
| `cart_to_purchase_rate`   | % of cart adds that become purchases | `purchases / cart_adds`     |
| `overall_conversion_rate` | % of viewers who purchase            | `purchases / views`         |
| `cart_abandonment_rate`   | % of cart adds that don't convert    | `1 - cart_to_purchase_rate` |

**Example Calculation:**

```python
# For product "123456789"
views = 150
cart_adds = 45
purchases = 12

view_to_cart_rate = 45 / 150 = 0.30 (30%)
cart_to_purchase_rate = 12 / 45 = 0.27 (27%)
overall_conversion_rate = 12 / 150 = 0.08 (8%)
```

### 3. **Temporal Metrics**

These metrics track when products are viewed and purchased:

| Feature                    | Description                    | Data Source                |
| -------------------------- | ------------------------------ | -------------------------- |
| `last_viewed_at`           | Most recent view timestamp     | User Interactions          |
| `last_purchased_at`        | Most recent purchase timestamp | Orders                     |
| `first_purchased_at`       | First purchase timestamp       | Orders                     |
| `days_since_last_purchase` | Days since last purchase       | Calculated from timestamps |

### 4. **Business Metrics**

These metrics track business performance:

| Feature              | Description              | Data Source           | Calculation                                      |
| -------------------- | ------------------------ | --------------------- | ------------------------------------------------ |
| `avg_selling_price`  | Average price when sold  | Orders                | Average of line item prices                      |
| `price_variance`     | Price variation          | Orders                | Standard deviation of prices                     |
| `total_inventory`    | Current inventory        | Product Data          | `total_inventory` field                          |
| `inventory_turnover` | How fast inventory moves | Orders + Product Data | `purchases / inventory`                          |
| `price_tier`         | Price category           | Product Data          | "low" (<$50), "medium" ($50-200), "high" (>$200) |

### 5. **Content Metrics**

These metrics measure content quality:

| Feature              | Description                | Data Source  | Calculation                    |
| -------------------- | -------------------------- | ------------ | ------------------------------ |
| `description_length` | Product description length | Product Data | Character count of description |
| `image_count`        | Number of product images   | Product Data | Count of images array          |
| `tag_diversity`      | Number of unique tags      | Product Data | Count of tags array            |
| `seo_title_length`   | SEO title length           | Product Data | Character count of title       |
| `has_video_content`  | Whether product has videos | Product Data | Boolean check                  |

### 6. **Performance Scores**

These are calculated scores that rank products:

| Feature             | Description                      | Calculation                                              |
| ------------------- | -------------------------------- | -------------------------------------------------------- |
| `popularity_score`  | How popular the product is       | Weighted combination of views, purchases, and engagement |
| `trending_score`    | How much the product is trending | Recent activity vs historical activity                   |
| `refund_risk_score` | Risk of refunds                  | Based on refund history and product characteristics      |

## How It All Works Together

### Step 1: Data Collection

```
Shopify API → Product Data
Shopify API → Order Data
Tracking Events → User Interactions
```

### Step 2: Feature Calculation

```
Product Data + Order Data + User Interactions → Feature Calculator
```

### Step 3: Feature Assembly

```
Engagement Metrics + Conversion Metrics + Business Metrics → Final Features
```

### Step 4: Storage

```
Final Features → Database → ML Models → Recommendations
```

## Example: Complete Feature Calculation

Let's say we have a product "Amazing T-Shirt" with this data:

**Product Data:**

```json
{
  "product_id": "123456789",
  "title": "Amazing T-Shirt",
  "price": 29.99,
  "total_inventory": 100,
  "description": "High quality cotton t-shirt for summer",
  "tags": ["clothing", "summer", "cotton"]
}
```

**30 Days of Interactions:**

- 150 product views
- 45 cart additions
- 12 purchases
- 3 refunds

**Calculated Features:**

```json
{
  "shop_id": "shop_123",
  "product_id": "123456789",

  // Engagement Metrics
  "view_count_30d": 150,
  "unique_viewers_30d": 120,
  "cart_add_count_30d": 45,
  "purchase_count_30d": 12,

  // Conversion Metrics
  "view_to_cart_rate": 0.3, // 30% of viewers add to cart
  "cart_to_purchase_rate": 0.27, // 27% of cart adds become purchases
  "overall_conversion_rate": 0.08, // 8% of viewers purchase

  // Business Metrics
  "avg_selling_price": 29.99,
  "total_inventory": 100,
  "inventory_turnover": 0.12, // 12% of inventory sold
  "price_tier": "medium",

  // Content Metrics
  "description_length": 45,
  "tag_diversity": 3,
  "image_count": 4,

  // Performance Scores
  "popularity_score": 0.75, // High popularity
  "trending_score": 0.6, // Moderate trending
  "refund_risk_score": 0.25, // Low refund risk

  "last_computed_at": "2023-01-15T10:30:00Z"
}
```

## How Features Are Used

### 1. **Recommendation Engine**

- `popularity_score` → Show popular products first
- `trending_score` → Show trending products
- `conversion_rate` → Show high-converting products

### 2. **Business Analytics**

- `inventory_turnover` → Manage stock levels
- `refund_risk_score` → Identify problematic products
- `price_tier` → Price optimization

### 3. **Customer Experience**

- `view_to_cart_rate` → Improve product pages
- `cart_abandonment_rate` → Optimize checkout
- `content_metrics` → Improve product descriptions

## Key Benefits

1. **Data-Driven Decisions**: Use metrics to make informed decisions
2. **Performance Tracking**: Monitor how products perform over time
3. **Optimization**: Identify areas for improvement
4. **Personalization**: Use features for better recommendations
5. **Business Intelligence**: Understand customer behavior and preferences

## Summary

Product features transform raw e-commerce data into actionable insights. They help understand:

- **What customers do** (engagement metrics)
- **How well products convert** (conversion metrics)
- **Business performance** (revenue, inventory)
- **Content quality** (SEO, media, descriptions)

These features power recommendation engines, business analytics, and customer experience optimization.
