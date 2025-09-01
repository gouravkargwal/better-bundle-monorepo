/**
 * Redis Streams service for event-driven architecture
 * Replaces the old Bull queue system with Redis Streams
 */

import Redis from "ioredis";
import { prisma } from "../database/prisma.server";

// Redis client configuration
const redisConfig = {
  host: process.env.REDIS_HOST || "localhost",
  port: parseInt(process.env.REDIS_PORT || "6379"),
  password: process.env.REDIS_PASSWORD || undefined,
  db: parseInt(process.env.REDIS_DB || "0"),
  retryDelayOnFailover: 100,
  maxRetriesPerRequest: 3,
};

// Stream names (must match Python worker)
const STREAMS = {
  DATA_JOB: "betterbundle:data-jobs",
  ML_TRAINING: "betterbundle:ml-training",
  ANALYSIS_RESULTS: "betterbundle:analysis-results",
  USER_NOTIFICATIONS: "betterbundle:user-notifications",
  FEATURES_COMPUTED: "betterbundle:features-computed",
} as const;

// Consumer group names
const CONSUMER_GROUPS = {
  DATA_PROCESSOR: "data-processors",
  ML_PROCESSOR: "ml-processors",
  NOTIFICATION_PROCESSOR: "notification-processors",
} as const;

class RedisStreamsService {
  private redis: Redis | null = null;
  private isInitialized = false;

  /**
   * Initialize Redis connection
   */
  async initialize(): Promise<void> {
    if (this.isInitialized) return;

    try {
      this.redis = new Redis(redisConfig);

      // Test connection
      await this.redis.ping();

      // Create consumer groups if they don't exist
      await this.createConsumerGroups();

      this.isInitialized = true;
      console.log("✅ Redis Streams service initialized successfully");
    } catch (error) {
      console.error("❌ Failed to initialize Redis Streams service:", error);
      throw error;
    }
  }

  /**
   * Create consumer groups for all streams
   */
  private async createConsumerGroups(): Promise<void> {
    if (!this.redis) return;

    try {
      // Create consumer groups for each stream
      for (const [name, stream] of Object.entries(STREAMS)) {
        try {
          await this.redis.xgroup(
            "CREATE",
            stream,
            CONSUMER_GROUPS.DATA_PROCESSOR,
            "$",
            "MKSTREAM",
          );
          console.log(`✅ Created consumer group for ${name} stream`);
        } catch (error: any) {
          // Group already exists is not an error
          if (!error.message.includes("BUSYGROUP")) {
            console.log(`ℹ️ Consumer group for ${name} stream already exists`);
          }
        }
      }
    } catch (error) {
      console.error("❌ Error creating consumer groups:", error);
    }
  }

  /**
   * Publish a data job event to the data job stream
   */
  async publishDataJob(jobData: {
    jobId: string;
    shopId: string;
    shopDomain: string;
    accessToken: string;
    type: "analysis" | "incremental" | "scheduled";
    priority?: "high" | "normal" | "low";
  }): Promise<string> {
    if (!this.redis) {
      throw new Error("Redis Streams service not initialized");
    }

    const eventData = {
      ...jobData,
      timestamp: Date.now(),
      source: "shopify-app",
    };

    const messageId = await this.redis.xadd(
      STREAMS.DATA_JOB,
      "*",
      ...Object.entries(eventData).flat(),
    );

    if (!messageId) {
      throw new Error("Failed to publish data job event");
    }

    console.log(`📤 Published data job event: ${messageId}`, eventData);
    return messageId;
  }

  /**
   * Publish a user notification event
   */
  async publishUserNotification(notificationData: {
    shopDomain: string;
    userId?: string;
    type:
      | "analysis_complete"
      | "analysis_failed"
      | "bundle_created"
      | "insights_ready";
    title: string;
    message: string;
    actionUrl?: string;
    metadata?: Record<string, any>;
  }): Promise<string> {
    if (!this.redis) {
      throw new Error("Redis Streams service not initialized");
    }

    const eventData = {
      ...notificationData,
      timestamp: Date.now(),
      source: "shopify-app",
    };

    const messageId = await this.redis.xadd(
      STREAMS.USER_NOTIFICATIONS,
      "*",
      ...Object.entries(eventData).flat(),
    );

    if (!messageId) {
      throw new Error("Failed to publish user notification event");
    }

    console.log(
      `📤 Published user notification event: ${messageId}`,
      eventData,
    );
    return messageId;
  }

