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
    // Extract refund data from payload
    const refund = payload;
    const refundId = refund.id?.toString();
    const orderId = refund.order_id?.toString();

    if (!refundId || !orderId) {
      console.error("❌ No refund ID or order ID found in payload");
      return json({ error: "No refund ID or order ID found" }, { status: 400 });
    }

    const kafkaProducer = await KafkaProducerService.getInstance();

    const streamData = {
      event_type: "refund_created",
      shop_domain: shop,
      shopify_id: orderId,
      refund_id: refundId,
      timestamp: new Date().toISOString(),
    };

    await kafkaProducer.publishShopifyEvent(streamData);

    return json({
      success: true,
      refundId: refundId,
      orderId: orderId,
      shopDomain: shop,
      message:
        "Refund event published to Kafka - will trigger data collection and normalization",
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
