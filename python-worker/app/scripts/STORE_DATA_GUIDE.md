# Shopify Store Data Management

Run all commands from `python-worker/` directory.

## Setup

```bash
cd /Users/gouravkargwal/Desktop/BetterBundle/python-worker
export SHOP_DOMAIN="rizz-shop-6616.myshopify.com"
export ACCESS_TOKEN="<YOUR_SHOPIFY_ACCESS_TOKEN>"
```

## Delete All Store Data

```bash
python3 app/scripts/delete_store_data.py
```

## Seed New Data

```bash
python3 app/scripts/seed_shopify_graphql.py
```

## Verify Store Counts

```bash
curl -s -X POST "https://$SHOP_DOMAIN/admin/api/2024-01/graphql.json" \
  -H "Content-Type: application/json" \
  -H "X-Shopify-Access-Token: $ACCESS_TOKEN" \
  -d '{"query": "{ ordersCount { count } productsCount { count } customersCount { count } collectionsCount { count } }"}'
```

## Trigger Data Collection

```bash
curl -X POST http://localhost:8000/api/v1/data-collection/trigger \
  -H "Content-Type: application/json" \
  -d '{"shop_id": "df19ef7f-c754-4749-8783-6f99268faad0", "data_types": ["orders", "products", "customers"], "since_hours": 720, "force_refresh": true}'
```
