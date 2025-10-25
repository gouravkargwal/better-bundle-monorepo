import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";
import { checkServiceSuspensionByDomain } from "../middleware/serviceSuspension";
import logger from "app/utils/logger";

export const action = async ({ request }: ActionFunctionArgs) => {
  const startTime = Date.now();

  try {
    logger.info("Products create webhook received");
    const { payload, session } = await authenticate.webhook(request);

    if (!session) {
      logger.error("Authentication failed for products create webhook");
      return json({ error: "Authentication failed" }, { status: 401 });
    }

    logger.info(
      { shop: session.shop },
      "Products create webhook authentication successful",
    );

    // Check if shop services are suspended
    const suspensionStatus = await checkServiceSuspensionByDomain(session.shop);
    if (suspensionStatus.isSuspended) {
      logger.info(
        { shop: session.shop, reason: suspensionStatus.reason },
        "Skipping product create - shop services suspended",
      );
      return json({
        success: true,
        message: "Product create skipped - services suspended",
        suspended: true,
        reason: suspensionStatus.reason,
      });
    }

    // Extract product data from payload
    const product = payload;
    const productId = product.id?.toString();

    if (!productId) {
      logger.error({ payload }, "No product ID found in payload");
      return json({ error: "No product ID found" }, { status: 400 });
    }

    logger.info({ productId }, "Product ID found in payload");

    const kafkaProducer = await KafkaProducerService.getInstance();

    const streamData = {
      event_type: "product_created",
      shop_domain: session.shop,
      shopify_id: productId,
      timestamp: new Date().toISOString(),
    };

    logger.info({ event: streamData }, "Publishing Kafka event");

    await kafkaProducer.publishShopifyEvent(streamData);

    logger.info(
      { productId, shopDomain: session.shop },
      "Kafka event published successfully",
    );

    const duration = Date.now() - startTime;
    logger.info(
      { productId, shopDomain: session.shop, duration },
      "Product create webhook processed successfully",
    );

    return json({
      success: true,
      productId: productId,
      shopDomain: session.shop,
      message:
        "Product create webhook processed - will trigger specific data collection",
    });
  } catch (error) {
    logger.error(
      {
        error: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined,
      },
      "Error processing products create webhook",
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
