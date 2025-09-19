import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { getRedisStreamService } from "../services/redis-stream.service";

// Simple in-memory deduplication
const recentWebhooks = new Map<string, number>();

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

    // Store raw product update data immediately
    const rawProductData = {
      shopId: shopRecord.id,
      payload: product,
      shopifyId: productId,
      shopifyCreatedAt: product.created_at
        ? new Date(product.created_at)
        : new Date(),
      shopifyUpdatedAt: product.updated_at
        ? new Date(product.updated_at)
        : new Date(),
    };

    const created = await prisma.rawProduct.create({
      data: {
        ...rawProductData,
        source: "webhook",
        format: "rest",
        receivedAt: new Date(),
      } as any,
    });

    // Publish to Redis Stream for real-time processing
    try {
      // Create deduplication key
      const dedupKey = `${shopRecord.id}_${productId}_product_updated`;
      const now = Date.now();

      // Check if we've processed this webhook recently (within 2 seconds)
      const lastProcessed = recentWebhooks.get(dedupKey);
      if (lastProcessed && now - lastProcessed < 2000) {
        return json({
          success: true,
          productId: productId,
          shopId: shopRecord.id,
          message: "Product data updated successfully (duplicate skipped)",
        });
      }

      // Record this webhook
      recentWebhooks.set(dedupKey, now);

      // Clean up old entries (older than 10 seconds)
      for (const [key, timestamp] of recentWebhooks.entries()) {
        if (now - timestamp > 10000) {
          recentWebhooks.delete(key);
        }
      }

      const streamService = await getRedisStreamService();

      const streamData = {
        event_type: "product_updated",
        shop_id: shopRecord.id,
        shopify_id: productId,
        timestamp: new Date().toISOString(),
      };

      await streamService.publishShopifyEvent(streamData);

      // Also publish a normalize job for canonical staging
      const normalizeJob = {
        event_type: "normalize_entity",
        data_type: "products",
        format: "rest",
        shop_id: shopRecord.id,
        raw_id: created.id,
        shopify_id: productId,
        timestamp: new Date().toISOString(),
      } as const;
      await streamService.publishShopifyEvent(normalizeJob);
    } catch (streamError) {
      console.error(`❌ Error publishing to Redis Stream:`, streamError);
      // Don't fail the webhook if stream publishing fails
    }

    return json({
      success: true,
      productId: productId,
      shopId: shopRecord.id,
      message: "Product data updated successfully",
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
