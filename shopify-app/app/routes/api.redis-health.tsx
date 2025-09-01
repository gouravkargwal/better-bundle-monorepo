import type { LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { redisStreamsService } from "../core/redis/redis-streams.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  try {
    const { session } = await authenticate.admin(request);
    
    // Initialize Redis Streams service
    await redisStreamsService.initialize();

    // Test Redis connection
    const isHealthy = await redisStreamsService.healthCheck();
    
    if (!isHealthy) {
      return Response.json(
        { 
          success: false, 
          error: "Redis connection failed",
          timestamp: new Date().toISOString()
        },
        { status: 503 }
      );
    }

    // Get stream statistics
    const streamStats = {
      dataJobs: await redisStreamsService.getStreamLength("betterbundle:data-jobs"),
      mlTraining: await redisStreamsService.getStreamLength("betterbundle:ml-training"),
      analysisResults: await redisStreamsService.getStreamLength("betterbundle:analysis-results"),
      userNotifications: await redisStreamsService.getStreamLength("betterbundle:user-notifications"),
      featuresComputed: await redisStreamsService.getStreamLength("betterbundle:features-computed"),
    };

    return Response.json({
      success: true,
      message: "Redis Streams service is healthy",
      timestamp: new Date().toISOString(),
      data: {
        redis: "connected",
        streams: streamStats,
        service: "ready"
      }
    });

  } catch (error) {
    console.error("Redis health check failed:", error);
    return Response.json(
      { 
        success: false, 
        error: "Redis health check failed",
        details: error instanceof Error ? error.message : "Unknown error",
        timestamp: new Date().toISOString()
      },
      { status: 500 }
    );
  }
};
