# BetterBundle Interaction System Documentation

## Overview

This document provides a comprehensive guide to the BetterBundle interaction tracking system, from frontend events to ML training.

## System Architecture

```
Frontend (Phoenix Extension)
    ↓
Analytics API (Python Worker)
    ↓
Database Storage (PostgreSQL)
    ↓
Feature Engineering (ML Pipeline)
    ↓
Gorse ML System (Recommendations)
```

## 1. Frontend Event Tracking

### Phoenix Extension Events

**Location**: `better-bundle/extensions/phoenix/assets/main.js`

```javascript
// Standardized interaction tracking
await this.analyticsApi.trackRecommendationView(
  this.config.shopDomain,
  this.config.context, // "cart"
  this.config.customerId,
  productIds,
  metadata
);
```

### Event Types

- `recommendation_viewed` - User viewed recommendations
- `recommendation_clicked` - User clicked on recommendation
- `add_to_cart` - User added item to cart
- `purchase` - User completed purchase

### Context Types

- `cart` - Cart page context
- `product_page` - Product detail page
- `homepage` - Homepage context
- `checkout` - Checkout process

## 2. Analytics API Processing

### Request Flow

**Location**: `python-worker/app/domains/analytics/api/phoenix_api.py`

```python
# 1. Shop validation
shop_id = await shop_resolver.get_shop_id_from_domain(request.shop_domain)

# 2. Session management
session = await session_service.get_or_create_session(
    shop_id=shop_id,
    customer_id=request.customer_id,
    browser_session_id=request.browser_session_id
)

# 3. Interaction tracking
interaction = await analytics_service.track_interaction(
    session_id=session.id,
    interaction_type=request.interaction_type,
    shop_id=shop_id,
    context=request.context,
    metadata=request.metadata
)
```

### Validation

- Shop existence validation
- Session ID generation with UUID
- Interaction type validation
- Context validation

## 3. Database Storage

### UserInteraction Table

**Location**: `python-worker/prisma/schema.prisma`

```sql
model UserInteraction {
  id               String           @id @default(cuid())
  sessionId        String
  shopId           String
  customerId       String?
  interactionType  String          // "recommendation_viewed"
  context          String          // "cart"
  metadata         Json?
  createdAt        DateTime        @default(now())
  updatedAt        DateTime        @updatedAt
}
```

### Data Flow

1. **Raw Events** → UserInteraction table
2. **Feature Engineering** → Feature tables
3. **Gorse Sync** → ML training data

## 4. Feature Engineering

### Behavioral Feature Generation

**Location**: `python-worker/app/domains/ml/generators/customer_behavior_feature_generator.py`

```python
# Extract behavioral patterns
customer_behaviors = await self._extract_customer_behaviors(
    shop_id=shop_id,
    customer_id=customer_id,
    interaction_types=["recommendation_viewed", "add_to_cart"]
)
```

### Feature Types

- **Customer Behaviors**: Purchase patterns, browsing habits
- **Session Features**: Session duration, page views
- **Product Features**: Product popularity, categories
- **Interaction Features**: Click-through rates, conversion rates

## 5. Gorse ML Integration

### Feedback Type Mapping

**Location**: `python-worker/app/shared/constants/interaction_types.py`

```python
# Standardized feedback types for Gorse
class FeedbackType:
    VIEW = "view"
    CART_ADD = "cart_add"
    CART_REMOVE = "cart_remove"
    PURCHASE = "purchase"
    CLICK = "click"
```

### Session Recommendations

**Location**: `python-worker/app/recommandations/hybrid.py`

```python
# Build session data for Gorse
session_data = [
    {
        "Comment": "cart_item_7894675292299",
        "FeedbackType": FeedbackType.CART_ADD,  # Standardized
        "ItemId": "shop_cmfnmj5sn0000v3gaipwx948o_7894675292299",
        "Timestamp": datetime.now().isoformat(),
        "UserId": "shop_cmfnmj5sn0000v3gaipwx948o_8619514265739"
    }
]
```

