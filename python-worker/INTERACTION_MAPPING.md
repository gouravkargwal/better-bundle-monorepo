# BetterBundle Interaction & Feedback Type Mapping

## Overview

This document maps all interaction types, events, and feedback types used throughout the BetterBundle system to ensure consistency from data collection to ML training.

## Current State Analysis

### 1. Analytics Tracking (Frontend → Backend)

#### Phoenix Extension Events

```javascript
// From: better-bundle/extensions/phoenix/assets/main.js
interaction_type: "recommendation_viewed"; // ✅ Consistent
context: "cart"; // ✅ Standardized
```

#### Analytics API Events

```python
# From: python-worker/app/domains/analytics/services/analytics_tracking_service.py
interaction_type: "recommendation_viewed"  // ✅ Consistent
context: "cart"                            // ✅ Standardized
```

### 2. Database Storage

#### UserInteraction Table

```sql
-- From: python-worker/prisma/schema.prisma
interaction_type: "recommendation_viewed"  // ✅ Consistent
context: "cart"                            // ✅ Standardized
```

### 3. Feature Engineering

#### Behavioral Events

```python
# From: python-worker/app/domains/ml/generators/customer_behavior_feature_generator.py
interaction_type: "recommendation_viewed"  // ✅ Consistent
context: "cart"                            // ✅ Standardized
```

### 4. Gorse Integration

#### Feedback Types (Current Issue)

```python
# Database has:
feedback_type: "cart_add"     # ✅ Correct
feedback_type: "view"         # ✅ Correct
feedback_type: "purchase"     # ✅ Correct

# Session data was sending:
feedback_type: "add_to_cart"  # ❌ Fixed to "cart_add"
```

## Standardized Mapping

### Interaction Types

| Frontend Event           | Analytics API            | Database                 | Feature Engineering      | Gorse      |
| ------------------------ | ------------------------ | ------------------------ | ------------------------ | ---------- |
| `recommendation_viewed`  | `recommendation_viewed`  | `recommendation_viewed`  | `recommendation_viewed`  | `view`     |
| `recommendation_clicked` | `recommendation_clicked` | `recommendation_clicked` | `recommendation_clicked` | `click`    |
| `add_to_cart`            | `add_to_cart`            | `add_to_cart`            | `add_to_cart`            | `cart_add` |
| `purchase`               | `purchase`               | `purchase`               | `purchase`               | `purchase` |

### Context Types

| Frontend Context | Analytics API  | Database       | Feature Engineering |
| ---------------- | -------------- | -------------- | ------------------- |
| `cart`           | `cart`         | `cart`         | `cart`              |
| `product_page`   | `product_page` | `product_page` | `product_page`      |
| `homepage`       | `homepage`     | `homepage`     | `homepage`          |
| `checkout`       | `checkout`     | `checkout`     | `checkout`          |

### Feedback Types (Gorse)

| Interaction Type | Gorse Feedback Type | Description                    |
| ---------------- | ------------------- | ------------------------------ |
| `view`           | `view`              | User viewed an item            |
| `cart_add`       | `cart_add`          | User added item to cart        |
| `purchase`       | `purchase`          | User purchased an item         |
| `click`          | `click`             | User clicked on recommendation |

## Implementation Status

### ✅ Completed

- [x] Phoenix extension interaction types standardized
- [x] Analytics API interaction types consistent
- [x] Database schema consistent
- [x] Feature engineering consistent
- [x] Gorse feedback type mapping fixed

### 🔄 Needs Standardization

- [ ] Session data feedback types
- [ ] Event metadata structure
- [ ] Error handling consistency

## Code Locations

### Frontend (Phoenix Extension)

- `better-bundle/extensions/phoenix/assets/main.js`
- `better-bundle/extensions/phoenix/assets/analytics.js`

### Backend (Python Worker)

- `python-worker/app/domains/analytics/services/analytics_tracking_service.py`
- `python-worker/app/domains/analytics/services/unified_session_service.py`
- `python-worker/app/recommandations/hybrid.py`
- `python-worker/app/domains/ml/generators/customer_behavior_feature_generator.py`

### Database

- `python-worker/prisma/schema.prisma`

## Recommendations

1. **Standardize all feedback types** to match Gorse expectations
2. **Create constants file** for all interaction types
3. **Add validation** for interaction type consistency
4. **Document all event flows** from frontend to ML training

## Next Steps

1. Create constants file for all interaction types
2. Standardize session data feedback types
3. Add validation for consistency
4. Update documentation
