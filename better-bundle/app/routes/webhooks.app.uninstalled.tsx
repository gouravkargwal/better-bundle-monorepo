import type { ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import db from "../db.server";
import { deactivateShopBilling } from "../services/shop.service";

export const action = async ({ request }: ActionFunctionArgs) => {
  const { shop, session, topic } = await authenticate.webhook(request);

  console.log(`Received ${topic} webhook for ${shop}`);

  try {
    // Webhook requests can trigger multiple times and after an app has already been uninstalled.
    // If this webhook already ran, the session may have been deleted previously.
    if (session) {
      // 1. Deactivate billing and mark shop as inactive
      await deactivateShopBilling(shop, "app_uninstalled");

      // 2. Delete sessions (original functionality)
      await db.sessions.deleteMany({ where: { shop } });

      console.log(`✅ Successfully processed app uninstall for ${shop}:`);
      console.log(`   - Deactivated billing and marked shop as inactive`);
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
