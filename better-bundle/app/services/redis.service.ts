import { createClient, RedisClientType } from "redis";

// Redis client singleton
let redisClient: RedisClientType | null = null;

export async function getRedisClient(): Promise<RedisClientType> {
  if (!redisClient) {
    const redisUrl = process.env.REDIS_URL || "redis://localhost:6379";
    console.log(`🔌 Creating Redis client with URL: ${redisUrl}`);

    redisClient = createClient({
      url: redisUrl,
      socket: {
        reconnectStrategy: (retries) => {
          console.log(`🔄 Redis reconnection attempt ${retries}`);
          if (retries > 10) {
            console.error("Redis connection failed after 10 retries");
            return new Error("Redis connection failed");
          }
          return Math.min(retries * 100, 3000);
        },
      },
    });

    redisClient.on("error", (err) => {
      console.error("❌ Redis Client Error:", err);
    });

    redisClient.on("connect", () => {
      console.log("✅ Redis Client Connected");
    });

    redisClient.on("ready", () => {
      console.log("✅ Redis Client Ready");
    });

    redisClient.on("end", () => {
      console.log("🔌 Redis Client Disconnected");
    });

    console.log(`🔌 Attempting to connect to Redis...`);
    await redisClient.connect();
    console.log(`✅ Redis connection established`);
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
      console.error(`Cache get error for key ${key}:`, error);
      return null;
    }
  }

  async set(key: string, value: any, ttlSeconds: number = 300): Promise<void> {
    try {
      await this.client.setEx(key, ttlSeconds, JSON.stringify(value));
    } catch (error) {
      console.error(`Cache set error for key ${key}:`, error);
    }
  }

  async del(key: string): Promise<void> {
    try {
      await this.client.del(key);
    } catch (error) {
      console.error(`Cache delete error for key ${key}:`, error);
    }
  }

  async delPattern(pattern: string): Promise<void> {
    try {
      const keys = await this.client.keys(pattern);
      if (keys.length > 0) {
        await this.client.del(keys);
      }
    } catch (error) {
      console.error(`Cache delete pattern error for ${pattern}:`, error);
    }
  }

  async exists(key: string): Promise<boolean> {
    try {
      const result = await this.client.exists(key);
      return result === 1;
    } catch (error) {
      console.error(`Cache exists error for key ${key}:`, error);
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
      console.error(`Cache getOrSet error for key ${key}:`, error);
      // If cache fails, still execute fallback function
      return await fallbackFn();
    }
  }

  // Invalidate cache patterns
  async invalidateDashboard(shopId: string): Promise<void> {
    await Promise.all([
      this.delPattern(`dashboard:${shopId}:*`),
      this.delPattern(`overview:${shopId}:*`),
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
  CONTEXT: 300, // 5 minutes
  PRODUCTS: 600, // 10 minutes
  ACTIVITY: 120, // 2 minutes
} as const;
