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
      // 1. Get shop subscription
      const subscription = await prisma.shop_subscriptions.findFirst({
        where: {
          shop_id: shopId,
          is_active: true,
        },
        include: {
          pricing_tiers: true,
          subscription_plans: true,
        },
        orderBy: {
          created_at: "desc",
        },
      });

      if (!subscription) {
        return {
          status: "trial_active",
          trialData: await this.getDefaultTrialData(shopId),
        };
      }

      const isTrialPhase = subscription.subscription_type === "TRIAL";
      const isPaidPhase = subscription.subscription_type === "PAID";

      // 2. TRIAL PHASE: Time-based, check expiry
      if (isTrialPhase) {
        const trialDays =
          subscription.trial_duration_days ||
          subscription.pricing_tiers?.trial_days ||
          14;
        const startedAt = subscription.started_at;
        const trialEnd = new Date(
          startedAt.getTime() + trialDays * 24 * 60 * 60 * 1000,
        );
        const now = new Date();
        const daysRemaining = Math.max(
          0,
          Math.ceil(
            (trialEnd.getTime() - now.getTime()) / (1000 * 60 * 60 * 24),
          ),
        );

        if (daysRemaining > 0 && subscription.status === "TRIAL") {
          return {
            status: "trial_active",
            trialData: {
              isActive: true,
              daysRemaining,
              trialDays,
              currency: subscription.pricing_tiers?.currency || "USD",
            },
          };
        }

        // Trial expired
        return {
          status: "trial_completed",
          trialData: {
            isActive: false,
            daysRemaining: 0,
            trialDays,
            currency: subscription.pricing_tiers?.currency || "USD",
          },
        };
      }

      // 3. PAID PHASE: Check Shopify subscription status
      if (isPaidPhase) {
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
              return {
                status: "subscription_active",
                subscriptionData: await this.getSubscriptionDataFromShopify(
                  subscription,
                  shopifyStatus,
                ),
              };
            }

            if (shopifyStatus.status === "CANCELLED") {
              return {
                status: "subscription_cancelled",
              };
            }
          }
        } else if (subscription.shopify_subscription_id) {
          // No admin client, use DB info
          return {
            status: "subscription_active",
            subscriptionData: {
              id: subscription.shopify_subscription_id,
              status:
                (subscription.shopify_status as any) || "ACTIVE",
              planName:
                subscription.subscription_plans?.name || "Flat Fee Plan",
              monthlyFee: Number(
                subscription.monthly_fee_override ||
                  subscription.pricing_tiers?.monthly_fee ||
                  29,
              ),
              currency: subscription.pricing_tiers?.currency || "USD",
            },
          };
        }
      }

      // 4. TRIAL COMPLETED - needs billing setup
      return {
        status: "trial_completed",
        trialData: await this.getDefaultTrialData(shopId),
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

  private static async getDefaultTrialData(shopId: string): Promise<TrialData> {
    const shop = await prisma.shops.findUnique({
      where: { id: shopId },
      select: { currency_code: true },
    });
    return {
      isActive: true,
      daysRemaining: 14,
      trialDays: 14,
      currency: shop?.currency_code || "USD",
    };
  }

  /**
   * Get subscription data from Shopify API (flat fee)
   */
  private static async getSubscriptionDataFromShopify(
    shopSubscription: any,
    shopifyStatus: any,
  ): Promise<SubscriptionData> {
    return {
      id: shopifyStatus.subscriptionId || shopSubscription.id,
      status: shopifyStatus.status as
        | "PENDING"
        | "ACTIVE"
        | "DECLINED"
        | "CANCELLED"
        | "EXPIRED",
      planName:
        shopSubscription.subscription_plans?.name || "Flat Fee Plan",
      monthlyFee:
        shopifyStatus.monthlyFee ||
        Number(
          shopSubscription.monthly_fee_override ||
            shopSubscription.pricing_tiers?.monthly_fee ||
            29,
        ),
      currency: shopifyStatus.currency || "USD",
      confirmationUrl: shopifyStatus.confirmationUrl,
      billingCycle: shopifyStatus.currentPeriodEnd
        ? {
            startDate: shopifyStatus.currentPeriodStart,
            endDate: shopifyStatus.currentPeriodEnd,
            cycleNumber: shopifyStatus.cycleNumber || 1,
          }
        : undefined,
    };
  }

  /**
   * Get real-time Shopify subscription status via GraphQL (flat fee)
   * Uses AppRecurringPricing instead of AppUsagePricing
   */
  static async getShopifySubscriptionStatus(
    shopId: string,
    admin: any,
  ): Promise<{
    status: string;
    subscriptionId?: string;
    confirmationUrl?: string;
    monthlyFee?: number;
    currency?: string;
    currentPeriodEnd?: string;
    currentPeriodStart?: string;
  } | null> {
    try {
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
                    __typename
                    ... on AppRecurringPricing {
                      price {
                        amount
                        currencyCode
                      }
                      interval
                    }
                    ... on AppUsagePricing {
                      cappedAmount {
                        amount
                        currencyCode
                      }
                      balanceUsed {
                        amount
                        currencyCode
                      }
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
        logger.error(
          { errors: data.errors },
          "GraphQL errors in activeSubscriptions query",
        );
      }

      // Check for active subscriptions from Shopify
      if (data.data?.currentAppInstallation?.activeSubscriptions?.length > 0) {
        const subscription =
          data.data.currentAppInstallation.activeSubscriptions[0];
        const lineItem = subscription.lineItems[0];
        const pricingDetails = lineItem?.plan?.pricingDetails;

        // Extract monthly fee (works for both recurring and usage-based)
        let monthlyFee: number | undefined;
        let currency: string | undefined;

        if (pricingDetails?.__typename === "AppRecurringPricing") {
          monthlyFee = pricingDetails.price?.amount;
          currency = pricingDetails.price?.currencyCode;
        } else if (pricingDetails?.__typename === "AppUsagePricing") {
          monthlyFee = pricingDetails.cappedAmount?.amount;
          currency = pricingDetails.cappedAmount?.currencyCode;
        }

        // Sync with database
        const dbSubscription = await prisma.shop_subscriptions.findFirst({
          where: {
            shop_id: shopId,
            is_active: true,
          },
          orderBy: { created_at: "desc" },
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
                  subscription.status === "ACTIVE" ||
                  subscription.status === "PENDING"
                    ? "ACTIVE"
                    : dbSubscription.status,
                updated_at: new Date(),
              },
            });
          } catch (error) {
            logger.error(
              { error },
              "Failed to update subscription with Shopify ID",
            );
          }
        }

        return {
          status: subscription.status,
          subscriptionId: subscription.id,
          monthlyFee,
          currency,
          currentPeriodEnd: subscription.currentPeriodEnd,
        };
      }

      // No active subscriptions found
      return null;
    } catch (error) {
      logger.error({ error }, "Error getting Shopify subscription status");
      return null;
    }
  }
}
