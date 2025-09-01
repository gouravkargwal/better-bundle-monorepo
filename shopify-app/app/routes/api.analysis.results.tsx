import type { LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { redisStreamsService } from "../core/redis/redis-streams.server";
import { prisma } from "../core/database/prisma.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  try {
    const { session } = await authenticate.admin(request);
    const shopDomain = session.shop!;

    // Initialize Redis Streams service
    await redisStreamsService.initialize();

    // Get the last processed message ID from query params or use "0" for all
    const url = new URL(request.url);
    const lastId = url.searchParams.get("lastId") || "0";
    const count = parseInt(url.searchParams.get("count") || "10");

    // Read analysis results from Redis Streams
    const results = await redisStreamsService.readAnalysisResults(
      shopDomain,
      lastId,
      count
    );

    // Get shop info
    const shop = await prisma.shop.findUnique({
      where: { shopDomain },
      select: { id: true, shopDomain: true },
    });

    if (!shop) {
      return Response.json(
        { success: false, error: "Shop not found" },
        { status: 404 }
      );
    }

    // Get analysis jobs for this shop
    const analysisJobs = await prisma.analysisJob.findMany({
      where: { shopId: shop.id },
      orderBy: { createdAt: "desc" },
      take: 10,
      select: {
        id: true,
        jobId: true,
        status: true,
        progress: true,
        createdAt: true,
        completedAt: true,
        error: true,
        result: true,
      },
    });

    // Get bundle analysis results
    const bundleResults = await prisma.bundleAnalysisResult.findMany({
      where: { shopId: shop.id, isActive: true },
      orderBy: { analysisDate: "desc" },
      take: 20,
    });

    return Response.json({
      success: true,
      data: {
        shop: {
          id: shop.id,
          domain: shop.shopDomain,
        },
        streamResults: results,
        analysisJobs,
        bundleResults,
        streamInfo: {
          lastId: results.length > 0 ? results[results.length - 1]?.id : lastId,
          count: results.length,
          hasMore: results.length === count,
        },
      },
    });
  } catch (error) {
    console.error("Error fetching analysis results:", error);
    return Response.json(
      { success: false, error: "Failed to fetch analysis results" },
      { status: 500 }
    );
  }
};

export const action = async ({ request }: LoaderFunctionArgs) => {
  try {
    const { session } = await authenticate.admin(request);

    // Initialize Redis Streams service
    await redisStreamsService.initialize();

    // Get stream statistics
    const streamStats = {
      dataJobs: await redisStreamsService.getStreamLength("betterbundle:data-jobs"),
      mlTraining: await redisStreamsService.getStreamLength("betterbundle:ml-training"),
      analysisResults: await redisStreamsService.getStreamLength("betterbundle:analysis-results"),
      userNotifications: await redisStreamsService.getStreamLength("betterbundle:user-notifications"),
      featuresComputed: await redisStreamsService.getStreamLength("betterbundle:features-computed"),
    };

    // Get pending messages for consumer groups
    const pendingStats = {
      dataProcessors: await redisStreamsService.getPendingMessages(
        "betterbundle:data-jobs",
        "data-processors",
        "consumer-1"
      ),
      mlProcessors: await redisStreamsService.getPendingMessages(
        "betterbundle:ml-training",
        "ml-processors",
        "consumer-1"
      ),
    };

    return Response.json({
      success: true,
      data: {
        streamStats,
        pendingStats: {
          dataProcessors: pendingStats.dataProcessors.length,
          mlProcessors: pendingStats.mlProcessors.length,
        },
        health: await redisStreamsService.healthCheck(),
      },
    });
  } catch (error) {
    console.error("Error getting stream statistics:", error);
    return Response.json(
      { success: false, error: "Failed to get stream statistics" },
      { status: 500 }
    );
  }
};
