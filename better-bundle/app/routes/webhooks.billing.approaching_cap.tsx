// webhooks.billing.approaching_cap.tsx
import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";

export async function action({ request }: ActionFunctionArgs) {
  const { topic, shop, payload } = await authenticate.webhook(request);

  console.log(`⚠️ Approaching cap: ${topic} for shop ${shop}`);

  try {
    const appSub = payload.app_subscription;
    const subscriptionId = appSub?.admin_graphql_api_id || appSub?.id;
    const currentUsage = appSub?.current_usage || 0;
    const cappedAmount = appSub?.capped_amount || 0;
    const usagePercentage = (currentUsage / cappedAmount) * 100;

    if (!subscriptionId) {
      console.error("❌ No subscription data in approaching cap webhook");
      return json(
        { success: false, error: "No subscription data" },
        { status: 400 },
      );
    }

    // Find shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true, shop_domain: true },
    });

    if (!shopRecord) {
      console.log(`⚠️ No shop record found for domain ${shop}`);
      return json({ success: true });
    }

    console.log(
      `📊 Cap warning: ${usagePercentage.toFixed(1)}% of cap used (${currentUsage}/${cappedAmount})`,
    );

    // Add your warning logic here:
    // - Send email notification
    // - Update dashboard
    // - Log for analytics

    return json({ success: true });
  } catch (error) {
    console.error("❌ Error processing approaching cap warning:", error);
    return json(
      { success: false, error: "Webhook processing failed" },
      { status: 500 },
    );
  }
}
