import type { LoaderFunctionArgs } from "@remix-run/node";

import prisma from "../db.server";

/**
 * Middleware to check service suspension status
 * Should be used in loader functions of protected routes
 */
export async function checkServiceSuspensionMiddleware(
  request: LoaderFunctionArgs["request"],
  shopDomain: string,
): Promise<{
  shouldRedirect: boolean;
  redirectUrl?: string;
  suspensionStatus?: any;
}> {
  try {
    // Get shop record
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: shopDomain },
      select: { id: true },
    });

    if (!shop) {
      return { shouldRedirect: false };
    }

    // Check suspension status
    const suspensionStatus = await checkServiceSuspension(shop.id);

    // If services are suspended and billing setup is required, redirect to billing setup
    if (suspensionStatus.isSuspended && suspensionStatus.requiresBillingSetup) {
      const message = suspensionStatus.message;

      if (message.actionRequired && message.actionUrl) {
        return {
          shouldRedirect: true,
          redirectUrl: message.actionUrl,
          suspensionStatus,
        };
      }
    }

    return { shouldRedirect: false, suspensionStatus };
  } catch (error) {
    console.error("Error in service suspension middleware:", error);
    return { shouldRedirect: false };
  }
}

export async function checkServiceSuspension(shopId: string): Promise<any> {
  try {
    // Get shop and billing plan
    const [shop, billingPlan] = await Promise.all([
      prisma.shops.findUnique({
        where: { id: shopId },
        select: {
          id: true,
          is_active: true,
          suspended_at: true,
          suspension_reason: true,
        },
      }),
      prisma.billing_plans.findFirst({
        where: { shop_id: shopId, status: { in: ["active", "suspended"] } },
        orderBy: { created_at: "desc" },
      }),
    ]);

    if (!shop || !billingPlan) {
      return {
        isSuspended: true,
        reason: "shop_not_found",
        requiresBillingSetup: false,
        trialCompleted: false,
        subscriptionActive: false,
        subscriptionPending: false,
      };
    }

    // ✅ PRIMARY CHECK: Shop is_active flag (set by backend)
    if (!shop.is_active) {
      const reason = shop.suspension_reason || "service_suspended";

      return {
        isSuspended: true,
        reason: reason,
        requiresBillingSetup:
          reason === "trial_completed_subscription_required",
        trialCompleted: !billingPlan.is_trial_active,
        subscriptionActive: false,
        subscriptionPending: billingPlan.subscription_status === "PENDING",
      };
    }

    // Check subscription status
    const subscriptionActive = billingPlan.subscription_status === "ACTIVE";
    const subscriptionPending = billingPlan.subscription_status === "PENDING";
    const trialCompleted = !billingPlan.is_trial_active;

    // If subscription is pending, services are suspended
    if (subscriptionPending) {
      return {
        isSuspended: true,
        reason: "subscription_pending_approval",
        requiresBillingSetup: false,
        trialCompleted: true,
        subscriptionActive: false,
        subscriptionPending: true,
      };
    }

    // Services are active
    return {
      isSuspended: false,
      reason: "active",
      requiresBillingSetup: false,
      trialCompleted: trialCompleted,
      subscriptionActive: subscriptionActive,
      subscriptionPending: false,
    };
  } catch (error) {
    console.error("Error checking service suspension:", error);
    return {
      isSuspended: true,
      reason: "error_checking_status",
      requiresBillingSetup: false,
      trialCompleted: false,
      subscriptionActive: false,
      subscriptionPending: false,
    };
  }
}
