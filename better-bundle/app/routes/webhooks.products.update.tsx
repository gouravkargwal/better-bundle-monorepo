import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";
import { checkServiceSuspensionByDomain } from "../middleware/serviceSuspension";
import logger from "app/utils/logger";

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    const { payload, session } = await authenticate.webhook(request);

    if (!session) {
      logger.error("Authentication failed for products update webhook");
      return json({ error: "Authentication failed" }, { status: 401 });
    }

    // Check if shop services are suspended
    const suspensionStatus = await checkServiceSuspensionByDomain(session.shop);
    if (suspensionStatus.isSuspended) {
      return json({
        success: true,
        message: "Product update skipped - services suspended",
        suspended: true,
        reason: suspensionStatus.reason,
      });
    }

    // Extract product data from payload
    const product = payload as any;
    const productId = product.id?.toString();

    if (!productId) {
      logger.error({ payload }, "No product ID found in payload");
      return json({ error: "No product ID found" }, { status: 400 });
    }

    // Publish Kafka event with shop_domain - backend will resolve shop_id
    const producer = await KafkaProducerService.getInstance();
    const event = {
      event_type: "product_updated",
      shop_domain: session.shop,
      shopify_id: productId,
      timestamp: new Date().toISOString(),
    } as const;

    await producer.publishShopifyEvent(event);

    return json({
      success: true,
      productId,
      shopDomain: session.shop,
      message:
        "Product update webhook processed - will trigger specific data collection",
    });
  } catch (error) {
    logger.error(
      {
        error: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined,
      },
      "Error processing products update webhook",
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
