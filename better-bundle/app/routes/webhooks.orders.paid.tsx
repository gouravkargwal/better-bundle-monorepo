import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";

export const action = async ({ request }: ActionFunctionArgs) => {
  let payload, session, topic, shop;

  try {
    const authResult = await authenticate.webhook(request);
    payload = authResult.payload;
    session = authResult.session;
    topic = authResult.topic;
    shop = authResult.shop;
  } catch (authError) {
    return json({ error: "Authentication failed" }, { status: 401 });
  }

  if (!session || !shop) {
    return json({ error: "Authentication failed" }, { status: 401 });
  }

  try {
    // Extract order data from payload
    const order = payload;
    const orderId = order.id?.toString();

    if (!orderId) {
      console.error("❌ No order ID found in payload");
      return json({ error: "No order ID found" }, { status: 400 });
    }

    const kafkaProducer = await KafkaProducerService.getInstance();

    const streamData = {
      event_type: "order_paid",
      shop_domain: shop,
      shopify_id: orderId,
      timestamp: new Date().toISOString(),
    } as const;

    await kafkaProducer.publishShopifyEvent(streamData);

    return json({
      success: true,
      orderId: orderId,
      shopDomain: shop,
      message:
        "Order paid webhook processed - will trigger specific data collection",
    });
  } catch (error) {
    console.error(`❌ Error processing ${topic} webhook:`, error);
    return json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 },
    );
  }
};
