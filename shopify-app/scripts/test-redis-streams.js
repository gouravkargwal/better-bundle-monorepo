#!/usr/bin/env node

/**
 * Test script to verify Redis Streams connectivity
 * Run with: node scripts/test-redis-streams.js
 */

import Redis from "ioredis";

const redisConfig = {
  host: process.env.REDIS_HOST || "localhost",
  port: parseInt(process.env.REDIS_PORT || "6379"),
  password: process.env.REDIS_PASSWORD || undefined,
  db: parseInt(process.env.REDIS_DB || "0"),
};

async function testRedisStreams() {
  console.log("🧪 Testing Redis Streams connectivity...");
  console.log("📡 Redis config:", { ...redisConfig, password: redisConfig.password ? "***" : undefined });

  const redis = new Redis(redisConfig);

  try {
    // Test basic connection
    console.log("\n1️⃣ Testing basic Redis connection...");
    const pong = await redis.ping();
    console.log("✅ Redis ping:", pong);

    // Test stream operations
    console.log("\n2️⃣ Testing Redis Streams operations...");
    
    const testStream = "test:stream";
    const testGroup = "test-group";
    
    // Add a test message
    const messageId = await redis.xadd(testStream, "*", "test", "value", "timestamp", Date.now());
    console.log("✅ Added test message:", messageId);

    // Create a consumer group
    try {
      await redis.xgroup("CREATE", testStream, testGroup, "$", "MKSTREAM");
      console.log("✅ Created consumer group:", testGroup);
    } catch (error) {
      if (error.message.includes("BUSYGROUP")) {
        console.log("ℹ️ Consumer group already exists");
      } else {
        throw error;
      }
    }

    // Read messages
    const messages = await redis.xread("COUNT", 1, "STREAMS", testStream, "0");
    console.log("✅ Read messages:", messages);

    // Get stream length
    const length = await redis.xlen(testStream);
    console.log("✅ Stream length:", length);

    // Clean up test stream
    await redis.del(testStream);
    console.log("✅ Cleaned up test stream");

    // Test BetterBundle streams
    console.log("\n3️⃣ Testing BetterBundle streams...");
    
    const streams = [
      "betterbundle:data-jobs",
      "betterbundle:ml-training", 
      "betterbundle:analysis-results",
      "betterbundle:user-notifications",
      "betterbundle:features-computed"
    ];

    for (const stream of streams) {
      try {
        const streamLength = await redis.xlen(stream);
        console.log(`✅ ${stream}: ${streamLength} messages`);
      } catch (error) {
        console.log(`ℹ️ ${stream}: ${error.message}`);
      }
    }

    console.log("\n🎉 All Redis Streams tests passed!");
    return true;

  } catch (error) {
    console.error("\n❌ Redis Streams test failed:", error.message);
    return false;
  } finally {
    await redis.quit();
    console.log("🔌 Redis connection closed");
  }
}

// Run the test
testRedisStreams()
  .then((success) => {
    process.exit(success ? 0 : 1);
  })
  .catch((error) => {
    console.error("💥 Test script error:", error);
    process.exit(1);
  });
