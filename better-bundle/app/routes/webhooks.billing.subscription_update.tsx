import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import {
  activateSubscription,
  increaseBillingCycleCap,
  reactivateShopIfSuspended,
} from "../services/billing.service";
import { invalidateSuspensionCache } from "../middleware/serviceSuspension";
import logger from "app/utils/logger";

export async function action({ request }: ActionFunctionArgs) {
  const startTime = Date.now();
  const { topic, shop, payload } = await authenticate.webhook(request);

  logger.info({ topic, shop }, "Subscription update webhook received");

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

    logger.info(
      { subscriptionId, status, currentCappedAmount },
      "Processing subscription update",
    );

    // Find shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true, shop_domain: true },
    });

    if (!shopRecord) {
      logger.warn({ shop }, "No shop record found for domain");
      return json({ success: true });
    }

    // Route based on status
    switch (status) {
      case "ACTIVE":
        logger.info({ subscriptionId }, "Handling active subscription");
        await handleActiveSubscription(
          shopRecord,
          subscriptionId,
          currentCappedAmount,
        );
        break;
      case "CANCELLED":
        logger.info({ subscriptionId }, "Handling cancelled subscription");
        await handleCancelledSubscription(shopRecord, subscriptionId);
        break;
      case "REJECTED":
        logger.info({ subscriptionId }, "Handling rejected subscription");
        await handleRejectedSubscription(shopRecord, subscriptionId);
        break;
      default:
        logger.warn({ status }, "Unhandled subscription status");
    }

    const duration = Date.now() - startTime;
    logger.info(
      { status, duration },
      "Subscription update processed successfully",
    );
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
  currentCappedAmount?: number,
) {
  // Check if this is a cap increase
  const shopSubscription = await prisma.shop_subscriptions.findFirst({
    where: { shop_id: shopRecord.id, is_active: true },
    include: {
      billing_cycles: {
        where: { status: "ACTIVE" as any },
        orderBy: { cycle_number: "desc" },
        take: 1,
      },
    },
  });

  if (shopSubscription) {
    const currentCycle = (shopSubscription as any)?.billing_cycles?.[0];
    const isCapIncrease =
      currentCycle &&
      currentCappedAmount &&
      currentCappedAmount > Number(currentCycle.current_cap_amount);

    if (isCapIncrease) {
      console.log(
        `📈 Cap increase detected: ${currentCycle.current_cap_amount} → ${currentCappedAmount}`,
      );
      await increaseBillingCycleCap(
        shopRecord.id,
        currentCappedAmount,
        "shopify_webhook",
      );
      await reactivateShopIfSuspended(shopRecord.id);
    } else {
      // Regular activation
      await activateSubscription(shopRecord.id, subscriptionId);
      // Invalidate cache after activation
      await invalidateSuspensionCache(shopRecord.id);
    }
  }

  console.log(
    `✅ Active subscription processed for shop ${shopRecord.shop_domain}`,
  );
}

async function handleCancelledSubscription(
  shopRecord: any,
  subscriptionId: string,
) {
  // Update subscription status
  await prisma.shop_subscriptions.updateMany({
    where: { shop_id: shopRecord.id, is_active: true },
    data: {
      status: "CANCELLED" as any,
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
      service_impact: "Services suspended due to cancellation",
      updated_at: new Date(),
    },
  });

  console.log(`🚫 Subscription cancelled for shop ${shopRecord.shop_domain}`);
}

async function handleRejectedSubscription(
  shopRecord: any,
  subscriptionId: string,
) {
  // Update subscription status
  await prisma.shop_subscriptions.updateMany({
    where: { shop_id: shopRecord.id, is_active: true },
    data: {
      status: "CANCELLED" as any, // Using CANCELLED as there's no REJECTED status in the enum
      cancelled_at: new Date(),
      updated_at: new Date(),
    },
  });

  console.log(`❌ Subscription rejected for shop ${shopRecord.shop_domain}`);
}
