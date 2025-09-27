import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    const { payload, session } = await authenticate.webhook(request);

    if (!session) {
      return json({ error: "Authentication failed" }, { status: 401 });
    }

    // Extract collection data from payload
    const collection = payload;
    const collectionId = collection.id?.toString();
    console.log(collection, "collection ------------------->");

    if (!collectionId) {
      console.error("❌ No collection ID found in payload");
      return json({ error: "No collection ID found" }, { status: 400 });
    }

    // Publish Kafka event with raw payload - let backend handle shop_id lookup
    const producer = await KafkaProducerService.getInstance();
    const event = {
      event_type: "collection_updated",
      shop_domain: session.shop, // Use session.shop to get the shop domain
      shopify_id: collectionId,
      timestamp: new Date().toISOString(),
      raw_payload: collection,
    } as const;

    await producer.publishShopifyEvent(event);

    return json({
      success: true,
      collectionId,
      shopDomain: session.shop,
      message: "Shopify event published",
    });
  } catch (error) {
    console.error(`❌ Error processing collections update webhook:`, error);
    return json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 },
    );
  }
};
