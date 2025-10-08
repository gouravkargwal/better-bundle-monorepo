import prisma from "../db.server";

export interface TrialRevenueData {
  attributedRevenue: number;
  commissionEarned: number;
}

export interface CurrentCycleMetrics {
  purchases: { count: number; total: number };
  net_revenue: number;
  commission: number;
  final_commission: number;
  capped_amount: number;
  days_remaining: number;
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
    commission_rate: number;
  };
  trial?: {
    status: string;
    threshold: number;
    accumulated_revenue: number;
    progress_percentage: number;
  };
  current_cycle?: {
    id: string;
    cycle_number: number;
    usage_amount: number;
    current_cap: number;
    usage_percentage: number;
    days_remaining: number;
  };
  shopify_subscription?: {
    status: string;
    shopify_id: string;
  };
}

/**
 * Get trial revenue data for a shop
 */
export async function getTrialRevenueData(
  shopId: string,
): Promise<TrialRevenueData> {
  try {
    // Get shop subscription
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopId,
        is_active: true,
      },
      include: {
        subscription_trials: true,
      },
    });

    if (!shopSubscription?.subscription_trials) {
      return {
        attributedRevenue: 0,
        commissionEarned: 0,
      };
    }

    const trial = shopSubscription.subscription_trials;

    return {
      attributedRevenue: Number(trial.accumulated_revenue),
      commissionEarned: Number(trial.commission_saved),
    };
  } catch (error) {
    console.error(
      `Error getting trial revenue data for shop ${shopId}:`,
      error,
    );
    throw error;
  }
}

/**
 * Get usage revenue data for a shop (paid phase)
 */
export async function getUsageRevenueData(
  shopId: string,
): Promise<TrialRevenueData> {
  try {
    // Get current billing cycle
    const currentCycle = await prisma.billing_cycles.findFirst({
      where: {
        shop_subscriptions: {
          shop_id: shopId,
          is_active: true,
        },
        status: "ACTIVE",
      },
    });

    if (!currentCycle) {
      return {
        attributedRevenue: 0,
        commissionEarned: 0,
      };
    }

    // Get commission records for current cycle
    const aggregate = await prisma.commission_records.aggregate({
      where: {
        shop_id: shopId,
        billing_cycle_id: currentCycle.id,
        billing_phase: "PAID",
        status: "recorded",
      },
      _sum: {
        attributed_revenue: true,
        commission_earned: true,
      },
    });

    return {
      attributedRevenue: Number(aggregate._sum?.attributed_revenue || 0),
      commissionEarned: Number(aggregate._sum?.commission_earned || 0),
    };
  } catch (error) {
    console.error(
      `Error getting usage revenue data for shop ${shopId}:`,
      error,
    );
    throw error;
  }
}

/**
 * Get current cycle metrics for a shop
 */
export async function getCurrentCycleMetrics(
  shopId: string,
  shopSubscription: any,
): Promise<CurrentCycleMetrics> {
  try {
    // Get current billing cycle
    const currentCycle = await prisma.billing_cycles.findFirst({
      where: {
        shop_subscription_id: shopSubscription.id,
        status: "ACTIVE",
      },
    });

    if (!currentCycle) {
      return {
        purchases: { count: 0, total: 0 },
        net_revenue: 0,
        commission: 0,
        final_commission: 0,
        capped_amount: Number(shopSubscription.user_chosen_cap_amount || 1000),
        days_remaining: 0,
      };
    }

    // Get commission records for current cycle
    const commissionRecords = await prisma.commission_records.findMany({
      where: {
        shop_id: shopId,
        billing_cycle_id: currentCycle.id,
        billing_phase: "PAID",
      },
    });

    // Calculate metrics
    const purchases = commissionRecords.filter(
      (r) => r.status === "recorded" || r.status === "invoiced",
    );

    const purchasesCount = purchases.length;
    const purchasesTotal = purchases.reduce(
      (sum, r) => sum + Number(r.attributed_revenue || 0),
      0,
    );

    const netRevenue = purchasesTotal;
    const commission = netRevenue * 0.03; // 3% commission
    const finalCommission = Math.min(
      commission,
      Number(currentCycle.current_cap_amount),
    );

    // Calculate days remaining
    const now = new Date();
    const daysRemaining = Math.max(
      0,
      Math.ceil(
        (currentCycle.end_date.getTime() - now.getTime()) /
          (1000 * 60 * 60 * 24),
      ),
    );

    return {
      purchases: { count: purchasesCount, total: purchasesTotal },
      net_revenue: netRevenue,
      commission: commission,
      final_commission: finalCommission,
      capped_amount: Number(currentCycle.current_cap_amount),
      days_remaining: daysRemaining,
    };
  } catch (error) {
    console.error("Error fetching current cycle metrics:", error);
    return {
      purchases: { count: 0, total: 0 },
      net_revenue: 0,
      commission: 0,
      final_commission: 0,
      capped_amount: Number(
        shopSubscription.pricing_tier?.trial_threshold_amount || 1000,
      ),
      days_remaining: 0,
    };
  }
}