## 6. Standardized Constants

### Interaction Types

```python
class InteractionType:
    RECOMMENDATION_VIEWED = "recommendation_viewed"
    RECOMMENDATION_CLICKED = "recommendation_clicked"
    ADD_TO_CART = "add_to_cart"
    PURCHASE = "purchase"
```

### Context Types

```python
class ContextType:
    CART = "cart"
    PRODUCT_PAGE = "product_page"
    HOMEPAGE = "homepage"
    CHECKOUT = "checkout"
```

### Feedback Types (Gorse)

```python
class FeedbackType:
    VIEW = "view"
    CART_ADD = "cart_add"
    PURCHASE = "purchase"
    CLICK = "click"
```

## 7. Data Flow Examples

### Example 1: Recommendation View

```
1. Frontend: User views recommendations on cart page
2. Phoenix Extension: trackRecommendationView("cart", productIds)
3. Analytics API: POST /api/phoenix/track-interaction
4. Database: UserInteraction(interaction_type="recommendation_viewed", context="cart")
5. Feature Engineering: Extract behavioral patterns
6. Gorse Sync: Convert to feedback type "view"
7. ML Training: Train recommendation models
8. Session Recommendations: Return personalized suggestions
```

### Example 2: Add to Cart

```
1. Frontend: User adds item to cart
2. Phoenix Extension: trackAddToCart(productId)
3. Analytics API: POST /api/phoenix/track-interaction
4. Database: UserInteraction(interaction_type="add_to_cart", context="cart")
5. Feature Engineering: Update cart behavior features
6. Gorse Sync: Convert to feedback type "cart_add"
7. ML Training: Update collaborative filtering
8. Recommendations: Improve item-to-item suggestions
```

## 8. Error Handling

### Common Issues

1. **Foreign Key Constraints**: Shop validation before creating records
2. **Session ID Collisions**: UUID-based session ID generation
3. **Feedback Type Mismatch**: Standardized constants and mapping
4. **Duplicate Events**: Deduplication logic in frontend

### Solutions Implemented

- ✅ Shop existence validation
- ✅ Session ID uniqueness with UUID
- ✅ Feedback type standardization
- ✅ Event deduplication
- ✅ Error logging and monitoring

## 9. Monitoring and Debugging

### Log Locations

- **Frontend**: Browser console logs
- **Analytics API**: Python worker logs
- **Database**: PostgreSQL logs
- **Gorse**: Docker container logs

### Key Metrics

- Interaction tracking success rate
- Session creation success rate
- Feature computation completion
- Gorse training status
- Recommendation quality scores

## 10. Best Practices

### Frontend

- Use standardized interaction types
- Implement deduplication
- Handle errors gracefully
- Log events for debugging

### Backend

- Validate all inputs
- Use standardized constants
- Implement proper error handling
- Monitor performance metrics

### ML Pipeline

- Ensure data consistency
- Monitor training completion
- Validate recommendation quality
- Handle edge cases

## 11. Troubleshooting

### Session Recommendations Not Working

1. Check Gorse training status
2. Verify feedback type mapping
3. Ensure data sync completion
4. Monitor Gorse logs

### Duplicate Events

1. Check frontend deduplication
2. Verify session ID generation
3. Monitor analytics API logs
4. Review database constraints

### Performance Issues

1. Monitor database queries
2. Check Gorse training time
3. Review feature computation
4. Optimize data sync

## 12. Future Improvements

### Planned Enhancements

- [ ] Real-time recommendation updates
- [ ] Advanced personalization features
- [ ] A/B testing framework
- [ ] Performance optimization
- [ ] Enhanced monitoring

### Technical Debt

- [ ] Legacy code cleanup
- [ ] Test coverage improvement
- [ ] Documentation updates
- [ ] Error handling enhancement
