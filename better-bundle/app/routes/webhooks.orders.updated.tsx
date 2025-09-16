import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { getRedisStreamService } from "../services/redis-stream.service";

export const action = async ({ request }: ActionFunctionArgs) => {
  console.log("🚀 Webhook request received - orders/updated");
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
    console.log(`🔔 ${topic} webhook received for ${shop}`);
    console.log(`📦 Order ID: ${payload.id}`);
    console.log(`💰 Total: ${payload.total_price}`);
    console.log(`📧 Customer: ${payload.email || "Guest"}`);
    console.log(`📅 Created: ${payload.created_at}`);
    console.log(`🔄 Financial Status: ${payload.financial_status}`);
    console.log(`📋 Fulfillment Status: ${payload.fulfillment_status}`);
    console.log(`🏷️ Tags: ${payload.tags}`);
    console.log(`📝 Note: ${payload.note || "No note"}`);
    console.log(`🔗 Note Attributes:`, payload.note_attributes || []);

    // Extract order data from payload
    const order = payload;
    const orderId = order.id?.toString();

    if (!orderId) {
      console.error("❌ No order ID found in payload");
      return json({ error: "No order ID found" }, { status: 400 });
    }

    // Get shop ID from database
    // Use findFirst to avoid depending on DB unique constraint during local/dev
    const shopRecord = await prisma.shop.findFirst({
      where: { shopDomain: shop },
      select: { id: true },
    });

    if (!shopRecord) {
      console.error(`❌ Shop not found: ${shop}`);
      return json({ error: "Shop not found" }, { status: 404 });
    }

    // Upsert without composite unique (shopifyId is nullable in schema)
    const existing = await prisma.rawOrder.findFirst({
      where: { shopId: shopRecord.id, shopifyId: orderId },
      select: { id: true },
    });

    if (existing) {
      await prisma.rawOrder.update({
        where: { id: existing.id },
        data: {
          payload: order,
          shopifyUpdatedAt: order.updated_at
            ? new Date(order.updated_at)
            : new Date(),
        },
      });
    } else {
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
    }

    console.log(`✅ Order ${orderId} updated in raw table for shop ${shop}`);

    // Publish to Redis Stream for real-time processing (only for significant updates)
    try {
      const streamService = await getRedisStreamService();

      // Only publish if this is a significant status change
      const currentStatus = payload.financial_status;
      const shouldPublish =
        currentStatus === "paid" ||
        currentStatus === "partially_paid" ||
        currentStatus === "refunded";

      if (shouldPublish) {
        const streamData = {
          event_type: "order_updated",
          shop_id: shopRecord.id,
          shopify_id: orderId,
          timestamp: new Date().toISOString(),
          order_status: currentStatus,
        };

        const messageId = await streamService.publishShopifyEvent(streamData);

        console.log(`📡 Published to Redis Stream:`, {
          messageId,
          eventType: streamData.event_type,
          shopId: streamData.shop_id,
          shopifyId: streamData.shopify_id,
          orderStatus: streamData.order_status,
        });
      } else {
        console.log(
          `⏭️ Skipping Redis Stream publish for minor update: ${currentStatus}`,
        );
      }
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
