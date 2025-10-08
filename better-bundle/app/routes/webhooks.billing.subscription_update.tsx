import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import {
  activateSubscription,
  increaseBillingCycleCap,
} from "../services/billing.service";

export async function action({ request }: ActionFunctionArgs) {
  const { topic, shop, payload } = await authenticate.webhook(request);

  console.log(`📋 Subscription update: ${topic} for shop ${shop}`);

  try {
    const appSub = payload.app_subscription;
    const subscriptionId = appSub?.admin_graphql_api_id || appSub?.id;
    const status = appSub?.status;
    const lineItems = appSub?.line_items || [];
    const currentCappedAmount =
      lineItems[0]?.plan?.pricing_details?.capped_amount?.amount;

    if (!subscriptionId || !status) {
      console.error("❌ No subscription data in update webhook");
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

    // Route based on status
    switch (status) {
      case "ACTIVE":
        await handleActiveSubscription(
          shopRecord,
          subscriptionId,
          currentCappedAmount,
        );
        break;
      case "CANCELLED":
        await handleCancelledSubscription(shopRecord, subscriptionId);
        break;
      case "REJECTED":
        await handleRejectedSubscription(shopRecord, subscriptionId);
        break;
      default:
        console.log(`⚠️ Unhandled subscription status: ${status}`);
    }

    return json({ success: true });
  } catch (error) {
    console.error("❌ Error processing subscription update:", error);
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
        where: { status: "ACTIVE" },
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
      status: "cancelled",
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
      status: "rejected",
      rejected_at: new Date(),
      updated_at: new Date(),
    },
  });

  console.log(`❌ Subscription rejected for shop ${shopRecord.shop_domain}`);
}

async function reactivateShopIfSuspended(shopId: string) {
  const currentShopRecord = await prisma.shops.findUnique({
    where: { id: shopId },
    select: { suspension_reason: true, is_active: true },
  });

  if (
    currentShopRecord?.suspension_reason === "monthly_cap_reached" &&
    !currentShopRecord.is_active
  ) {
    await prisma.shops.update({
      where: { id: shopId },
      data: {
        is_active: true,
        suspended_at: null,
        suspension_reason: null,
        service_impact: null,
        updated_at: new Date(),
      },
    });

    console.log(`🚀 Shop services reactivated after cap increase!`);
  }
}
