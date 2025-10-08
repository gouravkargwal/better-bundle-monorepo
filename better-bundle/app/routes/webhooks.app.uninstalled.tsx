import type { ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import db from "../db.server";
import prisma from "../db.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  const { shop, session, topic } = await authenticate.webhook(request);

  console.log(`Received ${topic} webhook for ${shop}`);

  try {
    // Webhook requests can trigger multiple times and after an app has already been uninstalled.
    // If this webhook already ran, the session may have been deleted previously.
    if (session) {
      // 1. Find shop record
      const shopRecord = await prisma.shops.findUnique({
        where: { shop_domain: shop },
        select: { id: true },
      });

      if (shopRecord) {
        // 2. Deactivate shop subscription using new schema
        await prisma.shop_subscriptions.updateMany({
          where: {
            shop_id: shopRecord.id,
            is_active: true,
          },
          data: {
            is_active: false,
            status: "cancelled",
            cancelled_at: new Date(),
            updated_at: new Date(),
          },
        });

        // 3. Mark shop as inactive
        await prisma.shops.update({
          where: { id: shopRecord.id },
          data: {
            is_active: false,
            suspended_at: new Date(),
            suspension_reason: "app_uninstalled",
            service_impact: "All services disabled",
            updated_at: new Date(),
          },
        });

        console.log(`✅ Successfully processed app uninstall for ${shop}:`);
        console.log(`   - Deactivated shop subscription`);
        console.log(`   - Marked shop as inactive`);
      }

      // 4. Delete sessions (original functionality)
      await db.sessions.deleteMany({ where: { shop } });

      console.log(`   - Deleted sessions`);
    } else {
      console.log(
        `⚠️ No session found for ${shop} - app may have been uninstalled previously`,
      );
    }
  } catch (error) {
    console.error(`❌ Error processing app uninstall for ${shop}:`, error);
    // Don't throw the error - we still want to return success to Shopify
    // to prevent webhook retries for uninstall events
  }

  return new Response();
};
