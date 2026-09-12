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

    // Get active shop subscription with related pricing and plan info
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
      // No subscription yet — first-time user in trial or just installed
      return json({
        shop_id: shopRecord.id,
        billing_status: "trial_active",
        message: "No subscription found, trial period active",
        subscription_type: null,
        subscription_status: null,
        plan_name: null,
        commission_rate: null,
        cap_amount: null,
        currency: shopRecord.currency_code || "USD",
        trial_active: true,
        shop_active: shopRecord.is_active,
      });
    }

    // Map DB subscription status to frontend billing status
    const dbStatus: string = shopSubscription.status;
    const planName =
      shopSubscription.subscription_plans?.name || "Pay As You Go";
    const currency = shopRecord.currency_code || "USD";

    let billingStatus: string;
    let message: string;
    let trialActive = false;

    switch (dbStatus) {
      case "TRIAL": {
        // Revenue-based trial. The worker flips this row to TRIAL_COMPLETED
        // when the threshold is crossed, so TRIAL here means still trialing —
        // there is no elapsed-time gate to evaluate.
        billingStatus = "trial_active";
        trialActive = true;
        message = "Trial active — free until the revenue threshold is reached";
        break;
      }

      case "TRIAL_COMPLETED":
        billingStatus = "trial_completed";
        message = "Trial completed — please set up billing";
        break;

      case "ACTIVE":
        billingStatus = "subscription_active";
        message = "Subscription active";
        break;

      case "SUSPENDED":
        billingStatus = "subscription_suspended";
        message = "Services suspended";
        break;

      case "CANCELLED":
        billingStatus = "subscription_cancelled";
        message = "Subscription cancelled";
        break;

      default:
        billingStatus = "trial_active";
        trialActive = true;
        message = "Trial period active";
        break;
    }

    return json({
      shop_id: shopRecord.id,
      billing_status: billingStatus,
      message,
      subscription_type: shopSubscription.subscription_type,
      subscription_status: dbStatus,
      plan_name: planName,
      commission_rate:
        Number(
          shopSubscription.commission_rate_override ??
            shopSubscription.subscription_plans?.commission_rate,
        ) || null,
      cap_amount:
        Number(
          shopSubscription.cap_amount_override ??
            shopSubscription.subscription_plans?.cap_amount,
        ) || null,
      currency,
      trial_active: trialActive,
      shopify_subscription_id: shopSubscription.shopify_subscription_id,
      confirmation_url: shopSubscription.confirmation_url,
      shop_active: shopRecord.is_active,
    });
  } catch (error) {
    logger.error({ error, shop }, "Error getting billing status");
    return json(
      {
        success: false,
        error: "An internal error occurred. Please try again later.",
      },
      { status: 500 },
    );
  }
}
