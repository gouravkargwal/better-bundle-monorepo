import type {
  BillingState,
  TrialData,
  SubscriptionData,
} from "../types/billing.types";
import prisma from "../../../db.server";

export class BillingService {
  /**
   * ✅ CORRECT: Get billing state - Clean architecture implementation
   */
  static async getBillingState(
    shopId: string,
    admin?: any,
  ): Promise<BillingState> {
    try {
      // 1. Get trial revenue (single source of truth)
      const trialRevenue = await this.getTrialRevenue(shopId);

      // 2. Get trial threshold (from any subscription record or default)
      const subscription = await prisma.shop_subscriptions.findFirst({
        where: { shop_id: shopId },
        include: { subscription_trials: true },
      });
      const trialThreshold = Number(
        subscription?.subscription_trials?.threshold_amount || 75,
      );

      // 3. Simple logic: If trial not completed, show trial
      if (trialRevenue < trialThreshold) {
        return {
          status: "trial_active",
          trialData: await this.getTrialDataFromRevenue(
            shopId,
            trialRevenue,
            trialThreshold,
          ),
        };
      }

      // 4. Trial completed - check if Shopify subscription exists and is active
      if (admin) {
        const shopifyStatus = await this.getShopifySubscriptionStatus(
          shopId,
          admin,
        );

        if (shopifyStatus?.status === "ACTIVE") {
          return {
            status: "subscription_active",
            subscriptionData: await this.getSubscriptionDataFromShopify(
              subscription,
              shopifyStatus,
            ),
          };
        } else if (shopifyStatus?.status === "PENDING") {
          return {
            status: "subscription_pending",
            subscriptionData: await this.getSubscriptionDataFromShopify(
              subscription,
              shopifyStatus,
            ),
          };
        }
      }

      // 5. Trial completed, no active Shopify subscription = show setup button
      return {
        status: "trial_completed",
        trialData: await this.getTrialDataFromRevenue(
          shopId,
          trialRevenue,
          trialThreshold,
        ),
      };
    } catch (error) {
      console.error("Error getting billing state:", error);
      return {
        status: "trial_active",
        error: {
          code: "BILLING_ERROR",
          message: "Failed to get billing state",
        },
      };
    }
  }

  /**
   * ✅ Simplified: Get trial revenue from commission records
   */
  private static async getTrialRevenue(shopId: string): Promise<number> {
    const result = await prisma.commission_records.aggregate({
      where: {
        shop_id: shopId,
        billing_phase: "TRIAL",
        status: {
          in: ["TRIAL_PENDING", "TRIAL_COMPLETED"],
        },
      },
      _sum: {
        attributed_revenue: true,
      },
    });
    return Number(result._sum?.attributed_revenue || 0);
  }

  /**
   * ✅ Simplified: Get trial data from revenue (no complex status checks)
   */
  private static async getTrialDataFromRevenue(
    shopId: string,
    revenue: number,
    threshold: number = 75,
  ): Promise<TrialData> {
    const progress = Math.min((revenue / threshold) * 100, 100);

    // Get shop currency from database
    const shop = await prisma.shops.findUnique({
      where: { id: shopId },
      select: { currency_code: true },
    });

    return {
      isActive: revenue < threshold,
      thresholdAmount: threshold,
      accumulatedRevenue: revenue,
      progress: Math.round(progress),
      currency: shop?.currency_code || "USD",
    };
  }

  /**
   * ✅ Simplified: Get subscription data from Shopify API
   */
  private static async getSubscriptionDataFromShopify(
    shopSubscription: any,
    shopifyStatus: any,
  ): Promise<SubscriptionData> {
    const spendingLimit =
      shopifyStatus.cappedAmount ||
      Number(shopSubscription.user_chosen_cap_amount || 0);
    const currentUsage = shopifyStatus.currentUsage || 0;
    const usagePercentage =
      spendingLimit > 0 ? Math.round((currentUsage / spendingLimit) * 100) : 0;

    return {
      id: shopifyStatus.subscriptionId || shopSubscription.id,
      status: shopifyStatus.status as
        | "PENDING"
        | "ACTIVE"
        | "DECLINED"
        | "CANCELLED"
        | "EXPIRED",
      spendingLimit,
      currentUsage,
      usagePercentage,
      confirmationUrl: shopifyStatus.confirmationUrl,
      currency: shopifyStatus.currency || "USD",
    };
  }

  /**
   * Get Shopify subscription status via API - Real-time status checking
   */
  static async getShopifySubscriptionStatus(
    shopId: string,
    admin: any,
  ): Promise<{
    status: string;
    subscriptionId?: string;
    confirmationUrl?: string;
    currentUsage?: number;
    cappedAmount?: number;
    currency?: string;
  } | null> {
    try {
      // Find the Shopify subscription record
      const shopifySub = await prisma.shopify_subscriptions.findFirst({
        where: {
          shop_subscriptions: {
            shop_id: shopId,
          },
        },
        orderBy: {
          created_at: "desc",
        },
      });

      if (!shopifySub?.shopify_subscription_id) {
        return null;
      }

      // Since Shopify GraphQL API doesn't provide direct query for app subscriptions,
      // we'll return data from our database record
      // Real-time status updates come via webhooks

      return {
        status: shopifySub.status,
        subscriptionId: shopifySub.shopify_subscription_id,
        confirmationUrl: shopifySub.confirmation_url || undefined,
        currentUsage: 0, // Will be updated via webhooks
        cappedAmount: 0, // Will be updated via webhooks
        currency: "USD", // Default currency
      };
    } catch (error) {
      console.error("Error getting Shopify subscription status:", error);
      return null;
    }
  }
}
