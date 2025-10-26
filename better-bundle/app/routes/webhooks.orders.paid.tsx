import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";
import { checkServiceSuspensionByDomain } from "../middleware/serviceSuspension";
import logger from "app/utils/logger";

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
    logger.error("Missing session or shop data");
    return json({ error: "Authentication failed" }, { status: 401 });
  }

  // Check if shop services are suspended
  try {
    const suspensionStatus = await checkServiceSuspensionByDomain(shop);
    if (suspensionStatus.isSuspended) {
      return json({
        success: true,
        message: "Order paid processing skipped - services suspended",
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
    // Extract order data from payload
    const order = payload;
    const orderId = order.id?.toString();

    if (!orderId) {
      logger.error({ payload }, "No order ID found in payload");
      return json({ error: "No order ID found" }, { status: 400 });
    }

    const kafkaProducer = await KafkaProducerService.getInstance();

    const streamData = {
      event_type: "order_paid",
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
