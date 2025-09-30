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

    // Publish Kafka event - backend will resolve shop_id
    const producer = await KafkaProducerService.getInstance();
    const event = {
      event_type: "collection_updated",
      shop_domain: session.shop,
      shopify_id: collectionId,
      timestamp: new Date().toISOString(),
    } as const;

    await producer.publishShopifyEvent(event);

    return json({
      success: true,
      collectionId,
      shopDomain: session.shop,
      message:
        "Collection update webhook processed - will trigger specific data collection",
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
