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
      const subscription = await prisma.shop_subscriptions.findFirst({
        where: {
          shop_id: shopId,
          is_active: true,
        },
        include: { subscription_plans: true },
        orderBy: { created_at: "desc" },
      });

      const monthlyPrice = Number(
        subscription?.subscription_plans?.monthly_price ?? 99.0,
      );
      const trialDays = Number(subscription?.subscription_plans?.trial_days ?? 14);

      const shop = await prisma.shops.findUnique({
        where: { id: shopId },
        select: { currency_code: true },
      });
      const currency = shop?.currency_code || "USD";

      // Check subscription status: Shopify GraphQL is the source of truth when available
      if (admin) {
        const shopifyStatus = await this.getShopifySubscriptionStatus(
          shopId,
          admin,
        );

        if (shopifyStatus) {
          if (shopifyStatus.status === "ACTIVE") {
            return {
              status: "subscription_active",
              subscriptionData: this.buildSubscriptionData(
                subscription || {},
                shopifyStatus,
                monthlyPrice,
              ),
            };
          }
          if (shopifyStatus.status === "PENDING") {
            // Merchant created the subscription but hasn't approved it in Shopify yet
            return {
              status: "subscription_pending",
              subscriptionData: this.buildSubscriptionData(
                subscription || {},
                shopifyStatus,
                monthlyPrice,
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
          subscriptionData: this.buildSubscriptionData(
            subscription,
            {
              status: subscription.shopify_status || "ACTIVE",
              subscriptionId: subscription.shopify_subscription_id,
              currency,
            },
            monthlyPrice,
          ),
        };
      }

      // No active Shopify subscription — merchant is in (or hasn't started) the free trial
      return {
        status: "trial_active",
        trialData: this.buildTrialData(trialDays, monthlyPrice, currency),
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
    trialDays: number,
    monthlyPrice: number,
    currency: string,
  ): TrialData {
    return {
      isActive: true,
      trialDays,
      monthlyPrice,
      currency,
    };
  }

  private static buildSubscriptionData(
    shopSubscription: any,
    shopifyStatus: any,
    monthlyPrice: number,
  ): SubscriptionData {
    return {
      id: shopifyStatus.subscriptionId || shopSubscription.id,
      status: shopifyStatus.status as
        | "PENDING"
        | "ACTIVE"
        | "DECLINED"
        | "CANCELLED"
        | "EXPIRED",
      monthlyPrice,
      currency: shopifyStatus.currency || "USD",
      confirmationUrl: shopifyStatus.confirmationUrl,
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
        logger.error(
          { errors: data.errors },
          "GraphQL errors in activeSubscriptions query",
        );
      }

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
            logger.error(
              { error },
              "Failed to update subscription with Shopify ID",
            );
          }
        }

        return {
          status: subscription.status,
          subscriptionId: subscription.id,
          currency: pricingDetails?.price?.currencyCode || "USD",
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
        currency: pricingDetails?.price?.currencyCode || "USD",
      };
    } catch (error) {
      logger.error({ error }, "Error getting Shopify subscription status");
      return null;
    }
  }
}
