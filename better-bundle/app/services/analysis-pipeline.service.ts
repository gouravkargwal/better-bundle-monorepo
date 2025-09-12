/**
 * Analysis Pipeline Service
 * Handles triggering data collection and analysis jobs via the Python worker
 */

interface TriggerAnalysisPipelineParams {
  shopDomain: string;
  accessToken: string;
  shopId?: string;
}

interface AnalysisPipelineResponse {
  message: string;
  job_id: string;
  event_id: string;
  status: string;
}

export class AnalysisPipelineService {
  private static readonly PYTHON_WORKER_URL =
    process.env.PYTHON_WORKER_URL || "http://localhost:8000";

  private static readonly ENDPOINT = "/api/data-collection/trigger";

  /**
   * Triggers the initial data collection and analysis pipeline for a new shop
   */
  static async triggerInitialAnalysis({
    shopDomain,
    accessToken,
    shopId,
  }: TriggerAnalysisPipelineParams): Promise<AnalysisPipelineResponse | null> {
    try {
      const resolvedShopId = shopId || shopDomain.replace(".myshopify.com", "");

      console.log("🚀 Triggering initial analysis pipeline", {
        shopDomain,
        shopId: resolvedShopId,
        pythonWorkerUrl: this.PYTHON_WORKER_URL,
      });

      const response = await fetch(
        `${this.PYTHON_WORKER_URL}${this.ENDPOINT}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            shop_id: resolvedShopId,
            shop_domain: shopDomain,
            access_token: accessToken,
            job_type: "data_collection",
          }),
        },
      );

      if (!response.ok) {
        const errorText = await response.text();
        console.error("❌ Failed to trigger analysis pipeline", {
          status: response.status,
          statusText: response.statusText,
          error: errorText,
          shopDomain,
        });
        return null;
      }

      const result: AnalysisPipelineResponse = await response.json();

      console.log("✅ Analysis pipeline triggered successfully", {
        jobId: result.job_id,
        eventId: result.event_id,
        shopDomain,
      });

      return result;
    } catch (error) {
      console.error("❌ Error triggering analysis pipeline", {
        error: error instanceof Error ? error.message : String(error),
        shopDomain,
      });
      return null;
    }
  }

  /**
   * Triggers a scheduled analysis job
   */
  static async triggerScheduledAnalysis({
    shopDomain,
    accessToken,
    shopId,
    analysisType = "scheduled_analysis",
  }: TriggerAnalysisPipelineParams & {
    analysisType?: string;
  }): Promise<AnalysisPipelineResponse | null> {
    try {
      const resolvedShopId = shopId || shopDomain.replace(".myshopify.com", "");

      console.log("🔄 Triggering scheduled analysis", {
        shopDomain,
        shopId: resolvedShopId,
        analysisType,
      });

      const response = await fetch(
        `${this.PYTHON_WORKER_URL}${this.ENDPOINT}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            shop_id: resolvedShopId,
            shop_domain: shopDomain,
            access_token: accessToken,
            job_type: analysisType,
          }),
        },
      );

      if (!response.ok) {
        const errorText = await response.text();
        console.error("❌ Failed to trigger scheduled analysis", {
          status: response.status,
          statusText: response.statusText,
          error: errorText,
          shopDomain,
          analysisType,
        });
        return null;
      }

      const result: AnalysisPipelineResponse = await response.json();

      console.log("✅ Scheduled analysis triggered successfully", {
        jobId: result.job_id,
        eventId: result.event_id,
        shopDomain,
        analysisType,
      });

      return result;
    } catch (error) {
      console.error("❌ Error triggering scheduled analysis", {
        error: error instanceof Error ? error.message : String(error),
        shopDomain,
        analysisType,
      });
      return null;
    }
  }

  /**
   * Checks if the Python worker is available
   */
  static async checkWorkerHealth(): Promise<boolean> {
    try {
      // Use AbortController for timeout instead of fetch timeout option
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout

      const response = await fetch(`${this.PYTHON_WORKER_URL}/health`, {
        method: "GET",
        signal: controller.signal,
      });

      clearTimeout(timeoutId);
      return response.ok;
    } catch (error) {
      console.warn("⚠️ Python worker health check failed", {
        error: error instanceof Error ? error.message : String(error),
        pythonWorkerUrl: this.PYTHON_WORKER_URL,
      });
      return false;
    }
  }
}
