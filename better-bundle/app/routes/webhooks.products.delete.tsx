import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";
import { checkServiceSuspensionByDomain } from "../middleware/serviceSuspension";

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    const { payload, session, shop } = await authenticate.webhook(request);

    if (!session || !shop) {
      return json({ error: "Authentication failed" }, { status: 401 });
    }

    // Check if shop services are suspended
    const suspensionStatus = await checkServiceSuspensionByDomain(shop);
    if (suspensionStatus.isSuspended) {
      console.log(
        `⏸️ Skipping product delete for ${shop} - services suspended (${suspensionStatus.reason})`,
      );
      return json({
        success: true,
        message: "Product delete skipped - services suspended",
        suspended: true,
        reason: suspensionStatus.reason,
      });
    }

    // Extract product data from payload
    const product = payload;
    const productId = product.id?.toString();

    if (!productId) {
      console.error("❌ No product ID found in payload");
      return json({ error: "No product ID found" }, { status: 400 });
    }

    const kafkaProducer = await KafkaProducerService.getInstance();

    const streamData = {
      event_type: "product_deleted",
      shop_domain: shop,
      shopify_id: productId,
      timestamp: new Date().toISOString(),
    };

    await kafkaProducer.publishShopifyEvent(streamData);

    return json({
      success: true,
      productId: productId,
      shopDomain: shop,
      message:
        "Product delete webhook processed - will trigger specific data collection",
    });
  } catch (error) {
    console.error(`❌ Error processing products delete webhook:`, error);
    return json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 },
    );
  }
};
