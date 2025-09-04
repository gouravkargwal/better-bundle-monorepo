import type { ActionFunctionArgs, LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { prisma } from "../core/database/prisma.server";
import { redisStreamsService } from "../core/redis/redis-streams.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  console.log("🔍 [API_ANALYSIS] GET request received");
  return json({ message: "Analysis API endpoint", method: "GET" });
};

export const action = async ({ request }: ActionFunctionArgs) => {
  console.log("🔍 [API_ANALYSIS] POST request received");
  try {
    const { session } = await authenticate.admin(request);
    const shopId = session.shop!;

    console.log(`🔍 [API_ANALYSIS] Processing request for shop: ${shopId}`);

    // Ensure shop exists in database
    let shop = await prisma.shop.findUnique({
      where: { shopDomain: shopId },
    });

    if (!shop) {
      // Create shop if it doesn't exist
      shop = await prisma.shop.create({
        data: {
          shopDomain: shopId,
          accessToken: session.accessToken!,
          isActive: true,
        },
      });
      console.log(
        `Created new shop: ${shop.id} for domain: ${shop.shopDomain}`,
      );
    }

    // Create job record in database
    const jobId = `analysis_${Date.now()}_${crypto.randomUUID()}`;

    const analysisJob = await prisma.analysisJob.create({
      data: {
        jobId,
        shopId: shop.id,
        status: "queued",
        progress: 0,
        createdAt: new Date(),
      },
    });

    console.log(`🔍 [API_ANALYSIS] Created analysis job: ${jobId}`);

    // Initialize Redis Streams service
    await redisStreamsService.initialize();

    // Publish job to Redis Streams
    try {
      const messageId = await redisStreamsService.publishDataJob({
        jobId,
        shopId: shop.id,
        shopDomain: shop.shopDomain,
        accessToken: "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",
        type: "data_collection", // Changed from "analysis" to trigger data collection
        priority: "normal",
      });

      console.log(`✅ Analysis job published to Redis Streams: ${messageId}`);

      // Update job status to indicate it's been queued
      await prisma.analysisJob.update({
        where: { id: analysisJob.id },
        data: {
          status: "queued",
          progress: 5, // Indicate job has been queued
        },
      });

      // Update last analysis timestamp
      await prisma.shop.update({
        where: { id: shop.id },
        data: {
          lastAnalysisAt: new Date(),
        },
      });

      console.log(`🔍 [API_ANALYSIS] Successfully queued analysis job`);
    } catch (error) {
      console.error("Error publishing job to Redis Streams:", error);

      // Update job status to failed
      await prisma.analysisJob.update({
        where: { id: analysisJob.id },
        data: {
          status: "failed",
          error: "Failed to publish job to Redis Streams",
          completedAt: new Date(),
        },
      });

      return json(
        {
          success: false,
          error: "Failed to queue analysis job",
          errorType: "queue-error",
        },
        { status: 500 },
      );
    }

    // Return 202 Accepted with job information
    return json(
      {
        success: true,
        message: "Analysis job queued successfully",
        jobId: jobId,
        status: "queued",
        data: {
          message:
            "Your analysis is being processed in the background. You can check the status on the dashboard.",
        },
      },
      { status: 202 },
    );
  } catch (error) {
    console.error("Error starting bundle analysis:", error);

    // Determine error type based on the error message
    let errorType = "api-error";
    if (error instanceof Error) {
      if (error.message.includes("No orders found")) {
        errorType = "no-orders";
      } else if (error.message.includes("insufficient data")) {
        errorType = "insufficient-data";
      } else if (error.message.includes("queue")) {
        errorType = "queue-error";
      }
    }

    return json(
      {
        success: false,
        error: "Failed to start bundle analysis. Please try again.",
        errorType,
      },
      { status: 500 },
    );
  }
};
