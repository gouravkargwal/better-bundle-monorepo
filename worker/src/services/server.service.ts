import express from "express";
import cors from "cors";
import helmet from "helmet";
import { Logger } from "../utils/logger";
import Queue from "bull";

export interface ServerConfig {
  analysisQueue: Queue.Queue;
  mlProcessingQueue: Queue.Queue;
  database: { prisma: any };
}

export interface ServerService {
  app: express.Application;
  setupMiddleware: () => void;
  setupRoutes: () => void;
  start: (port: number) => void;
}

// Create and configure Express server
export const createServerService = (config: ServerConfig): ServerService => {
  const { analysisQueue, mlProcessingQueue } = config;
  const app = express();

  // Setup middleware
  const setupMiddleware = () => {
    app.use(helmet());
    app.use(cors());
    app.use(express.json());
  };

  // Setup routes
  const setupRoutes = () => {
    // Health check endpoint
    app.get("/health", (req, res) => {
      Logger.info("Health check requested", {
        timestamp: new Date().toISOString(),
        service: "better-bundle-fly-worker",
      });

      res.json({
        status: "healthy",
        timestamp: new Date().toISOString(),
        service: "better-bundle-fly-worker",
      });
    });

    // Queue endpoint for receiving jobs from Shopify app
    app.post("/api/queue", async (req, res) => {
      const startTime = Date.now();
      Logger.info("Received queue job request", {
        body: req.body,
        headers: req.headers,
      });

      try {
        const { jobId, shopId, shopDomain, accessToken } = req.body;

        Logger.info("Processing queue job", {
          jobId,
          shopId,
          shopDomain,
          hasAccessToken: !!accessToken,
        });

        // Add job to analysis queue
        const queueStartTime = Date.now();
        await analysisQueue.add("process-analysis", {
          jobId,
          shopId,
          shopDomain,
          accessToken,
          timestamp: new Date().toISOString(),
        });
        const queueDuration = Date.now() - queueStartTime;

        Logger.performance("Job queuing", queueDuration, {
          jobId,
          shopId,
          queueName: analysisQueue.name,
        });

        const totalDuration = Date.now() - startTime;
        Logger.info("Job queued successfully", {
          jobId,
          shopId,
          totalDuration,
        });

        res.json({
          success: true,
          message: "Job queued successfully",
          jobId,
        });
      } catch (error) {
        const totalDuration = Date.now() - startTime;
        Logger.error("Failed to queue job", {
          totalDuration,
          error,
        });

        res.status(500).json({
          success: false,
          error: "Failed to queue job",
        });
      }
    });

    // Cron service endpoint to check analysis schedules
    app.get("/api/cron/check-schedules", async (req, res) => {
      const startTime = Date.now();
      Logger.info("Cron service checking analysis schedules");

      try {
        // Get all shops that need analysis based on heuristic decisions
        const shopsNeedingAnalysis = await config.database.prisma.shop.findMany({
          where: {
            lastAnalysisAt: {
              not: null,
            },
          },
          select: {
            id: true,
            shopId: true,
            shopDomain: true,
            lastAnalysisAt: true,
          },
        });

        const analysisCandidates = [];

        for (const shop of shopsNeedingAnalysis) {
          // Get the latest heuristic decision for this shop
          const latestDecision = await config.database.prisma.heuristicDecision.findFirst({
            where: { shopId: shop.id },
            orderBy: { createdAt: 'desc' },
          });

          if (latestDecision && latestDecision.metadata?.nextAnalysisHours) {
            const nextAnalysisTime = new Date(shop.lastAnalysisAt!);
            nextAnalysisTime.setHours(nextAnalysisTime.getHours() + latestDecision.metadata.nextAnalysisHours);

            if (new Date() >= nextAnalysisTime) {
              analysisCandidates.push({
                shopId: shop.shopId,
                shopDomain: shop.shopDomain,
                lastAnalysisAt: shop.lastAnalysisAt,
                nextAnalysisTime,
                heuristicDecision: latestDecision.metadata,
              });
            }
          }
        }

        Logger.info("Analysis schedule check completed", {
          totalShops: shopsNeedingAnalysis.length,
          shopsNeedingAnalysis: analysisCandidates.length,
        });

        res.json({
          success: true,
          shopsNeedingAnalysis: analysisCandidates,
          totalShops: shopsNeedingAnalysis.length,
          timestamp: new Date().toISOString(),
        });
      } catch (error) {
        Logger.error("Failed to check analysis schedules", { error });
        res.status(500).json({
          success: false,
          error: "Failed to check analysis schedules",
        });
      }
    });
  };

  // Start server
  const start = (port: number) => {
    app.listen(port, () => {
      Logger.info("Fly.io Worker started successfully", {
        port,
        analysisQueue: analysisQueue.name,
        mlProcessingQueue: mlProcessingQueue.name,
        environment: process.env.NODE_ENV || "development",
        timestamp: new Date().toISOString(),
      });
    });
  };

  return {
    app,
    setupMiddleware,
    setupRoutes,
    start,
  };
};
