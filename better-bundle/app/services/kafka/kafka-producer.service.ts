import type { Producer, RecordMetadata } from "kafkajs";
import { KafkaClientService } from "./kafka-client.service";
import { kafkaConfig } from "../../utils/kafka-config";
import logger from "../../utils/logger";

export interface ShopifyEventData {
  event_type: string;
  shop_id?: string; // Optional for backward compatibility
  shop_domain?: string; // New: shop domain for backend resolution
  shopify_id: string;
  timestamp: string;
  [key: string]: any;
}

export class KafkaProducerService {
  private static instance: KafkaProducerService;
  private clientService!: KafkaClientService;
  private producer: Producer | null = null;
  private messageCount = 0;
  private errorCount = 0;

  public static async getInstance(): Promise<KafkaProducerService> {
    if (!KafkaProducerService.instance) {
      KafkaProducerService.instance = new KafkaProducerService();
      await KafkaProducerService.instance.initialize();
    }
    return KafkaProducerService.instance;
  }

  private async initialize(): Promise<void> {
    try {
      this.clientService = await KafkaClientService.getInstance();
      this.producer = await this.clientService.getProducer();
    } catch (error) {
      logger.error({ error }, "Failed to initialize Kafka producer service");
      throw error;
    }
  }

  /**
   * Publish a Shopify event to Kafka
   */
  public async publishShopifyEvent(
    eventData: ShopifyEventData,
  ): Promise<string> {
    try {
      const shopIdentifier =
        eventData.shop_id || eventData.shop_domain || "unknown";

      // Add metadata
      const messageWithMetadata = {
        ...eventData,
        timestamp: new Date().toISOString(),
        worker_id: kafkaConfig.workerId,
        source: "shopify_webhook",
      };

      // Determine key for partitioning (use shop_id or shop_domain for consistent partitioning)
      const key = eventData.shop_id || eventData.shop_domain || "unknown";

      if (!this.producer) {
        logger.error("Producer not initialized");
        throw new Error("Producer not initialized");
      }

      const result: RecordMetadata = await this.producer.send({
        topic: "shopify-events",
        messages: [
          {
            key,
            value: JSON.stringify(messageWithMetadata),
            headers: {
              "event-type": eventData.event_type,
              "shop-id":
                eventData.shop_id || eventData.shop_domain || "unknown",
              timestamp: new Date().toISOString(),
            },
          },
        ],
      });

      this.messageCount++;
      const messageId = `${result[0].topicName}:${result[0].partition}:${result[0].offset}`;

      logger.info({ messageId }, "Shopify event published");
      return messageId;
    } catch (error) {
      this.errorCount++;
      logger.error({ error }, "Failed to publish Shopify event");
      throw error;
    }
  }

  /**
   * Publish a data collection job event
   */
  public async publishDataJobEvent(jobData: any): Promise<string> {
    try {
      const messageWithMetadata = {
        ...jobData,
        timestamp: new Date().toISOString(),
        worker_id: kafkaConfig.workerId,
        source: "data_collection",
      };

      const key = jobData.shop_id;

      if (!this.producer) {
        throw new Error("Producer not initialized");
      }

      const result: RecordMetadata = await this.producer.send({
        topic: "data-collection-jobs",
        messages: [
          {
            key,
            value: JSON.stringify(messageWithMetadata),
            headers: {
              "job-type": jobData.job_type,
              "shop-id": jobData.shop_id,
              timestamp: new Date().toISOString(),
            },
          },
        ],
      });

      this.messageCount++;
      const messageId = `${result[0].topicName}:${result[0].partition}:${result[0].offset}`;

      logger.info({ messageId }, "Data job published");
      return messageId;
    } catch (error) {
      this.errorCount++;
      logger.error({ error }, "Failed to publish data job");
      throw error;
    }
  }

  /**
   * Publish an access control event
   */
  public async publishAccessControlEvent(accessData: any): Promise<string> {
    try {
      const messageWithMetadata = {
        ...accessData,
        timestamp: new Date().toISOString(),
        worker_id: kafkaConfig.workerId,
        source: "access_control",
      };

      const key = accessData.shop_id;

      if (!this.producer) {
        throw new Error("Producer not initialized");
      }

      const result: RecordMetadata = await this.producer.send({
        topic: "access-control",
        messages: [
          {
            key,
            value: JSON.stringify(messageWithMetadata),
            headers: {
              "event-type": accessData.event_type,
              "shop-id": accessData.shop_id,
              timestamp: new Date().toISOString(),
            },
          },
        ],
      });

      this.messageCount++;
      const messageId = `${result[0].topicName}:${result[0].partition}:${result[0].offset}`;

      logger.info({ messageId }, "Access control event published");
      return messageId;
    } catch (error) {
      this.errorCount++;
      logger.error({ error }, "Failed to publish access control event");
      throw error;
    }
  }

  /**
   * Publish multiple events in batch
   */
  public async publishBatch(
    events: Array<{ topic: string; data: any; key?: string }>,
  ): Promise<string[]> {
    try {
      if (!this.producer) {
        throw new Error("Producer not initialized");
      }

      const messages = events.map((event) => ({
        topic: event.topic,
        messages: [
          {
            key: event.key || event.data.shop_id,
            value: JSON.stringify({
              ...event.data,
              timestamp: new Date().toISOString(),
              worker_id: kafkaConfig.workerId,
            }),
          },
        ],
      }));

      const results: RecordMetadata[] = [];
      for (const message of messages) {
        const result = await this.producer.send(message);
        results.push(...result);
      }

      this.messageCount += events.length;
      const messageIds = results.map(
        (r) => `${r.topicName}:${r.partition}:${r.offset}`,
      );

      logger.info({ messageIds }, "Batch published");
      return messageIds;
    } catch (error) {
      this.errorCount += events.length;
      logger.error({ error }, "Failed to publish batch");
      throw error;
    }
  }

  /**
   * Get producer metrics
   */
  public getMetrics(): {
    messagesSent: number;
    errors: number;
    successRate: number;
  } {
    return {
      messagesSent: this.messageCount,
      errors: this.errorCount,
      successRate:
        this.messageCount > 0
          ? ((this.messageCount - this.errorCount) / this.messageCount) * 100
          : 0,
    };
  }

  /**
   * Close producer
   */
  public async close(): Promise<void> {
    if (this.producer) {
      await this.producer.disconnect();
      this.producer = null;
      logger.info("Kafka producer service closed");
    }
  }
}
