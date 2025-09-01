import axios from "axios";
import { Logger } from "../utils/logger";
import { PrismaClient } from "@prisma/client";
import { updateJobStatus } from "./job-status.service";
import { sendAnalysisCompletionEmail } from "./email-notification.service";
import { saveHeuristicDecision } from "./database.service";
import { AnalysisHeuristicService } from "./heuristic.service";

export interface MLProcessingConfig {
  jobId: string;
  shopId: string;
  shopDomain: string;
  database: { prisma: PrismaClient };
}

// Process ML analysis
export const processMLAnalysis = async (
  config: MLProcessingConfig
): Promise<void> => {
  const { jobId, shopId, shopDomain, database } = config;
  const startTime = Date.now();

  Logger.info("Starting ML job processing", {
    jobId,
    shopId,
    shopDomain,
  });

  // Get shop details from database
  let shop;
  try {
    Logger.info("Fetching shop details for ML processing", { shopDomain });

    const shopFetchStartTime = Date.now();
    shop = await database.prisma.shop.findUnique({
      where: { shopDomain },
      select: { shopDomain: true, accessToken: true },
    });
    const shopFetchDuration = Date.now() - shopFetchStartTime;

    Logger.performance("Shop details fetch", shopFetchDuration, { shopDomain });

    if (!shop) {
      throw new Error(`Shop not found: ${shopDomain}`);
    }

    Logger.info("Shop details retrieved successfully", {
      shopDomain: shop.shopDomain,
      hasAccessToken: !!shop.accessToken,
    });
  } catch (error) {
    Logger.error("Failed to get shop details for ML processing", {
      shopDomain,
      error,
    });
    throw error;
  }

  try {
    Logger.info("Processing ML analysis", {
      jobId,
      shopId,
      shopDomain,
    });

    await updateJobStatus(jobId, "processing", 70);

    // Call ML API - it will fetch and transform data automatically
    const mlApiUrl = process.env.ML_API_URL || "http://localhost:8000";
    Logger.info("Calling ML API", {
      jobId,
      mlApiUrl,
      shopId,
    });

    const mlApiStartTime = Date.now();
    const response = await axios.post(
      `${mlApiUrl}/api/bundle-analysis/${shopId}`,
      {}, // No body needed - endpoint fetches data automatically
      {
        timeout: 120000, // 2 minute timeout for ML processing
      }
    );
    const mlApiDuration = Date.now() - mlApiStartTime;

    Logger.performance("ML API call", mlApiDuration, {
      jobId,
      shopId,
      responseStatus: response.status,
      responseSuccess: response.data.success,
    });

    if (response.data.success) {
      await updateJobStatus(jobId, "completed", 100);
      Logger.info("ML job completed successfully", {
        jobId,
        shopId,
        totalDuration: Date.now() - startTime,
      });

      // Calculate complex heuristic for next analysis run
      const heuristicResult = await AnalysisHeuristicService.calculateNextAnalysisTime(
        database.prisma,
        shopId,
        response.data
      );

      // Save detailed heuristic decision for next analysis run
      await saveHeuristicDecision(database, shopId, {
        decision: "analysis_completed",
        reason: "ML analysis completed successfully",
        metadata: {
          jobId,
          totalDuration: Date.now() - startTime,
          analysisDate: new Date(),
          nextAnalysisHours: heuristicResult.nextAnalysisHours,
          nextAnalysisDays: (heuristicResult.nextAnalysisHours / 24).toFixed(1),
          factors: heuristicResult.factors,
          reasoning: heuristicResult.reasoning,
          confidence: heuristicResult.confidence,
        },
      });

      // Update shop's last analysis timestamp
      await database.prisma.shop.update({
        where: { id: shopId },
        data: { lastAnalysisAt: new Date() },
      });

      // Send success email notification
      await sendAnalysisCompletionEmail(
        {
          shopDomain: shop.shopDomain,
          jobId,
        },
        true
      );
    } else {
      throw new Error(response.data.error || "ML API returned failure");
    }
  } catch (error) {
    const totalDuration = Date.now() - startTime;
    Logger.error("ML job failed", {
      jobId,
      shopId,
      totalDuration,
      error,
    });

    await updateJobStatus(jobId, "failed", 0, error.message);

    // Send failure email notification
    await sendAnalysisCompletionEmail(
      {
        shopDomain: shop.shopDomain,
        jobId,
      },
      false,
      error.message
    );

    throw error;
  }
};
