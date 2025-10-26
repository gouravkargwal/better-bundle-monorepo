import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";
import { checkServiceSuspensionByDomain } from "../middleware/serviceSuspension";
import logger from "../utils/logger";

export const action = async ({ request }: ActionFunctionArgs) => {
  let payload, session, topic, shop;

  try {
    const authResult = await authenticate.webhook(request);
    payload = authResult.payload;
    session = authResult.session;
    topic = authResult.topic;
    shop = authResult.shop;
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
      return json({
        success: true,
        message: "Order update skipped - services suspended",
        suspended: true,
        reason: suspensionStatus.reason,
      });
    }
  } catch (suspensionError) {
    logger.error(
      { error: suspensionError, shop },
      "Error checking suspension status",
    );
    throw suspensionError;
  }

  try {
    const orderId = payload.id?.toString();

    if (!orderId) {
      logger.error({ payload }, "No order ID found in payload");
      return json({ error: "No order ID found in payload" }, { status: 400 });
    }

    const kafkaProducer = await KafkaProducerService.getInstance();

    const streamData = {
      event_type: "order_updated",
      shop_domain: shop,
      shopify_id: orderId,
      timestamp: new Date().toISOString(),
    } as const;

    const messageId = await kafkaProducer.publishShopifyEvent(streamData);

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
