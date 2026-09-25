import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";
import { checkServiceSuspensionByDomain } from "../middleware/serviceSuspension";
import logger from "../utils/logger";

export const action = async ({ request }: ActionFunctionArgs) => {
  let payload, session, shop;

  try {
    const authResult = await authenticate.webhook(request);
    payload = authResult.payload;
    session = authResult.session;
    shop = authResult.shop;
  } catch (authError) {
    return json({ error: "Authentication failed" }, { status: 401 });
  }

  if (!session || !shop) {
    return json({ error: "Authentication failed" }, { status: 401 });
  }

  // Check if shop services are suspended
  try {
    const suspensionStatus = await checkServiceSuspensionByDomain(shop);
    if (suspensionStatus.isSuspended) {
      return json({
        success: true,
        message: "Refund processing skipped - services suspended",
        suspended: true,
        reason: suspensionStatus.reason,
      });
    }
  } catch (suspensionError) {
    logger.warn(
      { error: suspensionError, shop },
      "Error checking suspension status, proceeding with refund processing",
    );
  }

  try {
    // Extract refund data from payload
    const refund = payload;
    const refundId = refund.id?.toString();
    const orderId = refund.order_id?.toString();

    if (!refundId || !orderId) {
      logger.error(
        { payload: refund },
        "No refund ID or order ID found in payload",
      );
      return json({ error: "No refund ID or order ID found" }, { status: 400 });
    }

    const kafkaProducer = await KafkaProducerService.getInstance();

    // Publishes the ORDER id, not the refund: the consumer re-fetches the whole
    // order from the Admin API, which carries the refunds with their line items.
    // More reliable than trusting this payload, and it is the same path a
    // backfill takes.
    //
    // Refunds feed the recommendation engine — a returned item is not evidence
    // that products belong together, so co-purchase mining subtracts it. They
    // deliberately do NOT adjust billing; commission is charged on the sale.
    const streamData = {
      event_type: "refund_created",
      shop_domain: shop,
      shopify_id: orderId,
      metadata: {
        trigger: "refund_created",
        refund_id: refundId,
        purpose: "recommendation_signal",
      },
      timestamp: new Date().toISOString(),
    } as const;

    await kafkaProducer.publishShopifyEvent(streamData);

    return json({
      success: true,
      refundId: refundId,
      orderId: orderId,
      shopDomain: shop,
      message:
        "Refund event published to Kafka - will trigger order data update only (no refund attribution processing)",
    });
  } catch (error) {
    logger.error({ error, shop }, "Error processing refund webhook");
    return json({ error: "Internal server error" }, { status: 500 });
  }
};
