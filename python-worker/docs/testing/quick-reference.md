# Quick Reference: Minimal Test Data

## 📋 Test Data Summary

| Data Type       | Count | Purpose                                 |
| --------------- | ----- | --------------------------------------- |
| **Products**    | 5     | Test product feature computation        |
| **Collections** | 2     | Test collection feature computation     |
| **Customers**   | 3     | Test user feature computation           |
| **Orders**      | 5     | Test order processing and relationships |
| **Line Items**  | 8     | Test product-order relationships        |

## 🏷️ Product Categories

| Product             | Category      | Price   | Vendor        | Tags                           |
| ------------------- | ------------- | ------- | ------------- | ------------------------------ |
| Wireless Headphones | Electronics   | $199.99 | TechCorp      | wireless, bluetooth, premium   |
| Cotton T-Shirt      | Clothing      | $29.99  | FashionBrand  | cotton, casual, clothing       |
| Phone Case          | Accessories   | $19.99  | TechCorp      | phone, protection, accessories |
| LED Desk Lamp       | Home & Garden | $49.99  | HomeGoods     | led, desk, lighting, usb       |
| Programming Guide   | Books         | $24.99  | BookPublisher | programming, guide, education  |

## 📦 Collection Mapping

| Collection         | Products                 | Count |
| ------------------ | ------------------------ | ----- |
| Electronics & Tech | Headphones, Phone Case   | 2     |
| Lifestyle & Home   | T-Shirt, Desk Lamp, Book | 3     |

## 👥 Customer Profiles

| Customer      | Email              | Orders | Total Spent | Profile          |
| ------------- | ------------------ | ------ | ----------- | ---------------- |
| John Smith    | customer1@test.com | 2      | $294.96     | Regular customer |
| Sarah Johnson | customer2@test.com | 2      | $334.95     | Premium customer |
| Mike Davis    | customer3@test.com | 1      | $29.99      | New customer     |

## 🛒 Order Patterns

| Order | Customer | Products                      | Total   | Date       |
| ----- | -------- | ----------------------------- | ------- | ---------- |
| 1     | John     | Headphones + Phone Case       | $219.98 | 7 days ago |
| 2     | Sarah    | T-Shirt (2x)                  | $59.98  | 5 days ago |
| 3     | John     | Desk Lamp + Book              | $74.98  | 3 days ago |
| 4     | Mike     | T-Shirt                       | $29.99  | 2 days ago |
| 5     | Sarah    | Headphones + Desk Lamp + Book | $274.97 | 1 day ago  |

## ✅ Expected Results

### Database Counts

- `product_data`: 5
- `collection_data`: 2
- `customer_data`: 3
- `order_data`: 5
- `line_item_data`: 8

### Feature Counts

- `product_features`: 5
- `user_features`: 3
- `collection_features`: 2
- `product_pair_features`: 2-4

## 🚀 Quick Test Commands

```bash
# Check data collection
SELECT COUNT(*) FROM product_data;        -- Should be 5
SELECT COUNT(*) FROM customer_data;       -- Should be 3
SELECT COUNT(*) FROM order_data;          -- Should be 5

# Check feature computation
SELECT COUNT(*) FROM product_features;    -- Should be 5
SELECT COUNT(*) FROM user_features;       -- Should be 3
SELECT COUNT(*) FROM collection_features; -- Should be 2
```

## 🎯 Key Test Scenarios

1. **Product Features**: All 5 products should have features
2. **User Features**: All 3 customers should have features
3. **Collection Features**: Both collections should have features
4. **Product Pairs**: Headphones + Phone Case should be a pair
5. **Cross-category**: Electronics + Lifestyle collections should work
