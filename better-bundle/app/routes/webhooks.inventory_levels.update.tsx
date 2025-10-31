import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { KafkaProducerService } from "../services/kafka/kafka-producer.service";
import { checkServiceSuspensionByDomain } from "../middleware/serviceSuspension";

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    const { payload, session, shop } = await authenticate.webhook(request);

    if (!session || !shop) {
      return json({ error: "Authentication failed" }, { status: 401 });
    }

    // Check if shop services are suspended
    const suspensionStatus = await checkServiceSuspensionByDomain(shop);
    if (suspensionStatus.isSuspended) {
      return json({
        success: true,
        message: "Inventory update skipped - services suspended",
        suspended: true,
        reason: suspensionStatus.reason,
      });
    }

    // Extract inventory level data from payload
    const inventoryLevel = payload as any;
    const inventoryItemId = inventoryLevel.inventory_item_id?.toString();
    const locationId = inventoryLevel.location_id?.toString();
    const available = inventoryLevel.available;

    if (!inventoryItemId) {
      console.error("❌ No inventory_item_id found in payload");
      return json({ error: "No inventory_item_id found" }, { status: 400 });
    }

    // Publish Kafka event with shop_domain - backend will resolve shop_id
    const producer = await KafkaProducerService.getInstance();
    const event = {
      event_type: "inventory_updated",
      shop_domain: shop,
      shopify_id: inventoryItemId,
      inventory_data: {
        inventory_item_id: inventoryItemId,
        location_id: locationId,
        available: available,
        updated_at: inventoryLevel.updated_at,
      },
      timestamp: new Date().toISOString(),
    } as const;

    await producer.publishShopifyEvent(event);

    return json({
      success: true,
      inventoryItemId,
      locationId,
      available,
      shopDomain: shop,
      message: "Inventory update webhook processed - will trigger data refresh",
    });
  } catch (error) {
    console.error(
      `❌ Error processing inventory_levels update webhook:`,
      error,
    );
    return json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : String(error),
      },
      { status: 500 },
    );
  }
};
