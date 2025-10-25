import type { LoaderFunctionArgs } from "@remix-run/node";

import prisma from "../db.server";
import { getCacheService } from "../services/redis.service";

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
      // Generate appropriate message and action URL based on suspension reason
      let actionUrl = "";
      let actionRequired = false;

      if (suspensionStatus.reason === "trial_completed_awaiting_setup") {
        actionUrl = "/app/billing";
        actionRequired = true;
      } else if (
        suspensionStatus.reason === "trial_completed_subscription_required"
      ) {
        actionUrl = "/app/billing";
        actionRequired = true;
      }

      if (actionRequired && actionUrl) {
        return {
          shouldRedirect: true,
          redirectUrl: actionUrl,
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
    const cacheService = await getCacheService();
    const cacheKey = `suspension:${shopId}`;

    // Use your existing cache pattern with getOrSet
    return await cacheService.getOrSet(
      cacheKey,
      async () => {
        // Get shop and subscription
        const [shop, shopSubscription] = await Promise.all([
          prisma.shops.findUnique({
            where: { id: shopId },
            select: {
              id: true,
              is_active: true,
              suspended_at: true,
              suspension_reason: true,
            },
          }),
          prisma.shop_subscriptions.findFirst({
            where: {
              shop_id: shopId,
              is_active: true,
            },
            include: {
              subscription_trials: true,
              billing_cycles: {
                where: { status: "ACTIVE" },
                orderBy: { cycle_number: "desc" },
                take: 1,
              },
            },
          }),
        ]);

        if (!shop || !shopSubscription) {
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
            requiresCapIncrease: reason === "monthly_cap_reached",
            trialCompleted: shopSubscription.status !== "TRIAL",
            subscriptionActive: false,
            subscriptionPending: shopSubscription.status === "PENDING_APPROVAL",
          };
        }

        // Check subscription status
        const subscriptionActive = shopSubscription.status === "ACTIVE";
        const subscriptionPending =
          shopSubscription.status === "PENDING_APPROVAL";

        // ✅ Trial active - services active
        if (shopSubscription.status === "TRIAL") {
          return {
            isSuspended: false,
            reason: "trial_active",
            requiresBillingSetup: false,
            trialCompleted: false,
            subscriptionActive: false,
            subscriptionPending: false,
          };
        }

        // ✅ NEW: Trial completed - services SUSPENDED until user sets up billing
        if (shopSubscription.status === ("TRIAL_COMPLETED" as any)) {
          return {
            isSuspended: true,
            reason: "trial_completed_awaiting_setup",
            requiresBillingSetup: true,
            trialCompleted: true,
            subscriptionActive: false,
            subscriptionPending: false,
          };
        }

        // ✅ Subscription pending approval - services SUSPENDED
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

        // ✅ Subscription active - services ACTIVE
        if (subscriptionActive) {
          return {
            isSuspended: false,
            reason: "active",
            requiresBillingSetup: false,
            trialCompleted: true,
            subscriptionActive: true,
            subscriptionPending: false,
          };
        }

        // ✅ Suspended/Cancelled - services SUSPENDED
        return {
          isSuspended: true,
          reason: `subscription_${shopSubscription.status.toLowerCase()}`,
          requiresBillingSetup: shopSubscription.status === "SUSPENDED",
          trialCompleted: true,
          subscriptionActive: false,
          subscriptionPending: false,
        };
      },
      300, // 5 minutes TTL
    );
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

/**
 * Check suspension status by shop domain (for webhook endpoints)
 */
export async function checkServiceSuspensionByDomain(
  shopDomain: string,
): Promise<any> {
  try {
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: shopDomain },
      select: { id: true },
    });

    if (!shop) {
      return {
        isSuspended: true,
        reason: "shop_not_found",
        subscriptionActive: false,
      };
    }

    return await checkServiceSuspension(shop.id);
  } catch (error) {
    console.error(
      { error, shopDomain },
      "Error checking suspension status by domain",
    );
    return {
      isSuspended: true,
      reason: "suspension_check_error",
      subscriptionActive: false,
    };
  }
}

/**
 * Invalidate suspension cache when shop status changes
 * Call this when suspending/reactivating shops
 */
export async function invalidateSuspensionCache(shopId: string): Promise<void> {
  try {
    const cacheService = await getCacheService();
    const cacheKey = `suspension:${shopId}`;
    await cacheService.del(cacheKey);
    console.log(`✅ Suspension cache invalidated for shop ${shopId}`);
  } catch (error) {
    console.error(
      `❌ Error invalidating suspension cache for shop ${shopId}:`,
      error,
    );
  }
}
