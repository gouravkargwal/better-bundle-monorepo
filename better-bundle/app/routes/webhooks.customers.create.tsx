import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";
import { checkServiceSuspensionByDomain } from "../middleware/serviceSuspension";
import logger from "app/utils/logger";

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    const { payload, session, shop } = await authenticate.webhook(request);

    if (!session || !shop) {
      logger.error("Authentication failed for customers create webhook");
      return json({ error: "Authentication failed" }, { status: 401 });
    }

    // Check if shop services are suspended
    const suspensionStatus = await checkServiceSuspensionByDomain(shop);
    if (suspensionStatus.isSuspended) {
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

    const kafkaProducer = await KafkaProducerService.getInstance();

    const streamData = {
      event_type: "customer_created",
      shop_domain: shop,
      shopify_id: customerId,
      timestamp: new Date().toISOString(),
    };

    await kafkaProducer.publishShopifyEvent(streamData);

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
