import prisma from "app/db.server";
import { KafkaProducerService } from "./kafka/kafka-producer.service";

export const triggerFullAnalysis = async (shopDomain: string) => {
  try {
    // Get shop information from database to retrieve shop_id and access_token
    const shop = await prisma.shop.findUnique({
      where: { shopDomain },
      select: { id: true, accessToken: true },
    });

    if (!shop) {
      throw new Error(`Shop not found for domain: ${shopDomain}`);
    }

    if (!shop.accessToken) {
      throw new Error(`No access token found for shop: ${shopDomain}`);
    }

    // Create a job ID; Kafka ensures ordering and we key by shop for partitioning
    const jobId = `analysis_${shopDomain}_${Date.now()}`;

    const jobData = {
      event_type: "data_collection",
      job_id: jobId,
      shop_id: shop.id,
      shop_domain: shopDomain,
      access_token: shop.accessToken,
      job_type: "data_collection",
      data_types: ["products", "orders", "customers", "collections"],
      trigger_source: "manual_analysis",
      timestamp: new Date().toISOString(),
      priority: "high",
    };

    const producer = await KafkaProducerService.getInstance();
    const messageId = await producer.publishDataJobEvent(jobData);
    console.log(`✅ Data collection job published to Kafka: ${messageId}`);
    return { success: true, messageId };
  } catch (error: any) {
    console.error("❌ Failed to publish data collection job:", error);
    throw new Error(`Failed to trigger analysis: ${error.message}`);
  }
};
