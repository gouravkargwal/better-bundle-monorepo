# BetterBundle Feature Computation Documentation

## Overview

This documentation explains the complete feature computation system for BetterBundle, covering how raw Shopify data is transformed into machine learning features for recommendation engines and analytics.

## Documentation Structure

### 📊 Feature Types

| Feature Type                   | Documentation                                                             | Status      | Records Expected |
| ------------------------------ | ------------------------------------------------------------------------- | ----------- | ---------------- |
| **Product Features**           | [📄 Product Features](./features/product-features.md)                     | ✅ Complete | 350              |
| **User Features**              | [📄 User Features](./features/user-features.md)                           | ✅ Complete | 381              |
| **Collection Features**        | [📄 Collection Features](./features/collection-features.md)               | ✅ Complete | 6                |
| **Product Pair Features**      | [📄 Product Pair Features](./features/product-pair-features.md)           | ✅ Complete | Variable         |
| **Session Features**           | [📄 Session Features](./features/session-features.md)                     | ✅ Complete | 0\*              |
| **Customer Behavior Features** | [📄 Customer Behavior Features](./features/customer-behavior-features.md) | ✅ Complete | 0\*              |
| **Interaction Features**       | [📄 Interaction Features](./features/interaction-features.md)             | ✅ Complete | 0\*              |
| **Search Product Features**    | [📄 Search Product Features](./features/search-product-features.md)       | ✅ Complete | 0\*              |

\*Expected to be 0 until user interaction tracking is implemented

### 🏗️ System Architecture

- [📄 System Overview](./system-overview.md) - Complete data flow and architecture
- [📄 Data Sources](./data-sources.md) - Input data tables and their purposes
- [📄 Feature Engineering Pipeline](./feature-engineering-pipeline.md) - How features are computed
- [📄 Performance & Monitoring](./performance-monitoring.md) - Optimization and debugging

### 🧪 Testing & Validation

- [📄 Minimal Testing Guide](./testing/minimal-testing-guide.md) - Step-by-step test data setup
- [📄 Quick Reference](./testing/quick-reference.md) - Test data summary and expected results
- [📄 Create Test Data](./testing/create-test-data.md) - Scripts and manual steps for Shopify data creation

## Quick Start

1. **Understand the Data Flow**: Start with [System Overview](./system-overview.md)
2. **Learn Feature Types**: Read individual feature documentation
3. **Check Current Status**: See what's working and what needs fixes
4. **Monitor Performance**: Use monitoring guides for optimization

## Current System Status

### ✅ Working Features

- **Data Collection**: 350 products, 395 orders, 340 line items
- **Normalization**: Raw data properly normalized
- **Collections**: Products now get collections data
- **Collection Features**: 6 records generated correctly

### ⚠️ Issues to Fix

- **Product Features**: Only 1 record instead of 350
- **User Features**: Only 1 record instead of 381
- **Missing Interaction Data**: No user interaction tracking

### 🎯 Expected Results After Fixes

- **Product Features**: 350 records (one per product)
- **User Features**: 381 records (one per customer)
- **Collection Features**: 6 records (already working)
- **Other Features**: 0 records (expected - no interaction data)

## Data Flow Summary

```
Raw Shopify API → Normalization → Main Tables → Feature Computation → Feature Tables
     ↓                ↓              ↓              ↓                ↓
  Products         product_data   ProductFeatures  ML Features   Gorse Sync
  Orders          order_data     UserFeatures     Analytics     Recommendations
  Customers       customer_data  CollectionFeatures
  Collections     collection_data
```

## Getting Help

- **Code Issues**: Check individual feature documentation
- **Performance**: See [Performance & Monitoring](./performance-monitoring.md)
- **Data Problems**: Review [Data Sources](./data-sources.md)
- **Architecture**: Read [System Overview](./system-overview.md)

---

_Last Updated: 2025-01-26_  
_Version: 1.0_
