import type { ActionFunctionArgs } from "@remix-run/node";
import { prisma } from "../core/database/prisma.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    const { jobId, shopId, results } = await request.json();

    // Update job status to completed
    await prisma.analysisJob.update({
      where: { jobId },
      data: {
        status: "completed",
        progress: 100,
        result: results,
        completedAt: new Date(),
      },
    });

    // Update shop's last analysis timestamp
    await prisma.shop.update({
      where: { shopId },
      data: {
        lastAnalysisAt: new Date(),
      },
    });

    // Store bundle analysis results
    if (results.bundles && results.bundles.length > 0) {
      // Clear existing results
      await prisma.bundleAnalysisResult.deleteMany({
        where: { shopId },
      });

      // Store new results
      const bundleData = results.bundles.map((bundle: any) => ({
        shopId,
        productIds: bundle.product_ids,
        bundleSize: bundle.product_ids.length,
        coPurchaseCount: bundle.co_purchase_count,
        confidence: bundle.confidence,
        lift: bundle.lift,
        support: bundle.support,
        revenue: bundle.revenue_potential || 0,
        avgOrderValue: bundle.total_price || 0,
        discount: 0,
        isActive: true,
      }));

      await prisma.bundleAnalysisResult.createMany({
        data: bundleData,
      });
    }

    return Response.json({ success: true });
  } catch (error) {
    console.error("Error completing job:", error);
    return Response.json(
      { success: false, error: "Failed to complete job" },
      { status: 500 }
    );
  }
};
