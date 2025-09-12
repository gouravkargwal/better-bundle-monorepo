# Development Store Seeding

This directory contains scripts to seed realistic data into your Shopify development stores. The seeding system uses the same data generators as your ML pipeline to create consistent, realistic test data.

## Overview

The seeding system creates:

- **15 Products** across 3 categories (Clothing, Accessories, Electronics)
- **8 Diverse Customer Profiles** (VIP, new customers, moderate buyers, etc.)
- **12 Realistic Orders** with purchase patterns
- **Behavioral Events** for user journeys (optional)

## Quick Start

### 1. Set Up Development Stores

First, you need development stores with your app installed:

```bash
# Create development stores in your Shopify Partner Dashboard
# Install your BetterBundle app on each store
```

### 2. Get Access Tokens

Run the helper script to get instructions:

```bash
cd python-worker
python -m app.scripts.get_dev_store_tokens
```

This will show you how to get access tokens from your app's database or Shopify Admin API.

### 3. Configure Stores

Create or edit the configuration file:

```bash
python -m app.scripts.get_dev_store_tokens --create-config
```

Edit `development_stores_config.json` with your store details:

```json
{
  "development_stores": [
    {
      "name": "My Fashion Store",
      "domain": "my-fashion-store.myshopify.com",
      "access_token": "shpat_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
      "description": "Development store for testing fashion recommendations",
      "enabled": true
    }
  ]
}
```

### 4. Run the Seeder

```bash
cd python-worker
python -m app.scripts.seed_development_stores
```

## Configuration Options

### Store Configuration

Each store in `development_stores_config.json` can have:

- `name`: Display name for the store
- `domain`: Shopify store domain (e.g., `my-store.myshopify.com`)
- `access_token`: API access token (starts with `shpat_`)
- `description`: Optional description
- `enabled`: Whether to seed this store (true/false)

### Seeding Options

Control what gets created:

```json
{
  "seeding_options": {
    "create_products": true, // Create products
    "create_customers": true, // Create customers
    "create_orders": true, // Create orders
    "create_collections": false, // Create collections (not implemented yet)
    "clear_existing_data": false, // Clear existing data first (not implemented yet)
    "batch_size": 10 // API request batch size
  }
}
```

### Data Customization

Control the amount of data:

```json
{
  "data_customization": {
    "product_count": 15, // Number of products to create
    "customer_count": 8, // Number of customers to create
    "order_count": 12, // Number of orders to create
    "include_behavioral_events": false // Include behavioral events (not implemented yet)
  }
}
```

## Generated Data

### Products (15 total)

**Clothing (5 products):**

- Premium Cotton Hoodie
- Classic V-Neck T-Shirt
- Slim Fit Jeans
- Athletic Shorts
- Wool Blend Sweater

**Accessories (5 products):**

- Designer Sunglasses
- Leather Crossbody Bag
- Silk Scarf
- Leather Belt
- Baseball Cap

**Electronics (5 products):**

- Wireless Earbuds Pro
- Smart Watch
- Phone Case
- Portable Charger
- Bluetooth Speaker

### Customers (8 profiles)

1. **Alice Johnson** - VIP customer with high spending
2. **Bob Smith** - New customer (browsing only)
3. **Charlie Brown** - Moderate buyer, electronics-focused
4. **Dana Lee** - Abandoned cart customer
5. **Eve Adams** - Cross-category buyer
6. **Frank Wilson** - Tech enthusiast
7. **Grace Taylor** - Fashion lover
8. **Henry Davis** - Bargain hunter

### Orders (12 total)

Orders are created with realistic patterns:

- VIP customers have multiple orders
- New customers have no orders (browsing only)
- Orders include proper line items and pricing
- Orders are distributed across different time periods

## Troubleshooting

### Common Issues

1. **"No enabled stores found"**

   - Make sure at least one store has `"enabled": true` in the config

2. **"API request failed"**

   - Check your access token is correct and starts with `shpat_`
   - Verify the store domain is correct
   - Ensure your app has the necessary scopes

3. **"Failed to create product/customer/order"**
   - Check the error message for specific API issues
   - Verify your app has write permissions for the resource type

### Getting Access Tokens

**From your app's database:**

```sql
SELECT "shopDomain", "accessToken" FROM "Shop" WHERE "isActive" = true;
```

**From Shopify CLI:**

```bash
shopify app info
```

**From your app's session storage:**

- Check your Prisma database for the Shop table
- Look for the accessToken field

## Integration with ML Pipeline

The seeded data is compatible with your existing ML pipeline:

1. **Raw Data**: The seeder creates the same data structure as your generators
2. **Processing**: You can run your existing pipeline on the seeded data
3. **Recommendations**: Test your recommendation system with realistic data

To process the seeded data through your ML pipeline:

```bash
# Run the existing seed pipeline runner
python -m app.scripts.seed_pipeline_runner
```

## Next Steps

After seeding your development stores:

1. **Test Recommendations**: Use the seeded data to test your recommendation system
2. **Verify Data Quality**: Check that products, customers, and orders look realistic
3. **Run ML Pipeline**: Process the data through your feature engineering pipeline
4. **Test UI Components**: Verify your app's UI works with the seeded data

## Files

- `seed_development_stores.py` - Main seeding script
- `development_stores_config.json` - Configuration file
- `get_dev_store_tokens.py` - Helper for getting access tokens
- `seed_data_generators/` - Data generators (shared with ML pipeline)
- `README_SEEDING.md` - This documentation
