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

// ✅ Business logic handlers - Handle subscription activation
async function handleActiveSubscription(
  shopRecord: any,
  subscriptionId: string,
  currentCappedAmount?: number,
) {
  try {
    // Find the shop subscription record
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: { shop_id: shopRecord.id },
      include: {
        shopify_subscriptions: true,
        pricing_tiers: true,
        billing_cycles: true,
      },
    });

    if (!shopSubscription) {
      logger.error(
        { shop: shopRecord.shop_domain, subscriptionId },
        "No shop subscription found for active subscription",
      );
      return;
    }

    // Update shopify_subscriptions table
    if (shopSubscription.shopify_subscriptions) {
      await prisma.shopify_subscriptions.update({
        where: { id: shopSubscription.shopify_subscriptions.id },
        data: {
          status: "ACTIVE",
          activated_at: new Date(),
          updated_at: new Date(),
        },
      });
    }

    // Update shop_subscriptions table
    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        status: "ACTIVE",
        is_active: true,
        activated_at: new Date(),
        updated_at: new Date(),
      },
    });

    // ✅ CREATE BILLING CYCLE if it doesn't exist
    // Check if there's already an active billing cycle
    const activeCycle = shopSubscription.billing_cycles?.find(
      (cycle: any) => cycle.status === "ACTIVE",
    );

    if (!activeCycle) {
      // Determine cap amount: use current capped amount from Shopify, or user_chosen_cap_amount, or default
      const capAmount =
        currentCappedAmount || shopSubscription.user_chosen_cap_amount || 1000;

      logger.info(
        {
          shop: shopRecord.shop_domain,
          capAmount,
          source: currentCappedAmount
            ? "shopify"
            : shopSubscription.user_chosen_cap_amount
              ? "user_chosen"
              : "default",
        },
        "Creating billing cycle for activated subscription",
      );

      // Create first billing cycle
      await prisma.billing_cycles.create({
        data: {
          shop_subscription_id: shopSubscription.id,
          cycle_number: 1,
          start_date: new Date(),
          end_date: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), // 30 days
          initial_cap_amount: capAmount,
          current_cap_amount: capAmount,
          usage_amount: 0,
          commission_count: 0,
          status: "ACTIVE",
          activated_at: new Date(),
        },
      });

      logger.info(
        {
          shop: shopRecord.shop_domain,
          capAmount,
        },
        "Billing cycle created successfully",
      );
    } else {
      logger.info(
        {
          shop: shopRecord.shop_domain,
          cycleId: activeCycle.id,
        },
        "Active billing cycle already exists, skipping creation",
      );
    }

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
      {
        shop: shopRecord.shop_domain,
        subscriptionId,
        currentCappedAmount,
        shopSubscriptionId: shopSubscription.id,
      },
      "Subscription activated and shop reactivated",
    );
  } catch (error) {
    logger.error({ error }, "Error activating subscription");
    throw error;
  }
}

async function handleCancelledSubscription(
  shopRecord: any,
  subscriptionId: string,
) {
  try {
    // Find the shop subscription record
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: { shop_id: shopRecord.id },
      include: { shopify_subscriptions: true },
    });

    if (!shopSubscription) {
      logger.error(
        { shop: shopRecord.shop_domain, subscriptionId },
        "No shop subscription found for cancelled subscription",
      );
      return;
    }

    // Update shopify_subscriptions table
    if (shopSubscription.shopify_subscriptions) {
      await prisma.shopify_subscriptions.update({
        where: { id: shopSubscription.shopify_subscriptions.id },
        data: {
          status: "CANCELLED",
          cancelled_at: new Date(),
          updated_at: new Date(),
        },
      });
    }

    // Update shop_subscriptions table
    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
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
        service_impact: "Services suspended due to subscription cancellation",
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
