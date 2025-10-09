import type {
  BillingState,
  BillingStatus,
  TrialData,
  SubscriptionData,
  BillingSetupData,
  BillingMetrics,
} from "../types/billing.types";
import prisma from "../../../db.server";

export class BillingService {
  /**
   * Get current billing state for a shop
   * This is the single source of truth for billing status
   */
  static async getBillingState(shopId: string): Promise<BillingState> {
    try {
      // Get shop subscription with related data
      const shopSubscription = await prisma.shop_subscriptions.findFirst({
        where: {
          shop_id: shopId,
          is_active: true,
        },
        include: {
          subscription_trials: true,
          shopify_subscriptions: true,
          billing_cycles: {
            where: { status: "ACTIVE" },
            orderBy: { cycle_number: "desc" },
            take: 1,
          },
        },
      });

      if (!shopSubscription) {
        return {
          status: "trial_active", // Default to trial if no subscription
          error: {
            code: "NO_SUBSCRIPTION",
            message: "No subscription found",
          },
        };
      }

      // ✅ Determine billing status dynamically based on actual data
      const status = await this.determineBillingStatus(shopSubscription);

      const state: BillingState = {
        status,
      };

      // Add trial data if trial is active or completed
      if (status === "trial_active" || status === "trial_completed") {
        state.trialData = await this.getTrialData(shopSubscription);
      }

      // Add subscription data if subscription exists
      if (
        status === "subscription_pending" ||
        status === "subscription_active"
      ) {
        state.subscriptionData =
          await this.getSubscriptionData(shopSubscription);
      }

      return state;
    } catch (error) {
      console.error("Error getting billing state:", error);
      return {
        status: "trial_active",
        error: {
          code: "FETCH_ERROR",
          message: "Failed to load billing information",
        },
      };
    }
  }

  /**
   * ✅ Determine billing status dynamically based on actual data
   * Never rely on pre-computed database fields
   */
  private static async determineBillingStatus(
    shopSubscription: any,
  ): Promise<BillingStatus> {
    const dbStatus = shopSubscription.status;

    // For trial-related statuses, check actual revenue data
    if (dbStatus === "TRIAL" || dbStatus === "TRIAL_COMPLETED") {
      // Get actual attributed revenue from commission records
      const actualRevenue = await prisma.commission_records.aggregate({
        where: {
          shop_id: shopSubscription.shop_id,
          billing_phase: "TRIAL",
          status: {
            in: ["TRIAL_PENDING", "TRIAL_COMPLETED"],
          },
        },
        _sum: {
          attributed_revenue: true,
        },
      });

      const actualAccumulatedRevenue = Number(
        actualRevenue._sum?.attributed_revenue || 0,
      );
      const thresholdAmount = Number(
        shopSubscription.subscription_trials?.threshold_amount || 0,
      );

      // ✅ Determine status based on ACTUAL data, not stored values
      if (actualAccumulatedRevenue >= thresholdAmount) {
        return "trial_completed";
      } else {
        return "trial_active";
      }
    }

    // For other statuses, use the existing mapping
    switch (dbStatus) {
      case "PENDING_APPROVAL":
        return "subscription_pending";
      case "ACTIVE":
        return "subscription_active";
      case "SUSPENDED":
        return "subscription_suspended";
      case "CANCELLED":
        return "subscription_cancelled";
      default:
        return "trial_active";
    }
  }

