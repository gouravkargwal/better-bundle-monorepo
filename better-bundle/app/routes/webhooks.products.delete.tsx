import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { getRedisStreamService } from "../services/redis-stream.service";

export const action = async ({ request }: ActionFunctionArgs) => {
  let payload, session, topic, shop;

  try {
    const authResult = await authenticate.webhook(request);
    payload = authResult.payload;
    session = authResult.session;
    topic = authResult.topic;
    shop = authResult.shop;
  } catch (authError) {
    return json({ error: "Authentication failed" }, { status: 401 });
  }

  if (!session || !shop) {
    return json({ error: "Authentication failed" }, { status: 401 });
  }

  try {
    // Extract product data from payload
    const product = payload;
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

    // Store raw product data for deletion event
    await prisma.rawProduct.create({
      data: {
        shopId: shopRecord.id,
        payload: product,
        shopifyId: productId,
        shopifyCreatedAt: product.created_at
          ? new Date(product.created_at)
          : new Date(),
        shopifyUpdatedAt: new Date(), // Use current time for deletion
      },
    });

    // Publish deletion event to Redis stream
    try {
      const eventData = {
        event_type: "product_deleted",
        shop_id: shopRecord.id,
        shopify_id: productId,
        timestamp: new Date().toISOString(),
        payload: product,
      };

      const redisStreamService = await getRedisStreamService();
      await redisStreamService.publishShopifyEvent(eventData);
    } catch (redisError) {
      console.error(
        "❌ Failed to publish deletion event to Redis:",
        redisError,
      );
      // Don't fail the webhook if Redis publishing fails
    }

    return json({
      success: true,
      productId: productId,
      shopId: shopRecord.id,
      message: "Product deletion event stored successfully",
    });
  } catch (error) {
    console.error(`❌ Error processing ${topic} webhook:`, error);
    return json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 },
    );
  }
};
