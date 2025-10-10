/**
 * Kafka client service for BetterBundle
 */

import { Kafka, Producer, Consumer, Admin } from "kafkajs";
import { kafkaConfig } from "../../utils/kafka-config";

export class KafkaClientService {
  private static instance: KafkaClientService;
  private kafka: Kafka;
  private producer: Producer | null = null;
  private consumer: Consumer | null = null;
  private admin: Admin | null = null;
  private connected = false;

  private constructor() {
    this.kafka = new Kafka({
      clientId: kafkaConfig.clientId,
      brokers: kafkaConfig.bootstrapServers,
      retry: {
        initialRetryTime: 100,
        retries: 8,
      },
    });
  }

  public static async getInstance(): Promise<KafkaClientService> {
    if (!KafkaClientService.instance) {
      KafkaClientService.instance = new KafkaClientService();
      await KafkaClientService.instance.initialize();
    }
    return KafkaClientService.instance;
  }

  private async initialize(): Promise<void> {
    try {
      console.log("🔧 Initializing Kafka client service...");
      console.log("📋 Kafka config:", {
        clientId: kafkaConfig.clientId,
        bootstrapServers: kafkaConfig.bootstrapServers,
        workerId: kafkaConfig.workerId
      });

      // Initialize admin client
      this.admin = this.kafka.admin();
      console.log("🔌 Connecting to Kafka admin...");
      await this.admin.connect();

      // Test connection
      console.log("🧪 Testing Kafka connection...");
      await this.testConnection();
      this.connected = true;

      console.log("✅ Kafka client service initialized successfully");
    } catch (error) {
      console.error("❌ Failed to initialize Kafka client:", error);
      console.error("Error details:", {
        message: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined,
        bootstrapServers: kafkaConfig.bootstrapServers
      });
      throw error;
    }
  }

  private async testConnection(): Promise<void> {
    if (!this.admin) {
      throw new Error("Admin client not initialized");
    }

    try {
      const metadata = await this.admin.describeCluster();
      console.log(`🔗 Connected to Kafka cluster: ${metadata.clusterId}`);
    } catch (error) {
      console.error("❌ Kafka connection test failed:", error);
      throw error;
    }
  }

  public async getProducer(): Promise<Producer> {
    if (!this.producer) {
      console.log("🔧 Creating Kafka producer...");
      this.producer = this.kafka.producer({
        maxInFlightRequests: 1,
        idempotent: true,
        transactionTimeout: 30000,
        retry: {
          initialRetryTime: 100,
          retries: 8,
        },
      });

      console.log("🔌 Connecting Kafka producer...");
      await this.producer.connect();
      console.log("📤 Kafka producer connected successfully");
    }
    return this.producer;
  }

  public async getConsumer(groupId: string): Promise<Consumer> {
    if (!this.consumer) {
      this.consumer = this.kafka.consumer({
        groupId,
        sessionTimeout: 30000,
        heartbeatInterval: 3000,
        maxWaitTimeInMs: 5000,
        retry: {
          initialRetryTime: 100,
          retries: 8,
        },
      });

      await this.consumer.connect();
      console.log(`📥 Kafka consumer connected for group: ${groupId}`);
    }
    return this.consumer;
  }

  public async getAdmin(): Promise<Admin> {
    if (!this.admin) {
      this.admin = this.kafka.admin();
      await this.admin.connect();
    }
    return this.admin;
  }

  public async healthCheck(): Promise<{ status: string; details: any }> {
    try {
      if (!this.admin) {
        return {
          status: "unhealthy",
          details: { error: "Admin client not initialized" },
        };
      }

      const metadata = await this.admin.describeCluster();

      return {
        status: "healthy",
        details: {
          clusterId: metadata.clusterId,
          brokers: metadata.brokers.length,
          connected: this.connected,
        },
      };
    } catch (error) {
      return {
        status: "unhealthy",
        details: {
          error: error instanceof Error ? error.message : String(error),
        },
      };
    }
  }

  public async close(): Promise<void> {
    try {
      if (this.producer) {
        await this.producer.disconnect();
        this.producer = null;
      }

      if (this.consumer) {
        await this.consumer.disconnect();
        this.consumer = null;
      }

      if (this.admin) {
        await this.admin.disconnect();
        this.admin = null;
      }

      this.connected = false;
      console.log("🔌 Kafka client service closed");
    } catch (error) {
      console.error("❌ Error closing Kafka client:", error);
    }
  }

  public get isConnected(): boolean {
    return this.connected;
  }
}
