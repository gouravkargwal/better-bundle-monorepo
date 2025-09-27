import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    const { payload, session, shop } = await authenticate.webhook(request);

    if (!session || !shop) {
      return json({ error: "Authentication failed" }, { status: 401 });
    }

    // Extract collection data from payload
    const collection = payload;
    const collectionId = collection.id?.toString();

    if (!collectionId) {
      console.error("❌ No collection ID found in payload");
      return json({ error: "No collection ID found" }, { status: 400 });
    }

    const kafkaProducer = await KafkaProducerService.getInstance();

    const eventData = {
      event_type: "collection_deleted",
      shop_domain: shop,
      shopify_id: collectionId,
      timestamp: new Date().toISOString(),
    };

    await kafkaProducer.publishShopifyEvent(eventData);

    return json({
      success: true,
      collectionId: collectionId,
      shopDomain: shop,
      message:
        "Collection delete webhook processed - will trigger specific data collection",
    });
  } catch (error) {
    console.error(`❌ Error processing collections delete webhook:`, error);
    return json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 },
    );
  }
};
