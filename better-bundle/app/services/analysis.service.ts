import prisma from "app/db.server";
import { KafkaProducerService } from "./kafka/kafka-producer.service";

export const triggerFullAnalysis = async (shopDomain: string) => {
  try {
    // Get shop information from database to retrieve shop_id and access_token
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: shopDomain },
      select: { id: true, access_token: true },
    });

    if (!shop) {
      throw new Error(`Shop not found for domain: ${shopDomain}`);
    }

    if (!shop.access_token) {
      throw new Error(`No access token found for shop: ${shopDomain}`);
    }

    // Create a job ID; Kafka ensures ordering and we key by shop for partitioning
    const jobId = `analysis_${shopDomain}_${Date.now()}`;

    // Create collection payload for full analysis (all data types)
    const collectionPayload = {
      data_types: ["products", "orders", "customers", "collections"],
    };

    const jobData = {
      event_type: "data_collection",
      job_id: jobId,
      shop_id: shop.id,
      job_type: "data_collection",
      mode: "historical", // This ensures all historical data is processed during onboarding
      collection_payload: collectionPayload, // New: specify what data to collect
      trigger_source: "analysis", // New: indicate this is triggered by analysis
      timestamp: new Date().toISOString(),
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

/**
 * Trigger specific data collection for a shop
 */
export const triggerSpecificDataCollection = async (
  shopDomain: string,
  dataTypes: string[],
  mode: "incremental" | "historical" = "incremental",
) => {
  try {
    // Get shop information from database to retrieve shop_id and access_token
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: shopDomain },
      select: { id: true, access_token: true },
    });

    if (!shop) {
      throw new Error(`Shop not found for domain: ${shopDomain}`);
    }

    if (!shop.access_token) {
      throw new Error(`No access token found for shop: ${shopDomain}`);
    }

    // Create a job ID; Kafka ensures ordering and we key by shop for partitioning
    const jobId = `specific_${shopDomain}_${Date.now()}`;

    // Create collection payload for specific data types
    const collectionPayload = {
      data_types: dataTypes,
    };

    const jobData = {
      event_type: "data_collection",
      job_id: jobId,
      shop_id: shop.id,
      job_type: "data_collection",
      mode: mode,
      collection_payload: collectionPayload,
      trigger_source: "analysis",
      timestamp: new Date().toISOString(),
    };

    const producer = await KafkaProducerService.getInstance();
    const messageId = await producer.publishDataJobEvent(jobData);
    console.log(
      `✅ Specific data collection job published to Kafka: ${messageId}`,
    );
    return { success: true, messageId };
  } catch (error: any) {
    console.error("❌ Failed to publish specific data collection job:", error);
    throw new Error(
      `Failed to trigger specific data collection: ${error.message}`,
    );
  }
};
