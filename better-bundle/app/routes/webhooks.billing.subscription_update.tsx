import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import { invalidateSuspensionCache } from "../middleware/serviceSuspension";
import logger from "app/utils/logger";

export async function action({ request }: ActionFunctionArgs) {
  const { shop, payload } = await authenticate.webhook(request);

  try {
    const appSub = payload.app_subscription;
    const subscriptionId = appSub?.admin_graphql_api_id || appSub?.id;
    const status = appSub?.status;
    const lineItems = appSub?.line_items || [];
    const currentCappedAmount =
      lineItems[0]?.plan?.pricing_details?.capped_amount?.amount;

    if (!subscriptionId || !status) {
      logger.error({ payload }, "No subscription data in update webhook");
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

    // ✅ Handle business logic only - No status syncing
    switch (status) {
      case "ACTIVE":
        await handleActiveSubscription(
          shopRecord,
          subscriptionId,
          currentCappedAmount,
        );
        break;
      case "CANCELLED":
      case "DECLINED":
        await handleCancelledSubscription(shopRecord, subscriptionId);
        break;
      case "APPROACHING_CAPPED_AMOUNT":
        await handleCapApproach(shopRecord, subscriptionId);
        break;
      default:
        logger.info({ status }, "Subscription status change logged");
    }

    return json({ success: true });
  } catch (error) {
    logger.error(
      {
        error: error instanceof Error ? error.message : String(error),
        stack: error instanceof Error ? error.stack : undefined,
      },
      "Error processing subscription update",
    );
    return json(
      { success: false, error: "Webhook processing failed" },
      { status: 500 },
    );
  }
}

// ✅ Business logic handlers - No status syncing
async function handleActiveSubscription(
  shopRecord: any,
  subscriptionId: string,
  currentCappedAmount?: number,
) {
  try {
    // Reactivate shop if suspended
    await prisma.shops.update({
      where: { id: shopRecord.id },
      data: {
        is_active: true,
        suspended_at: null,
        suspension_reason: null,
        service_impact: null,
        updated_at: new Date(),
      },
    });

    // Invalidate suspension cache
    await invalidateSuspensionCache(shopRecord.id);

    logger.info(
      { shop: shopRecord.shop_domain, subscriptionId },
      "Shop reactivated",
    );
  } catch (error) {
    logger.error({ error }, "Error reactivating shop");
    throw error;
  }
}

async function handleCancelledSubscription(
  shopRecord: any,
  subscriptionId: string,
) {
  try {
    // Suspend shop services
    await prisma.shops.update({
      where: { id: shopRecord.id },
      data: {
        is_active: false,
        suspended_at: new Date(),
        suspension_reason: "subscription_cancelled",
        service_impact: "Services suspended due to subscription cancellation",
        updated_at: new Date(),
      },
    });

    logger.info(
      { shop: shopRecord.shop_domain, subscriptionId },
      "Shop suspended due to cancellation",
    );
  } catch (error) {
    logger.error({ error }, "Error suspending shop");
    throw error;
  }
}

async function handleCapApproach(shopRecord: any, subscriptionId: string) {
  try {
    // Handle cap approach - could send notifications, etc.
    logger.info(
      { shop: shopRecord.shop_domain, subscriptionId },
      "Subscription approaching capped amount",
    );

    // TODO: Add cap approach logic (notifications, warnings, etc.)
  } catch (error) {
    logger.error({ error }, "Error handling cap approach");
    throw error;
  }
}
