import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";
import logger from "app/utils/logger";

export const action = async ({ request }: ActionFunctionArgs) => {
  const startTime = Date.now();

  try {
    logger.info("Products update webhook received");
    const { payload, session } = await authenticate.webhook(request);

    if (!session) {
      logger.error("Authentication failed for products update webhook");
      return json({ error: "Authentication failed" }, { status: 401 });
    }

    logger.info(
      { shop: session.shop },
      "Products update webhook authentication successful",
    );

    // Extract product data from payload
    const product = payload as any;
    const productId = product.id?.toString();

    if (!productId) {
      logger.error({ payload }, "No product ID found in payload");
      return json({ error: "No product ID found" }, { status: 400 });
    }

    logger.info({ productId }, "Product ID found in payload");

    // Publish Kafka event with shop_domain - backend will resolve shop_id
    const producer = await KafkaProducerService.getInstance();
    const event = {
      event_type: "product_updated",
      shop_domain: session.shop,
      shopify_id: productId,
      timestamp: new Date().toISOString(),
    } as const;

    logger.info({ event }, "Publishing Kafka event");

    await producer.publishShopifyEvent(event);

    logger.info(
      { productId, shopDomain: session.shop },
      "Kafka event published successfully",
    );

    const duration = Date.now() - startTime;
    logger.info(
      { productId, shopDomain: session.shop, duration },
      "Product update webhook processed successfully",
    );

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
