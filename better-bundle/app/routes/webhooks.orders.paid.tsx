import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { getRedisStreamService } from "../services/redis-stream.service";

export const action = async ({ request }: ActionFunctionArgs) => {
  console.log("🚀 Webhook request received - orders/paid");
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

    // ===== CUSTOMER LINKING INTEGRATION =====
    // Extract session ID from order note attributes for customer linking
    const sessionId = payload.note_attributes?.find(
      (attr) => attr.name === "session_id",
    )?.value;

    if (payload.customer && payload.customer.id && sessionId) {
      console.log(
        `🔗 Triggering customer linking for customer ${payload.customer.id} with session ${sessionId}`,
      );

      try {
        // Call your Python worker's customer linking API
        const response = await fetch(
          `${process.env.PYTHON_WORKER_URL}/api/customer-identity/identify-customer`,
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              session_id: sessionId,
              customer_id: payload.customer.id.toString(),
              shop_id: shop,
              trigger_event: "purchase",
              customer_data: {
                email: payload.customer.email,
                phone: payload.customer.phone,
                first_name: payload.customer.first_name,
                last_name: payload.customer.last_name,
                order_id: payload.id,
                order_total: payload.total_price,
                order_currency: payload.currency,
              },
            }),
          },
        );

        if (response.ok) {
          const result = await response.json();
          console.log(
            `✅ Customer linking successful: ${result.data?.total_sessions_linked || 0} sessions linked`,
          );
        } else {
          console.error(
            `❌ Customer linking failed: ${response.status} ${response.statusText}`,
          );
        }
      } catch (error) {
        console.error(`❌ Error calling customer linking API:`, error);
        // Don't fail the webhook if customer linking fails
      }
    } else {
      console.log(
        `ℹ️ Skipping customer linking - no customer ID or session ID found`,
      );
    }

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

    let rawRecordId: string | null = null;
    if (existing) {
      const updated = await prisma.rawOrder.update({
        where: { id: existing.id },
        data: {
          payload: order,
          shopifyUpdatedAt: order.updated_at
            ? new Date(order.updated_at)
            : new Date(),
          source: "webhook" as any,
          format: "rest" as any,
          receivedAt: new Date() as any,
        } as any,
      });
      rawRecordId = updated.id;
    } else {
      const created = await prisma.rawOrder.create({
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
          source: "webhook" as any,
          format: "rest" as any,
          receivedAt: new Date() as any,
        } as any,
      });
      rawRecordId = created.id;
    }

    console.log(
      `✅ Order ${orderId} payment confirmed in raw table for shop ${shop}`,
    );

    // Publish to Redis Stream for real-time processing (critical event - always publish)
    try {
      const streamService = await getRedisStreamService();

      const streamData = {
        event_type: "order_paid",
        shop_id: shopRecord.id,
        shopify_id: orderId,
        timestamp: new Date().toISOString(),
        order_status: "paid",
      };

      const messageId = await streamService.publishShopifyEvent(streamData);

      console.log(`📡 Published to Redis Stream:`, {
        messageId,
        eventType: streamData.event_type,
        shopId: streamData.shop_id,
        shopifyId: streamData.shopify_id,
        orderStatus: streamData.order_status,
      });

      // Also publish a normalize job for canonical staging
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
      orderId: orderId,
      shopId: shopRecord.id,
      message: "Order payment data stored successfully",
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
