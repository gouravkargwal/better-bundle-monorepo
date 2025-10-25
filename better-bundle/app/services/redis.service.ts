import { createClient, type RedisClientType } from "redis";
import logger from "../utils/logger";

// Redis client singleton
let redisClient: RedisClientType | null = null;

export async function getRedisClient(): Promise<RedisClientType> {
  if (!redisClient) {
    // Support both REDIS_URL and individual Redis configuration
    const redisUrl = process.env.REDIS_URL;
    const redisHost = process.env.REDIS_HOST || "localhost";
    const redisPort = parseInt(process.env.REDIS_PORT || "6379");
    const redisPassword = process.env.REDIS_PASSWORD;
    const redisDb = parseInt(process.env.REDIS_DB || "0");

    // Build Redis configuration
    const redisConfig: any = {
      socket: {
        reconnectStrategy: (retries: number) => {
          logger.info({ retries }, "Redis reconnection attempt");
          if (retries > 10) {
            logger.error("Redis connection failed after 10 retries");
            return new Error("Redis connection failed");
          }
          return Math.min(retries * 100, 3000);
        },
      },
    };

    // Use REDIS_URL if provided, otherwise build from individual components
    if (redisUrl) {
      redisConfig.url = redisUrl;
    } else {
      redisConfig.socket = {
        ...redisConfig.socket,
        host: redisHost,
        port: redisPort,
      };
      redisConfig.database = redisDb;
      if (redisPassword) {
        redisConfig.password = redisPassword;
      }
    }

    redisClient = createClient(redisConfig);

    redisClient.on("error", (err) => {
      logger.error({ error: err }, "Redis Client Error");
    });

    await redisClient.connect();
  }

  return redisClient;
}

// Cache utility functions
export class CacheService {
  private client: RedisClientType;

  constructor(client: RedisClientType) {
    this.client = client;
  }

  async get<T>(key: string): Promise<T | null> {
    try {
      const value = await this.client.get(key);
      return value ? JSON.parse(value) : null;
    } catch (error) {
      logger.error({ error, key }, "Cache get error");
      return null;
    }
  }

  async set(key: string, value: any, ttlSeconds: number = 300): Promise<void> {
    try {
      await this.client.setEx(key, ttlSeconds, JSON.stringify(value));
    } catch (error) {
      logger.error({ error, key }, "Cache set error");
    }
  }

  async del(key: string): Promise<void> {
    try {
      await this.client.del(key);
    } catch (error) {
      logger.error({ error, key }, "Cache delete error");
    }
  }

  async delPattern(pattern: string): Promise<void> {
    try {
      const keys = await this.client.keys(pattern);
      if (keys.length > 0) {
        await this.client.del(keys);
      }
    } catch (error) {
      logger.error({ error, pattern }, "Cache delete pattern error");
    }
  }

  async exists(key: string): Promise<boolean> {
    try {
      const result = await this.client.exists(key);
      return result === 1;
    } catch (error) {
      logger.error({ error, key }, "Cache exists error");
      return false;
    }
  }

  // Cache with fallback function
  async getOrSet<T>(
    key: string,
    fallbackFn: () => Promise<T>,
    ttlSeconds: number = 300,
  ): Promise<T> {
    try {
      // Try to get from cache first
      const cached = await this.get<T>(key);
      if (cached !== null) {
        return cached;
      }

      // Cache miss - execute fallback function
      const result = await fallbackFn();

      // Store in cache
      await this.set(key, result, ttlSeconds);

      return result;
    } catch (error) {
      logger.error({ error, key }, "Cache getOrSet error");
      // If cache fails, still execute fallback function
      return await fallbackFn();
    }
  }

  // Invalidate cache patterns
  async invalidateDashboard(shopId: string): Promise<void> {
    await Promise.all([
      this.delPattern(`dashboard:${shopId}:*`),
      this.delPattern(`overview:${shopId}:*`),
      this.delPattern(`performance:${shopId}:*`),
      this.delPattern(`context:${shopId}:*`),
      this.delPattern(`products:${shopId}:*`),
      this.delPattern(`activity:${shopId}:*`),
    ]);
  }

  async invalidateShop(shopDomain: string): Promise<void> {
    await this.del(`shop:${shopDomain}`);
  }
}

// Cache service singleton
let cacheService: CacheService | null = null;

export async function getCacheService(): Promise<CacheService> {
  if (!cacheService) {
    const client = await getRedisClient();
    cacheService = new CacheService(client);
  }
  return cacheService;
}

// Cache key generators
export const CacheKeys = {
  shop: (domain: string) => `shop:${domain}`,
  dashboard: (
    shopId: string,
    period: string,
    startDate: string,
    endDate: string,
  ) => `dashboard:${shopId}:${period}:${startDate}:${endDate}`,
  overview: (shopId: string, startDate: string, endDate: string) =>
    `overview:${shopId}:${startDate}:${endDate}`,
  performance: (shopId: string, startDate: string, endDate: string) =>
    `performance:${shopId}:${startDate}:${endDate}`,
  context: (shopId: string, startDate: string, endDate: string) =>
    `context:${shopId}:${startDate}:${endDate}`,
  products: (
    shopId: string,
    startDate: string,
    endDate: string,
    limit: number,
  ) => `products:${shopId}:${startDate}:${endDate}:${limit}`,
  activity: (shopId: string, startDate: string, endDate: string) =>
    `activity:${shopId}:${startDate}:${endDate}`,
};

// Cache TTL constants (in seconds)
export const CacheTTL = {
  SHOP: 3600, // 1 hour
  DASHBOARD: 300, // 5 minutes
  OVERVIEW: 300, // 5 minutes
  PERFORMANCE: 300, // 5 minutes
  CONTEXT: 300, // 5 minutes
  PRODUCTS: 600, // 10 minutes
  ACTIVITY: 120, // 2 minutes
} as const;
