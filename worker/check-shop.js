require('dotenv').config({ path: '../local.env' });
const { PrismaClient } = require('@prisma/client');

const prisma = new PrismaClient();

async function checkShop() {
  try {
    console.log('🔍 Checking shop details...');

    const shop = await prisma.shop.findFirst({
      select: {
        id: true,
        shopId: true,
        shopDomain: true,
        lastAnalysisAt: true,
        createdAt: true
      }
    });

    if (shop) {
      console.log(`\n🏪 Shop Details:`);
      console.log(`   ID: ${shop.id}`);
      console.log(`   Shopify ID: ${shop.shopId}`);
      console.log(`   Domain: ${shop.shopDomain}`);
      console.log(`   Last Analysis: ${shop.lastAnalysisAt || 'Never'}`);
      console.log(`   Created: ${shop.createdAt}`);
    } else {
      console.log('❌ No shop found');
    }

  } catch (error) {
    console.error('❌ Error checking shop:', error);
  } finally {
    await prisma.$disconnect();
  }
}

checkShop();
