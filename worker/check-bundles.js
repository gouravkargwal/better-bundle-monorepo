require('dotenv').config({ path: '../local.env' });
const { PrismaClient } = require('@prisma/client');

const prisma = new PrismaClient();

async function checkBundles() {
  try {
    console.log('🔍 Checking bundle analysis results...');
    console.log(`🔑 DATABASE_URL: ${process.env.DATABASE_URL ? 'Set' : 'Not set'}`);

    // Check if we have any shops
    const shops = await prisma.shop.findMany({
      select: { id: true, shopId: true, shopDomain: true }
    });
    console.log(`📊 Found ${shops.length} shops`);

    if (shops.length === 0) {
      console.log('❌ No shops found in database');
      return;
    }

    // Check bundle analysis results
    const bundles = await prisma.bundleAnalysisResult.findMany({
      take: 10,
      include: {
        shop: {
          select: { shopDomain: true }
        }
      }
    });

    console.log(`🎯 Found ${bundles.length} bundle analysis results`);

    if (bundles.length > 0) {
      console.log('\n📋 Sample bundles:');
      bundles.slice(0, 3).forEach((bundle, index) => {
        console.log(`\n${index + 1}. Shop: ${bundle.shop.shopDomain}`);
        console.log(`   Products: ${bundle.productIds.join(', ')}`);
        console.log(`   Confidence: ${bundle.confidence}`);
        console.log(`   Lift: ${bundle.lift}`);
        console.log(`   Revenue: $${bundle.revenue}`);
        console.log(`   Created: ${bundle.analysisDate}`);
      });
    } else {
      console.log('❌ No bundle analysis results found');

      // Check if we have orders and products
      const orders = await prisma.orderData.count();
      const products = await prisma.productData.count();
      console.log(`\n📊 Database has ${orders} orders and ${products} products`);
    }

    // Check heuristic decisions
    const decisions = await prisma.heuristicDecision.findMany({
      take: 5,
      include: {
        shop: {
          select: { shopDomain: true }
        }
      }
    });

    console.log(`\n🧠 Found ${decisions.length} heuristic decisions`);
    if (decisions.length > 0) {
      decisions.slice(0, 2).forEach((decision, index) => {
        console.log(`\n${index + 1}. Shop: ${decision.shop.shopDomain}`);
        console.log(`   Decision: ${decision.decision}`);
        console.log(`   Reason: ${decision.reason}`);
        console.log(`   Created: ${decision.createdAt}`);
      });
    }

  } catch (error) {
    console.error('❌ Error checking bundles:', error);
  } finally {
    await prisma.$disconnect();
  }
}

checkBundles();
