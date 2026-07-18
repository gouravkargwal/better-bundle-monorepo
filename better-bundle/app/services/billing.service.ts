import prisma from "../db.server";
import logger from "../utils/logger";
import { invalidateSuspensionCache } from "../middleware/serviceSuspension";

export interface TrialData {
  daysRemaining: number;
  trialDays: number;
  isExpired: boolean;
}

export interface BillingSummary {
  shop_id: string;
  subscription: {
    id: string;
    status: string;
    start_date: string;
    plan_name: string;
  };
  pricing_tier: {
    currency: string;
    monthly_fee: number;
  };
  trial?: {
    days_remaining: number;
    total_days: number;
    is_expired: boolean;
  };
  current_cycle?: {
    id: string;
    cycle_number: number;
    start_date: string;
    end_date: string;
    days_remaining: number;
  };
  shopify_subscription?: {
    status: string;
    shopify_id: string;
  };
}

/**
 * Get trial days remaining for a shop
 */
export async function getTrialData(shopId: string): Promise<TrialData> {
  try {
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopId,
        is_active: true,
        subscription_type: "TRIAL",
        status: "TRIAL",
      },
      include: {
        pricing_tiers: true,
      },
    });

    if (!shopSubscription || !shopSubscription.started_at) {
      return { daysRemaining: 0, trialDays: 14, isExpired: false };
    }

    const trialDays =
      shopSubscription.trial_duration_days ||
      shopSubscription.pricing_tiers?.trial_days ||
      14;

    const trialEnd = new Date(
      shopSubscription.started_at.getTime() + trialDays * 24 * 60 * 60 * 1000,
    );
    const now = new Date();
    const daysRemaining = Math.max(
      0,
      Math.ceil((trialEnd.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)),
    );

    return {
      daysRemaining,
      trialDays,
      isExpired: daysRemaining <= 0,
    };
  } catch (error) {
    logger.error({ error, shopId }, "Error getting trial data");
    return { daysRemaining: 0, trialDays: 14, isExpired: false };
  }
}

/**
 * Get billing summary for a shop (flat fee)
 */
export async function getBillingSummary(
  shopId: string,
): Promise<BillingSummary | null> {
  try {
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopId,
        is_active: true,
      },
      include: {
        subscription_plans: true,
        pricing_tiers: true,
        billing_cycles: {
          where: { status: "ACTIVE" },
          orderBy: { cycle_number: "desc" },
          take: 1,
        },
      },
    });

    if (!shopSubscription) {
      return null;
    }

    const currentCycle = shopSubscription.billing_cycles[0];

    return {
      shop_id: shopId,
      subscription: {
        id: shopSubscription.id,
        status: shopSubscription.status,
        start_date: shopSubscription.started_at.toISOString(),
        plan_name: shopSubscription.subscription_plans?.name || "Unknown",
      },
      pricing_tier: {
        currency: shopSubscription.pricing_tiers?.currency || "USD",
        monthly_fee: Number(
          shopSubscription.pricing_tiers?.monthly_fee || 29.0,
        ),
      },
      trial:
        shopSubscription.subscription_type === "TRIAL"
          ? (() => {
              // Compute trial days remaining in TypeScript (trial_remaining_days is a Python @property, not a DB column)
              const trialTotalDays =
                shopSubscription.trial_duration_days ||
                shopSubscription.pricing_tiers?.trial_days ||
                14;
              let daysRemaining = 0;
              if (shopSubscription.started_at) {
                const trialEnd = new Date(
                  shopSubscription.started_at.getTime() +
                    trialTotalDays * 24 * 60 * 60 * 1000,
                );
                daysRemaining = Math.max(
                  0,
                  Math.ceil(
                    (trialEnd.getTime() - Date.now()) /
                      (1000 * 60 * 60 * 24),
                  ),
                );
              }
              return {
                days_remaining: daysRemaining,
                total_days: trialTotalDays,
                is_expired: daysRemaining <= 0,
              };
            })()
          : undefined,
      current_cycle: currentCycle
        ? {
            id: currentCycle.id,
            cycle_number: currentCycle.cycle_number,
            start_date: currentCycle.start_date.toISOString(),
            end_date: currentCycle.end_date.toISOString(),
            days_remaining: Math.max(
              0,
              Math.ceil(
                (currentCycle.end_date.getTime() - Date.now()) /
                  (1000 * 60 * 60 * 24),
              ),
            ),
          }
        : undefined,
      shopify_subscription: shopSubscription.shopify_subscription_id
        ? {
            status: shopSubscription.shopify_status || "UNKNOWN",
            shopify_id: shopSubscription.shopify_subscription_id,
          }
        : undefined,
    };
  } catch (error) {
    logger.error({ error, shopId }, "Error getting billing summary");
    return null;
  }
}

