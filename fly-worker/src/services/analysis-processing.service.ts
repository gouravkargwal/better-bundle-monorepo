import { Logger } from "../utils/logger";
import { PrismaClient } from "@prisma/client";
import { collectIncrementalShopData } from "./data-collection.service";
import { updateJobStatus } from "./job-status.service";
import { sendAnalysisStartedEmail } from "./email-notification.service";
import Queue from "bull";

export interface AnalysisProcessingConfig {
  jobId: string;
  shopId: string;
  database: { prisma: PrismaClient };
  mlProcessingQueue?: Queue.Queue;
}

// Process analysis job
export const processAnalysisJob = async (
  config: AnalysisProcessingConfig
): Promise<void> => {
  const { jobId, shopId, database } = config;
  const startTime = Date.now();

  Logger.info("Starting analysis job processing", {
    jobId,
    shopId,
  });

  // Get shop details from database
  let shop;
  try {
    Logger.info("Fetching shop details for analysis", { shopId });

    const shopFetchStartTime = Date.now();
    shop = await database.prisma.shop.findUnique({
      where: { shopId },
      select: { shopDomain: true, accessToken: true },
    });
    const shopFetchDuration = Date.now() - shopFetchStartTime;

    Logger.performance("Shop details fetch for analysis", shopFetchDuration, {
      shopId,
    });

    if (!shop) {
      throw new Error(`Shop not found: ${shopId}`);
    }

    Logger.info("Shop details retrieved for analysis", {
      shopDomain: shop.shopDomain,
      hasAccessToken: !!shop.accessToken,
    });
  } catch (error) {
    Logger.error("Failed to get shop details for analysis", {
      shopId,
      error,
    });
    throw error;
  }

  try {
    Logger.info("Processing analysis job", {
      jobId,
      shopId,
      shopDomain: shop.shopDomain,
    });

    // Send analysis started email notification
    await sendAnalysisStartedEmail({
      shopDomain: shop.shopDomain,
      jobId,
    });

    Logger.info("Updating job status to processing (30%)", { jobId });
    await updateJobStatus(jobId, "processing", 30);

    Logger.info("Starting data collection", {
      jobId,
      shopDomain: shop.shopDomain,
    });

    // Collect shop data - use full collection for fresh runs, incremental for updates
    const dataCollectionStartTime = Date.now();

    // Check if we have existing data to determine collection strategy
    const existingData = await database.prisma.orderData.count({
      where: { shopId },
    });

    if (existingData === 0) {
      // No existing data - do full collection
      Logger.info("No existing data found, performing full data collection", {
        jobId,
      });
      const { collectAndSaveShopData } = await import(
        "./data-collection.service"
      );
      await collectAndSaveShopData({
        database,
        shopifyApi: {
          shopId,
          shopDomain: shop.shopDomain,
          accessToken:
            process.env.SHOPIFY_ACCESS_TOKEN || shop.accessToken || "",
        },
      });
    } else {
      // Existing data found - do incremental collection
      Logger.info(
        "Existing data found, performing incremental data collection",
        {
          jobId,
          existingDataCount: existingData,
        }
      );
      await collectIncrementalShopData({
        database,
        shopifyApi: {
          shopId,
          shopDomain: shop.shopDomain,
          accessToken:
            process.env.SHOPIFY_ACCESS_TOKEN || shop.accessToken || "",
        },
      });
    }
    const dataCollectionDuration = Date.now() - dataCollectionStartTime;

    Logger.performance("Data collection", dataCollectionDuration, {
      jobId,
      shopDomain: shop.shopDomain,
    });

    Logger.info("Data collection completed", { jobId });

    Logger.info("Updating job status to processing (60%)", { jobId });
    await updateJobStatus(jobId, "processing", 60);

    Logger.info("Analysis job completed successfully", {
      jobId,
      totalDuration: Date.now() - startTime,
    });

    // Queue ML processing job if queue is available
    if (config.mlProcessingQueue) {
      Logger.info("Queueing ML processing job", {
        jobId,
        shopId,
        shopDomain: shop.shopDomain,
      });

      await config.mlProcessingQueue.add("process-ml-analysis", {
        jobId,
        shopId,
        shopDomain: shop.shopDomain,
      });

      Logger.info("ML processing job queued successfully", {
        jobId,
        shopId,
        shopDomain: shop.shopDomain,
      });
    } else {
      Logger.warn("ML processing queue not available, skipping ML job", {
        jobId,
        shopId,
      });
    }
  } catch (error) {
    const totalDuration = Date.now() - startTime;
    Logger.error("Analysis job failed", {
      jobId,
      shopId,
      totalDuration,
      error,
    });

    await updateJobStatus(jobId, "failed", 0, error.message);
    throw error;
  }
};
