// webhooks.billing.approaching_cap.tsx
import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import logger from "../utils/logger";

export async function action({ request }: ActionFunctionArgs) {
  const { topic, shop, payload } = await authenticate.webhook(request);

  logger.warn({ shop, topic }, "Approaching cap warning");

  try {
    const appSub = payload.app_subscription;
    const subscriptionId = appSub?.admin_graphql_api_id || appSub?.id;
    const currentUsage = appSub?.current_usage || 0;
    const cappedAmount = appSub?.capped_amount || 0;
    const usagePercentage = (currentUsage / cappedAmount) * 100;

    if (!subscriptionId) {
      logger.error({ shop }, "No subscription data in approaching cap webhook");
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
      logger.warn({ shop }, "No shop record found for domain");
      return json({ success: true });
    }

    logger.warn(
      { shop, usagePercentage, currentUsage, cappedAmount },
      "Cap warning triggered",
    );

    // Add your warning logic here:
    // - Send email notification
    // - Update dashboard
    // - Log for analytics

    return json({ success: true });
  } catch (error) {
    logger.error({ error, shop }, "Error processing approaching cap warning");
    return json(
      { success: false, error: "Webhook processing failed" },
      { status: 500 },
    );
  }
}
