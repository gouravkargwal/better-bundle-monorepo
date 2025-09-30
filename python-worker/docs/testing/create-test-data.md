# Shopify Test Data Creation Script

This guide provides a script to help create the minimal test data in Shopify programmatically.

## 🚀 Quick Setup Script

### Prerequisites

- Shopify CLI installed
- Access to your Shopify development store
- Basic knowledge of Shopify GraphQL API

### 1. Create Products Script

```javascript
// create-products.js
const products = [
  {
    title: "Wireless Bluetooth Headphones",
    description: "Premium wireless headphones with noise cancellation",
    price: "199.99",
    productType: "Electronics",
    vendor: "TechCorp",
    tags: ["wireless", "bluetooth", "premium", "electronics"],
    inventory: 50,
  },
  {
    title: "Cotton T-Shirt",
    description: "Comfortable 100% cotton t-shirt",
    price: "29.99",
    productType: "Clothing",
    vendor: "FashionBrand",
    tags: ["cotton", "casual", "clothing"],
    inventory: 100,
  },
  {
    title: "Phone Case",
    description: "Protective phone case with design",
    price: "19.99",
    productType: "Accessories",
    vendor: "TechCorp",
    tags: ["phone", "protection", "accessories"],
    inventory: 75,
  },
  {
    title: "LED Desk Lamp",
    description: "Adjustable LED desk lamp with USB port",
    price: "49.99",
    productType: "Home & Garden",
    vendor: "HomeGoods",
    tags: ["led", "desk", "lighting", "usb"],
    inventory: 30,
  },
  {
    title: "Programming Guide",
    description: "Complete guide to modern programming",
    price: "24.99",
    productType: "Books",
    vendor: "BookPublisher",
    tags: ["programming", "guide", "education", "books"],
    inventory: 25,
  },
];

// GraphQL mutation for creating products
const createProductMutation = `
  mutation productCreate($input: ProductInput!) {
    productCreate(input: $input) {
      product {
        id
        title
        handle
      }
      userErrors {
        field
        message
      }
    }
  }
`;

// Function to create products
async function createProducts() {
  for (const product of products) {
    const input = {
      title: product.title,
      description: product.description,
      productType: product.productType,
      vendor: product.vendor,
      tags: product.tags,
      variants: [
        {
          price: product.price,
          inventoryQuantity: product.inventory,
        },
      ],
    };

    // Execute mutation
    console.log(`Creating product: ${product.title}`);
    // Add your Shopify API call here
  }
}
```

### 2. Create Collections Script

```javascript
// create-collections.js
const collections = [
  {
    title: "Electronics & Tech",
    description: "Latest electronics and technology products",
    handle: "electronics-tech",
    productIds: [], // Will be populated after products are created
  },
  {
    title: "Lifestyle & Home",
    description: "Products for comfortable living",
    handle: "lifestyle-home",
    productIds: [], // Will be populated after products are created
  },
];

const createCollectionMutation = `
  mutation collectionCreate($input: CollectionInput!) {
    collectionCreate(input: $input) {
      collection {
        id
        title
        handle
      }
      userErrors {
        field
        message
      }
    }
  }
`;
```

### 3. Create Customers Script

```javascript
// create-customers.js
const customers = [
  {
    email: "customer1@test.com",
    firstName: "John",
    lastName: "Smith",
    phone: "+1-555-0101",
    addresses: [
      {
        address1: "123 Main St",
        city: "New York",
        province: "NY",
        zip: "10001",
        country: "US",
      },
    ],
    tags: ["regular", "loyal"],
  },
  {
    email: "customer2@test.com",
    firstName: "Sarah",
    lastName: "Johnson",
    phone: "+1-555-0102",
    addresses: [
      {
        address1: "456 Oak Ave",
        city: "Los Angeles",
        province: "CA",
        zip: "90210",
        country: "US",
      },
    ],
    tags: ["premium", "high-value"],
  },
  {
    email: "customer3@test.com",
    firstName: "Mike",
    lastName: "Davis",
    phone: "+1-555-0103",
    addresses: [
      {
        address1: "789 Pine St",
        city: "Chicago",
        province: "IL",
        zip: "60601",
        country: "US",
      },
    ],
    tags: ["new", "first-time"],
  },
];

const createCustomerMutation = `
  mutation customerCreate($input: CustomerInput!) {
    customerCreate(input: $input) {
      customer {
        id
        email
        firstName
        lastName
      }
      userErrors {
        field
        message
      }
    }
  }