/**
 * Get comprehensive billing summary for a shop using new schema
 */
export async function getBillingSummary(
  shopId: string,
): Promise<BillingSummary | null> {
  try {
    // Get shop subscription with all related data
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopId,
        is_active: true,
      },
      include: {
        subscription_plans: true,
        pricing_tiers: true,
        subscription_trials: true,
        billing_cycles: {
          where: { status: "ACTIVE" },
          orderBy: { cycle_number: "desc" },
          take: 1,
        },
        shopify_subscriptions: true,
      },
    });

    if (!shopSubscription) {
      return null;
    }

    const currentCycle = shopSubscription.billing_cycles[0];
    const trial = shopSubscription.subscription_trials;
    const shopifySub = shopSubscription.shopify_subscriptions;

    return {
      shop_id: shopId,
      subscription: {
        id: shopSubscription.id,
        status: shopSubscription.status,
        start_date: shopSubscription.start_date.toISOString(),
        plan_name: shopSubscription.subscription_plans?.name || "Unknown",
      },
      pricing_tier: {
        currency: shopSubscription.pricing_tiers?.currency,
        commission_rate: Number(
          shopSubscription.pricing_tiers?.commission_rate || 0.03,
        ),
      },
      trial: trial
        ? {
            status: trial.status,
            threshold: Number(trial.threshold_amount),
            accumulated_revenue: Number(trial.accumulated_revenue),
            progress_percentage: 0, // Calculate based on accumulated_revenue / threshold_amount
          }
        : undefined,
      current_cycle: currentCycle
        ? {
            id: currentCycle.id,
            cycle_number: currentCycle.cycle_number,
            usage_amount: Number(currentCycle.usage_amount),
            current_cap: Number(currentCycle.current_cap_amount),
            usage_percentage: 0, // Calculate based on usage_amount / current_cap_amount
            days_remaining: 0, // Calculate based on end_date - now
          }
        : undefined,
      shopify_subscription: shopifySub
        ? {
            status: shopifySub.status,
            shopify_id: shopifySub.shopify_subscription_id,
          }
        : undefined,
    };
  } catch (error) {
    console.error(`Error getting billing summary for shop ${shopId}:`, error);
    return null;
  }
}

/**
 * Create a new shop subscription (when shop installs)
 */
export async function createShopSubscription(
  shopId: string,
  shopDomain: string,
): Promise<any> {
  try {
    // Get default subscription plan
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

    // Create shop subscription
    const shopSubscription = await prisma.shop_subscriptions.create({
      data: {
        shop_id: shopId,
        subscription_plan_id: defaultPlan.id,
        pricing_tier_id: defaultPricingTier.id,
        status: "TRIAL",
        start_date: new Date(),
        is_active: true,
        auto_renew: true,
        user_chosen_cap_amount: defaultPricingTier.trial_threshold_amount,
      },
    });

    // Create subscription trial
    const subscriptionTrial = await prisma.subscription_trials.create({
      data: {
        shop_subscription_id: shopSubscription.id,
        threshold_amount: defaultPricingTier.trial_threshold_amount,
        accumulated_revenue: 0,
        commission_saved: 0,
        status: "ACTIVE",
        started_at: new Date(),
      },
    });

    return {
      shop_subscription: shopSubscription,
      subscription_trial: subscriptionTrial,
    };
  } catch (error) {
    console.error(
      `Error creating shop subscription for shop ${shopId}:`,
      error,
    );
    throw error;
  }
}

/**
 * Complete trial and create first billing cycle
 */
