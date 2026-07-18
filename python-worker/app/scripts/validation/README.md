# Recommendation Validation Suite

Seed test data and validate Gorse recommendations end-to-end.

## Complete Workflow

```bash
# Step 1: Create a fake shop (triggers the ML pipeline)
uv run python-worker/app/scripts/validation/seed_shop.py

# Step 2: Seed products, customers, orders, collections (includes refunded order)
uv run python-worker/app/scripts/validation/seed_test_data.py

# Step 3: Seed browsing sessions, interactions, purchase attributions
#         (includes recommendation_declined events)
uv run python-worker/app/scripts/validation/seed_interactions.py

# Step 4: Force-run the feature computation + Gorse sync pipeline
uv run python-worker/app/scripts/validation/run_pipeline.py

# Step 5: Validate recommendations
uv run python-worker/app/scripts/validation/validate_recommendations.py
```

## Scripts

| Script | Seeds | Purpose |
|--------|-------|---------|
| `seed_shop.py` | `shops` | Creates a fake shop → triggers pipeline |
| `seed_test_data.py` | `product_data`, `customer_data`, `order_data`, `collection_data` | 30 products, 5 customers, ~37 orders (incl. 2 refunded), 5 collections |
| `seed_interactions.py` | `user_sessions`, `user_interactions`, `purchase_attributions` | 21 sessions, ~150 events, purchase attributions + recommendation_declined |
| `run_pipeline.py` | — | Runs feature computation + Gorse sync immediately |
| `validate_recommendations.py` | — | Calls Gorse API and checks recommendations |
