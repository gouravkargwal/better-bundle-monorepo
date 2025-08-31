import type { ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { prisma } from "../core/database/prisma.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  const { shop, session, topic } = await authenticate.webhook(request);

  console.log(`Received ${topic} webhook for ${shop}`);

  try {
    // Webhook requests can trigger multiple times and after an app has already been uninstalled.
    // If this webhook already ran, the session may have been deleted previously.
    if (session) {
      console.log(`🧹 Cleaning up data for uninstalled app: ${shop}`);

      // Delete sessions first
      const deletedSessions = await prisma.session.deleteMany({
        where: { shop },
      });
      console.log(`🗑️ Deleted ${deletedSessions.count} sessions for ${shop}`);

      // Find the shop record to get its database ID
      const shopRecord = await prisma.shop.findUnique({
        where: { shopDomain: shop },
        select: { id: true },
      });

      if (shopRecord) {
        console.log(`🏪 Found shop record with ID: ${shopRecord.id}`);

        // Delete all analysis jobs for this shop
        const deletedJobs = await prisma.analysisJob.deleteMany({
          where: { shopId: shopRecord.id },
        });
        console.log(
          `🗑️ Deleted ${deletedJobs.count} analysis jobs for ${shop}`,
        );

        // Delete all order data for this shop
        const deletedOrders = await prisma.orderData.deleteMany({
          where: { shopId: shopRecord.id },
        });
        console.log(`🗑️ Deleted ${deletedOrders.count} orders for ${shop}`);

        // Delete all product data for this shop
        const deletedProducts = await prisma.productData.deleteMany({
          where: { shopId: shopRecord.id },
        });
        console.log(`🗑️ Deleted ${deletedProducts.count} products for ${shop}`);

        // Delete all bundle analysis results for this shop
        const deletedBundles = await prisma.bundleAnalysisResult.deleteMany({
          where: { shopId: shopRecord.id },
        });
        console.log(
          `🗑️ Deleted ${deletedBundles.count} bundle analyses for ${shop}`,
        );

        // Delete all tracked sales for this shop
        const deletedSales = await prisma.trackedSale.deleteMany({
          where: { shopId: shopRecord.id },
        });
        console.log(
          `🗑️ Deleted ${deletedSales.count} tracked sales for ${shop}`,
        );

        // Delete all widget events for this shop
        const deletedEvents = await prisma.widgetEvent.deleteMany({
          where: { shopId: shopRecord.id },
        });
        console.log(
          `🗑️ Deleted ${deletedEvents.count} widget events for ${shop}`,
        );

        // Delete widget configuration for this shop
        const deletedWidgetConfig = await prisma.widgetConfiguration.deleteMany(
          {
            where: { shopId: shopRecord.id },
          },
        );
        console.log(
          `🗑️ Deleted ${deletedWidgetConfig.count} widget configurations for ${shop}`,
        );

        // Delete shop analysis config for this shop
        const deletedAnalysisConfig =
          await prisma.shopAnalysisConfig.deleteMany({
            where: { shopId: shopRecord.id },
          });
        console.log(
          `🗑️ Deleted ${deletedAnalysisConfig.count} analysis configs for ${shop}`,
        );

        // Delete all heuristic decisions for this shop
        const deletedDecisions = await prisma.heuristicDecision.deleteMany({
          where: { shopId: shopRecord.id },
        });
        console.log(
          `🗑️ Deleted ${deletedDecisions.count} heuristic decisions for ${shop}`,
        );

        // Delete all incremental analysis logs for this shop
        const deletedLogs = await prisma.incrementalAnalysisLog.deleteMany({
          where: { shopId: shopRecord.id },
        });
        console.log(
          `🗑️ Deleted ${deletedLogs.count} incremental logs for ${shop}`,
        );

        // Finally, delete the shop record itself
        await prisma.shop.delete({
          where: { id: shopRecord.id },
        });
        console.log(`🗑️ Deleted shop record for ${shop}`);

        console.log(`✅ Complete cleanup completed for ${shop}`);
      } else {
        console.log(
          `⚠️ No shop record found for ${shop}, skipping data cleanup`,
        );
      }
    } else {
      console.log(
        `⚠️ No session found for ${shop}, app may have been already uninstalled`,
      );
    }
  } catch (error) {
    console.error(`❌ Error during app uninstall cleanup for ${shop}:`, error);
    // Don't throw the error as webhook failures can cause issues
    // Just log it for debugging
  }

  return new Response();
};
