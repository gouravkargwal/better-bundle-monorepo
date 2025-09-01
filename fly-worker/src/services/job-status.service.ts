import axios from "axios";
import { Logger } from "../utils/logger";

export interface JobStatusUpdate {
  jobId: string;
  status: string;
  progress: number;
  error?: string;
}

// Update job status in Shopify app
export const updateJobStatus = async (
  jobId: string,
  status: string,
  progress: number,
  error?: string
): Promise<void> => {
  const startTime = Date.now();
  try {
    // Use the global environment variable
    const shopifyAppUrl =
      process.env.SHOPIFY_APP_URL ||
      "https://hottest-falls-adjusted-launched.trycloudflare.com";

    Logger.info("Updating job status", {
      jobId,
      status,
      progress,
      hasError: !!error,
      shopifyAppUrl,
    });

    const response = await axios.post(
      `${shopifyAppUrl}/api/analysis/update-status`,
      {
        jobId,
        status,
        progress,
        error,
      },
      {
        timeout: 10000, // 10 second timeout
      }
    );

    const duration = Date.now() - startTime;
    Logger.performance("Job status update", duration, {
      jobId,
      status,
      progress,
      responseStatus: response.status,
    });

    Logger.info("Job status updated successfully", {
      jobId,
      status,
      progress,
      responseStatus: response.status,
    });
  } catch (error) {
    const duration = Date.now() - startTime;
    Logger.error("Failed to update job status", {
      jobId,
      status,
      progress,
      duration,
      error,
    });
    throw error; // Re-throw so the caller can handle it
  }
};
