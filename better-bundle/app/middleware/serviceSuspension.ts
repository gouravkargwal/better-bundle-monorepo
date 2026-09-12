import type { LoaderFunctionArgs } from "@remix-run/node";

import prisma from "../db.server";
import { getCacheService } from "../services/redis.service";
import logger from "app/utils/logger";
import { incrementCounter } from "../services/metrics.service";

export interface SuspensionStatus {
  isSuspended: boolean;
  reason: string;
  requiresBillingSetup: boolean;
  trialCompleted: boolean;
  subscriptionActive: boolean;
}

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
  suspensionStatus?: SuspensionStatus;
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
      } else if (suspensionStatus.reason === "payment_failure") {
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

export async function checkServiceSuspension(
  shopId: string,
): Promise<SuspensionStatus> {
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
          }),
        ]);

        if (!shop || !shopSubscription) {
          return {
            isSuspended: true,
            reason: "shop_not_found",
            requiresBillingSetup: false,
            trialCompleted: false,
            subscriptionActive: false,
          };
        }

        // ✅ PRIMARY CHECK: Shop is_active flag (set by backend)
        if (!shop.is_active) {
          const reason = shop.suspension_reason || "service_suspended";

          incrementCounter("suspension.check", {
            shopId,
            reason,
            isSuspended: 1,
          });

          return {
            isSuspended: true,
            reason: reason,
            requiresBillingSetup:
              reason === "trial_completed_subscription_required" ||
              reason === "payment_failure",
            trialCompleted: shopSubscription.status !== "TRIAL",
            subscriptionActive: false,
          };
        }

        // Check subscription status
        const subscriptionActive = shopSubscription.status === "ACTIVE";

        // ✅ Trial active - services active
        if (shopSubscription.status === "TRIAL") {
          return {
            isSuspended: false,
            reason: "trial_active",
            requiresBillingSetup: false,
            trialCompleted: false,
            subscriptionActive: false,
          };
        }

        // ✅ NEW: Trial completed - services SUSPENDED until user sets up billing
        // NOTE: "TRIAL_COMPLETED" should be added to the Prisma SubscriptionStatus enum.
        // Using string comparison until schema is updated.
        // Also treat legacy "PENDING_APPROVAL" as TRIAL_COMPLETED since we no longer lock the UI
        if (shopSubscription.status === "TRIAL_COMPLETED" || shopSubscription.status === "PENDING_APPROVAL") {
          return {
            isSuspended: true,
            reason: "trial_completed_awaiting_setup",
            requiresBillingSetup: true,
            trialCompleted: true,
            subscriptionActive: false,
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
          };
        }

        // ✅ Suspended/Cancelled - services SUSPENDED
        return {
          isSuspended: true,
          reason: `subscription_${shopSubscription.status.toLowerCase()}`,
          requiresBillingSetup: shopSubscription.status === "SUSPENDED",
          trialCompleted: true,
          subscriptionActive: false,
        };
      },
      300, // 5 minutes TTL
    );
  } catch (error) {
    // Structured logging for Redis/cache failure
    console.error(
      "[SuspensionMiddleware] Redis/cache failed, falling back to direct DB query:",
      error,
    );
    logger.error({ error }, "Redis/cache failure in checkServiceSuspension");

    // Fallback: try direct DB query when cache is unavailable
    try {
      const shop = await prisma.shops.findUnique({
        where: { id: shopId },
        select: {
          id: true,
          is_active: true,
          suspended_at: true,
          suspension_reason: true,
        },
      });

      if (!shop) {
        return {
          isSuspended: true,
          reason: "shop_not_found",
          requiresBillingSetup: false,
          trialCompleted: false,
          subscriptionActive: false,
        };
      }

      const shopSubscription = await prisma.shop_subscriptions.findFirst({
        where: { shop_id: shopId, is_active: true },
      });

      if (!shopSubscription) {
        return {
          isSuspended: true,
          reason: "shop_not_found",
          requiresBillingSetup: false,
          trialCompleted: false,
          subscriptionActive: false,
        };
      }

      if (!shop.is_active) {
        return {
          isSuspended: true,
          reason: shop.suspension_reason || "service_suspended",
          requiresBillingSetup:
            shop.suspension_reason ===
              "trial_completed_subscription_required" ||
            shop.suspension_reason === "payment_failure",
          trialCompleted: shopSubscription.status !== "TRIAL",
          subscriptionActive: false,
        };
      }

      if (shopSubscription.status === "ACTIVE") {
        return {
          isSuspended: false,
          reason: "active",
          requiresBillingSetup: false,
          trialCompleted: true,
          subscriptionActive: true,
        };
      }

      // For any other status, return suspended but let through on errors
      return {
        isSuspended: true,
        reason: `subscription_${shopSubscription.status.toLowerCase()}`,
        requiresBillingSetup: false,
        trialCompleted: true,
        subscriptionActive: false,
      };
    } catch (dbError) {
      // Both Redis and DB failed — fail-open: allow service access
      console.error(
        "[SuspensionMiddleware] Redis AND DB both failed, failing open (isSuspended=false):",
        dbError,
      );
      logger.error(
        { error: dbError },
        "DB fallback also failed in checkServiceSuspension, failing open",
      );

      return {
        isSuspended: false,
        reason: "suspension_check_error",
        requiresBillingSetup: false,
        trialCompleted: false,
        subscriptionActive: false,
      };
    }
  }
}

/**
 * Check suspension status by shop domain (for webhook endpoints)
 */
export async function checkServiceSuspensionByDomain(
  shopDomain: string,
): Promise<SuspensionStatus> {
  try {
    const shop = await prisma.shops.findUnique({
      where: { shop_domain: shopDomain },
      select: { id: true },
    });

    if (!shop) {
      return {
        isSuspended: true,
        reason: "shop_not_found",
        requiresBillingSetup: false,
        trialCompleted: false,
        subscriptionActive: false,
      };
    }

    return await checkServiceSuspension(shop.id);
  } catch (error) {
    console.error(
      "[SuspensionMiddleware] Error checking suspension by domain, failing open:",
      error,
    );
    logger.error(
      { error, shopDomain },
      "Error checking suspension status by domain, failing open",
    );

    // Fail-open: allow service access on error
    return {
      isSuspended: false,
      reason: "suspension_check_error",
      requiresBillingSetup: false,
      trialCompleted: false,
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
  } catch (error) {
    logger.error({ error }, "Error invalidating suspension cache for shop");
  }
}
