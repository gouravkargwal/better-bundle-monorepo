# BetterBundle Interaction System - Simple Guide

## Current Working System

### 1. Frontend Events (Phoenix Extension)

```javascript
// Track recommendation view
await this.analyticsApi.trackRecommendationView(
  shopDomain,
  "cart", // context
  customerId,
  productIds,
  metadata
);
```

### 2. Backend Processing

```python
# Analytics API receives event
interaction = await analytics_service.track_interaction(
    session_id=session.id,
    interaction_type="recommendation_viewed",  # Our interaction type
    shop_id=shop_id,
    context="cart",
    metadata=metadata
)
```

### 3. Database Storage

```sql
-- UserInteraction table stores our interaction types
interaction_type: "recommendation_viewed"
context: "cart"
```

### 4. Gorse ML Integration

```python
# Session recommendations use Gorse feedback types
session_data = [
    {
        "FeedbackType": "cart_add",  # Gorse expects "cart_add"
        "ItemId": "shop_xxx_product_yyy",
        "UserId": "shop_xxx_customer_zzz"
    }
]
```

## Key Mapping

| Our System    | Gorse System |
| ------------- | ------------ |
| `add_to_cart` | `cart_add`   |
| `view`        | `view`       |
| `purchase`    | `purchase`   |
| `click`       | `click`      |

## What's Working

✅ **Session Recommendations**: Now returning 3 recommendations with scores  
✅ **Data Pipeline**: Shopify → Features → Gorse → Recommendations  
✅ **Feedback Types**: Correctly mapped to Gorse expectations  
✅ **Training**: Gorse models trained and working

## Files Updated

- `app/recommandations/hybrid.py` - Uses correct Gorse feedback types
- `app/shared/constants/interaction_types.py` - Simple mapping function
- Session recommendations now work with proper feedback type mapping

## Test Results

```
🎉 SUCCESS! Session recommendations are working!
  1. shop_cmfnmj5sn0000v3gaipwx948o_7903467045003 (Score: 0.083)
  2. shop_cmfnmj5sn0000v3gaipwx948o_7894674243723 (Score: 0.033)
  3. shop_cmfnmj5sn0000v3gaipwx948o_7894679355531 (Score: 0.028)
```

The system is now working end-to-end! 🚀
