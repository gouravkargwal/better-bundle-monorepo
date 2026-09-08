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

      // 2. TRIAL PHASE: ends on attributed revenue only — no elapsed-time gate.
      if (isTrialPhase) {
        const currency = await this.getShopCurrency(shopId);
        const trialThreshold = Number(
          subscription.trial_threshold_override ??
            subscription.subscription_plans?.trial_revenue_threshold ??
            1000,
        );
        const revenueEarned = await this.getTrialRevenueEarned(shopId);
        const commissionRate = Number(
          subscription.commission_rate_override ??
            subscription.subscription_plans?.commission_rate ??
            0.03,
        );
        const cappedAmount = Number(
          subscription.cap_amount_override ??
            subscription.subscription_plans?.cap_amount ??
            299,
        );

        // The worker flips status to TRIAL_COMPLETED once the threshold is
        // crossed; reaching it here too keeps the UI honest between webhooks.
        const stillTrialing =
          subscription.status === "TRIAL" && revenueEarned < trialThreshold;

        return {
          status: stillTrialing ? "trial_active" : "trial_completed",
          trialData: {
            isActive: stillTrialing,
            revenueEarned,
            trialThreshold,
            commissionRate,
            cappedAmount,
            currency,
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
          const cycle = await this.getCurrentCycleUsage(subscription.id);
          return {
            status: "subscription_active",
            subscriptionData: {
              id: subscription.shopify_subscription_id,
              status: (subscription.shopify_status as any) || "ACTIVE",
              planName:
                subscription.subscription_plans?.name || "Pay As You Go",
              commissionRate: Number(
                subscription.commission_rate_override ??
                  subscription.subscription_plans?.commission_rate ??
                  0.03,
              ),
              cappedAmount: Number(
                subscription.cap_amount_override ??
                  subscription.subscription_plans?.cap_amount ??
                  299,
              ),
              usageThisCycle: cycle.usageAmount,
              attributedThisCycle: cycle.attributedRevenue,
              currency: await this.getShopCurrency(shopId),
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

  private static async getShopCurrency(shopId: string): Promise<string> {
    const shop = await prisma.shops.findUnique({
      where: { id: shopId },
      select: { currency_code: true },
    });
    return shop?.currency_code || "USD";
  }

  /**
   * Attributed revenue accumulated during the trial.
   *
   * Sums TRIAL-phase commission rows only — the same basis the worker uses to
   * decide when the trial is over, so the two never disagree.
   */
  private static async getTrialRevenueEarned(shopId: string): Promise<number> {
    const result = await prisma.commission_records.aggregate({
      where: { shop_id: shopId, billing_phase: "TRIAL" },
      _sum: { attributed_revenue: true },
    });
    return Number(result._sum.attributed_revenue ?? 0);
  }

  /** Usage charged and revenue attributed in the shop's open billing cycle. */
  private static async getCurrentCycleUsage(
    shopSubscriptionId: string,
  ): Promise<{ usageAmount: number; attributedRevenue: number }> {
    const cycle = await prisma.billing_cycles.findFirst({
      where: { shop_subscription_id: shopSubscriptionId, status: "ACTIVE" },
      orderBy: { start_date: "desc" },
    });
    if (!cycle) return { usageAmount: 0, attributedRevenue: 0 };

    const attributed = await prisma.commission_records.aggregate({
      where: { billing_cycle_id: cycle.id },
      _sum: { attributed_revenue: true },
    });
    return {
      usageAmount: Number(cycle.usage_amount ?? 0),
      attributedRevenue: Number(attributed._sum.attributed_revenue ?? 0),
    };
  }

  private static async getDefaultTrialData(shopId: string): Promise<TrialData> {
    return {
      isActive: true,
      revenueEarned: 0,
      trialThreshold: 1000,
      commissionRate: 0.03,
      cappedAmount: 299,
      currency: await this.getShopCurrency(shopId),
    };
  }

  /**
   * Build subscription data from the live Shopify subscription plus our own
   * cycle rows. Shopify knows the cap and the balance it has billed; only we
   * know how much revenue was attributed to produce it.
   */
  private static async getSubscriptionDataFromShopify(
    shopSubscription: any,
    shopifyStatus: any,
  ): Promise<SubscriptionData> {
    const cycle = await this.getCurrentCycleUsage(shopSubscription.id);
    return {
      id: shopifyStatus.subscriptionId || shopSubscription.id,
      status: shopifyStatus.status as
        | "PENDING"
        | "ACTIVE"
        | "DECLINED"
        | "CANCELLED"
        | "EXPIRED",
      planName: shopSubscription.subscription_plans?.name || "Pay As You Go",
      commissionRate: Number(
        shopSubscription.commission_rate_override ??
          shopSubscription.subscription_plans?.commission_rate ??
          0.03,
      ),
      // Prefer Shopify's cap: it is what the merchant actually approved, and
      // it is authoritative if our row drifted.
      cappedAmount: Number(
        shopifyStatus.cappedAmount ??
          shopSubscription.cap_amount_override ??
          shopSubscription.subscription_plans?.cap_amount ??
          299,
      ),
      usageThisCycle: Number(shopifyStatus.balanceUsed ?? cycle.usageAmount),
      attributedThisCycle: cycle.attributedRevenue,
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
   * Get real-time Shopify subscription status via GraphQL.
   *
   * Reads AppUsagePricing: `cappedAmount` is the ceiling the merchant approved
   * and `balanceUsed` is what Shopify has actually billed this cycle — the
   * authoritative figure, since Shopify rejects usage records past the cap.
   */
  static async getShopifySubscriptionStatus(
    shopId: string,
    admin: any,
  ): Promise<{
    status: string;
    subscriptionId?: string;
    confirmationUrl?: string;
    cappedAmount?: number;
    balanceUsed?: number;
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
                    ... on AppUsagePricing {
                      terms
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

        let cappedAmount: number | undefined;
        let balanceUsed: number | undefined;
        let currency: string | undefined;

        if (pricingDetails?.__typename === "AppUsagePricing") {
          cappedAmount = Number(pricingDetails.cappedAmount?.amount);
          balanceUsed = Number(pricingDetails.balanceUsed?.amount);
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
          cappedAmount,
          balanceUsed,
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
