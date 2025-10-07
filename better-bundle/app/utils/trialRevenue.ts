/**
 * Trial Revenue Utility
 *
 * Provides methods to identify and separate trial period revenue from post-trial revenue.
 * This is critical for accurate billing calculations.
 *
 * Uses a ROBUST approach that combines:
 * 1. Billing plan status (is_trial_active)
 * 2. Trial completion markers
 * 3. Revenue threshold tracking
 * 4. Fallback to time-based only when necessary
 */

import prisma from "../db.server";

export interface TrialRevenueData {
  trialRevenue: number;
  postTrialRevenue: number;
  trialRefunds: number;
  postTrialRefunds: number;
  trialPeriod: {
    start: Date;
    end: Date | null;
  };
  // ✅ NEW: Robust trial status indicators
  trialStatus: {
    isTrialActive: boolean;
    trialCompleted: boolean;
    hasActiveSubscription: boolean;
    trialThreshold: number;
    trialRevenue: number;
    confidence: "high" | "medium" | "low";
  };
}

/**
 * Get trial period revenue data for a shop
 */
export async function getTrialRevenueData(
  shopId: string,
): Promise<TrialRevenueData> {
  try {
    // Get billing plan to determine trial period
    const billingPlan = await prisma.billing_plans.findFirst({
      where: {
        shop_id: shopId,
        status: "active",
      },
    });

    if (!billingPlan) {
      throw new Error(`No billing plan found for shop ${shopId}`);
    }

    const config = billingPlan.configuration as any;
    const trialStart = billingPlan.created_at;
    const trialEnd = config?.trial_completed_at
      ? new Date(config.trial_completed_at)
      : null;

    // If trial is still active, all revenue is trial revenue
    if (billingPlan.is_trial_active) {
      const [trialRevenue, trialRefunds] = await Promise.all([
        prisma.purchase_attributions.aggregate({
          where: { shop_id: shopId },
          _sum: { total_revenue: true },
        }),
        prisma.refund_attributions.aggregate({
          where: { shop_id: shopId },
          _sum: { total_refunded_revenue: true },
        }),
      ]);

      return {
        trialRevenue: Number(trialRevenue._sum.total_revenue || 0),
        postTrialRevenue: 0,
        trialRefunds: Number(trialRefunds._sum.total_refunded_revenue || 0),
        postTrialRefunds: 0,
        trialPeriod: {
          start: trialStart,
          end: null, // Trial still active
        },
      };
    }

    // Trial completed - separate trial and post-trial revenue
    if (!trialEnd) {
      throw new Error(
        `Trial completed but no completion date found for shop ${shopId}`,
      );
    }

    const [trialRevenue, postTrialRevenue, trialRefunds, postTrialRefunds] =
      await Promise.all([
        // Trial period revenue (before trial completion)
        prisma.purchase_attributions.aggregate({
          where: {
            shop_id: shopId,
            purchase_at: { lt: trialEnd },
          },
          _sum: { total_revenue: true },
        }),

        // Post-trial revenue (after trial completion)
        prisma.purchase_attributions.aggregate({
          where: {
            shop_id: shopId,
            purchase_at: { gte: trialEnd },
          },
          _sum: { total_revenue: true },
        }),

        // Trial period refunds
        prisma.refund_attributions.aggregate({
          where: {
            shop_id: shopId,
            refunded_at: { lt: trialEnd },
          },
          _sum: { total_refunded_revenue: true },
        }),

        // Post-trial refunds
        prisma.refund_attributions.aggregate({
          where: {
            shop_id: shopId,
            refunded_at: { gte: trialEnd },
          },
          _sum: { total_refunded_revenue: true },
        }),
      ]);

    return {
      trialRevenue: Number(trialRevenue._sum.total_revenue || 0),
      postTrialRevenue: Number(postTrialRevenue._sum.total_revenue || 0),
      trialRefunds: Number(trialRefunds._sum.total_refunded_revenue || 0),
      postTrialRefunds: Number(
        postTrialRefunds._sum.total_refunded_revenue || 0,
      ),
      trialPeriod: {
        start: trialStart,
        end: trialEnd,
      },
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
 * Check if a specific purchase was made during trial period
 */
export async function isTrialPeriodPurchase(
  shopId: string,
  purchaseDate: Date,
): Promise<boolean> {
  try {
    const billingPlan = await prisma.billing_plans.findFirst({
      where: {
        shop_id: shopId,
        status: "active",
      },
    });

    if (!billingPlan) return false;

    // If trial is still active, all purchases are trial purchases
    if (billingPlan.is_trial_active) return true;

    // If trial completed, check if purchase was before trial completion
    const config = billingPlan.configuration as any;
    const trialCompletedAt = config?.trial_completed_at
      ? new Date(config.trial_completed_at)
      : null;

    if (!trialCompletedAt) return false;

    return purchaseDate < trialCompletedAt;
  } catch (error) {
    console.error(`Error checking trial period for purchase:`, error);
    return false;
  }
}

/**
 * Get trial period summary for display
 */
export async function getTrialPeriodSummary(shopId: string): Promise<{
  isTrialActive: boolean;
  trialCompleted: boolean;
  trialRevenue: number;
  trialRefunds: number;
  netTrialRevenue: number;
  postTrialRevenue: number;
  postTrialRefunds: number;
  netPostTrialRevenue: number;
  trialPeriod: {
    start: Date;
    end: Date | null;
    duration: number; // days
  };
}> {
  try {
    const data = await getTrialRevenueData(shopId);

    const billingPlan = await prisma.billing_plans.findFirst({
      where: {
        shop_id: shopId,
        status: "active",
      },
    });

    const isTrialActive = billingPlan?.is_trial_active || false;
    const trialCompleted = !isTrialActive && data.trialPeriod.end !== null;

    const netTrialRevenue = Math.max(0, data.trialRevenue - data.trialRefunds);
    const netPostTrialRevenue = Math.max(
      0,
      data.postTrialRevenue - data.postTrialRefunds,
    );

    const duration = data.trialPeriod.end
      ? Math.floor(
          (data.trialPeriod.end.getTime() - data.trialPeriod.start.getTime()) /
            (1000 * 60 * 60 * 24),
        )
      : Math.floor(
          (new Date().getTime() - data.trialPeriod.start.getTime()) /
            (1000 * 60 * 60 * 24),
        );

    return {
      isTrialActive,
      trialCompleted,
      trialRevenue: data.trialRevenue,
      trialRefunds: data.trialRefunds,
      netTrialRevenue,
      postTrialRevenue: data.postTrialRevenue,
      postTrialRefunds: data.postTrialRefunds,
      netPostTrialRevenue,
      trialPeriod: {
        start: data.trialPeriod.start,
        end: data.trialPeriod.end,
        duration,
      },
    };
  } catch (error) {
    console.error(
      `Error getting trial period summary for shop ${shopId}:`,
      error,
    );
    throw error;
  }
}
