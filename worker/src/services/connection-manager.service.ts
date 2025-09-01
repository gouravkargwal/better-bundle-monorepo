import Redis from "ioredis";
import { PrismaClient } from "@prisma/client";
import { Logger } from "../utils/logger";

export interface ConnectionConfig {
  redis: {
    host: string;
    port: number;
    password?: string;
    tls?: any;
  };
  database: { prisma: PrismaClient };
}

export interface ConnectionManager {
  redis: Redis;
  database: { prisma: PrismaClient };
  closeConnections: () => Promise<void>;
}

// Create connection manager with automatic reconnection
export const createConnectionManager = (
  config: ConnectionConfig
): ConnectionManager => {
  const { redis: redisConfig, database } = config;

  // Initialize Redis with reconnection settings
  const redis = new Redis({
    ...redisConfig,
    maxRetriesPerRequest: 3,
    lazyConnect: true,
    keepAlive: 30000,
    connectTimeout: 10000,
    commandTimeout: 5000,
  });

  // Redis connection event handlers
  redis.on("connect", () => {
    Logger.info("Redis connected successfully");
  });

  redis.on("ready", () => {
    Logger.info("Redis is ready to accept commands");
  });

  redis.on("error", (error) => {
    Logger.error("Redis connection error", error);
  });

  redis.on("close", () => {
    Logger.warn("Redis connection closed");
  });

  redis.on("reconnecting", (delay: number) => {
    Logger.info("Redis reconnecting", { delay });
  });

  redis.on("end", () => {
    Logger.warn("Redis connection ended");
  });

  // Setup graceful shutdown handlers
  const setupGracefulShutdown = () => {
    const gracefulShutdown = async (signal: string) => {
      Logger.info(`Received ${signal}, closing connections gracefully`);
      await closeConnections();
    };

    process.on("SIGTERM", () => gracefulShutdown("SIGTERM"));
    process.on("SIGINT", () => gracefulShutdown("SIGINT"));
  };

  // Close all connections
  const closeConnections = async (): Promise<void> => {
    try {
      Logger.info("Closing all connections");

      // Close Redis
      await redis.disconnect();
      Logger.info("Redis connection closed");

      // Close Database
      await database.prisma.$disconnect();
      Logger.info("Database connection closed");

      Logger.info("All connections closed successfully");
    } catch (error) {
      Logger.error("Error closing connections", { error });
      throw error;
    }
  };

  return {
    redis,
    database,
    closeConnections,
  };
};
