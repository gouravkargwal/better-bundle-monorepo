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
        monthly_fee: null,
        currency: shopRecord.currency_code || "USD",
        trial_active: true,
        trial_days_remaining: 14,
        shop_active: shopRecord.is_active,
      });
    }

    // Map DB subscription status to frontend billing status
    const dbStatus: string = shopSubscription.status;
    const planName =
      shopSubscription.subscription_plans?.name || "Flat Fee Plan";
    const currency = shopRecord.currency_code || "USD";

    let billingStatus: string;
    let message: string;
    let trialActive = false;

    switch (dbStatus) {
      case "TRIAL": {
        // Time-based trial
        const trialDays = shopSubscription.trial_duration_days || 14;
        const startedAt = shopSubscription.started_at;
        const trialEnd = new Date(
          startedAt.getTime() + trialDays * 24 * 60 * 60 * 1000,
        );
        const now = new Date();
        const daysRemaining = Math.max(
          0,
          Math.ceil(
            (trialEnd.getTime() - now.getTime()) / (1000 * 60 * 60 * 24),
          ),
        );

        if (daysRemaining > 0) {
          billingStatus = "trial_active";
          trialActive = true;
          message = `Trial active — ${daysRemaining} days remaining`;
        } else {
          billingStatus = "trial_completed";
          message = "Trial period has ended";
        }
        break;
      }

      case "TRIAL_COMPLETED":
        billingStatus = "trial_completed";
        message = "Trial completed — please set up billing";
        break;

      case "PENDING_APPROVAL":
        billingStatus = "subscription_pending";
        message = "Subscription pending approval";
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

    // Calculate trial days remaining if still in trial
    let trialDaysRemaining = 0;
    if (trialActive && shopSubscription.started_at) {
      const trialDays = shopSubscription.trial_duration_days || 14;
      const trialEnd = new Date(
        shopSubscription.started_at.getTime() + trialDays * 24 * 60 * 60 * 1000,
      );
      trialDaysRemaining = Math.max(
        0,
        Math.ceil((trialEnd.getTime() - Date.now()) / (1000 * 60 * 60 * 24)),
      );
    }

    return json({
      shop_id: shopRecord.id,
      billing_status: billingStatus,
      message,
      subscription_type: shopSubscription.subscription_type,
      subscription_status: dbStatus,
      plan_name: planName,
      monthly_fee:
        Number(shopSubscription.subscription_plans?.monthly_fee) || null,
      currency,
      trial_active: trialActive,
      trial_days_remaining: trialDaysRemaining,
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
