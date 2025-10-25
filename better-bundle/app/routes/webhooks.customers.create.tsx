import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";
import { checkServiceSuspensionByDomain } from "../middleware/serviceSuspension";
import logger from "app/utils/logger";

export const action = async ({ request }: ActionFunctionArgs) => {
  const startTime = Date.now();

  try {
    logger.info("Customers create webhook received");
    const { payload, session, shop } = await authenticate.webhook(request);

    if (!session || !shop) {
      logger.error("Authentication failed for customers create webhook");
      return json({ error: "Authentication failed" }, { status: 401 });
    }

    logger.info({ shop }, "Customers create webhook authentication successful");

    // Check if shop services are suspended
    const suspensionStatus = await checkServiceSuspensionByDomain(shop);
    if (suspensionStatus.isSuspended) {
      logger.info(
        { shop, reason: suspensionStatus.reason },
        "Skipping customer create - shop services suspended",
      );
      return json({
        success: true,
        message: "Customer create skipped - services suspended",
        suspended: true,
        reason: suspensionStatus.reason,
      });
    }

    // Extract customer data from payload
    const customer = payload;
    const customerId = customer.id?.toString();

    if (!customerId) {
      logger.error({ payload }, "No customer ID found in payload");
      return json({ error: "No customer ID found" }, { status: 400 });
    }

    logger.info({ customerId }, "Customer ID found in payload");

    const kafkaProducer = await KafkaProducerService.getInstance();

    const streamData = {
      event_type: "customer_created",
      shop_domain: shop,
      shopify_id: customerId,
      timestamp: new Date().toISOString(),
    };

    logger.info({ event: streamData }, "Publishing Kafka event");

    await kafkaProducer.publishShopifyEvent(streamData);

    logger.info(
      { customerId, shopDomain: shop },
      "Kafka event published successfully",
    );

    const duration = Date.now() - startTime;
    logger.info(
      { customerId, shopDomain: shop, duration },
      "Customer create webhook processed successfully",
    );

    return json({
      success: true,
      customerId: customerId,
      shopDomain: shop,
      message:
        "Customer create webhook processed - will trigger specific data collection",
    });
  } catch (error) {
    logger.error(
      {
        error: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined,
      },
      "Error processing customers create webhook",
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
