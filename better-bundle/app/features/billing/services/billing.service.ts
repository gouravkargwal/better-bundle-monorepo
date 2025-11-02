import type {
  BillingState,
  TrialData,
  SubscriptionData,
} from "../types/billing.types";
import prisma from "../../../db.server";
import logger from "app/utils/logger";

export class BillingService {
  static async getBillingState(
    shopId: string,
    admin?: any,
  ): Promise<BillingState> {
    try {
      // 1. Get trial revenue (single source of truth)
      const trialRevenue = await this.getTrialRevenue(shopId);

      // 2. Get trial threshold (from subscription override or pricing tier)
      // Get active subscription (prioritize ACTIVE status, but also check SUSPENDED for cap increases)
      const subscription = await prisma.shop_subscriptions.findFirst({
        where: {
          shop_id: shopId,
          is_active: true,
        },
        include: { pricing_tiers: true },
        orderBy: {
          created_at: "desc", // Get most recent active subscription
        },
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

      // 4. Check subscription status: Always check Shopify GraphQL first (source of truth)
      if (admin) {
        const shopifyStatus = await this.getShopifySubscriptionStatus(
          shopId,
          admin,
        );

        if (shopifyStatus) {
          if (
            shopifyStatus.status === "ACTIVE" ||
            shopifyStatus.status === "PENDING"
          ) {
            // Both ACTIVE and PENDING subscriptions should show as active in our UI
            // PENDING just means awaiting merchant approval
            return {
              status: "subscription_active",
              subscriptionData: await this.getSubscriptionDataFromShopify(
                subscription || {},
                shopifyStatus,
              ),
            };
          }
        }
      } else if (
        subscription &&
        subscription.subscription_type === "PAID" &&
        subscription.shopify_subscription_id
      ) {
        // No admin client, but we have subscription with Shopify ID, assume active
        return {
          status: "subscription_active",
          subscriptionData: await this.getSubscriptionDataFromShopify(
            subscription,
            {
              status: subscription.shopify_status || "ACTIVE",
              subscriptionId: subscription.shopify_subscription_id,
              cappedAmount: Number(subscription.user_chosen_cap_amount || 0),
              currentUsage: 0,
              currency: subscription.pricing_tiers?.currency || "USD",
            },
          ),
        };
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
      logger.error({ error }, "Error getting billing state");
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
    // currentUsage from Shopify is commission amount (usage charged)
    // Calculate percentage: commission / cap
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
      // ALWAYS check GraphQL first (source of truth) when admin is available
      // This ensures we get the real-time status even if DB is out of sync
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

      if (data.errors) {
        console.error(
          "GraphQL errors in activeSubscriptions query:",
          data.errors,
        );
      }

      console.log("[BillingService] GraphQL activeSubscriptions response:", {
        hasData: !!data.data,
        subscriptionCount:
          data.data?.currentAppInstallation?.activeSubscriptions?.length || 0,
        firstSubscription:
          data.data?.currentAppInstallation?.activeSubscriptions?.[0]?.status,
      });

      // If we found active subscriptions via GraphQL, use that
      if (data.data?.currentAppInstallation?.activeSubscriptions?.length > 0) {
        const subscription =
          data.data.currentAppInstallation.activeSubscriptions[0];
        const lineItem = subscription.lineItems[0];
        const pricingDetails = lineItem?.plan?.pricingDetails;

        // Sync with database - find subscription record and update it
        const dbSubscription = await prisma.shop_subscriptions.findFirst({
          where: {
            shop_id: shopId,
            is_active: true,
          },
          orderBy: {
            created_at: "desc",
          },
        });

        if (dbSubscription) {
          try {
            await prisma.shop_subscriptions.update({
              where: { id: dbSubscription.id },
              data: {
                shopify_subscription_id: subscription.id,
                shopify_status: subscription.status,
                subscription_type: "PAID",
                status:
                  subscription.status === "ACTIVE"
                    ? "ACTIVE"
                    : subscription.status === "PENDING"
                      ? "ACTIVE" // PENDING subscriptions should still be shown as ACTIVE in our system
                      : dbSubscription.status,
                updated_at: new Date(),
              },
            });
          } catch (error) {
            console.error(
              "Failed to update subscription with Shopify ID:",
              error,
            );
          }
        }

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

      // If no active subscriptions found, check if we have a subscription ID in DB and query it
      const shopifySub = await prisma.shop_subscriptions.findFirst({
        where: {
          shop_id: shopId,
          is_active: true,
          shopify_subscription_id: { not: null },
        },
        orderBy: {
          created_at: "desc",
        },
      });

      if (!shopifySub?.shopify_subscription_id) {
        // No subscription ID in DB - we already checked GraphQL above, so return null
        return null;
      }

      // We have a subscription ID in DB but it wasn't in activeSubscriptions
      // Query it directly to get its status (might be pending, cancelled, etc.)
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

      const nodeResponse = await admin.graphql(subscriptionQuery, {
        variables: {
          id: shopifySub.shopify_subscription_id,
        },
      });

      const nodeData = await nodeResponse.json();

      if (nodeData.errors) {
        logger.error(
          { errors: nodeData.errors },
          "GraphQL errors in node query",
        );
        return null;
      }

      const subscription = nodeData.data?.node;
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
      logger.error({ error }, "Error getting Shopify subscription status");
      return null;
    }
  }
}