export async function completeTrialAndCreateCycle(
  shopId: string,
): Promise<any> {
  try {
    // Get shop subscription
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopId,
        is_active: true,
      },
      include: {
        pricing_tiers: true,
        subscription_trials: true,
      },
    });

    if (!shopSubscription) {
      throw new Error("Shop subscription not found");
    }

    // Update trial status
    await prisma.subscription_trials.update({
      where: { id: shopSubscription.subscription_trials!.id },
      data: {
        status: "completed",
        completed_at: new Date(),
      },
    });

    // Update shop subscription status
    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        status: "pending_approval",
      },
    });

    return {
      success: true,
      message: "Trial completed, subscription pending approval",
    };
  } catch (error) {
    console.error(`Error completing trial for shop ${shopId}:`, error);
    throw error;
  }
}

/**
 * Activate subscription and create first billing cycle
 */
export async function activateSubscription(
  shopId: string,
  shopifySubscriptionId: string,
): Promise<any> {
  try {
    // Get shop subscription
    const shopSubscription = await prisma.shop_subscriptions.findFirst({
      where: {
        shop_id: shopId,
        is_active: true,
      },
      select: {
        id: true,
        user_chosen_cap_amount: true,
        pricing_tiers: true,
      },
    });

    if (!shopSubscription) {
      throw new Error("Shop subscription not found");
    }

    // Create or update Shopify subscription record
    const shopifySubscription = await prisma.shopify_subscriptions.upsert({
      where: {
        shopify_subscription_id: shopifySubscriptionId,
      },
      update: {
        status: "ACTIVE",
        activated_at: new Date(),
        error_count: "0",
      },
      create: {
        shop_subscription_id: shopSubscription.id,
        shopify_subscription_id: shopifySubscriptionId,
        status: "ACTIVE",
        created_at: new Date(),
        activated_at: new Date(),
        error_count: "0",
      },
    });

    // Update shop subscription status
    await prisma.shop_subscriptions.update({
      where: { id: shopSubscription.id },
      data: {
        status: "ACTIVE",
        activated_at: new Date(),
      },
    });

    // Create first billing cycle using user's chosen cap
    const userChosenCap = shopSubscription.user_chosen_cap_amount || 1000; // Fallback to 1000 if not set
    const billingCycle = await prisma.billing_cycles.create({
      data: {
        shop_subscription_id: shopSubscription.id,
        cycle_number: 1,
        start_date: new Date(),
        end_date: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), // 30 days from now
        initial_cap_amount: userChosenCap,
        current_cap_amount: userChosenCap,
        usage_amount: 0,
        commission_count: 0,
        status: "ACTIVE",
        activated_at: new Date(),
      },
    });

    return {
      success: true,
      shopify_subscription: shopifySubscription,
      billing_cycle: billingCycle,
    };
  } catch (error) {
    console.error(`Error activating subscription for shop ${shopId}:`, error);
    throw error;
  }
}

/**
 * Increase billing cycle cap
 */
export async function increaseBillingCycleCap(
  shopId: string,
  newCapAmount: number,
  adjustedBy: string = "user",
): Promise<any> {
  try {
    // Get current billing cycle
    const currentCycle = await prisma.billing_cycles.findFirst({
      where: {
        shop_subscriptions: {
          shop_id: shopId,
          is_active: true,
        },
        status: "ACTIVE",
      },
    });

    if (!currentCycle) {
      throw new Error("No active billing cycle found");
    }

    const oldCapAmount = currentCycle.current_cap_amount;
    const adjustmentAmount = newCapAmount - Number(oldCapAmount);

    // Create adjustment record
    await prisma.billing_cycle_adjustments.create({
      data: {
        billing_cycle_id: currentCycle.id,
        old_cap_amount: oldCapAmount,
        new_cap_amount: newCapAmount,
        adjustment_amount: adjustmentAmount,
        adjustment_reason: "CAP_INCREASE",
        adjusted_by: adjustedBy,
        adjusted_by_type: "user",
        adjusted_at: new Date(),
      },
    });

    // Update billing cycle cap
    await prisma.billing_cycles.update({
      where: { id: currentCycle.id },
      data: {
        current_cap_amount: newCapAmount,
      },
    });

    return {
      success: true,
      message: `Cap increased from $${oldCapAmount} to $${newCapAmount}`,
    };
  } catch (error) {
    console.error(`Error increasing cap for shop ${shopId}:`, error);
    throw error;
  }
}
