# Test Data Generator for BetterBundle Pipeline

This directory contains a comprehensive test data generator that creates realistic Shopify data for testing the entire BetterBundle pipeline.

## 🎯 Overview

The generator creates realistic test data that flows through the entire pipeline:

1. **Raw Shopify API data** → 2. **Main processed data** → 3. **Gorse bridge tables** → 4. **Incremental data push**

## 📁 File Structure

```
data/
├── base_data_generator.py              # Common utilities and base class
├── raw_products_generator.py           # Generates raw product data
├── raw_customers_generator.py          # Generates raw customer data
├── raw_orders_generator.py             # Generates raw order data (with relations)
├── raw_collections_generator.py        # Generates raw collection data
├── raw_behavioral_events_generator.py  # Generates behavioral event data
├── main_data_generator.py              # Main orchestrator
├── requirements.txt                    # Dependencies (none required)
└── README.md                          # This file
```

## 🚀 Quick Start

### Generate Medium Volume Data (Default)

```bash
cd data
python main_data_generator.py
```

### Generate Large Volume Data

```bash
python main_data_generator.py --volume large
```

### Generate Small Volume Data (for testing)

```bash
python main_data_generator.py --volume small
```

### Generate without saving to files

```bash
python main_data_generator.py --no-save
```

## 📊 Data Volumes

| Volume | Products | Customers | Orders | Collections | Events | Total Records |
| ------ | -------- | --------- | ------ | ----------- | ------ | ------------- |
| Small  | 150      | 300       | 600    | 30          | 3,000  | ~4,080        |
| Medium | 600      | 1,500     | 3,000  | 75          | 15,000 | ~20,175       |
| Large  | 1,500    | 3,000     | 6,000  | 150         | 30,000 | ~40,650       |

## 🏪 Multi-Tenancy

The generator creates data for **3 shops**:

- `shop_123` - Fashion Store
- `shop_456` - Electronics Hub
- `shop_789` - Home & Garden

Each shop has independent data with proper relations between customers, products, and orders.

## 🔗 Data Relations

The generator ensures proper relations between data:

### Products ↔ Collections

- Products are assigned to realistic collections
- Collections have proper rules and metadata

### Customers ↔ Orders

- Orders reference actual customer IDs
- Customer data includes order history

### Orders ↔ Products

- Order line items reference actual product IDs
- Realistic quantities, prices, and variants

### Behavioral Events ↔ Customers/Products

- Events reference actual customer and product IDs
- Realistic event sequences and timestamps

## 📋 Generated Data Types

### Raw Products

- Realistic product titles, descriptions, variants
- Proper categories, vendors, and pricing
- Images, options, and metafields
- Shopify-compatible structure

### Raw Customers

- Realistic names, emails, addresses
- Order history and spending patterns
- Customer tags and metafields
- Multi-address support

### Raw Orders

- Complete order structure with line items
- Realistic pricing, taxes, and shipping
- Fulfillment and refund data
- Customer and product relations

### Raw Collections

- Curated product collections
- Collection rules and filters
- Seasonal and thematic groupings
- Proper metadata

### Raw Behavioral Events

- Page views, product views, cart actions
- Purchase events with order relations
- Search and navigation events
- Realistic user behavior patterns

## 🎯 Testing Scenarios

This data supports testing:

### Multi-Tenancy

- Shop isolation and data separation
- Cross-shop data integrity
- Tenant-specific recommendations

### Incremental Processing

- Timestamp-based incremental updates
- Data change detection
- Pipeline efficiency

### Data Relations

- Customer-product interactions
- Order history and patterns
- Behavioral event sequences

### Edge Cases

- Empty data sets
- Missing relations
- Invalid data formats

## 🔧 Customization

### Modify Data Volumes

Edit `main_data_generator.py`:

```python
self.data_volumes = {
    "custom": {
        "products_per_shop": 1000,
        "customers_per_shop": 2000,
        # ... other settings
    }
}
```

### Add New Shops

Edit `main_data_generator.py`:

```python
self.shops = [
    {"id": "shop_123", "name": "Fashion Store"},
    {"id": "shop_456", "name": "Electronics Hub"},
    {"id": "shop_789", "name": "Home & Garden"},
    {"id": "shop_999", "name": "New Shop"}  # Add new shop
]
```

### Customize Product Categories

Edit `raw_products_generator.py`:

```python
self.product_titles = {
    "YourCategory": [
        "Your Product 1",
        "Your Product 2",
        # ... more products
    ]
}
```

## 📈 Usage in Pipeline Testing

1. **Generate Data**: Run the generator with desired volume
2. **Load Raw Data**: Insert generated data into raw tables
3. **Run Sync**: Execute your sync processes
4. **Test Incremental**: Run incremental data push
5. **Verify Results**: Check Gorse recommendations

## 🐛 Troubleshooting

### Import Errors

```bash
# Make sure you're in the data directory
cd data
python main_data_generator.py
```

### Memory Issues

- Use smaller volume: `--volume small`
- Generate data in batches
- Process one shop at a time

### File Permissions

```bash
# Create output directory with proper permissions
mkdir -p generated_data
chmod 755 generated_data
```

## 📝 Notes

- **No External Dependencies**: Uses only Python standard library
- **Deterministic**: Same seed produces same data (for testing)
- **Realistic**: Data mimics real Shopify store patterns
- **Scalable**: Can generate millions of records
- **Relations**: Maintains proper data relationships

## 🎉 Next Steps

1. Generate test data
2. Load into your database
3. Run your sync processes
4. Test incremental data push
5. Verify Gorse recommendations
6. Iterate and improve!

Happy testing! 🚀
