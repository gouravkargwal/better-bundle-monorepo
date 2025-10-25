import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";
import logger from "app/utils/logger";

export const action = async ({ request }: ActionFunctionArgs) => {
  const startTime = Date.now();
  let payload, session, topic, shop;

  logger.info("Order paid webhook triggered");

  try {
    const authResult = await authenticate.webhook(request);
    payload = authResult.payload;
    session = authResult.session;
    topic = authResult.topic;
    shop = authResult.shop;
    logger.info({ shop, topic }, "Webhook authentication successful");
  } catch (authError) {
    logger.error(
      {
        error:
          authError instanceof Error ? authError.message : String(authError),
      },
      "Webhook authentication failed",
    );
    return json({ error: "Authentication failed" }, { status: 401 });
  }

  if (!session || !shop) {
    logger.error("Missing session or shop data");
    return json({ error: "Authentication failed" }, { status: 401 });
  }

  try {
    // Extract order data from payload
    const order = payload;
    const orderId = order.id?.toString();

    logger.info(
      { orderId, shop, orderKeys: Object.keys(order) },
      "Order data received",
    );

    if (!orderId) {
      logger.error({ payload }, "No order ID found in payload");
      return json({ error: "No order ID found" }, { status: 400 });
    }

    logger.info("Initializing Kafka producer");
    const kafkaProducer = await KafkaProducerService.getInstance();
    logger.info("Kafka producer initialized");

    const streamData = {
      event_type: "order_paid",
      shop_domain: shop,
      shopify_id: orderId,
      timestamp: new Date().toISOString(),
    } as const;

    logger.info({ event: streamData }, "Publishing event to Kafka");
    const messageId = await kafkaProducer.publishShopifyEvent(streamData);
    logger.info({ messageId }, "Event published successfully");

    const duration = Date.now() - startTime;
    logger.info(
      { orderId, shopDomain: shop, duration },
      "Order paid webhook processed successfully",
    );

    return json({
      success: true,
      orderId: orderId,
      shopDomain: shop,
      messageId: messageId,
      message:
        "Order paid webhook processed - will trigger specific data collection",
    });
  } catch (error) {
    logger.error(
      {
        error: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined,
        topic,
      },
      "Error processing order paid webhook",
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
