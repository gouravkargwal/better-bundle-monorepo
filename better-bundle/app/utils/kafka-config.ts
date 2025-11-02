/**
 * Kafka configuration for BetterBundle
 */

export const kafkaConfig = {
  // Connection settings
  bootstrapServers: process.env.KAFKA_BOOTSTRAP_SERVERS?.split(",") || [
    "localhost:9092",
  ],
  clientId: process.env.KAFKA_CLIENT_ID || "betterbundle",
  workerId: process.env.KAFKA_WORKER_ID || "worker-1",

  // Producer settings
  producer: {
    acks: "all" as const,
    retries: 3,
    batchSize: 16384,
    lingerMs: 10,
    bufferMemory: 33554432,
    compressionType: "snappy" as const,
    maxBlockMs: 60000,
    requestTimeoutMs: 30000,
  },

  // Consumer settings
  consumer: {
    autoOffsetReset: "latest" as const,
    enableAutoCommit: false,
    maxPollRecords: 500,
    sessionTimeoutMs: 30000,
    heartbeatIntervalMs: 10000,
    maxPollIntervalMs: 300000,
    requestTimeoutMs: 30000,
  },

  // Admin settings
  admin: {
    requestTimeoutMs: 30000,
    connectionsMaxIdleMs: 540000,
  },

  // Topic configurations
  topics: {
    "shopify-events": {
      partitions: 6,
      replicationFactor: 3,
      retentionMs: 604800000, // 7 days
      compressionType: "snappy",
      cleanupPolicy: "delete",
    },
    "data-collection-jobs": {
      partitions: 4,
      replicationFactor: 3,
      retentionMs: 259200000, // 3 days
      compressionType: "snappy",
      cleanupPolicy: "delete",
    },
    "normalization-jobs": {
      partitions: 4,
      replicationFactor: 3,
      retentionMs: 259200000, // 3 days
      compressionType: "snappy",
      cleanupPolicy: "delete",
    },
    "ml-training": {
      partitions: 2,
      replicationFactor: 3,
      retentionMs: 86400000, // 1 day
      compressionType: "snappy",
      cleanupPolicy: "delete",
    },
    "behavioral-events": {
      partitions: 8,
      replicationFactor: 3,
      retentionMs: 259200000, // 3 days
      compressionType: "snappy",
      cleanupPolicy: "delete",
    },
    "billing-events": {
      partitions: 4,
      replicationFactor: 3,
      retentionMs: 259200000, // 3 days
      compressionType: "snappy",
      cleanupPolicy: "delete",
    },
    "shopify-usage-events": {
      partitions: 4,
      replicationFactor: 3,
      retentionMs: 259200000, // 3 days
      compressionType: "snappy",
      cleanupPolicy: "delete",
    },
    "access-control": {
      partitions: 6,
      replicationFactor: 3,
      retentionMs: 604800000, // 7 days
      compressionType: "snappy",
      cleanupPolicy: "delete",
    },
  },

  // Consumer groups
  consumerGroups: {
    "shopify-events-processors": "shopify-events",
    "data-collection-processors": "data-collection-jobs",
    "normalization-processors": "normalization-jobs",
    "ml-training-processors": "ml-training",
    "behavioral-events-processors": "behavioral-events",
    "billing-processors": "billing-events",
    "shopify-usage-processors": "shopify-usage-events",
    "access-control-processors": "access-control",
  },

  // Health check settings
  healthCheck: {
    interval: 30000, // 30 seconds
    timeout: 5000, // 5 seconds
  },
};

export default kafkaConfig;