/**
 * Create a new shop subscription (flat fee trial)
 */
export async function createShopSubscription(
  shopId: string,
  shopDomain: string,
): Promise<any> {
  try {
    // Idempotency: return existing active or pending subscription
    const existing = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopId,
        OR: [
          { is_active: true },
          {
            status: {
              in: [
                "TRIAL",
                "PENDING_APPROVAL",
                "ACTIVE",
                "SUSPENDED",
              ] as any,
            },
          },
        ],
      },
      orderBy: { created_at: "desc" },
    });

    if (existing) {
      return { shop_subscription: existing };
    }

    // Get default subscription plan (flat fee)
    const defaultPlan = await prisma.subscription_plans.findFirst({
      where: {
        is_active: true,
        is_default: true,
      },
    });

    if (!defaultPlan) {
      throw new Error("No default subscription plan found");
    }

    // Get default pricing tier for the plan
    const defaultPricingTier = await prisma.pricing_tiers.findFirst({
      where: {
        subscription_plan_id: defaultPlan.id,
        is_active: true,
        is_default: true,
      },
    });

    if (!defaultPricingTier) {
      throw new Error("No default pricing tier found");
    }

    // Create trial subscription with time-based trial
    const shopSubscription = await prisma.shop_subscriptions.create({
      data: {
        shop_id: shopId,
        subscription_plan_id: defaultPlan.id,
        pricing_tier_id: defaultPricingTier.id,
        subscription_type: "TRIAL",
        status: "TRIAL",
        started_at: new Date(),
        is_active: true,
        auto_renew: true,
        trial_duration_days: defaultPricingTier.trial_days || 14,
      },
    });

    return {
      shop_subscription: shopSubscription,
    };
  } catch (error: any) {
    logger.error(
      {
        shopId,
        err: {
          name: error?.name,
          code: error?.code,
          message: error?.message,
          meta: error?.meta,
        },
      },
      "Error creating shop subscription",
    );
    throw error;
  }
}

/**
 * Activate subscription and create first billing cycle (flat fee)
 */
export async function activateSubscription(
  shopId: string,
  shopifySubscriptionId: string,
  monthlyFee?: number,
): Promise<any> {
  try {
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopId,
        is_active: true,
      },
    });

    if (!shopSubscription) {
      throw new Error("Shop subscription not found");
    }

    // Update shop subscription with Shopify subscription info
    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        shopify_subscription_id: shopifySubscriptionId,
        shopify_status: "ACTIVE",
        subscription_type: "PAID",
        status: "ACTIVE",
        updated_at: new Date(),
      },
    });

    // Create first billing cycle with period fee
    const fee =
      monthlyFee ||
      Number(shopSubscription.monthly_fee_override) ||
      29.0;

    const billingCycle = await prisma.billing_cycles.create({
      data: {
        shop_subscription_id: shopSubscription.id,
        cycle_number: 1,
        start_date: new Date(),
        end_date: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000),
        period_fee: fee,
        status: "ACTIVE",
        activated_at: new Date(),
      },
    });

    // Reactivate shop services
    await reactivateShopIfSuspended(shopId);

    return {
      success: true,
      billing_cycle: billingCycle,
    };
  } catch (error) {
    logger.error({ error, shopId }, "Error activating subscription");
    throw error;
  }
}

/**
 * Reactivate shop services if suspended
 */
export async function reactivateShopIfSuspended(shopId: string): Promise<void> {
  try {
    const shop = await prisma.shops.findUnique({
      where: { id: shopId },
      select: { id: true, shop_domain: true, is_active: true },
    });

    if (!shop) {
      logger.warn({ shopId }, "Shop not found");
      return;
    }

    if (!shop.is_active) {
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

      await invalidateSuspensionCache(shopId);
    }
  } catch (error) {
    logger.error({ error, shopId }, "Error reactivating shop");
    throw error;
  }
}
