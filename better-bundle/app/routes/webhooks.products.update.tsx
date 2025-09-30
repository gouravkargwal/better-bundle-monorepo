import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    const { payload, session } = await authenticate.webhook(request);

    if (!session) {
      return json({ error: "Authentication failed" }, { status: 401 });
    }

    // Extract product data from payload
    const product = payload as any;
    const productId = product.id?.toString();

    if (!productId) {
      console.error("❌ No product ID found in payload");
      return json({ error: "No product ID found" }, { status: 400 });
    }

    console.log(product, "product ------------------->");

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
    console.error(`❌ Error processing products update webhook:`, error);
    return json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 },
    );
  }
};
