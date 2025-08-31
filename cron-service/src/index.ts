import express from "express";
import cors from "cors";
import helmet from "helmet";
import axios from "axios";
import { PrismaClient } from "@prisma/client";
import dotenv from "dotenv";

// Load environment variables
dotenv.config();

const app = express();
const prisma = new PrismaClient();

// Middleware
app.use(helmet());
app.use(cors());
app.use(express.json());

// Health check endpoint
app.get("/health", (req, res) => {
  res.json({
    status: "healthy",
    timestamp: new Date().toISOString(),
    service: "better-bundle-cron-service",
  });
});

// Cron job endpoint (called by external cron service)
app.post("/api/cron/check-scheduled-analyses", async (req, res) => {
  try {
    console.log("🔍 Cron job triggered - checking scheduled analyses...");

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
            accessToken: true,
          },
        },
      },
    });

    console.log(`📊 Found ${shopsDue.length} shops due for analysis`);

    // Process each shop
    for (const shopConfig of shopsDue) {
      try {
        console.log(
          `📋 Queuing scheduled analysis for shop: ${shopConfig.shop.shopDomain}`
        );

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

        const response = await axios.post(`${flyWorkerUrl}/api/queue`, {
          jobId,
          shopId: shopConfig.shop.shopId,
          shopDomain: shopConfig.shop.shopDomain,
          accessToken: shopConfig.shop.accessToken,
        });

        if (response.data.success) {
          console.log(
            `✅ Scheduled analysis queued for ${shopConfig.shop.shopDomain}: ${jobId}`
          );
        } else {
          console.error(
            `❌ Failed to queue scheduled analysis for ${shopConfig.shop.shopDomain}`
          );
        }
      } catch (error) {
        console.error(
          `❌ Error processing scheduled analysis for shop ${shopConfig.shop.shopDomain}:`,
          error
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
    }

    console.log("✅ Cron job completed successfully");

    res.json({
      success: true,
      message: "Scheduled analysis check completed",
      shopsProcessed: shopsDue.length,
    });
  } catch (error) {
    console.error("❌ Cron job error:", error);
    res.status(500).json({
      success: false,
      error: "Failed to check scheduled analyses",
    });
  }
});

// Start server
const PORT = process.env.CRON_SERVICE_PORT || 3002;
app.listen(PORT, () => {
  console.log(`🚀 Cron Service running on port ${PORT}`);
  console.log(
    `⏰ Scheduled analysis endpoint: /api/cron/check-scheduled-analyses`
  );
});

// Graceful shutdown
process.on("SIGTERM", async () => {
  console.log("🛑 Received SIGTERM, shutting down gracefully...");
  await prisma.$disconnect();
  process.exit(0);
});
