import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { getRedisStreamService } from "../services/redis-stream.service";

export const action = async ({ request }: ActionFunctionArgs) => {
  console.log("🚀 Webhook request received - products/delete");
  console.log("📋 Request method:", request.method);
  console.log("📋 Request URL:", request.url);
  console.log(
    "📋 Request headers:",
    Object.fromEntries(request.headers.entries()),
  );

  let payload, session, topic, shop;

  try {
    const authResult = await authenticate.webhook(request);
    payload = authResult.payload;
    session = authResult.session;
    topic = authResult.topic;
    shop = authResult.shop;
    console.log("✅ Authentication successful");
    console.log("📋 Topic:", topic);
    console.log("📋 Shop:", shop);
  } catch (authError) {
    console.log("❌ Authentication failed:", authError);
    return json({ error: "Authentication failed" }, { status: 401 });
  }

  if (!session || !shop) {
    console.log(`❌ Session or shop missing for ${topic} webhook`);
    return json({ error: "Authentication failed" }, { status: 401 });
  }

  try {
    console.log(`🔔 ${topic} webhook received for ${shop}:`, payload);

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

    console.log(
      `✅ Product ${productId} deletion event stored in raw table for shop ${shop}`,
    );

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
      console.log(`📤 Product deletion event published to Redis stream`);
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
