import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";
import { checkServiceSuspensionByDomain } from "../middleware/serviceSuspension";
import logger from "../utils/logger";

export const action = async ({ request }: ActionFunctionArgs) => {
  let payload, session, topic, shop;

  logger.info("Order updated webhook triggered");

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
    logger.error({ session, shop }, "Missing session or shop data");
    return json({ error: "Authentication failed" }, { status: 401 });
  }

  // Check if shop services are suspended
  try {
    const suspensionStatus = await checkServiceSuspensionByDomain(shop);
    if (suspensionStatus.isSuspended) {
      logger.info(
        { shop, reason: suspensionStatus.reason },
        "Skipping order update - shop services suspended"
      );
      return json({
        success: true,
        message: "Order update skipped - services suspended",
        suspended: true,
        reason: suspensionStatus.reason,
      });
    }
  } catch (suspensionError) {
    logger.warn(
      { error: suspensionError, shop },
      "Error checking suspension status, proceeding with order update"
    );
  }

  try {
    const orderId = payload.id?.toString();

    if (!orderId) {
      logger.error({ payload }, "No order ID found in payload");
      return json({ error: "No order ID found in payload" }, { status: 400 });
    }

    logger.info("Initializing Kafka producer");
    const kafkaProducer = await KafkaProducerService.getInstance();
    logger.info("Kafka producer initialized");

    const streamData = {
      event_type: "order_updated",
      shop_domain: shop,
      shopify_id: orderId,
      timestamp: new Date().toISOString(),
    } as const;

    logger.info({ streamData }, "Publishing event to Kafka");
    const messageId = await kafkaProducer.publishShopifyEvent(streamData);
    logger.info({ messageId }, "Event published successfully");

    return json({
      success: true,
      orderId: orderId,
      shopDomain: shop,
      messageId: messageId,
      message:
        "Order updated webhook processed - will trigger post-purchase revenue attribution",
    });
  } catch (error) {
    logger.error(
      {
        error: error instanceof Error ? error.message : String(error),
        topic,
        shop,
      },
      "Error processing webhook",
    );
    return json({ error: "Internal server error" }, { status: 500 });
  }
};
