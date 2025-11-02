import type {
  BillingState,
  TrialData,
  SubscriptionData,
} from "../types/billing.types";
import prisma from "../../../db.server";

export class BillingService {
  static async getBillingState(
    shopId: string,
    admin?: any,
  ): Promise<BillingState> {
    try {
      // 1. Get trial revenue (single source of truth)
      const trialRevenue = await this.getTrialRevenue(shopId);

      // 2. Get trial threshold (from subscription override or pricing tier)
      const subscription = await prisma.shop_subscriptions.findFirst({
        where: { shop_id: shopId },
        include: { pricing_tiers: true },
      });
      const trialThreshold = Number(
        subscription?.trial_threshold_override ||
          subscription?.pricing_tiers?.trial_threshold_amount ||
          75,
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
   * Get real-time Shopify subscription status via GraphQL API
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
      // First, check if we have any subscription records with Shopify subscription ID
      const shopifySub = await prisma.shop_subscriptions.findFirst({
        where: {
          shop_id: shopId,
          shopify_subscription_id: { not: null },
        },
        orderBy: {
          created_at: "desc",
        },
      });

      if (!shopifySub?.shopify_subscription_id) {
        // No subscription exists, check for active subscriptions via currentAppInstallation
        const currentInstallationQuery = `
        query {
          currentAppInstallation {
            activeSubscriptions {
              id
              name
              status
              test
              currentPeriodEnd
              lineItems {
                plan {
                  pricingDetails {
                    ... on AppUsagePricing {
                      cappedAmount {
                        amount
                        currencyCode
                      }
                      balanceUsed {
                        amount
                        currencyCode
                      }
                      terms
                    }
                    ... on AppRecurringPricing {
                      price {
                        amount
                        currencyCode
                      }
                      interval
                    }
                  }
                }
              }
            }
          }
        }
      `;

        const response = await admin.graphql(currentInstallationQuery);
        const data = await response.json();

        if (
          data.data?.currentAppInstallation?.activeSubscriptions?.length > 0
        ) {
          const subscription =
            data.data.currentAppInstallation.activeSubscriptions[0];
          const lineItem = subscription.lineItems[0];
          const pricingDetails = lineItem?.plan?.pricingDetails;

          return {
            status: subscription.status,
            subscriptionId: subscription.id,
            currentUsage: pricingDetails?.balanceUsed?.amount || 0,
            cappedAmount: pricingDetails?.cappedAmount?.amount || 0,
            currency:
              pricingDetails?.cappedAmount?.currencyCode ||
              pricingDetails?.price?.currencyCode ||
              "USD",
          };
        }

        return null;
      }

      // Query specific subscription by ID for real-time status
      const subscriptionQuery = `
      query($id: ID!) {
        node(id: $id) {
          ... on AppSubscription {
            id
            name
            status
            test
            currentPeriodEnd
            lineItems {
              plan {
                pricingDetails {
                  ... on AppUsagePricing {
                    cappedAmount {
                      amount
                      currencyCode
                    }
                    balanceUsed {
                      amount
                      currencyCode
                    }
                    terms
                  }
                  ... on AppRecurringPricing {
                    price {
                      amount
                      currencyCode
                    }
                    interval
                  }
                }
              }
            }
          }
        }
      }
    `;

      const response = await admin.graphql(subscriptionQuery, {
        variables: {
          id: shopifySub.shopify_subscription_id,
        },
      });

      const data = await response.json();

      if (data.errors) {
        console.error("GraphQL errors:", data.errors);
        return null;
      }

      const subscription = data.data?.node;
      if (!subscription) {
        return null;
      }

      const lineItem = subscription.lineItems[0];
      const pricingDetails = lineItem?.plan?.pricingDetails;

      return {
        status: subscription.status,
        subscriptionId: subscription.id,
        currentUsage: pricingDetails?.balanceUsed?.amount || 0,
        cappedAmount: pricingDetails?.cappedAmount?.amount || 0,
        currency:
          pricingDetails?.cappedAmount?.currencyCode ||
          pricingDetails?.price?.currencyCode ||
          "USD",
      };
    } catch (error) {
      console.error("Error getting Shopify subscription status:", error);
      return null;
    }
  }
}
