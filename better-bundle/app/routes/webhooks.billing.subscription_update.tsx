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

    switch (status) {
      case "ACTIVE":
        await handleActiveSubscription(shopRecord, subscriptionId);
        break;
      case "DECLINED":
        await handleDeclinedSubscription(shopRecord, subscriptionId);
        break;
      case "CANCELLED":
        await handleCancelledSubscription(shopRecord, subscriptionId);
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

async function handleActiveSubscription(
  shopRecord: any,
  subscriptionId: string,
) {
  try {
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: { shop_id: shopRecord.id, is_active: true },
    });

    if (!shopSubscription) {
      logger.error(
        { shop: shopRecord.shop_domain, subscriptionId },
        "No shop subscription found for active subscription",
      );
      return;
    }

    // When Shopify subscription becomes ACTIVE, convert from TRIAL to ACTIVE
    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        shopify_subscription_id: subscriptionId,
        shopify_status: "ACTIVE",
        status: "ACTIVE",
        is_active: true,
        updated_at: new Date(),
      },
    });

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

    await invalidateSuspensionCache(shopRecord.id);

    logger.info(
      {
        shop: shopRecord.shop_domain,
        subscriptionId,
        shopSubscriptionId: shopSubscription.id,
      },
      "Subscription activated and shop reactivated",
    );
  } catch (error) {
    logger.error({ error }, "Error activating subscription");
    throw error;
  }
}

async function handleDeclinedSubscription(
  shopRecord: any,
  subscriptionId: string,
) {
  try {
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: { shop_id: shopRecord.id, is_active: true },
    });

    if (!shopSubscription) {
      logger.error(
        { shop: shopRecord.shop_domain, subscriptionId },
        "No shop subscription found for declined subscription",
      );
      return;
    }

    // DECLINED means the merchant rejected the approval in Shopify.
    // Reset to TRIAL status so they can set up billing again.
    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        shopify_subscription_id: null,
        shopify_line_item_id: null,
        shopify_status: "DECLINED",
        status: "TRIAL",
        confirmation_url: null,
        cancelled_at: null,
        updated_at: new Date(),
      },
    });

    logger.info(
      {
        shop: shopRecord.shop_domain,
        subscriptionId,
        shopSubscriptionId: shopSubscription.id,
      },
      "Subscription was declined — reset to TRIAL for retry",
    );
  } catch (error) {
    logger.error({ error }, "Error handling declined subscription");
    throw error;
  }
}

async function handleCancelledSubscription(
  shopRecord: any,
  subscriptionId: string,
) {
  try {
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: { shop_id: shopRecord.id, is_active: true },
    });

    if (!shopSubscription) {
      logger.error(
        { shop: shopRecord.shop_domain, subscriptionId },
        "No shop subscription found for cancelled subscription",
      );
      return;
    }

    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        shopify_subscription_id: subscriptionId,
        shopify_status: "CANCELLED",
        status: "CANCELLED",
        is_active: false,
        cancelled_at: new Date(),
        updated_at: new Date(),
      },
    });

    // Suspend shop services
    await prisma.shops.update({
      where: { id: shopRecord.id },
      data: {
        is_active: false,
        suspended_at: new Date(),
        suspension_reason: "subscription_cancelled",
        service_impact: "suspended",
        updated_at: new Date(),
      },
    });

    logger.info(
      {
        shop: shopRecord.shop_domain,
        subscriptionId,
        shopSubscriptionId: shopSubscription.id,
      },
      "Subscription cancelled and shop suspended",
    );
  } catch (error) {
    logger.error({ error }, "Error handling cancelled subscription");
    throw error;
  }
}
