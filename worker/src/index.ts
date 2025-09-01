import dotenv from "dotenv";
import { PrismaClient } from "@prisma/client";
import path from "path";
import { Logger } from "./utils/logger";
import { createConnectionManager } from "./services/connection-manager.service";
import { createQueueService } from "./services/queue.service";
import { createServerService } from "./services/server.service";

// Load environment variables from the global local.env file
const envPath = path.join(__dirname, "../../local.env");
Logger.info("Loading environment configuration", { envPath });
dotenv.config({ path: envPath });

// Log key environment variables for debugging
Logger.info("Environment configuration loaded", {
  DATABASE_URL: process.env.DATABASE_URL ? "✅ Set" : "❌ Missing",
  REDIS_HOST: process.env.REDIS_HOST || "localhost",
  REDIS_PORT: process.env.REDIS_PORT || "6379",
  SHOPIFY_APP_URL: process.env.SHOPIFY_APP_URL || "Not set",
  ML_API_URL: process.env.ML_API_URL || "Not set",
  WORKER_PORT: process.env.WORKER_PORT || "3001",
  SHOPIFY_ACCESS_TOKEN: process.env.SHOPIFY_ACCESS_TOKEN || "Not set",
});

// Initialize Prisma client
const prisma = new PrismaClient();

// Redis configuration
const redisConfig = {
  host: process.env.REDIS_HOST || "localhost",
  port: parseInt(process.env.REDIS_PORT || "6379"),
  password: process.env.REDIS_PASSWORD,
  tls: process.env.REDIS_TLS === "true" ? {} : undefined,
};

Logger.info("Initializing connection manager", redisConfig);

// Initialize connection manager with automatic reconnection
const connectionManager = createConnectionManager({
  redis: redisConfig,
  database: { prisma },
});

// Setup graceful shutdown handlers
const gracefulShutdown = async (signal: string) => {
  Logger.info(`Received ${signal}, starting graceful shutdown`);

  try {
    await queueService.closeQueues();
    await connectionManager.closeConnections();
    Logger.info("Graceful shutdown completed");
    process.exit(0);
  } catch (error) {
    Logger.error("Error during graceful shutdown", error);
    process.exit(1);
  }
};

process.on("SIGTERM", () => gracefulShutdown("SIGTERM"));
process.on("SIGINT", () => gracefulShutdown("SIGINT"));

// Initialize services
const queueService = createQueueService({
  redis: redisConfig,
  database: connectionManager.database,
});

const serverService = createServerService({
  analysisQueue: queueService.analysisQueue,
  mlProcessingQueue: queueService.mlProcessingQueue,
  database: connectionManager.database,
});

// Setup services
queueService.setupQueueProcessors();
queueService.setupQueueEventListeners();
serverService.setupMiddleware();
serverService.setupRoutes();

// Start server
const PORT = parseInt(process.env.WORKER_PORT || "3001");
serverService.start(PORT);