  /**
   * Publish a tracking event
   */
  async publishTrackingEvent(trackingData: {
    shop_id: string;
    event_type: string;
    event_id: string;
    session_id: string;
    tracking_id: string;
    user_id?: string;
    timestamp: number;
    metadata: Record<string, any>;
  }): Promise<string> {
    if (!this.redis) {
      throw new Error("Redis Streams service not initialized");
    }

    const eventData = {
      ...trackingData,
      source: "shopify-app",
    };

    const messageId = await this.redis.xadd(
      "betterbundle:tracking-events",
      "*",
      ...Object.entries(eventData).flat(),
    );

    if (!messageId) {
      throw new Error("Failed to publish tracking event");
    }

    console.log(`📤 Published tracking event: ${messageId}`, eventData);
    return messageId;
  }

  /**
   * Read analysis results from the results stream
   */
  async readAnalysisResults(
    shopDomain: string,
    lastId: string = "0",
    count: number = 10,
  ): Promise<Array<{ id: string; data: any }>> {
    if (!this.redis) {
      throw new Error("Redis Streams service not initialized");
    }

    try {
      const results = await this.redis.xread(
        "COUNT",
        count,
        "STREAMS",
        STREAMS.ANALYSIS_RESULTS,
        lastId,
      );

      if (!results || results.length === 0) {
        return [];
      }

      const [, messages] = results[0];
      return messages
        .filter(([, fields]) => {
          // Filter by shop domain if present
          const shopField = fields.find(
            (_, index) => index % 2 === 0 && fields[index] === "shopDomain",
          );
          if (shopField) {
            const shopIndex = fields.indexOf("shopDomain");
            return fields[shopIndex + 1] === shopDomain;
          }
          return true;
        })
        .map(([id, fields]) => {
          const data: any = {};
          for (let i = 0; i < fields.length; i += 2) {
            data[fields[i]] = fields[i + 1];
          }
          return { id, data };
        });
    } catch (error) {
      console.error("❌ Error reading analysis results:", error);
      return [];
    }
  }

  /**
   * Get stream length (number of messages)
   */
  async getStreamLength(streamName: string): Promise<number> {
    if (!this.redis) {
      throw new Error("Redis Streams service not initialized");
    }

    try {
      return await this.redis.xlen(streamName);
    } catch (error) {
      console.error(`❌ Error getting length for stream ${streamName}:`, error);
      return 0;
    }
  }

  /**
   * Get pending messages for a consumer group
   */
  async getPendingMessages(
    streamName: string,
    groupName: string,
    consumerName: string,
  ): Promise<any[]> {
    if (!this.redis) {
      throw new Error("Redis Streams service not initialized");
    }

    try {
      const pending = await this.redis.xpending(
        streamName,
        groupName,
        "-",
        "+",
        100,
        consumerName,
      );
      return pending;
    } catch (error) {
      console.error(
        `❌ Error getting pending messages for ${streamName}:`,
        error,
      );
      return [];
    }
  }

  /**
   * Acknowledge a message as processed
   */
  async acknowledgeMessage(
    streamName: string,
    groupName: string,
    messageId: string,
  ): Promise<void> {
    if (!this.redis) {
      throw new Error("Redis Streams service not initialized");
    }

    try {
      await this.redis.xack(streamName, groupName, messageId);
      console.log(`✅ Acknowledged message ${messageId} from ${streamName}`);
    } catch (error) {
      console.error(`❌ Error acknowledging message ${messageId}:`, error);
    }
  }

  /**
   * Close Redis connection
   */
  async close(): Promise<void> {
    if (this.redis) {
      await this.redis.quit();
      this.redis = null;
      this.isInitialized = false;
      console.log("🔌 Redis Streams service connection closed");
    }
  }

  /**
   * Check if service is healthy
   */
  async healthCheck(): Promise<boolean> {
    try {
      if (!this.redis) return false;
      await this.redis.ping();
      return true;
    } catch (error) {
      console.error("❌ Redis Streams health check failed:", error);
      return false;
    }
  }
}

// Export singleton instance
export const redisStreamsService = new RedisStreamsService();

// Export types and constants
export { STREAMS, CONSUMER_GROUPS };
export type { RedisStreamsService };
