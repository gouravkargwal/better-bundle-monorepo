import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
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

    const shopRecord = await prisma.shop.findFirst({
      where: { shopDomain: shop },
      select: { id: true },
    });

    if (!shopRecord) {
      console.error(`❌ Shop not found: ${shop}`);
      return json({ error: "Shop not found" }, { status: 404 });
    }

    const kafkaProducer = await KafkaProducerService.getInstance();

    const streamData = {
      event_type: "refund_created",
      shop_id: shopRecord.id,
      shopify_id: orderId,
      refund_id: refundId,
      timestamp: new Date().toISOString(),
      raw_payload: refund, // Include the full raw refund payload
    };

    await kafkaProducer.publishShopifyEvent(streamData);

    return json({
      success: true,
      refundId: refundId,
      orderId: orderId,
      shopId: shopRecord.id,
      message: "Refund event published to Kafka",
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
