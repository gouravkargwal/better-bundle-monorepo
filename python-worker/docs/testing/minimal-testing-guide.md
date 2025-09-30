# Minimal Testing Guide for BetterBundle Feature Computation

This guide provides step-by-step instructions for creating minimal test data in Shopify to validate the complete end-to-end feature computation pipeline.

## 🎯 Testing Objectives

- **Data Collection**: Verify raw data collection from Shopify APIs
- **Normalization**: Confirm data transformation to canonical format
- **Feature Computation**: Test feature generation for all feature types
- **ML Integration**: Validate Gorse sync and recommendation engine

## 📊 Minimal Test Data Requirements

### 1. Products (Minimum: 5 products)

Create 5 products with the following characteristics:

#### Product 1: Electronics - High Value

```
Title: "Wireless Bluetooth Headphones"
Description: "Premium wireless headphones with noise cancellation"
Price: $199.99
Product Type: Electronics
Vendor: TechCorp
Tags: ["wireless", "bluetooth", "premium", "electronics"]
Inventory: 50 units
Status: Active
```

#### Product 2: Clothing - Medium Value

```
Title: "Cotton T-Shirt"
Description: "Comfortable 100% cotton t-shirt"
Price: $29.99
Product Type: Clothing
Vendor: FashionBrand
Tags: ["cotton", "casual", "clothing"]
Inventory: 100 units
Status: Active
```

#### Product 3: Accessories - Low Value

```
Title: "Phone Case"
Description: "Protective phone case with design"
Price: $19.99
Product Type: Accessories
Vendor: TechCorp
Tags: ["phone", "protection", "accessories"]
Inventory: 75 units
Status: Active
```

#### Product 4: Home & Garden - Medium Value

```
Title: "LED Desk Lamp"
Description: "Adjustable LED desk lamp with USB port"
Price: $49.99
Product Type: Home & Garden
Vendor: HomeGoods
Tags: ["led", "desk", "lighting", "usb"]
Inventory: 30 units
Status: Active
```

#### Product 5: Books - Low Value

```
Title: "Programming Guide"
Description: "Complete guide to modern programming"
Price: $24.99
Product Type: Books
Vendor: BookPublisher
Tags: ["programming", "guide", "education", "books"]
Inventory: 25 units
Status: Active
```

### 2. Collections (Minimum: 2 collections)

#### Collection 1: Electronics Collection

```
Title: "Electronics & Tech"
Description: "Latest electronics and technology products"
Handle: electronics-tech
Product Count: 2 products (Product 1, Product 3)
Status: Active
```

#### Collection 2: Lifestyle Collection

```
Title: "Lifestyle & Home"
Description: "Products for comfortable living"
Handle: lifestyle-home
Product Count: 3 products (Product 2, Product 4, Product 5)
Status: Active
```

### 3. Customers (Minimum: 3 customers)

#### Customer 1: Regular Customer

```
Email: customer1@test.com
First Name: John
Last Name: Smith
Phone: +1-555-0101
Address: 123 Main St, New York, NY 10001
Tags: ["regular", "loyal"]
Status: Active
```

#### Customer 2: Premium Customer

```
Email: customer2@test.com
First Name: Sarah
Last Name: Johnson
Phone: +1-555-0102
Address: 456 Oak Ave, Los Angeles, CA 90210
Tags: ["premium", "high-value"]
Status: Active
```

#### Customer 3: New Customer

```
Email: customer3@test.com
First Name: Mike
Last Name: Davis
Phone: +1-555-0103
Address: 789 Pine St, Chicago, IL 60601
Tags: ["new", "first-time"]
Status: Active
```

### 4. Orders (Minimum: 5 orders)

#### Order 1: Electronics Purchase

```
Customer: customer1@test.com
Products:
  - Wireless Bluetooth Headphones (1x) = $199.99
  - Phone Case (1x) = $19.99
Total: $219.98
Status: Paid, Fulfilled
Date: 7 days ago
```

#### Order 2: Clothing Purchase

```
Customer: customer2@test.com
Products:
  - Cotton T-Shirt (2x) = $59.98
Total: $59.98
Status: Paid, Fulfilled
Date: 5 days ago
```

#### Order 3: Mixed Purchase

```
Customer: customer1@test.com
Products:
  - LED Desk Lamp (1x) = $49.99
  - Programming Guide (1x) = $24.99
Total: $74.98
Status: Paid, Fulfilled
Date: 3 days ago
```

#### Order 4: Single Item Purchase

```
Customer: customer3@test.com
Products:
  - Cotton T-Shirt (1x) = $29.99
Total: $29.99
Status: Paid, Fulfilled
Date: 2 days ago
```

#### Order 5: Large Purchase

```
Customer: customer2@test.com
Products:
  - Wireless Bluetooth Headphones (1x) = $199.99
  - LED Desk Lamp (1x) = $49.99
  - Programming Guide (1x) = $24.99
Total: $274.97
Status: Paid, Fulfilled
Date: 1 day ago
```

## 🧪 Expected Test Results

### Data Collection Results

- **Products**: 5 records
- **Collections**: 2 records
- **Customers**: 3 records
- **Orders**: 5 records
- **Line Items**: 8 records

### Feature Computation Results

#### Product Features (Expected: 5 records)

- Product 1: High engagement, premium pricing
- Product 2: Medium engagement, clothing category
- Product 3: Low engagement, accessory category
- Product 4: Medium engagement, home category
- Product 5: Low engagement, book category

#### User Features (Expected: 3 records)

