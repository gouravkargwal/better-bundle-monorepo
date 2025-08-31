import { faker } from '@faker-js/faker';
import fetch from 'node-fetch';
import dotenv from 'dotenv';

// Load environment variables from .env file
dotenv.config();

const SHOP = process.env.SHOP_DOMAIN; // Replace with your store domain
const ACCESS_TOKEN = process.env.SHOPIFY_ACCESS_TOKEN; // Replace with your private app or admin API access token

if (!SHOP) {
  console.error('❌ SHOP_DOMAIN environment variable is required');
  console.log('💡 Add SHOP_DOMAIN=your-store.myshopify.com to your .env file');
  process.exit(1);
}

if (!ACCESS_TOKEN) {
  console.error('❌ SHOPIFY_ACCESS_TOKEN environment variable is required');
  console.log('💡 Add SHOPIFY_ACCESS_TOKEN=your_token to your .env file');
  console.log('');
  console.log('🔍 Debug info:');
  console.log(`   - SHOP_DOMAIN: ${SHOP || 'NOT SET'}`);
  console.log(`   - SHOPIFY_ACCESS_TOKEN: ${ACCESS_TOKEN ? 'SET' : 'NOT SET'}`);
  console.log(`   - .env file location: ${process.cwd()}/.env`);
  process.exit(1);
}

// Helper function to make authenticated Shopify API requests with rate limit handling
async function shopifyRequest(endpoint, method = 'GET', body = null, retryCount = 0) {
  const url = `https://${SHOP}/admin/api/2025-07/${endpoint}`;
  const options = {
    method,
    headers: {
      'X-Shopify-Access-Token': ACCESS_TOKEN,
      'Content-Type': 'application/json',
    },
  };
  if (body) options.body = JSON.stringify(body);

  try {
    const response = await fetch(url, options);

    // Handle rate limiting with exponential backoff
    if (response.status === 429) {
      const retryAfter = response.headers.get('Retry-After') || 60;
      const backoffTime = Math.min(retryAfter * 1000 * Math.pow(2, retryCount), 300000); // Max 5 minutes

      console.log(`⏳ Rate limited. Waiting ${Math.round(backoffTime / 1000)}s before retry ${retryCount + 1}/3...`);
      await new Promise(resolve => setTimeout(resolve, backoffTime));

      if (retryCount < 3) {
        return shopifyRequest(endpoint, method, body, retryCount + 1);
      } else {
        throw new Error(`Rate limit exceeded after ${retryCount + 1} retries`);
      }
    }

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Shopify API error: ${response.status} ${errorText}`);
    }

    return response.json();
  } catch (error) {
    if (error.message.includes('Rate limit') && retryCount < 3) {
      const backoffTime = Math.min(60000 * Math.pow(2, retryCount), 300000); // 1min, 2min, 4min
      console.log(`⏳ Rate limit error. Waiting ${Math.round(backoffTime / 1000)}s before retry ${retryCount + 1}/3...`);
      await new Promise(resolve => setTimeout(resolve, backoffTime));
      return shopifyRequest(endpoint, method, body, retryCount + 1);
    }
    throw error;
  }
}

// Define bundle categories with related products
const bundleCategories = [
  {
    name: 'Skincare Bundle',
    products: [
      { title: 'Gentle Facial Cleanser', price: '24.99', type: 'Cleanser' },
      { title: 'Hydrating Moisturizer', price: '32.99', type: 'Moisturizer' },
      { title: 'Vitamin C Serum', price: '45.99', type: 'Serum' },
      { title: 'Sunscreen SPF 30', price: '28.99', type: 'Sunscreen' }
    ]
  },
  {
    name: 'Coffee Bundle',
    products: [
      { title: 'Premium Coffee Beans', price: '18.99', type: 'Coffee' },
      { title: 'Coffee Grinder', price: '89.99', type: 'Grinder' },
      { title: 'French Press', price: '45.99', type: 'Press' },
      { title: 'Coffee Mug Set', price: '34.99', type: 'Mugs' }
    ]
  },
  {
    name: 'Fitness Bundle',
    products: [
      { title: 'Yoga Mat', price: '39.99', type: 'Mat' },
      { title: 'Resistance Bands Set', price: '24.99', type: 'Bands' },
      { title: 'Foam Roller', price: '29.99', type: 'Roller' },
      { title: 'Water Bottle', price: '19.99', type: 'Bottle' }
    ]
  },
  {
    name: 'Tech Bundle',
    products: [
      { title: 'Wireless Earbuds', price: '79.99', type: 'Earbuds' },
      { title: 'Phone Stand', price: '24.99', type: 'Stand' },
      { title: 'USB-C Cable', price: '14.99', type: 'Cable' },
      { title: 'Screen Protector', price: '9.99', type: 'Protector' }
    ]
  },
  {
    name: 'Baking Bundle',
    products: [
      { title: 'Stand Mixer', price: '199.99', type: 'Mixer' },
      { title: 'Baking Sheet Set', price: '34.99', type: 'Sheets' },
      { title: 'Measuring Cups', price: '19.99', type: 'Cups' },
      { title: 'Spatula Set', price: '24.99', type: 'Spatulas' }
    ]
  }
];

// Create products with deliberate bundle patterns
async function createBundleProducts() {
  console.log('📦 Creating bundle-friendly products...');
  const createdProducts = [];

  for (const category of bundleCategories) {
    console.log(`\n🏷️  Creating ${category.name} products...`);
    
    for (const product of category.products) {
      try {
        const productData = {
          product: {
            title: product.title,
            body_html: `${product.title} - Perfect for your daily needs. High quality and durable.`,
            vendor: faker.company.name(),
            product_type: product.type,
            tags: category.name.toLowerCase().replace(' ', '-'),
            variants: [{
              price: product.price,
              sku: faker.string.alphanumeric(8),
              inventory_management: 'shopify',
              inventory_quantity: faker.number.int({ min: 10, max: 100 }),
            }],
            images: [
              { src: faker.image.url({ width: 640, height: 480, category: 'product' }) }
            ],
          }
        };

        const productResponse = await shopifyRequest('products.json', 'POST', productData);
        const variantId = productResponse.product.variants[0].id;
        
        createdProducts.push({
          id: variantId,
          title: product.title,
          category: category.name,
          type: product.type,
          price: parseFloat(product.price)
        });

        console.log(`✅ Created: ${product.title} ($${product.price})`);
        await new Promise(resolve => setTimeout(resolve, 1000));
      } catch (error) {
        console.error(`❌ Error creating ${product.title}:`, error.message);
      }
    }
  }

  return createdProducts;
}

// Create orders with deliberate bundle patterns
async function createBundleOrders(products) {
  console.log('\n🛒 Creating orders with bundle patterns...');
  
  // Group products by category
  const productsByCategory = {};
  products.forEach(product => {
    if (!productsByCategory[product.category]) {
      productsByCategory[product.category] = [];
    }
    productsByCategory[product.category].push(product);
  });

  let successfulOrders = 0;
  const totalOrders = 50; // Create more orders for better bundle detection

  for (let i = 0; i < totalOrders; i++) {
    try {
      const lineItems = [];
      
      // 70% chance to create a bundle order (2+ products from same category)
      if (Math.random() < 0.7) {
        // Bundle order - pick a random category and add 2-3 products from it
        const categories = Object.keys(productsByCategory);
        const selectedCategory = categories[Math.floor(Math.random() * categories.length)];
        const categoryProducts = productsByCategory[selectedCategory];
        
        // Add 2-3 products from the same category
        const bundleSize = Math.random() < 0.6 ? 2 : 3; // 60% chance for 2 products, 40% for 3
        const shuffled = [...categoryProducts].sort(() => 0.5 - Math.random());
        
        for (let j = 0; j < Math.min(bundleSize, shuffled.length); j++) {
          const product = shuffled[j];
          lineItems.push({
            variant_id: product.id,
            quantity: faker.number.int({ min: 1, max: 2 }),
          });
        }
        
        console.log(`✅ Bundle order ${i + 1}: ${bundleSize} products from ${selectedCategory}`);
      } else {
        // Single product order (30% chance)
        const randomProduct = products[Math.floor(Math.random() * products.length)];
        lineItems.push({
          variant_id: randomProduct.id,
          quantity: faker.number.int({ min: 1, max: 3 }),
        });
        console.log(`✅ Single order ${i + 1}: ${randomProduct.title}`);
      }

      const totalPrice = lineItems.reduce((acc, item) => {
        const product = products.find(p => p.id === item.variant_id);
        return acc + (item.quantity * (product?.price || 20));
      }, 0);

      const orderData = {
        order: {
          line_items: lineItems,
          email: faker.internet.email(),
          financial_status: 'paid',
          total_price: totalPrice.toFixed(2),
          billing_address: {
            first_name: faker.person.firstName(),
            last_name: faker.person.lastName(),
            address1: '123 Main St',
            city: 'New York',
            province: 'NY',
            country: 'US',
            zip: '10001',
          },
          tags: `Bundle Test Order #${i + 1}`,
        },
      };

      await shopifyRequest('orders.json', 'POST', orderData);
      successfulOrders++;

      // Longer delay for orders
      await new Promise(resolve => setTimeout(resolve, 2000));
    } catch (error) {
      console.error(`❌ Error creating order ${i + 1}:`, error.message);
      if (error.message.includes('Rate limit exceeded')) {
        console.log('⚠️  Stopping order creation due to rate limits. You can run the script again later.');
        break;
      }
    }
  }

  return successfulOrders;
}

