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
      // 1. Load subscription — single source of truth for trial_revenue and commission_rate
      const subscription = await prisma.shop_subscriptions.findFirst({
        where: {
          shop_id: shopId,
          is_active: true,
        },
        include: { pricing_tiers: true },
        orderBy: { created_at: "desc" },
      });

      const trialRevenue = Number(subscription?.trial_revenue || 0);
      const trialThreshold = Number(
        subscription?.trial_threshold_override ||
          subscription?.pricing_tiers?.trial_threshold_amount ||
          75,
      );
      const commissionRate = Number(
        subscription?.pricing_tiers?.commission_rate || 0.03,
      );

      // Load shop currency for trial data
      const shop = await prisma.shops.findUnique({
        where: { id: shopId },
        select: { currency_code: true },
      });
      const currency = shop?.currency_code || "USD";

      // 2. If trial not completed, show trial
      if (trialRevenue < trialThreshold) {
        return {
          status: "trial_active",
          trialData: this.buildTrialData(
            trialRevenue,
            trialThreshold,
            commissionRate,
            currency,
          ),
        };
      }

      // 3. Check subscription status: Always check Shopify GraphQL first (source of truth)
      if (admin) {
        const shopifyStatus = await this.getShopifySubscriptionStatus(
          shopId,
          admin,
        );

        if (shopifyStatus) {
          if (shopifyStatus.status === "ACTIVE") {
            return {
              status: "subscription_active",
              subscriptionData: await this.getSubscriptionDataFromShopify(
                subscription || {},
                shopifyStatus,
                commissionRate,
              ),
            };
          }
          if (shopifyStatus.status === "PENDING") {
            // Merchant created the subscription but hasn't approved it in Shopify yet
            return {
              status: "subscription_pending",
              subscriptionData: await this.getSubscriptionDataFromShopify(
                subscription || {},
                shopifyStatus,
                commissionRate,
              ),
            };
          }
        }
      } else if (
        subscription &&
        subscription.status === "ACTIVE" &&
        subscription.shopify_subscription_id
      ) {
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
            commissionRate,
          ),
        };
      }

      // 4. Trial completed, no active Shopify subscription = show setup button
      return {
        status: "trial_completed",
        trialData: this.buildTrialData(
          trialRevenue,
          trialThreshold,
          commissionRate,
          currency,
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

  private static buildTrialData(
    revenue: number,
    threshold: number,
    commissionRate: number,
    currency: string,
  ): TrialData {
    const progress = Math.min((revenue / threshold) * 100, 100);
    return {
      isActive: revenue < threshold,
      thresholdAmount: threshold,
      accumulatedRevenue: revenue,
      progress: Math.round(progress),
      currency,
      commissionRate,
    };
  }

  /**
   * Get subscription data from Shopify API.
   *
   * Usage is read from billing_cycles.usage_amount (single source of truth,
   * maintained by the Python worker). No longer recomputes PENDING commissions
   * from commission_records — eliminating the duplicate billing logic between
   * the Remix app and the Python worker.
   */
  private static async getSubscriptionDataFromShopify(
    shopSubscription: any,
    shopifyStatus: any,
    commissionRate: number = 0.03,
  ): Promise<SubscriptionData> {
    // Load active billing cycle — single source of truth for usage and cap
    const billingCycle = await prisma.billing_cycles.findFirst({
      where: {
        shop_subscription_id: shopSubscription.id,
        status: "ACTIVE",
      },
    });

    const shopifyUsage = shopifyStatus.currentUsage || 0;

    // ✅ currentUsage = billing_cycles.usage_amount (maintained by Python worker
    //    via update_billing_cycle_usage after each Shopify usage recording).
    //    Fall back to shopifyUsage from GraphQL if no billing cycle exists yet.
    const usageAmount = billingCycle ? Number(billingCycle.usage_amount) : shopifyUsage;

    // ✅ spendingLimit from billing cycle, fallback to Shopify or user-chosen cap
    const spendingLimit = billingCycle
      ? Number(billingCycle.current_cap_amount)
      : shopifyStatus.cappedAmount ||
        Number(shopSubscription.user_chosen_cap_amount || 0);

    // ✅ Rejected amount: lightweight query (display transparency only, not used in billing logic)
    let rejectedAmount: number | undefined;
    if (billingCycle) {
      try {
        const rejectedResult = await prisma.commission_records.aggregate({
          where: {
            billing_cycle_id: billingCycle.id,
            billing_phase: "PAID",
            status: "REJECTED",
          },
          _sum: { commission_earned: true },
        });
        rejectedAmount = Number(rejectedResult._sum?.commission_earned || 0);
      } catch (error) {
        logger.error({ error }, "Error fetching rejected commissions");
        rejectedAmount = undefined;
      }
    }

    const usagePercentage =
      spendingLimit > 0 ? Math.round((usageAmount / spendingLimit) * 100) : 0;

    return {
      id: shopifyStatus.subscriptionId || shopSubscription.id,
      status: shopifyStatus.status as
        | "PENDING"
        | "ACTIVE"
        | "DECLINED"
        | "CANCELLED"
        | "EXPIRED",
      spendingLimit,
      currentUsage: usageAmount,
      shopifyUsage,
      expectedCharge: 0, // No longer recomputed — usage_amount is the source of truth
      rejectedAmount,
      usagePercentage,
      confirmationUrl: shopifyStatus.confirmationUrl,
      currency: shopifyStatus.currency || "USD",
      commissionRate,
      billingCycle: billingCycle
        ? {
            startDate: billingCycle.start_date.toISOString(),
            endDate: billingCycle.end_date.toISOString(),
            cycleNumber: billingCycle.cycle_number,
          }
        : undefined,
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
            // Map Shopify status to local status.
            // PENDING_APPROVAL removed — merchant stays in TRIAL until Shopify confirms ACTIVE.
            const localStatus =
              subscription.status === "ACTIVE"
                ? "ACTIVE"
                : subscription.status === "PENDING"
                  ? "TRIAL"
                  : subscription.status === "CANCELLED"
                    ? "CANCELLED"
                    : subscription.status === "DECLINED"
                      ? "TRIAL"
                      : dbSubscription.status;

            await prisma.shop_subscriptions.update({
              where: { id: dbSubscription.id },
              data: {
                shopify_subscription_id: subscription.id,
                shopify_status: subscription.status,
                status: localStatus as any,
                is_active: localStatus !== "CANCELLED" && localStatus !== "EXPIRED",
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
