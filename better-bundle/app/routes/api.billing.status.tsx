import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import prisma from "../db.server";
import logger from "../utils/logger";

export async function loader({ request }: LoaderFunctionArgs) {
  const { session } = await authenticate.admin(request);
  const { shop } = session;

  try {
    // Get shop record
    const shopRecord = await prisma.shops.findUnique({
      where: { shop_domain: shop },
      select: { id: true, currency_code: true, is_active: true },
    });

    if (!shopRecord) {
      return json({ success: false, error: "Shop not found" }, { status: 404 });
    }

    // Get the active subscription using the unified model
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopRecord.id,
        is_active: true,
      },
      include: {
        subscription_plans: true,
      },
      orderBy: { created_at: "desc" },
    });

    if (!shopSubscription) {
      return json({
        shop_id: shopRecord.id,
        billing_status: "no_subscription",
        message: "No subscription found",
        shop_active: shopRecord.is_active,
      });
    }

    // Determine billing status from unified subscription status
    const statusMap: Record<string, string> = {
      TRIAL: "trial_active",
      ACTIVE: "subscription_active",
      SUSPENDED: "subscription_suspended",
      CANCELLED: "subscription_cancelled",
      EXPIRED: "subscription_expired",
    };

    const subscriptionStatus = shopSubscription.status as string;
    const billingStatus = statusMap[subscriptionStatus] || subscriptionStatus.toLowerCase();

    const monthlyPrice = Number(
      shopSubscription.subscription_plans?.monthly_price ?? 99.0,
    );
    const trialDays = Number(shopSubscription.subscription_plans?.trial_days ?? 14);

    return json({
      shop_id: shopRecord.id,
      billing_status: billingStatus,
      message: getStatusMessage(billingStatus, monthlyPrice),
      trial_active: shopSubscription.status === "TRIAL",
      trial_days: trialDays,
      subscription_id: shopSubscription.shopify_subscription_id,
      subscription_status: shopSubscription.shopify_status,
      subscription_confirmation_url: shopSubscription.confirmation_url,
      shop_active: shopRecord.is_active,
      currency: shopRecord.currency_code || "USD",
      monthly_price: monthlyPrice,
    });
  } catch (error) {
    logger.error({ error }, "Error getting billing status");
    return json(
      {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
}

function getStatusMessage(
  status: string,
  trialRevenue: number,
  trialThreshold: number,
): string {
  switch (status) {
    case "trial_active":
      return `Trial active — $${trialRevenue.toFixed(2)} / $${trialThreshold.toFixed(2)} revenue`;
    case "subscription_active":
      return "Subscription active";
    case "subscription_pending":
      return "Subscription pending approval";
    case "subscription_cancelled":
      return "Subscription cancelled";
    case "subscription_suspended":
      return "Services suspended — cap reached or billing issue";
    default:
      return `Status: ${status}`;
  }
}
