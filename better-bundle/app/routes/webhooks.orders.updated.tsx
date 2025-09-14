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

    // Extract order data from payload
    const order = payload;
    const orderId = order.id?.toString();

    if (!orderId) {
      console.error("❌ No order ID found in payload");
      return json({ error: "No order ID found" }, { status: 400 });
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

    // Store raw order update data immediately
    await prisma.rawOrder.create({
      data: {
        shopId: shopRecord.id,
        payload: order,
        shopifyId: orderId,
        shopifyCreatedAt: order.created_at
          ? new Date(order.created_at)
          : new Date(),
        shopifyUpdatedAt: order.updated_at
          ? new Date(order.updated_at)
          : new Date(),
      },
    });

    console.log(`✅ Order ${orderId} updated in raw table for shop ${shop}`);

    // Publish to Redis Stream for real-time processing
    try {
      const streamService = await getRedisStreamService();

      const streamData = {
        event_type: "order_updated",
        shop_id: shopRecord.id,
        shopify_id: orderId,
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
      orderId: orderId,
      shopId: shopRecord.id,
      message: "Order data updated successfully",
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
