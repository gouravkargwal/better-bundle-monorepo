import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

async function cleanupStaleData(shopDomain) {
  console.log(`🧹 Starting cleanup for shop: ${shopDomain}`);
  
  try {
    // Find the shop record
    const shopRecord = await prisma.shop.findUnique({
      where: { shopDomain },
      select: { id: true, shopDomain: true }
    });

    if (!shopRecord) {
      console.log(`⚠️ No shop record found for ${shopDomain}`);
      return;
    }

    console.log(`🏪 Found shop record with ID: ${shopRecord.id}`);

    // Delete all sessions for this shop
    const deletedSessions = await prisma.session.deleteMany({
      where: { shop: shopDomain }
    });
    console.log(`🗑️ Deleted ${deletedSessions.count} sessions`);

    // Delete all analysis jobs
    const deletedJobs = await prisma.analysisJob.deleteMany({
      where: { shopId: shopRecord.id }
    });
    console.log(`🗑️ Deleted ${deletedJobs.count} analysis jobs`);

    // Delete all order data
    const deletedOrders = await prisma.orderData.deleteMany({
      where: { shopId: shopRecord.id }
    });
    console.log(`🗑️ Deleted ${deletedOrders.count} orders`);

    // Delete all product data
    const deletedProducts = await prisma.productData.deleteMany({
      where: { shopId: shopRecord.id }
    });
    console.log(`🗑️ Deleted ${deletedProducts.count} products`);

    // Delete all bundle analysis results
    const deletedBundles = await prisma.bundleAnalysisResult.deleteMany({
      where: { shopId: shopRecord.id }
    });
    console.log(`🗑️ Deleted ${deletedBundles.count} bundle analyses`);

    // Delete all tracked sales
    const deletedSales = await prisma.trackedSale.deleteMany({
      where: { shopId: shopRecord.id }
    });
    console.log(`🗑️ Deleted ${deletedSales.count} tracked sales`);

    // Delete all widget events
    const deletedEvents = await prisma.widgetEvent.deleteMany({
      where: { shopId: shopRecord.id }
    });
    console.log(`🗑️ Deleted ${deletedEvents.count} widget events`);

    // Delete widget configuration
    const deletedWidgetConfig = await prisma.widgetConfiguration.deleteMany({
      where: { shopId: shopRecord.id }
    });
    console.log(`🗑️ Deleted ${deletedWidgetConfig.count} widget configurations`);

    // Delete shop analysis config
    const deletedAnalysisConfig = await prisma.shopAnalysisConfig.deleteMany({
      where: { shopId: shopRecord.id }
    });
    console.log(`🗑️ Deleted ${deletedAnalysisConfig.count} analysis configs`);

    // Delete all heuristic decisions
    const deletedDecisions = await prisma.heuristicDecision.deleteMany({
      where: { shopId: shopRecord.id }
    });
    console.log(`🗑️ Deleted ${deletedDecisions.count} heuristic decisions`);

    // Delete all incremental analysis logs
    const deletedLogs = await prisma.incrementalAnalysisLog.deleteMany({
      where: { shopId: shopRecord.id }
    });
    console.log(`🗑️ Deleted ${deletedLogs.count} incremental logs`);

    // Finally, delete the shop record itself
    await prisma.shop.delete({
      where: { id: shopRecord.id }
    });
    console.log(`🗑️ Deleted shop record`);

    console.log(`✅ Complete cleanup completed for ${shopDomain}`);
    
  } catch (error) {
    console.error(`❌ Error during cleanup:`, error);
  } finally {
    await prisma.$disconnect();
  }
}

// Get shop domain from command line argument
const shopDomain = process.argv[2];

if (!shopDomain) {
  console.log('Usage: node scripts/cleanup-stale-data.js <shop-domain>');
  console.log('Example: node scripts/cleanup-stale-data.js vnsaid.myshopify.com');
  process.exit(1);
}

cleanupStaleData(shopDomain);
