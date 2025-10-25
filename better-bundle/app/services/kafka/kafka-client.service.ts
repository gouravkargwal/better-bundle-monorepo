/**
 * Kafka client service for BetterBundle
 */

import { Kafka, Producer, Consumer, Admin } from "kafkajs";
import { kafkaConfig } from "../../utils/kafka-config";
import logger from "../../utils/logger";

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
      this.admin = this.kafka.admin();
      await this.admin.connect();
      this.connected = true;
    } catch (error) {
      logger.error({ error }, "Failed to initialize Kafka client");
      throw error;
    }
  }

  private async testConnection(): Promise<void> {
    if (!this.admin) {
      throw new Error("Admin client not initialized");
    }

    try {
      await this.admin.describeCluster();
    } catch (error) {
      logger.error({ error }, "Kafka connection test failed");
      throw error;
    }
  }

  public async getProducer(): Promise<Producer> {
    if (!this.producer) {
      this.producer = this.kafka.producer({
        maxInFlightRequests: 1,
        idempotent: true,
        transactionTimeout: 30000,
        retry: {
          initialRetryTime: 100,
          retries: 8,
        },
      });

      await this.producer.connect();
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
    } catch (error) {
      logger.error({ error }, "Error closing Kafka client");
    }
  }

  public get isConnected(): boolean {
    return this.connected;
  }
}