- Customer 1: 2 orders, $294.96 total spent
- Customer 2: 2 orders, $334.95 total spent
- Customer 3: 1 order, $29.99 total spent

#### Collection Features (Expected: 2 records)

- Electronics Collection: 2 products, mixed performance
- Lifestyle Collection: 3 products, varied performance

#### Product Pair Features (Expected: Variable)

- Headphones + Phone Case (co-purchased)
- T-Shirt + Desk Lamp (co-purchased)
- Other combinations based on order patterns

## 🚀 Testing Steps

### Step 1: Create Test Data in Shopify

1. **Create Products**

   - Go to Products → Add product
   - Create each product with the specifications above
   - Ensure all products are published and active

2. **Create Collections**

   - Go to Products → Collections → Create collection
   - Add products to collections as specified
   - Ensure collections are published

3. **Create Customers**

   - Go to Customers → Add customer
   - Create each customer with the details above
   - Ensure customers are active

4. **Create Orders**
   - Go to Orders → Create order
   - Create each order with the specified products and customers
   - Mark orders as paid and fulfilled

### Step 2: Trigger Analysis

1. **Run Full Analysis**

   ```bash
   # In your Remix app, trigger the analysis
   # This should process all data in historical mode
   ```

2. **Monitor Logs**
   ```bash
   # Check the logs for processing status
   tail -f python-worker/logs/app.log
   ```

### Step 3: Verify Results

1. **Check Database**

   ```sql
   -- Verify data collection
   SELECT COUNT(*) FROM product_data;
   SELECT COUNT(*) FROM collection_data;
   SELECT COUNT(*) FROM customer_data;
   SELECT COUNT(*) FROM order_data;
   SELECT COUNT(*) FROM line_item_data;

   -- Verify feature computation
   SELECT COUNT(*) FROM product_features;
   SELECT COUNT(*) FROM user_features;
   SELECT COUNT(*) FROM collection_features;
   SELECT COUNT(*) FROM product_pair_features;
   ```

2. **Expected Counts**
   - `product_data`: 5 records
   - `collection_data`: 2 records
   - `customer_data`: 3 records
   - `order_data`: 5 records
   - `line_item_data`: 8 records
   - `product_features`: 5 records
   - `user_features`: 3 records
   - `collection_features`: 2 records
   - `product_pair_features`: Variable (2-4 records)

## 🔍 Validation Checklist

### ✅ Data Collection

- [ ] All 5 products collected
- [ ] All 2 collections collected
- [ ] All 3 customers collected
- [ ] All 5 orders collected
- [ ] All 8 line items collected

### ✅ Normalization

- [ ] No normalization errors in logs
- [ ] All required fields present
- [ ] Data types correct
- [ ] Relationships maintained

### ✅ Feature Computation

- [ ] Product features: 5 records
- [ ] User features: 3 records
- [ ] Collection features: 2 records
- [ ] Product pair features: 2+ records
- [ ] No feature computation errors

### ✅ ML Integration

- [ ] Gorse sync successful
- [ ] No sync errors
- [ ] Features available in Gorse

## 🐛 Troubleshooting

### Common Issues

1. **Missing Data**

   - Check if products are published
   - Verify orders are marked as paid
   - Ensure customers are active

2. **Feature Computation Errors**

   - Check for missing required fields
   - Verify data relationships
   - Review error logs

3. **Low Feature Counts**
   - Ensure sufficient order data
   - Check for data quality issues
   - Verify processing mode (historical vs incremental)

### Debug Commands

```bash
# Check data collection status
python -c "
from app.core.database.session import get_session_context
from app.core.database.models import ProductData, CustomerData, OrderData
with get_session_context() as session:
    print(f'Products: {session.query(ProductData).count()}')
    print(f'Customers: {session.query(CustomerData).count()}')
    print(f'Orders: {session.query(OrderData).count()}')
"

# Check feature computation status
python -c "
from app.core.database.session import get_session_context
from app.core.database.models import ProductFeatures, UserFeatures, CollectionFeatures
with get_session_context() as session:
    print(f'Product Features: {session.query(ProductFeatures).count()}')
    print(f'User Features: {session.query(UserFeatures).count()}')
    print(f'Collection Features: {session.query(CollectionFeatures).count()}')
"
```

## 📈 Performance Expectations

### Processing Time

- **Data Collection**: 30-60 seconds
- **Normalization**: 10-30 seconds
- **Feature Computation**: 60-120 seconds
- **Gorse Sync**: 30-60 seconds
- **Total**: 2-4 minutes

### Resource Usage

- **Memory**: 100-200 MB
- **CPU**: Moderate usage during processing
- **Database**: 1-5 MB storage

## 🎯 Success Criteria

The test is successful when:

1. **All data collected** without errors
2. **All features computed** with expected counts
3. **No critical errors** in logs
4. **Gorse sync successful** with features available
5. **Processing time** within expected range

## 📝 Test Report Template

```
Test Date: [DATE]
Shopify Shop: [SHOP_NAME]
Test Data: [PRODUCTS/COLLECTIONS/CUSTOMERS/ORDERS]

Results:
- Data Collection: ✅/❌
- Normalization: ✅/❌
- Feature Computation: ✅/❌
- ML Integration: ✅/❌

Issues Found:
- [List any issues]

Performance:
- Total Time: [X] minutes
- Memory Usage: [X] MB
- Database Size: [X] MB

Recommendations:
- [Any recommendations for improvement]
```

---

**Note**: This minimal test data is designed to validate the complete pipeline while keeping the setup simple. For production testing, consider using larger datasets with more diverse patterns.
