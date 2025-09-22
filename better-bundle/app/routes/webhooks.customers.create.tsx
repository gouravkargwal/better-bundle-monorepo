import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";

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

    // Store raw customer data immediately
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
      `✅ Customer ${customerId} stored in raw table for shop ${shop}`,
    );

    // ===== CUSTOMER LINKING INTEGRATION =====
    console.log(
      `🔗 Triggering customer linking for new customer ${customerId}`,
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
            session_id: null, // No specific session for account creation
            customer_id: customerId,
            shop_id: shop,
            trigger_event: "account_creation",
            customer_data: {
              email: customer.email,
              phone: customer.phone,
              first_name: customer.first_name,
              last_name: customer.last_name,
              created_at: customer.created_at,
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

    // Publish to Kafka for real-time processing
    try {
      const kafkaProducer = await KafkaProducerService.getInstance();

      const streamData = {
        event_type: "customer_created",
        shop_id: shopRecord.id,
        shopify_id: customerId,
        timestamp: new Date().toISOString(),
      };

      const messageId = await kafkaProducer.publishShopifyEvent(streamData);

      console.log(`📡 Published to Kafka:`, {
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
      await kafkaProducer.publishShopifyEvent(normalizeJob);
    } catch (kafkaError) {
      console.error(`❌ Error publishing to Kafka:`, kafkaError);
      // Don't fail the webhook if Kafka publishing fails
    }

    return json({
      success: true,
      customerId: customerId,
      shopId: shopRecord.id,
      message: "Customer data stored successfully",
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
