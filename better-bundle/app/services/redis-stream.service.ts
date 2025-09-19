import { getRedisClient } from "./redis.service";

export interface ShopifyEventData {
  event_type: string;
  shop_id: string;
  shopify_id: string;
  timestamp: string;
}

export class RedisStreamService {
  private static instance: RedisStreamService;
  private client: any;
  private recentEvents: Map<string, number> = new Map(); // For deduplication

  private constructor() {}

  public static async getInstance(): Promise<RedisStreamService> {
    if (!RedisStreamService.instance) {
      RedisStreamService.instance = new RedisStreamService();
      RedisStreamService.instance.client = await getRedisClient();
    }
    return RedisStreamService.instance;
  }

  /**
   * Publish a Shopify event to the Redis Stream
   */
  async publishShopifyEvent(eventData: ShopifyEventData): Promise<string> {
    try {
      console.log(`🚀 Starting publishShopifyEvent with data:`, eventData);

      // Create a deduplication key
      const dedupKey = `${eventData.shop_id}_${eventData.shopify_id}_${eventData.event_type}`;
      const now = Date.now();

      console.log(`🔍 Checking deduplication for key: ${dedupKey}`);

      // Check if we've seen this event recently (within 5 seconds)
      const lastSeen = this.recentEvents.get(dedupKey);
      if (lastSeen && now - lastSeen < 5000) {
        console.log(
          `🔄 Skipping duplicate event: ${dedupKey} (last seen ${now - lastSeen}ms ago)`,
        );
        return "duplicate";
      }

      console.log(`✅ New event, proceeding with publish: ${dedupKey}`);

      // Record this event
      this.recentEvents.set(dedupKey, now);

      // Clean up old entries (older than 30 seconds)
      for (const [key, timestamp] of this.recentEvents.entries()) {
        if (now - timestamp > 30000) {
          this.recentEvents.delete(key);
        }
      }

      const streamName = "betterbundle:shopify-events";
      console.log(`📡 Publishing to stream: ${streamName}`);

      // Convert event data to Redis Stream format
      const streamFields = [
        "event_type",
        eventData.event_type,
        "shop_id",
        eventData.shop_id,
        "shopify_id",
        eventData.shopify_id,
        "timestamp",
        eventData.timestamp,
      ];

      console.log(`📡 Stream fields:`, streamFields);

      // Check if client is connected
      if (!this.client.isOpen) {
        console.log(`🔌 Redis client not connected, attempting to connect...`);
        await this.client.connect();
      }

      console.log(`🔌 Redis client status:`, {
        isOpen: this.client.isOpen,
        isReady: this.client.isReady,
      });

      // Use XADD to add event to stream
      console.log(`📤 Calling xAdd...`);
      const messageId = await this.client.xAdd(streamName, "*", streamFields);
      console.log(`✅ xAdd successful, messageId: ${messageId}`);

      console.log(`📡 Published event to Redis Stream:`, {
        streamName,
        messageId,
        eventType: eventData.event_type,
        shopId: eventData.shop_id,
        shopifyId: eventData.shopify_id,
      });

      return messageId;
    } catch (error) {
      console.error("❌ Error publishing to Redis Stream:", error);
      console.error("❌ Error details:", {
        message: error.message,
        stack: error.stack,
        name: error.name,
      });
      throw error;
    }
  }

  /**
   * Create consumer group for the stream (if it doesn't exist)
   */
  async ensureConsumerGroup(
    streamName: string,
    groupName: string,
  ): Promise<void> {
    try {
      await this.client.xGroupCreate(streamName, groupName, "0", {
        MKSTREAM: true, // Create stream if it doesn't exist
      });
      console.log(
        `✅ Consumer group '${groupName}' created for stream '${streamName}'`,
      );
    } catch (error: any) {
      // Group might already exist, which is fine
      if (error.message?.includes("BUSYGROUP")) {
        console.log(
          `ℹ️ Consumer group '${groupName}' already exists for stream '${streamName}'`,
        );
      } else {
        console.error(`❌ Error creating consumer group:`, error);
        throw error;
      }
    }
  }

  /**
   * Publish message directly to a specific stream
   */
  async publishToStream(streamName: string, messageData: any): Promise<string> {
    try {
      console.log(`📤 Publishing to stream: ${streamName}`, messageData);

      // Convert message to Redis Stream format (key-value pairs as array)
      const streamFields = Object.entries(messageData).flat();
      const messageId = await this.client.xAdd(streamName, "*", streamFields);

      console.log(`✅ Published to ${streamName} with ID: ${messageId}`);
      return messageId;
    } catch (error) {
      console.error(`❌ Error publishing to stream ${streamName}:`, error);
      throw error;
    }
  }

  /**
   * Get stream info
   */
  async getStreamInfo(streamName: string): Promise<any> {
    try {
      return await this.client.xInfoStream(streamName);
    } catch (error) {
      console.error(`❌ Error getting stream info:`, error);
      throw error;
    }
  }
}

// Export singleton instance getter
export async function getRedisStreamService(): Promise<RedisStreamService> {
  return await RedisStreamService.getInstance();
}