  /**
   * Get trial data for display
   */
  private static async getTrialData(shopSubscription: any): Promise<TrialData> {
    const trial = shopSubscription.subscription_trials;

    if (!trial) {
      return {
        isActive: false,
        thresholdAmount: 0,
        accumulatedRevenue: 0,
        progress: 0,
        currency: "USD",
      };
    }

    // ✅ ALWAYS calculate from source data - never use pre-computed values
    const actualRevenue = await prisma.commission_records.aggregate({
      where: {
        shop_id: shopSubscription.shop_id,
        billing_phase: "TRIAL",
        status: {
          in: ["TRIAL_PENDING", "TRIAL_COMPLETED"],
        },
      },
      _sum: {
        attributed_revenue: true,
      },
    });

    const actualAccumulatedRevenue = Number(
      actualRevenue._sum?.attributed_revenue || 0,
    );
    const thresholdAmount = Number(trial.threshold_amount);

    // ✅ Check if trial should be completed based on ACTUAL data
    const hasExceededThreshold = actualAccumulatedRevenue >= thresholdAmount;
    const progress = Math.min(
      (actualAccumulatedRevenue / thresholdAmount) * 100,
      100,
    );

    return {
      isActive: trial.status === "ACTIVE" && !hasExceededThreshold,
      thresholdAmount: thresholdAmount,
      accumulatedRevenue: actualAccumulatedRevenue, // ✅ Always fresh data
      progress: Math.round(progress),
      currency: "USD", // TODO: Get from shop
    };
  }

  /**
   * Get subscription data for display
   */
  private static async getSubscriptionData(
    shopSubscription: any,
  ): Promise<SubscriptionData> {
    const shopifySub = shopSubscription.shopify_subscriptions;
    const currentCycle = shopSubscription.billing_cycles[0];

    return {
      id: shopSubscription.id,
      status: shopifySub?.status || "pending",
      spendingLimit: Number(shopSubscription.user_chosen_cap_amount || 0),
      currentUsage: currentCycle ? Number(currentCycle.usage_amount) : 0,
      usagePercentage: currentCycle
        ? Math.round(
            (Number(currentCycle.usage_amount) /
              Number(currentCycle.current_cap_amount)) *
              100,
          )
        : 0,
      confirmationUrl: shopifySub?.confirmation_url,
      currency: "USD", // TODO: Get from shop
      billingCycle: currentCycle
        ? {
            startDate: currentCycle.start_date.toISOString(),
            endDate: currentCycle.end_date.toISOString(),
            cycleNumber: currentCycle.cycle_number,
          }
        : undefined,
    };
  }

  /**
   * Setup billing - transition from trial_completed to subscription_pending
   */
  static async setupBilling(
    shopId: string,
    setupData: BillingSetupData,
  ): Promise<{
    success: boolean;
    confirmationUrl?: string;
    error?: string;
  }> {
    try {
      // This will be handled by the existing API route
      // We'll call it from here for consistency
      const response = await fetch("/api/billing/setup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          monthlyCap: setupData.spendingLimit,
        }),
      });

      const result = await response.json();

      if (result.success) {
        return {
          success: true,
          confirmationUrl: result.confirmation_url,
        };
      } else {
        return {
          success: false,
          error: result.error,
        };
      }
    } catch (error) {
      console.error("Error setting up billing:", error);
      return {
        success: false,
        error: "Failed to setup billing",
      };
    }
  }

  /**
   * Get billing metrics for dashboard
   */
  static async getBillingMetrics(shopId: string): Promise<BillingMetrics> {
    try {
      // Get commission records for current billing cycle
      const currentCycle = await prisma.billing_cycles.findFirst({
        where: {
          shop_subscriptions: {
            shop_id: shopId,
            is_active: true,
          },
          status: "ACTIVE",
        },
        include: {
          commission_records: true,
        },
      });

      if (!currentCycle) {
        return {
          totalRevenue: 0,
          attributedRevenue: 0,
          commissionEarned: 0,
          commissionRate: 0,
          currency: "USD",
        };
      }

      const totalRevenue = currentCycle.commission_records.reduce(
        (sum, record) => sum + Number(record.attributed_revenue),
        0,
      );

      const commissionEarned = currentCycle.commission_records.reduce(
        (sum, record) => sum + Number(record.commission_earned),
        0,
      );

      return {
        totalRevenue,
        attributedRevenue: totalRevenue,
        commissionEarned,
        commissionRate:
          totalRevenue > 0 ? (commissionEarned / totalRevenue) * 100 : 0,
        currency: "USD",
      };
    } catch (error) {
      console.error("Error getting billing metrics:", error);
      return {
        totalRevenue: 0,
        attributedRevenue: 0,
        commissionEarned: 0,
        commissionRate: 0,
        currency: "USD",
      };
    }
  }
}
