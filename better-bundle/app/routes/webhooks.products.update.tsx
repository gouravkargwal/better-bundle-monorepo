import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { getRedisStreamService } from "../services/redis-stream.service";

// Simple in-memory deduplication
const recentWebhooks = new Map<string, number>();

export const action = async ({ request }: ActionFunctionArgs) => {
  console.log("🚀 Webhook request received - products/update");
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
    console.log(`📊 Product update webhook payload structure:`, {
      hasId: !!payload.id,
      idType: typeof payload.id,
      idValue: payload.id,
      hasTitle: !!payload.title,
      titleValue: payload.title,
      hasHandle: !!payload.handle,
      handleValue: payload.handle,
      hasCreatedAt: !!payload.created_at,
      createdAtValue: payload.created_at,
      hasUpdatedAt: !!payload.updated_at,
      updatedAtValue: payload.updated_at,
      hasVariants: !!payload.variants,
      variantsCount: payload.variants?.length || 0,
      hasImages: !!payload.images,
      imagesCount: payload.images?.length || 0,
      hasTags: !!payload.tags,
      tagsValue: payload.tags,
      payloadKeys: Object.keys(payload),
    });

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

    console.log(`💾 Storing raw product update data:`, {
      shopId: rawProductData.shopId,
      shopifyId: rawProductData.shopifyId,
      shopifyCreatedAt: rawProductData.shopifyCreatedAt,
      shopifyUpdatedAt: rawProductData.shopifyUpdatedAt,
      payloadSize: JSON.stringify(product).length,
      payloadSample: {
        id: product.id,
        title: product.title,
        handle: product.handle,
        product_type: product.product_type,
        vendor: product.vendor,
        tags: product.tags,
        status: product.status,
        created_at: product.created_at,
        updated_at: product.updated_at,
      },
    });

    await prisma.rawProduct.create({
      data: rawProductData,
    });

    console.log(
      `✅ Product ${productId} updated in raw table for shop ${shop}`,
    );

    // Publish to Redis Stream for real-time processing
    try {
      // Create deduplication key
      const dedupKey = `${shopRecord.id}_${productId}_product_updated`;
      const now = Date.now();

      console.log(`🔍 Webhook deduplication check for key: ${dedupKey}`);
      console.log(`📊 Current recentWebhooks size: ${recentWebhooks.size}`);

      // Check if we've processed this webhook recently (within 2 seconds)
      const lastProcessed = recentWebhooks.get(dedupKey);
      if (lastProcessed && now - lastProcessed < 2000) {
        console.log(
          `🔄 Skipping duplicate webhook: ${dedupKey} (processed ${now - lastProcessed}ms ago)`,
        );
        return json({
          success: true,
          productId: productId,
          shopId: shopRecord.id,
          message: "Product data updated successfully (duplicate skipped)",
        });
      }

      console.log(`✅ New webhook, proceeding with processing: ${dedupKey}`);

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

      const messageId = await streamService.publishShopifyEvent(streamData);

      console.log(`📡 Published to Redis Stream:`, {
        messageId,
        eventType: streamData.event_type,
        shopId: streamData.shop_id,
        shopifyId: streamData.shopify_id,
      });
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
