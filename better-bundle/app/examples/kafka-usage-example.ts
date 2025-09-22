/**
 * Kafka usage examples for BetterBundle (Node.js/TypeScript)
 */

import { KafkaProducerService } from "../services/kafka/kafka-producer.service";
import { KafkaClientService } from "../services/kafka/kafka-client.service";

async function exampleProducerUsage() {
  console.log("🚀 Kafka Producer Example (Node.js)");

  try {
    // Get producer service
    const producer = await KafkaProducerService.getInstance();

    // Send Shopify event
    const shopifyEvent = {
      event_type: "product_updated",
      shop_id: "shop_123",
      shopify_id: "product_456",
      timestamp: new Date().toISOString(),
    };

    const messageId = await producer.publishShopifyEvent(shopifyEvent);
    console.log(`✅ Shopify event published: ${messageId}`);

    // Send billing event
    const billingEvent = {
      event_type: "plan_expired",
      shop_id: "shop_123",
      timestamp: new Date().toISOString(),
    };

    const billingMessageId = await producer.publishBillingEvent(billingEvent);
    console.log(`✅ Billing event published: ${billingMessageId}`);

    // Send access control event
    const accessEvent = {
      event_type: "access_blocked",
      shop_id: "shop_123",
      reason: "trial_expired",
      timestamp: new Date().toISOString(),
    };

    const accessMessageId =
      await producer.publishAccessControlEvent(accessEvent);
    console.log(`✅ Access control event published: ${accessMessageId}`);

    // Get metrics
    const metrics = producer.getMetrics();
    console.log(`📊 Producer metrics:`, metrics);
  } catch (error) {
    console.error("❌ Producer example failed:", error);
  }
}

async function exampleClientUsage() {
  console.log("🔧 Kafka Client Example (Node.js)");

  try {
    // Get client service
    const client = await KafkaClientService.getInstance();

    // Check health
    const health = await client.healthCheck();
    console.log(`🏥 Health status:`, health);

    // Check connection status
    console.log(`🔗 Connected: ${client.isConnected}`);
  } catch (error) {
    console.error("❌ Client example failed:", error);
  }
}

async function exampleWebhookIntegration() {
  console.log("🔗 Webhook Integration Example (Node.js)");

  try {
    const producer = await KafkaProducerService.getInstance();

    // Simulate webhook data
    const webhookData = {
      event_type: "order_paid",
      shop_id: "shop_123",
      shopify_id: "order_456",
      timestamp: new Date().toISOString(),
      order_data: {
        total_price: "99.99",
        currency: "USD",
        line_items: [{ product_id: "prod_123", quantity: 2, price: "49.99" }],
      },
    };

    // Publish to Kafka (this would replace Redis stream publishing)
    const messageId = await producer.publishShopifyEvent(webhookData);
    console.log(`✅ Webhook event published to Kafka: ${messageId}`);

    // Also publish normalization job
    const normalizeJob = {
      event_type: "normalize_entity",
      data_type: "orders",
      format: "rest",
      shop_id: "shop_123",
      raw_id: "raw_789",
      shopify_id: "order_456",
      timestamp: new Date().toISOString(),
    };

    const normalizeMessageId = await producer.publishShopifyEvent(normalizeJob);
    console.log(`✅ Normalization job published: ${normalizeMessageId}`);
  } catch (error) {
    console.error("❌ Webhook integration example failed:", error);
  }
}

async function main() {
  console.log("🎯 Kafka Examples for BetterBundle (Node.js)");
  console.log("=".repeat(50));

  try {
    // Client example
    await exampleClientUsage();
    console.log();

    // Producer example
    await exampleProducerUsage();
    console.log();

    // Webhook integration example
    await exampleWebhookIntegration();
    console.log();
  } catch (error) {
    console.error("❌ Error running examples:", error);
  }

  console.log("✅ Examples completed!");
}

// Export for use in other files
export { exampleProducerUsage, exampleClientUsage, exampleWebhookIntegration };

// Run if called directly
if (require.main === module) {
  main().catch(console.error);
}
