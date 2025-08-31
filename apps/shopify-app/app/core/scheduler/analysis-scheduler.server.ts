import { prisma } from "../database/prisma.server";
import { AnalysisHeuristicService } from "../heuristics/analysis-heuristic.server";
import axios from "axios";

export class AnalysisScheduler {
  private static isRunning = false;
  private static intervalId: NodeJS.Timeout | null = null;
  private static scheduledAnalysisEnabled = false; // Flag to control scheduled analysis

  /**
   * Start the scheduler
   */
  static async start() {
    if (this.isRunning) {
      console.log("⚠️ Analysis scheduler is already running");
      return;
    }

    console.log("🚀 Starting Analysis Scheduler...");
    this.isRunning = true;

    // Run initial check for scheduled analysis
    await this.checkScheduledAnalyses();

    // Set up interval to check every hour
    this.intervalId = setInterval(
      async () => {
        await this.checkScheduledAnalyses();
      },
      60 * 60 * 1000,
    ); // Check every hour

    console.log("✅ Analysis Scheduler started successfully");
  }

  /**
   * Enable scheduled analysis
   */
  static enableScheduledAnalysis() {
    this.scheduledAnalysisEnabled = true;
    console.log("✅ Scheduled analysis enabled");
  }

  /**
   * Disable scheduled analysis
   */
  static disableScheduledAnalysis() {
    this.scheduledAnalysisEnabled = false;
    console.log("⏸️ Scheduled analysis disabled");
  }

  /**
   * Check if scheduled analysis is enabled
   */
  static isScheduledAnalysisEnabled() {
    return this.scheduledAnalysisEnabled;
  }

  /**
   * Stop the scheduler
   */
  static stop() {
    if (this.intervalId) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
    this.isRunning = false;
    console.log("🛑 Analysis Scheduler stopped");
  }

  /**
   * Check for shops that are due for analysis
   */
  static async checkScheduledAnalyses() {
    try {
      // Don't run if scheduled analysis is disabled
      if (!this.scheduledAnalysisEnabled) {
        console.log(
          "⏸️ Skipping scheduled analysis check - scheduled analysis disabled",
        );
        return;
      }

      console.log("🔍 Checking for shops due for analysis...");

      const now = new Date();

      // Find shops that are due for analysis
      const shopsDue = await prisma.shopAnalysisConfig.findMany({
        where: {
          autoAnalysisEnabled: true,
          nextScheduledAnalysis: {
            lte: now,
          },
        },
        include: {
          shop: {
            select: {
              shopId: true,
              shopDomain: true,
            },
          },
        },
      });

      console.log(`📊 Found ${shopsDue.length} shops due for analysis`);

      // Queue analysis jobs for each shop
      for (const shopConfig of shopsDue) {
        try {
          console.log(
            `📋 Queuing scheduled analysis for shop: ${shopConfig.shop.shopDomain}`,
          );

          // Get shop data for Fly.io worker
          const shop = await prisma.shop.findUnique({
            where: { shopId: shopConfig.shop.shopId },
            select: { shopDomain: true, accessToken: true },
          });

          if (!shop) {
            console.error(`❌ Shop not found: ${shopConfig.shop.shopId}`);
            continue;
          }

          // Create job record in database
          const jobId = `scheduled_${Date.now()}_${crypto.randomUUID()}`;

          const analysisJob = await prisma.analysisJob.create({
            data: {
              jobId,
              shopId: shopConfig.shopId,
              status: "queued",
              progress: 0,
              createdAt: new Date(),
            },
          });

          // Send job to Fly.io worker
          const flyWorkerUrl =
            process.env.FLY_WORKER_URL || "http://localhost:3001";

          try {
            const response = await axios.post(`${flyWorkerUrl}/api/queue`, {
              jobId,
              shopId: shopConfig.shop.shopId,
              shopDomain: shop.shopDomain,
              accessToken: shop.accessToken,
            });

            if (response.data.success) {
              console.log(
                `✅ Scheduled analysis queued for ${shopConfig.shop.shopDomain}: ${jobId}`,
              );
            } else {
              console.error(
                `❌ Failed to queue scheduled analysis for ${shopConfig.shop.shopDomain}`,
              );
            }
          } catch (error) {
            console.error(
              `❌ Error sending scheduled analysis to Fly.io worker for ${shopConfig.shop.shopDomain}:`,
              error,
            );

            // Update job status to failed
            await prisma.analysisJob.update({
              where: { id: analysisJob.id },
              data: {
                status: "failed",
                error: "Failed to send job to worker",
                completedAt: new Date(),
              },
            });
          }
        } catch (error) {
          console.error(
            `❌ Error queuing scheduled analysis for shop ${shopConfig.shop.shopDomain}:`,
            error,
          );
        }
      }

      console.log("✅ Scheduled analysis check completed");
    } catch (error) {
      console.error("❌ Error checking scheduled analyses:", error);
    }
  }

