import prisma from "app/db.server";
import type { Session } from "@shopify/shopify-api";

interface SubscriptionPlan {
  id: string;
  name: string;
  price: {
    amount: string;
    currencyCode: string;
  };
  interval: string;
  trialDays?: number;
}

interface UsageRecord {
  id: string;
  subscriptionLineItemId: string;
  description: string;
  price: {
    amount: string;
    currencyCode: string;
  };
  createdAt: string;
}

/**
 * Service for managing Shopify usage-based subscriptions
 */
export class SubscriptionService {
  private session: Session;
  private admin: any;

  constructor(session: Session, admin: any) {
    this.session = session;
    this.admin = admin;
  }

  /**
   * Create a usage-based subscription plan
   */
  async createUsageBasedSubscription(
    shopId: string,
    planName: string = "Better Bundle Usage Plan",
    cappedAmount: number = 1000, // $1000 USD cap per billing cycle
    currencyCode: string = "USD",
  ): Promise<SubscriptionPlan | null> {
    try {
      console.log(`🔄 Creating usage-based subscription for shop ${shopId}`);

      const mutation = `
        mutation appSubscriptionCreate($subscription: AppSubscriptionInput!) {
          appSubscriptionCreate(subscription: $subscription) {
            appSubscription {
              id
              name
              status
              lineItems {
                id
                plan {
                  pricingDetails {
                    ... on AppRecurringPricing {
                      price {
                        amount
                        currencyCode
                      }
                      interval
                    }
                    ... on AppUsagePricing {
                      balanceUsed {
                        amount
                        currencyCode
                      }
                      cappedAmount {
                        amount
                        currencyCode
                      }
                      interval
                      terms
                    }
                  }
                }
              }
              createdAt
              currentPeriodEnd
            }
            userErrors {
              field
              message
            }
          }
        }
      `;

      const variables = {
        subscription: {
          name: planName,
          lineItems: [
            {
              plan: {
                appRecurringPricingDetails: {
                  price: {
                    amount: "0.00", // Free base price
                    currencyCode: currencyCode,
                  },
                  interval: "EVERY_30_DAYS",
                },
                appUsagePricingDetails: {
                  cappedAmount: {
                    amount: cappedAmount.toString(),
                    currencyCode: currencyCode,
                  },
                  interval: "EVERY_30_DAYS",
                  terms: "3% of attributed revenue",
                },
              },
            },
          ],
          returnUrl: `${process.env.SHOPIFY_APP_URL}/app/billing/setup?shop=${this.session.shop}`,
          test: process.env.NODE_ENV !== "production", // Use test mode in development
        },
      };

      const response = await this.admin.graphql(mutation, { variables });
      const responseData = await response.json();

      if (responseData.data?.appSubscriptionCreate?.userErrors?.length > 0) {
        console.error(
          "❌ Subscription creation errors:",
          responseData.data.appSubscriptionCreate.userErrors,
        );
        return null;
      }

      const subscription =
        responseData.data?.appSubscriptionCreate?.appSubscription;
      if (!subscription) {
        console.error("❌ No subscription returned from Shopify");
        return null;
      }

      console.log(`✅ Usage-based subscription created: ${subscription.id}`);

      // Store subscription in database
      await this.storeSubscription(shopId, subscription);

      return {
        id: subscription.id,
        name: subscription.name,
        price: {
          amount: "0.00",
          currencyCode: currencyCode,
        },
        interval: "EVERY_30_DAYS",
      };
    } catch (error) {
      console.error("❌ Error creating usage-based subscription:", error);
      return null;
    }
  }

  /**
   * Create a usage record for billing
   */
  async createUsageRecord(
    shopId: string,
    subscriptionId: string,
    description: string,
    amount: number,
    currencyCode: string = "USD",
  ): Promise<UsageRecord | null> {
    try {
      console.log(
        `🔄 Creating usage record for subscription ${subscriptionId}`,
      );

      const mutation = `
        mutation appUsageRecordCreate($subscriptionLineItemId: ID!, $description: String!, $price: MoneyInput!) {
          appUsageRecordCreate(subscriptionLineItemId: $subscriptionLineItemId, description: $description, price: $price) {
            appUsageRecord {
              id
              subscriptionLineItemId
              description
              price {
                amount
                currencyCode
              }
              createdAt
            }
            userErrors {
              field
              message
            }
          }
        }
      `;

      // Get the subscription line item ID
      const subscription = await this.getSubscription(subscriptionId);
      if (!subscription?.lineItems?.[0]?.id) {
        console.error("❌ No line item found for subscription");
        return null;
      }

      const variables = {
        subscriptionLineItemId: subscription.lineItems[0].id,
        description: description,
        price: {
          amount: amount.toString(),
          currencyCode: currencyCode,
        },
      };

      const response = await this.admin.graphql(mutation, { variables });
      const responseData = await response.json();

      if (responseData.data?.appUsageRecordCreate?.userErrors?.length > 0) {
        console.error(
          "❌ Usage record creation errors:",
          responseData.data.appUsageRecordCreate.userErrors,
        );
        return null;
      }

      const usageRecord =
        responseData.data?.appUsageRecordCreate?.appUsageRecord;
      if (!usageRecord) {
        console.error("❌ No usage record returned from Shopify");
        return null;
      }

      console.log(`✅ Usage record created: ${usageRecord.id}`);

      // Store usage record in database
      await this.storeUsageRecord(
        shopId,
        usageRecord,
        description,
        amount,
        currencyCode,
      );

      return {
        id: usageRecord.id,
        subscriptionLineItemId: usageRecord.subscriptionLineItemId,
        description: usageRecord.description,
        price: usageRecord.price,
        createdAt: usageRecord.createdAt,
      };
    } catch (error) {
      console.error("❌ Error creating usage record:", error);
      return null;
    }
  }

