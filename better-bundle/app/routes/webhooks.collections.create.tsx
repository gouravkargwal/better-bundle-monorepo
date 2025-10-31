import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";
import { checkServiceSuspensionByDomain } from "../middleware/serviceSuspension";

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    const { payload, session } = await authenticate.webhook(request);

    if (!session) {
      return json({ error: "Authentication failed" }, { status: 401 });
    }

    // Check if shop services are suspended
    const suspensionStatus = await checkServiceSuspensionByDomain(session.shop);
    if (suspensionStatus.isSuspended) {
      return json({
        success: true,
        message: "Collection create skipped - services suspended",
        suspended: true,
        reason: suspensionStatus.reason,
      });
    }

    // Extract collection data from payload
    const collection = payload;
    const collectionId = collection.id?.toString();

    if (!collectionId) {
      console.error("❌ No collection ID found in payload");
      return json({ error: "No collection ID found" }, { status: 400 });
    }

    const kafkaProducer = await KafkaProducerService.getInstance();

    const streamData = {
      event_type: "collection_created",
      shop_domain: session.shop,
      shopify_id: collectionId,
      timestamp: new Date().toISOString(),
    };

    await kafkaProducer.publishShopifyEvent(streamData);

    return json({
      success: true,
      collectionId: collectionId,
      shopDomain: session.shop,
      message:
        "Collection create webhook processed - will trigger specific data collection",
    });
  } catch (error) {
    console.error(`❌ Error processing collections create webhook:`, error);
    return json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 },
    );
  }
};