  /**
   * Schedule next analysis for a shop using heuristic
   */
  static async scheduleNextAnalysis(shopId: string, analysisResult: any) {
    try {
      console.log(`📅 Scheduling next analysis for shop: ${shopId}`);

      // Calculate next analysis time using heuristic
      const heuristicResult =
        await AnalysisHeuristicService.calculateNextAnalysisTime(
          shopId,
          analysisResult,
        );

      // Calculate next scheduled time
      const nextScheduledTime = new Date();
      nextScheduledTime.setHours(
        nextScheduledTime.getHours() + heuristicResult.nextAnalysisHours,
      );

      // Update or create shop analysis config
      await prisma.shopAnalysisConfig.upsert({
        where: { shopId },
        update: {
          lastAnalysisAt: new Date(),
          nextScheduledAnalysis: nextScheduledTime,
          heuristicFactors: JSON.parse(JSON.stringify(heuristicResult.factors)),
          lastHeuristicResult: JSON.parse(JSON.stringify(heuristicResult)),
        },
        create: {
          shopId,
          lastAnalysisAt: new Date(),
          nextScheduledAnalysis: nextScheduledTime,
          heuristicFactors: JSON.parse(JSON.stringify(heuristicResult.factors)),
          lastHeuristicResult: JSON.parse(JSON.stringify(heuristicResult)),
        },
      });

      // Store heuristic decision for learning
      await AnalysisHeuristicService.storeHeuristicDecision(
        shopId,
        heuristicResult,
        analysisResult,
      );

      console.log(
        `✅ Next analysis scheduled for ${shopId} in ${heuristicResult.nextAnalysisHours} hours (${nextScheduledTime.toISOString()})`,
      );

      return {
        success: true,
        nextScheduledTime,
        heuristicResult,
      };
    } catch (error) {
      console.error(
        `❌ Error scheduling next analysis for shop ${shopId}:`,
        error,
      );
      return {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      };
    }
  }

  /**
   * Get scheduler status
   */
  static getStatus() {
    return {
      isRunning: this.isRunning,
      lastCheck: new Date().toISOString(),
    };
  }

  /**
   * Get shops due for analysis (for monitoring)
   */
  static async getShopsDueForAnalysis() {
    const now = new Date();

    return await prisma.shopAnalysisConfig.findMany({
      where: {
        autoAnalysisEnabled: true,
        nextScheduledAnalysis: {
          lte: now,
        },
      },
      include: {
        shop: {
          select: {
            shopId: true,
            shopDomain: true,
          },
        },
      },
    });
  }