async function seedShopify() {
  console.log('🚀 Starting Bundle-Friendly Shopify Store Seeding...\n');
  console.log(`🏪 Target store: ${SHOP}\n`);

  // Create products with deliberate bundle patterns
  const products = await createBundleProducts();
  
  if (products.length === 0) {
    console.error('❌ No products were created. Cannot proceed with orders.');
    return;
  }

  console.log(`\n📊 Created ${products.length} products across ${bundleCategories.length} categories`);

  // Create orders with bundle patterns
  const successfulOrders = await createBundleOrders(products);

  console.log('\n🎉 Bundle-friendly seeding completed!');
  console.log(`📊 Summary:`);
  console.log(`   - Products created: ${products.length}`);
  console.log(`   - Orders created: ${successfulOrders}`);
  console.log(`   - Bundle categories: ${bundleCategories.length}`);
  console.log(`   - Expected bundle combinations: ~${Math.floor(successfulOrders * 0.7 * 2)}`);
  
  console.log('\n🏷️  Bundle Categories Created:');
  bundleCategories.forEach(category => {
    console.log(`   - ${category.name}: ${category.products.length} products`);
  });

  console.log('\n💡 Bundle Patterns:');
  console.log('   - 70% of orders contain 2-3 products from the same category');
  console.log('   - 30% of orders contain single products');
  console.log('   - Perfect for testing bundle analytics!');

  console.log('\n🚀 Next steps:');
  console.log('   1. Open your BetterBundle app');
  console.log('   2. Click "Analyze My Store"');
  console.log('   3. You should now see bundle recommendations!');
  console.log('   4. Look for bundles like "Skincare Bundle", "Coffee Bundle", etc.');
}

seedShopify().catch(console.error);
