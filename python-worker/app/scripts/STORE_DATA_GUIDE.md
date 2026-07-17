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

## Seed New Data (store only, no behavioral data)

```bash
python app/scripts/seed_shopify_graphql.py
```

## Verify Store Counts

```bash
curl -s -X POST "https://$SHOP_DOMAIN/admin/api/2024-01/graphql.json" \
  -H "Content-Type: application/json" \
  -H "X-Shopify-Access-Token: $ACCESS_TOKEN" \
  -d '{"query": "{ ordersCount { count } productsCount { count } customersCount { count } collectionsCount { count } }"}'
```

## Seed Everything for TFRS Testing (recommended)

The app must already be installed on the target shop (a row in `shops` for
`SHOP_DOMAIN`) before running this — it writes into that shop's tables.

```bash
export SHOP_DOMAIN="<your-shop>.myshopify.com"
export ACCESS_TOKEN="<your-access-token>"
python3 app/scripts/seed_full_pipeline.py
```

This does the whole pipeline in one command:

1. Creates real products/customers/orders in the Shopify store (same as
   `seed_shopify_graphql.py`, but orders are now biased toward each
   customer's assigned category so there's real affinity signal instead of
   picking products uniformly at random)
2. Mirrors that data directly into `product_data`/`customer_data`/
   `order_data`/`line_item_data` — no need to wait on the Kafka
   data-collection consumer or call the trigger endpoint separately
3. Seeds the behavioral signal TFRS actually trains on: `user_sessions`,
   `user_interactions` (views/cart-adds/checkouts, clustered by the same
   category affinity), and `purchase_attributions` for every order

Co-purchase pairs need no separate seeding — `TfrsTrainer._load_co_purchases`
derives them directly from multi-item paid orders in `order_data`/
`line_item_data`.

### Running the steps individually

If you'd rather use the real data-collection pipeline instead of the direct
DB mirror (e.g. to also test that pipeline), run these instead of
`seed_full_pipeline.py`:

```bash
python3 app/scripts/seed_shopify_graphql.py
curl -X POST http://localhost:8000/api/v1/data-collection/trigger \
  -H "Content-Type: application/json" \
  -d '{"shop_id": "df19ef7f-c754-4749-8783-6f99268faad0", "data_types": ["orders", "products", "customers"], "since_hours": 720, "force_refresh": true}'
python3 app/scripts/seed_tfrs_training_data.py
```