  /**
   * Get upcoming scheduled analyses (for monitoring)
   */
  static async getUpcomingScheduledAnalyses(limit: number = 10) {
    const now = new Date();

    return await prisma.shopAnalysisConfig.findMany({
      where: {
        autoAnalysisEnabled: true,
        nextScheduledAnalysis: {
          gt: now,
        },
      },
      include: {
        shop: {
          select: {
            shopId: true,
            shopDomain: true,
          },
        },
      },
      orderBy: {
        nextScheduledAnalysis: "asc",
      },
      take: limit,
    });
  }

  /**
   * Manually trigger analysis for a shop
   */
  static async triggerAnalysis(shopId: string) {
    try {
      console.log(`🔧 Manually triggering analysis for shop: ${shopId}`);

      // Get shop data for Fly.io worker
      const shop = await prisma.shop.findUnique({
        where: { shopId },
        select: { id: true, shopDomain: true, accessToken: true },
      });

      if (!shop) {
        console.error(`❌ Shop not found: ${shopId}`);
        return { success: false, error: "Shop not found" };
      }

      // Create job record in database
      const jobId = `manual_${Date.now()}_${crypto.randomUUID()}`;

      const analysisJob = await prisma.analysisJob.create({
        data: {
          jobId,
          shopId: shop.id,
          status: "queued",
          progress: 0,
          createdAt: new Date(),
        },
      });

      // Send job to Fly.io worker
      const flyWorkerUrl =
        process.env.FLY_WORKER_URL || "http://localhost:3001";

      try {
        const response = await axios.post(`${flyWorkerUrl}/api/queue`, {
          jobId,
          shopId,
          shopDomain: shop.shopDomain,
          accessToken: shop.accessToken,
        });

        if (response.data.success) {
          console.log(`✅ Manual analysis triggered for ${shopId}: ${jobId}`);
          return { success: true, jobId: jobId };
        } else {
          console.error(`❌ Failed to trigger manual analysis for ${shopId}`);
          return { success: false, error: "Failed to queue job" };
        }
      } catch (error) {
        console.error(
          `❌ Error sending manual analysis to Fly.io worker for ${shopId}:`,
          error,
        );

        // Update job status to failed
        await prisma.analysisJob.update({
          where: { id: analysisJob.id },
          data: {
            status: "failed",
            error: "Failed to send job to worker",
            completedAt: new Date(),
          },
        });

        return { success: false, error: "Failed to send job to worker" };
      }
    } catch (error) {
      console.error(
        `❌ Error triggering manual analysis for shop ${shopId}:`,
        error,
      );
      return {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      };
    }
  }

  /**
   * Enable/disable auto-analysis for a shop
   */
  static async setAutoAnalysisEnabled(shopId: string, enabled: boolean) {
    try {
      await prisma.shopAnalysisConfig.upsert({
        where: { shopId },
        update: { autoAnalysisEnabled: enabled },
        create: {
          shopId,
          autoAnalysisEnabled: enabled,
        },
      });

      console.log(
        `✅ Auto-analysis ${enabled ? "enabled" : "disabled"} for shop: ${shopId}`,
      );
      return { success: true };
    } catch (error) {
      console.error(
        `❌ Error setting auto-analysis for shop ${shopId}:`,
        error,
      );
      return {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      };
    }
  }

  /**
   * Get scheduler statistics
   */
  static async getSchedulerStats() {
    const now = new Date();

    const [totalShops, enabledShops, dueShops, upcomingShops] =
      await Promise.all([
        prisma.shop.count(),
        prisma.shopAnalysisConfig.count({
          where: { autoAnalysisEnabled: true },
        }),
        prisma.shopAnalysisConfig.count({
          where: {
            autoAnalysisEnabled: true,
            nextScheduledAnalysis: { lte: now },
          },
        }),
        prisma.shopAnalysisConfig.count({
          where: {
            autoAnalysisEnabled: true,
            nextScheduledAnalysis: { gt: now },
          },
        }),
      ]);

    return {
      totalShops,
      enabledShops,
      dueShops,
      upcomingShops,
      schedulerStatus: this.getStatus(),
    };
  }
}
