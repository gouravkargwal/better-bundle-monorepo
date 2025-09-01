import Queue from "bull";
import { Logger } from "../utils/logger";
import { processAnalysisJob } from "./analysis-processing.service";
import { processMLAnalysis } from "./ml-processing.service";
import { PrismaClient } from "@prisma/client";

export interface QueueConfig {
  redis: {
    host: string;
    port: number;
    password?: string;
    tls?: any;
  };
  database: { prisma: PrismaClient };
}

export interface QueueService {
  analysisQueue: Queue.Queue;
  mlProcessingQueue: Queue.Queue;
  setupQueueProcessors: () => void;
  setupQueueEventListeners: () => void;
  closeQueues: () => Promise<void>;
}

// Initialize and configure queues
export const createQueueService = (config: QueueConfig): QueueService => {
  const { redis, database } = config;

  // Initialize queues
  const analysisQueue = new Queue("analysis-queue", { redis });
  const mlProcessingQueue = new Queue("ml-processing-queue", { redis });

  Logger.info("Queue initialization completed", {
    analysisQueue: analysisQueue.name,
    mlProcessingQueue: mlProcessingQueue.name,
  });

  // Setup queue processors
  const setupQueueProcessors = () => {
    // Process analysis jobs
    analysisQueue.process("process-analysis", async (job) => {
      const { jobId, shopId } = job.data;
      await processAnalysisJob({ 
        jobId, 
        shopId, 
        database,
        mlProcessingQueue 
      });
    });

    // Process ML jobs
    mlProcessingQueue.process("process-ml-analysis", async (job) => {
      const { jobId, shopId, shopDomain } = job.data;
      await processMLAnalysis({ jobId, shopId, shopDomain, database });
    });
  };

  // Setup queue event listeners
  const setupQueueEventListeners = () => {
    // Error handling for queues
    analysisQueue.on("error", (error) => {
      Logger.error("Analysis queue error", error);
    });

    mlProcessingQueue.on("error", (error) => {
      Logger.error("ML processing queue error", error);
    });

    // Queue event listeners for better monitoring
    analysisQueue.on("waiting", (jobId) => {
      Logger.info("Analysis job waiting", { jobId });
    });

    analysisQueue.on("active", (job) => {
      Logger.info("Analysis job started", {
        jobId: job.id,
        jobData: job.data,
      });
    });

    analysisQueue.on("completed", (job) => {
      Logger.info("Analysis job completed", {
        jobId: job.id,
        jobData: job.data,
      });
    });

    analysisQueue.on("failed", (job, error) => {
      Logger.error("Analysis job failed", {
        jobId: job.id,
        jobData: job.data,
        error,
      });
    });

    mlProcessingQueue.on("waiting", (jobId) => {
      Logger.info("ML job waiting", { jobId });
    });

    mlProcessingQueue.on("active", (job) => {
      Logger.info("ML job started", {
        jobId: job.id,
        jobData: job.data,
      });
    });

    mlProcessingQueue.on("completed", (job) => {
      Logger.info("ML job completed", {
        jobId: job.id,
        jobData: job.data,
      });
    });

    mlProcessingQueue.on("failed", (job, error) => {
      Logger.error("ML job failed", {
        jobId: job.id,
        jobData: job.data,
        error,
      });
    });
  };

  // Close queues gracefully
  const closeQueues = async () => {
    try {
      Logger.info("Closing analysis queue");
      await analysisQueue.close();

      Logger.info("Closing ML processing queue");
      await mlProcessingQueue.close();

      Logger.info("All queues closed successfully");
    } catch (error) {
      Logger.error("Error closing queues", error);
      throw error;
    }
  };

  return {
    analysisQueue,
    mlProcessingQueue,
    setupQueueProcessors,
    setupQueueEventListeners,
    closeQueues,
  };
};
