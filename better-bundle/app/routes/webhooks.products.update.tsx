import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    const { payload, session, shop } = await authenticate.webhook(request);

    if (!session || !shop) {
      return json({ error: "Authentication failed" }, { status: 401 });
    }

    // Extract product data from payload
    const product = payload as any;
    const productId = product.id?.toString();

    if (!productId) {
      console.error("❌ No product ID found in payload");
      return json({ error: "No product ID found" }, { status: 400 });
    }

    // Get shop ID from database
    const shopRecord = await prisma.shop.findUnique({
      where: { shopDomain: shop },
      select: { id: true },
    });

    if (!shopRecord) {
      console.error(`❌ Shop not found: ${shop}`);
      return json({ error: "Shop not found" }, { status: 404 });
    }

    // Publish Kafka event with raw payload
    const producer = await KafkaProducerService.getInstance();
    const event = {
      event_type: "product_updated",
      shop_id: shopRecord.id,
      shopify_id: productId,
      timestamp: new Date().toISOString(),
      raw_payload: product,
    } as const;
    await producer.publishShopifyEvent(event);

    return json({
      success: true,
      productId,
      shopId: shopRecord.id,
      message: "Shopify event published",
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
