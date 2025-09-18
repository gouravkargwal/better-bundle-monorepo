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

    // Extract customer data from payload
    const customer = payload;
    const customerId = customer.id?.toString();

    if (!customerId) {
      console.error("❌ No customer ID found in payload");
      return json({ error: "No customer ID found" }, { status: 400 });
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

    // Store raw customer update data immediately
    const created = await prisma.rawCustomer.create({
      data: {
        shopId: shopRecord.id,
        payload: customer,
        shopifyId: customerId,
        shopifyCreatedAt: customer.created_at
          ? new Date(customer.created_at)
          : new Date(),
        shopifyUpdatedAt: customer.updated_at
          ? new Date(customer.updated_at)
          : new Date(),
        source: "webhook",
        format: "rest",
        receivedAt: new Date(),
      } as any,
    });

    console.log(
      `✅ Customer ${customerId} updated in raw table for shop ${shop}`,
    );

    // Publish to Redis Stream for real-time processing
    try {
      const streamService = await getRedisStreamService();

      const streamData = {
        event_type: "customer_updated",
        shop_id: shopRecord.id,
        shopify_id: customerId,
        timestamp: new Date().toISOString(),
      };

      const messageId = await streamService.publishShopifyEvent(streamData);

      console.log(`📡 Published to Redis Stream:`, {
        messageId,
        eventType: streamData.event_type,
        shopId: streamData.shop_id,
        shopifyId: streamData.shopify_id,
      });

      // Also publish a normalize job for canonical staging
      const normalizeJob = {
        event_type: "normalize_entity",
        data_type: "customers",
        format: "rest",
        shop_id: shopRecord.id,
        raw_id: created.id,
        shopify_id: customerId,
        timestamp: new Date().toISOString(),
      } as const;
      await streamService.publishShopifyEvent(normalizeJob);
    } catch (streamError) {
      console.error(`❌ Error publishing to Redis Stream:`, streamError);
      // Don't fail the webhook if stream publishing fails
    }

    return json({
      success: true,
      customerId: customerId,
      shopId: shopRecord.id,
      message: "Customer data updated successfully",
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
