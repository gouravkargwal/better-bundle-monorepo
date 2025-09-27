# API Client Migration Guide

## Overview

The API client has been refactored into specialized clients for better maintainability and code organization.

## New Structure

### Before (Single File)

```
api_client.py (1773 lines)
├── Base functionality
├── Product methods
├── Collection methods
├── Order methods
├── Customer methods
└── Helper methods
```

### After (Modular Structure)

```
api/
├── __init__.py
├── base_client.py          # Common functionality
├── product_client.py       # Product-specific methods
├── collection_client.py    # Collection-specific methods
├── order_client.py         # Order-specific methods
└── customer_client.py     # Customer-specific methods

api_client_new.py           # Main client that delegates to specialized clients
```

## Benefits

1. **Maintainability**: Each data type has its own file
2. **Reusability**: Common functionality in base client
3. **Extensibility**: Easy to add new data types
4. **Testing**: Easier to test individual components
5. **Code Review**: Smaller, focused files

## Migration Steps

### 1. Update Imports

```python
# Old
from app.domains.shopify.services.api_client import ShopifyAPIClient

# New
from app.domains.shopify.services.api_client_new import ShopifyAPIClient
```

### 2. API Compatibility

The new client maintains the same interface:

```python
# All existing code continues to work
client = ShopifyAPIClient()
await client.set_access_token(shop_domain, token)

# Products
products = await client.get_products(shop_domain, limit=100)

# Collections
collections = await client.get_collections(shop_domain, limit=100)

# Orders
orders = await client.get_orders(shop_domain, limit=100)

# Customers
customers = await client.get_customers(shop_domain, limit=100)
```

### 3. New Features

The new client supports specific ID collection for webhooks:

```python
# Webhook collection for specific products
products = await client.get_products(
    shop_domain=shop_domain,
    product_ids=["123456789", "987654321"]
)

# Webhook collection for specific collections
collections = await client.get_collections(
    shop_domain=shop_domain,
    collection_ids=["123456789"]
)

# Webhook collection for specific orders
orders = await client.get_orders(
    shop_domain=shop_domain,
    order_ids=["123456789"]
)

# Webhook collection for specific customers
customers = await client.get_customers(
    shop_domain=shop_domain,
    customer_ids=["123456789"]
)
```

## File Organization

### Base Client (`base_client.py`)

- Common GraphQL functionality
- Rate limiting
- Error handling
- HTTP client management
- Shop info methods

### Product Client (`product_client.py`)

- `get_products()` with pagination and specific IDs
- Full data traversal (variants, images, metafields)
- Product-specific helper methods

### Collection Client (`collection_client.py`)

- `get_collections()` with pagination and specific IDs
- Full data traversal (products)
- Collection-specific helper methods

### Order Client (`order_client.py`)

- `get_orders()` with pagination and specific IDs
- Full data traversal (line items)
- Order-specific helper methods

### Customer Client (`customer_client.py`)

- `get_customers()` with pagination and specific IDs
- Full data traversal (addresses)
- Customer-specific helper methods

## Testing

Each client can be tested independently:

```python
# Test product client
product_client = ProductAPIClient()
await product_client.set_access_token(shop_domain, token)
products = await product_client.get_products(shop_domain, limit=10)

# Test collection client
collection_client = CollectionAPIClient()
await collection_client.set_access_token(shop_domain, token)
collections = await collection_client.get_collections(shop_domain, limit=10)
```

## Rollback Plan

If issues arise, you can easily rollback by:

1. Reverting import changes
2. Using the original `api_client.py`
3. The old file remains unchanged

## Next Steps

1. Update imports in data collection service
2. Test with existing functionality
3. Gradually adopt new specific ID features
4. Remove old API client file once migration is complete
