import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { getRedisStreamService } from "../services/redis-stream.service";

export const action = async ({ request }: ActionFunctionArgs) => {
  console.log("🚀 Webhook request received - refunds/create");
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
    console.log(`📦 Refund ID: ${payload.id}`);
    console.log(`📦 Order ID: ${payload.order_id}`);
    console.log(
      `💰 Refund Amount: ${payload.transactions?.reduce((sum: number, t: any) => sum + parseFloat(t.amount || 0), 0) || 0}`,
    );
    console.log(`📅 Created: ${payload.created_at}`);
    console.log(`📝 Note: ${payload.note || "No note"}`);
    console.log(`🔄 Restock: ${payload.restock}`);
    console.log(
      `📋 Refund Line Items: ${payload.refund_line_items?.length || 0} items`,
    );

    // Extract refund data from payload
    const refund = payload;
    const refundId = refund.id?.toString();
    const orderId = refund.order_id?.toString();

    if (!refundId || !orderId) {
      console.error("❌ No refund ID or order ID found in payload");
      return json({ error: "No refund ID or order ID found" }, { status: 400 });
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

    // Store refund data in RawOrder table (only if order exists)
    const existing = await prisma.rawOrder.findFirst({
      where: { shopId: shopRecord.id, shopifyId: orderId },
      select: { id: true, payload: true },
    });

    let rawRecordId: string | null = null;
    if (existing) {
      // Update existing order with refund information
      const existingPayload = existing.payload as any;
      const updatedPayload = {
        ...existingPayload,
        refunds: [...(existingPayload.refunds || []), refund],
      };

      const updated = await prisma.rawOrder.update({
        where: { id: existing.id },
        data: {
          payload: updatedPayload,
          shopifyUpdatedAt: refund.created_at
            ? new Date(refund.created_at)
            : new Date(),
          // cast because prisma types may not include new fields until client is regenerated
          source: "webhook" as any,
          format: "rest" as any,
          receivedAt: new Date() as any,
        } as any,
      });
      rawRecordId = updated.id;
    } else {
      // Order doesn't exist yet - refund webhook called before order webhook
      // This is normal in Shopify's webhook order, create minimal record with refund data
      console.log(
        `⚠️ Order ${orderId} not found in RawOrder table. Creating minimal record with refund data.`,
      );

      // Create minimal RawOrder record with refund data to prevent data loss
      const created = await prisma.rawOrder.create({
        data: {
          shopId: shopRecord.id,
          payload: {
            refunds: [refund],
            // Add minimal order data to prevent consumer errors
            id: orderId,
            created_at: refund.created_at || new Date().toISOString(),
            line_items: [], // Empty array to prevent consumer errors
            total_price: "0.00",
            currency: "USD",
          },
          shopifyId: orderId,
          shopifyCreatedAt: refund.created_at
            ? new Date(refund.created_at)
            : new Date(),
          shopifyUpdatedAt: refund.created_at
            ? new Date(refund.created_at)
            : new Date(),
          source: "webhook" as any,
          format: "rest" as any,
          receivedAt: new Date() as any,
        } as any,
      });
      rawRecordId = created.id;

      console.log(
        `✅ Created minimal RawOrder record for order ${orderId} with refund data`,
      );
    }

    console.log(
      `✅ Refund ${refundId} for order ${orderId} stored in raw table for shop ${shop}`,
    );

    // Publish to Redis Stream for real-time processing
    try {
      const streamService = await getRedisStreamService();

      const refundMessage = {
        event_type: "refund_created",
        shop_id: shopRecord.id,
        shopify_id: orderId,
        raw_record_id: rawRecordId, // Send the RawOrder record ID
        timestamp: new Date().toISOString(),
      };

      // Publish directly to refund normalization stream
      await streamService.publishToStream(
        "betterbundle:refund-normalization-jobs",
        refundMessage,
      );

      // Also publish a normalize job for canonical staging of orders (refund update)
      if (rawRecordId) {
        const normalizeJob = {
          event_type: "normalize_entity",
          data_type: "orders",
          format: "rest",
          shop_id: shopRecord.id,
          raw_id: rawRecordId,
          shopify_id: orderId,
          timestamp: new Date().toISOString(),
        } as const;
        await streamService.publishShopifyEvent(normalizeJob);
      }
    } catch (streamError) {
      console.error(`❌ Error publishing to Redis Stream:`, streamError);
      // Don't fail the webhook if stream publishing fails
    }

    return json({
      success: true,
      refundId: refundId,
      orderId: orderId,
      shopId: shopRecord.id,
      message: "Refund data stored successfully",
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
