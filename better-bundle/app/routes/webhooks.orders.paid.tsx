import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";

export const action = async ({ request }: ActionFunctionArgs) => {
  let payload, session, topic, shop;

  console.log("🔔 Order paid webhook triggered");

  try {
    const authResult = await authenticate.webhook(request);
    payload = authResult.payload;
    session = authResult.session;
    topic = authResult.topic;
    shop = authResult.shop;
    console.log("✅ Webhook authentication successful", { shop, topic });
  } catch (authError) {
    console.error("❌ Webhook authentication failed:", authError);
    return json({ error: "Authentication failed" }, { status: 401 });
  }

  if (!session || !shop) {
    console.error("❌ Missing session or shop data");
    return json({ error: "Authentication failed" }, { status: 401 });
  }

  try {
    // Extract order data from payload
    const order = payload;
    const orderId = order.id?.toString();

    console.log("📦 Order data received:", {
      orderId,
      shop,
      orderKeys: Object.keys(order),
    });

    if (!orderId) {
      console.error("❌ No order ID found in payload");
      return json({ error: "No order ID found" }, { status: 400 });
    }

    console.log("🚀 Initializing Kafka producer...");
    const kafkaProducer = await KafkaProducerService.getInstance();
    console.log("✅ Kafka producer initialized");

    const streamData = {
      event_type: "order_paid",
      shop_domain: shop,
      shopify_id: orderId,
      timestamp: new Date().toISOString(),
    } as const;

    console.log("📤 Publishing event to Kafka:", streamData);
    const messageId = await kafkaProducer.publishShopifyEvent(streamData);
    console.log("✅ Event published successfully:", messageId);

    return json({
      success: true,
      orderId: orderId,
      shopDomain: shop,
      messageId: messageId,
      message:
        "Order paid webhook processed - will trigger specific data collection",
    });
  } catch (error) {
    console.error(`❌ Error processing ${topic} webhook:`, error);
    console.error(
      "Error stack:",
      error instanceof Error ? error.stack : "No stack trace",
    );
    return json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 },
    );
  }
};
