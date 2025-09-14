import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  const { payload, session, topic, shop } = await authenticate.webhook(request);

  if (!session || !shop) {
    return json({ error: "Authentication failed" }, { status: 401 });
  }

  try {
    console.log(`🔔 ${topic} webhook received for ${shop}:`, payload);

    // Extract collection data from payload
    const collection = payload;
    const collectionId = collection.id?.toString();

    if (!collectionId) {
      console.error("❌ No collection ID found in payload");
      return json({ error: "No collection ID found" }, { status: 400 });
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

    // Store raw collection data for deletion event
    await prisma.rawCollection.create({
      data: {
        shopId: shopRecord.id,
        payload: collection,
        shopifyId: collectionId,
        shopifyCreatedAt: collection.created_at
          ? new Date(collection.created_at)
          : new Date(),
        shopifyUpdatedAt: new Date(), // Use current time for deletion
      },
    });

    console.log(
      `✅ Collection ${collectionId} deletion event stored in raw table for shop ${shop}`,
    );

    return json({
      success: true,
      collectionId: collectionId,
      shopId: shopRecord.id,
      message: "Collection deletion event stored successfully",
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
