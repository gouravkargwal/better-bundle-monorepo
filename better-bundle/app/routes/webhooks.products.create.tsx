import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { getRedisStreamService } from "../services/redis-stream.service";

export const action = async ({ request }: ActionFunctionArgs) => {
  const { payload, session, topic, shop } = await authenticate.webhook(request);

  if (!session || !shop) {
    return json({ error: "Authentication failed" }, { status: 401 });
  }

  try {
    console.log(`🔔 ${topic} webhook received for ${shop}:`, payload);
    console.log(`📊 Product webhook payload structure:`, {
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

    // Store raw product data immediately
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

    console.log(`💾 Storing raw product data:`, {
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

    console.log(`✅ Product ${productId} stored in raw table for shop ${shop}`);

    // Publish to Redis Stream for real-time processing
    try {
      const streamService = await getRedisStreamService();

      const streamData = {
        event_type: "product_created",
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
      message: "Product data stored successfully",
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
