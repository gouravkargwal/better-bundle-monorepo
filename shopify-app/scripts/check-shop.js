import { PrismaClient } from '@prisma/client';
import dotenv from 'dotenv';

dotenv.config();

const prisma = new PrismaClient();

async function checkAndCreateShop() {
  try {
    const shopDomain = 'vnsaid.myshopify.com';
    
    console.log(`🔍 Checking if shop exists: ${shopDomain}`);
    
    // Check if shop exists
    let shop = await prisma.shop.findUnique({
      where: { shopId: shopDomain }
    });
    
    if (!shop) {
      console.log(`❌ Shop not found. Creating shop record...`);
      
      // Create shop record
      shop = await prisma.shop.create({
        data: {
          shopId: shopDomain,
          shopDomain: shopDomain,
          accessToken: 'dummy-token-for-development',
          planType: 'Free',
          currencyCode: 'USD',
          moneyFormat: '${{amount}}',
          isActive: true
        }
      });
      
      console.log(`✅ Shop created successfully:`, shop.id);
    } else {
      console.log(`✅ Shop found:`, shop.id);
    }
    
    // Check if shop has any orders
    const orderCount = await prisma.orderData.count({
      where: { shopId: shop.id }
    });
    
    console.log(`📊 Shop has ${orderCount} orders`);
    
    // Check if shop has any products
    const productCount = await prisma.productData.count({
      where: { shopId: shop.id }
    });
    
    console.log(`📦 Shop has ${productCount} products`);
    
    return shop;
    
  } catch (error) {
    console.error('❌ Error checking/creating shop:', error);
    throw error;
  } finally {
    await prisma.$disconnect();
  }
}

checkAndCreateShop()
  .then(() => {
    console.log('✅ Shop check completed');
    process.exit(0);
  })
  .catch((error) => {
    console.error('❌ Shop check failed:', error);
    process.exit(1);
  });
