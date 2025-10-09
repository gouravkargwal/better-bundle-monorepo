import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";

export const action = async ({ request }: ActionFunctionArgs) => {
  let payload, session, topic, shop;

  console.log("🔔 Order edited webhook triggered");

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
    // For orders/edited, the payload structure is different
    const orderEdit = payload.order_edit;

    // The order ID is in order_edit.order_id (not in a nested order object)
    const orderId = orderEdit?.order_id?.toString();

    console.log("📦 Order edit data received:", {
      orderId,
      shop,
      orderEditKeys: Object.keys(payload),
      orderEditId: orderEdit?.id,
      orderEditOrderId: orderEdit?.order_id,
      orderEditStructure: orderEdit ? Object.keys(orderEdit) : [],
    });

    // Log the full payload structure for debugging
    console.log(
      "🔍 Full orders/edited webhook payload:",
      JSON.stringify(payload, null, 2),
    );

    if (!orderId) {
      console.error("❌ No order ID found in order edit payload");
      return json(
        { error: "No order ID found in order edit" },
        { status: 400 },
      );
    }

    console.log("🚀 Initializing Kafka producer...");
    const kafkaProducer = await KafkaProducerService.getInstance();
    console.log("✅ Kafka producer initialized");

    const streamData = {
      event_type: "order_edited",
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
        "Order edited webhook processed - will trigger post-purchase revenue attribution",
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
