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

    // ✅ ONLY FOR ORDER DATA UPDATE - No refund attribution processing
    const streamData = {
      event_type: "refund_created", // For order data normalization only
      shop_domain: shop,
      shopify_id: orderId, // Order ID for order data update
      metadata: {
        trigger: "refund_created",
        refund_id: refundId,
        // ✅ NO REFUND COMMISSION POLICY - Only for data collection
        purpose: "order_data_update_only",
      },
      timestamp: new Date().toISOString(),
    } as const;

    await kafkaProducer.publishShopifyEvent(streamData);

    return json({
      success: true,
      refundId: refundId,
      orderId: orderId,
      shopDomain: shop,
      message:
        "Refund event published to Kafka - will trigger order data update only (no refund attribution processing)",
    });
  } catch (error) {
    console.error("❌ Error processing refund webhook:", error);
    return json({ error: "Internal server error" }, { status: 500 });
  }
};