  /**
   * Get subscription details
   */
  async getSubscription(subscriptionId: string): Promise<any> {
    try {
      const query = `
        query appSubscription($id: ID!) {
          appSubscription(id: $id) {
            id
            name
            status
            lineItems {
              id
              plan {
                pricingDetails {
                  ... on AppRecurringPricing {
                    price {
                      amount
                      currencyCode
                    }
                    interval
                  }
                  ... on AppUsagePricing {
                    balanceUsed {
                      amount
                      currencyCode
                    }
                    cappedAmount {
                      amount
                      currencyCode
                    }
                    interval
                    terms
                  }
                }
              }
            }
            createdAt
            currentPeriodEnd
          }
        }
      `;

      const response = await this.admin.graphql(query, {
        variables: { id: subscriptionId },
      });
      const responseData = await response.json();

      return responseData.data?.appSubscription;
    } catch (error) {
      console.error("❌ Error getting subscription:", error);
      return null;
    }
  }

  /**
   * Check if shop has an active subscription
   */
  async hasActiveSubscription(shopId: string): Promise<boolean> {
    try {
      const billingPlan = await prisma.billing_plans.findFirst({
        where: {
          shop_id: shopId,
          status: "active",
        },
        select: {
          configuration: true,
        },
      });

      if (!billingPlan?.configuration) {
        return false;
      }

      const config = billingPlan.configuration as any;
      return config.subscription_id && config.subscription_status === "ACTIVE";
    } catch (error) {
      console.error("❌ Error checking subscription status:", error);
      return false;
    }
  }

  /**
   * Store subscription in database
   */
  private async storeSubscription(
    shopId: string,
    subscription: any,
  ): Promise<void> {
    try {
      await prisma.billing_plans.updateMany({
        where: {
          shop_id: shopId,
          status: "active",
        },
        data: {
          configuration: {
            subscription_id: subscription.id,
            subscription_status: subscription.status,
            subscription_created_at: subscription.createdAt,
            subscription_name: subscription.name,
            usage_based: true,
            capped_amount:
              subscription.lineItems?.[0]?.plan?.pricingDetails?.cappedAmount
                ?.amount || "1000",
            currency:
              subscription.lineItems?.[0]?.plan?.pricingDetails?.cappedAmount
                ?.currencyCode || "USD",
          },
        },
      });

      console.log(`✅ Subscription stored in database for shop ${shopId}`);
    } catch (error) {
      console.error("❌ Error storing subscription:", error);
    }
  }

  /**
   * Store usage record in database
   */
  private async storeUsageRecord(
    shopId: string,
    usageRecord: any,
    description: string,
    amount: number,
    currencyCode: string,
  ): Promise<void> {
    try {
      await prisma.billing_invoices.create({
        data: {
          shop_id: shopId,
          plan_id: "", // Usage-based doesn't have a plan ID
          invoice_number: `USAGE-${Date.now()}-${shopId.slice(0, 5)}`,
          status: "pending",
          subtotal: amount,
          taxes: 0,
          discounts: 0,
          total: amount,
          currency: currencyCode,
          period_start: new Date(),
          period_end: new Date(),
          due_date: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), // 30 days from now
          metrics_id: `usage-${Date.now()}`, // Generate a metrics ID
          billing_metadata: {
            usage_record_id: usageRecord.id,
            description: description,
            recorded_at: usageRecord.createdAt,
            type: "usage_based",
            subscription_line_item_id: usageRecord.subscriptionLineItemId,
          },
          created_at: new Date(),
        },
      });

      console.log(`✅ Usage record stored in database for shop ${shopId}`);
    } catch (error) {
      console.error("❌ Error storing usage record:", error);
    }
  }
}

/**
 * Create a usage-based subscription for a shop
 */
export async function createUsageBasedSubscription(
  session: Session,
  admin: any,
  shopId: string,
  shopDomain: string,
  currencyCode: string = "USD",
): Promise<SubscriptionPlan | null> {
  const subscriptionService = new SubscriptionService(session, admin);
  return await subscriptionService.createUsageBasedSubscription(
    shopId,
    "Better Bundle Usage Plan",
    1000, // $1000 USD cap
    currencyCode,
  );
}

/**
 * Create a usage record for billing
 */
export async function createUsageRecord(
  session: Session,
  admin: any,
  shopId: string,
  subscriptionId: string,
  description: string,
  amount: number,
  currencyCode: string = "USD",
): Promise<UsageRecord | null> {
  const subscriptionService = new SubscriptionService(session, admin);
  return await subscriptionService.createUsageRecord(
    shopId,
    subscriptionId,
    description,
    amount,
    currencyCode,
  );
}

/**
 * Check if shop has active subscription
 */
export async function hasActiveSubscription(
  session: Session,
  admin: any,
  shopId: string,
): Promise<boolean> {
  const subscriptionService = new SubscriptionService(session, admin);
  return await subscriptionService.hasActiveSubscription(shopId);
}