`;
```

### 4. Create Orders Script

```javascript
// create-orders.js
const orders = [
  {
    customerEmail: "customer1@test.com",
    lineItems: [
      {
        productTitle: "Wireless Bluetooth Headphones",
        quantity: 1,
        price: "199.99",
      },
      { productTitle: "Phone Case", quantity: 1, price: "19.99" },
    ],
    totalPrice: "219.98",
    financialStatus: "PAID",
    fulfillmentStatus: "FULFILLED",
  },
  {
    customerEmail: "customer2@test.com",
    lineItems: [
      { productTitle: "Cotton T-Shirt", quantity: 2, price: "29.99" },
    ],
    totalPrice: "59.98",
    financialStatus: "PAID",
    fulfillmentStatus: "FULFILLED",
  },
  {
    customerEmail: "customer1@test.com",
    lineItems: [
      { productTitle: "LED Desk Lamp", quantity: 1, price: "49.99" },
      { productTitle: "Programming Guide", quantity: 1, price: "24.99" },
    ],
    totalPrice: "74.98",
    financialStatus: "PAID",
    fulfillmentStatus: "FULFILLED",
  },
  {
    customerEmail: "customer3@test.com",
    lineItems: [
      { productTitle: "Cotton T-Shirt", quantity: 1, price: "29.99" },
    ],
    totalPrice: "29.99",
    financialStatus: "PAID",
    fulfillmentStatus: "FULFILLED",
  },
  {
    customerEmail: "customer2@test.com",
    lineItems: [
      {
        productTitle: "Wireless Bluetooth Headphones",
        quantity: 1,
        price: "199.99",
      },
      { productTitle: "LED Desk Lamp", quantity: 1, price: "49.99" },
      { productTitle: "Programming Guide", quantity: 1, price: "24.99" },
    ],
    totalPrice: "274.97",
    financialStatus: "PAID",
    fulfillmentStatus: "FULFILLED",
  },
];

const createOrderMutation = `
  mutation orderCreate($input: OrderInput!) {
    orderCreate(input: $input) {
      order {
        id
        name
        totalPrice
      }
      userErrors {
        field
        message
      }
    }
  }
`;
```

## 🛠️ Manual Creation Steps

If you prefer to create the data manually in Shopify Admin:

### 1. Create Products

1. Go to **Products** → **Add product**
2. Fill in the product details from the test data
3. Set price, inventory, and tags
4. Publish the product
5. Repeat for all 5 products

### 2. Create Collections

1. Go to **Products** → **Collections** → **Create collection**
2. Add collection title and description
3. Add products to the collection
4. Publish the collection
5. Repeat for both collections

### 3. Create Customers

1. Go to **Customers** → **Add customer**
2. Fill in customer details
3. Add address information
4. Save the customer
5. Repeat for all 3 customers

### 4. Create Orders

1. Go to **Orders** → **Create order**
2. Select the customer
3. Add products to the order
4. Set order status to "Paid" and "Fulfilled"
5. Save the order
6. Repeat for all 5 orders

## ✅ Verification Checklist

After creating the test data, verify:

- [ ] 5 products created and published
- [ ] 2 collections created with correct products
- [ ] 3 customers created with addresses
- [ ] 5 orders created with correct line items
- [ ] All orders marked as paid and fulfilled
- [ ] Product variants have inventory
- [ ] Collections are published and active

## 🚨 Common Issues

1. **Products not showing in collections**

   - Ensure products are published
   - Check collection conditions
   - Verify product tags match collection rules

2. **Orders not processing**

   - Ensure orders are marked as paid
   - Check that products have inventory
   - Verify customer information is complete

3. **Missing line items**
   - Ensure products are added to orders
   - Check product variants are available
   - Verify quantities are set correctly

## 📊 Expected Data Summary

After successful creation, you should have:

- **5 Products** across 5 different categories
- **2 Collections** with 2-3 products each
- **3 Customers** with different spending patterns
- **5 Orders** with 8 total line items
- **Total Revenue**: $659.90 across all orders

This data will provide a comprehensive test of the feature computation pipeline while keeping the setup minimal and manageable.
