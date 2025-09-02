/**
 * Shopify Billing Service
 * Handles automatic commission collection through Shopify's billing API
 */

import { prisma } from "../core/database/prisma.server";
import { performanceBillingService } from "./performance-billing.service";

export interface BillingCharge {
  id: string;
  shopId: string;
  amount: number;
  currency: string;
  description: string;
  billingPeriod: string;
  status: "pending" | "active" | "cancelled" | "declined";
  createdAt: Date;
  dueDate: Date;
  paidAt?: Date;
}

export interface BillingSubscription {
  id: string;
  shopId: string;
  planName: string;
  status: "active" | "cancelled" | "declined" | "frozen";
  trialDays: number;
  currentPeriodEnd: Date;
  nextBillingDate: Date;
  createdAt: Date;
}

export class ShopifyBillingService {
  private readonly APP_NAME = "BetterBundle";
  private readonly PLAN_NAME = "Performance-Based Recommendations";
  private readonly TRIAL_DAYS = 14;

  /**
   * Create or update billing subscription for a shop
   */
  async createBillingSubscription(
    shopDomain: string,
    accessToken: string,
  ): Promise<{ success: boolean; subscriptionId?: string; error?: string }> {
    try {
      // Get shop ID from domain
      const shop = await prisma.shop.findUnique({
        where: { shopDomain },
        select: { id: true }
      });

      if (!shop) {
        return {
          success: false,
          error: "Shop not found in database",
        };
      }

      // Check if shop already has an active subscription
      const existingSubscription = await prisma.billingSubscription.findFirst({
        where: {
          shopId: shop.id,
          status: "active",
        },
      });

      if (existingSubscription) {
        return {
          success: true,
          subscriptionId: existingSubscription.id,
          message: "Subscription already exists",
        };
      }

      // Create new subscription in Shopify
      const subscription = await this.createShopifySubscription(
        shopDomain,
        accessToken,
      );

      if (subscription.success && subscription.subscriptionId) {
        // Save subscription to database
        await prisma.billingSubscription.create({
          data: {
            id: subscription.subscriptionId,
            shopId: shop.id,
            planName: this.PLAN_NAME,
            status: "active",
            trialDays: this.TRIAL_DAYS,
            currentPeriodEnd: new Date(
              Date.now() + this.TRIAL_DAYS * 24 * 60 * 60 * 1000,
            ),
            nextBillingDate: new Date(
              Date.now() + this.TRIAL_DAYS * 24 * 60 * 60 * 1000,
            ),
            createdAt: new Date(),
          },
        });

        return {
          success: true,
          subscriptionId: subscription.subscriptionId,
        };
      }

      return subscription;
    } catch (error) {
      console.error("Error creating billing subscription:", error);
      return {
        success: false,
        error: "Failed to create billing subscription",
      };
    }
  }

  /**
   * Create subscription in Shopify
   */
  private async createShopifySubscription(
    shopDomain: string,
    accessToken: string,
  ): Promise<{ success: boolean; subscriptionId?: string; error?: string }> {
    try {
      const response = await fetch(
        `https://${shopDomain}/admin/api/2024-01/recurring_application_charges.json`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": accessToken,
          },
          body: JSON.stringify({
            recurring_application_charge: {
              name: this.PLAN_NAME,
              price: 0.0, // Start with $0, we'll charge based on performance
              return_url: `${process.env.APP_URL}/billing/confirm`,
              trial_days: this.TRIAL_DAYS,
              test: process.env.NODE_ENV === "development",
            },
          }),
        },
      );

      if (!response.ok) {
        const errorData = await response.json();
        console.error("Shopify billing API error:", errorData);
        return {
          success: false,
          error: `Shopify API error: ${response.status}`,
        };
      }

      const data = await response.json();
      const subscriptionId = data.recurring_application_charge.id.toString();

      return {
        success: true,
        subscriptionId,
      };
    } catch (error) {
      console.error("Error calling Shopify billing API:", error);
      return {
        success: false,
        error: "Failed to communicate with Shopify",
      };
    }
  }

  /**
   * Charge commission for a billing period
   */
  async chargeCommission(
    shopDomain: string,
    billingPeriod: string,
    amount: number,
  ): Promise<{ success: boolean; chargeId?: string; error?: string }> {
    try {
      // Get shop access token
      const shop = await prisma.shop.findUnique({
        where: { shopDomain },
      });

      if (!shop) {
        return {
          success: false,
          error: "Shop not found",
        };
      }

      // Create usage charge in Shopify
      const charge = await this.createUsageCharge(
        shopDomain,
        shop.accessToken,
        amount,
        billingPeriod,
      );

      if (charge.success && charge.chargeId) {
        // Save charge to database
        await prisma.billingCharge.create({
          data: {
            id: charge.chargeId,
            shopId: shopDomain,
            amount,
            currency: "USD",
            description: `Commission for ${billingPeriod} - Performance-based billing`,
            billingPeriod,
            status: "pending",
            createdAt: new Date(),
            dueDate: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000), // 30 days
          },
        });

        return {
          success: true,
          chargeId: charge.chargeId,
        };
      }

      return charge;
    } catch (error) {
      console.error("Error charging commission:", error);
      return {
        success: false,
        error: "Failed to charge commission",
      };
    }
  }

  /**
   * Create usage charge in Shopify
   */
  private async createUsageCharge(
    shopDomain: string,
    accessToken: string,
    amount: number,
    description: string,
  ): Promise<{ success: boolean; chargeId?: string; error?: string }> {
    try {
      // First, get the recurring application charge ID
      const subscription = await prisma.billingSubscription.findFirst({
        where: {
          shopId: shopDomain,
          status: "active",
        },
      });

      if (!subscription) {
        return {
          success: false,
          error: "No active subscription found",
        };
      }

      // Create usage charge
      const response = await fetch(
        `https://${shopDomain}/admin/api/2024-01/recurring_application_charges/${subscription.id}/usage_charges.json`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": accessToken,
          },
          body: JSON.stringify({
            usage_charge: {
              description: `Commission: ${description}`,
              price: amount,
              currency: "USD",
            },
          }),
        },
      );

      if (!response.ok) {
        const errorData = await response.json();
        console.error("Shopify usage charge API error:", errorData);
        return {
          success: false,
          error: `Shopify API error: ${response.status}`,
        };
      }

      const data = await response.json();
      const chargeId = data.usage_charge.id.toString();

      return {
        success: true,
        chargeId,
      };
    } catch (error) {
      console.error("Error calling Shopify usage charge API:", error);
      return {
        success: false,
        error: "Failed to communicate with Shopify",
      };
    }
  }

  /**
   * Process monthly billing for all shops
   */
  async processMonthlyBilling(): Promise<{
    success: boolean;
    processed: number;
    errors: string[];
  }> {
    try {
      const errors: string[] = [];
      let processed = 0;

      // Get all active shops
      const activeShops = await prisma.shop.findMany({
        where: { isActive: true },
      });

      for (const shop of activeShops) {
        try {
          // Calculate billing for the previous month
          const endDate = new Date();
          const startDate = new Date();
          startDate.setMonth(startDate.getMonth() - 1);
          startDate.setDate(1);

          const billing = await performanceBillingService.calculateBilling(
            shop.shopDomain,
            startDate,
            endDate,
          );

          if (billing.commissionAmount > 0) {
            const billingPeriod = `${startDate.getFullYear()}-${String(startDate.getMonth() + 1).padStart(2, "0")}`;

            const chargeResult = await this.chargeCommission(
              shop.shopDomain,
              billingPeriod,
              billing.commissionAmount,
            );

            if (chargeResult.success) {
              processed++;
              console.log(
                `Charged $${billing.commissionAmount} for shop ${shop.shopDomain}`,
              );
            } else {
              errors.push(
                `Failed to charge ${shop.shopDomain}: ${chargeResult.error}`,
              );
            }
          }
        } catch (error) {
          errors.push(`Error processing ${shop.shopDomain}: ${error}`);
        }
      }

      return {
        success: processed > 0,
        processed,
        errors,
      };
    } catch (error) {
      console.error("Error processing monthly billing:", error);
      return {
        success: false,
        processed: 0,
        errors: [error.toString()],
      };
    }
  }

  /**
   * Get billing status for a shop
   */
  async getBillingStatus(shopDomain: string): Promise<{
    subscription?: BillingSubscription;
    charges: BillingCharge[];
    totalPaid: number;
    totalPending: number;
  }> {
    try {
      const subscription = await prisma.billingSubscription.findFirst({
        where: {
          shopId: shopDomain,
          status: "active",
        },
      });

      const charges = await prisma.billingCharge.findMany({
        where: { shopId: shopDomain },
        orderBy: { createdAt: "desc" },
      });

      const totalPaid = charges
        .filter((c) => c.status === "active")
        .reduce((sum, c) => sum + c.amount, 0);

      const totalPending = charges
        .filter((c) => c.status === "pending")
        .reduce((sum, c) => sum + c.amount, 0);

      return {
        subscription,
        charges,
        totalPaid,
        totalPending,
      };
    } catch (error) {
      console.error("Error getting billing status:", error);
      return {
        charges: [],
        totalPaid: 0,
        totalPending: 0,
      };
    }
  }

  /**
   * Cancel subscription for a shop
   */
  async cancelSubscription(
    shopDomain: string,
  ): Promise<{ success: boolean; error?: string }> {
    try {
      const subscription = await prisma.billingSubscription.findFirst({
        where: {
          shopId: shopDomain,
          status: "active",
        },
      });

      if (!subscription) {
        return {
          success: false,
          error: "No active subscription found",
        };
      }

      // Cancel in Shopify
      const shop = await prisma.shop.findUnique({
        where: { shopDomain },
      });

      if (shop) {
        const response = await fetch(
          `https://${shopDomain}/admin/api/2024-01/recurring_application_charges/${subscription.id}.json`,
          {
            method: "DELETE",
            headers: {
              "X-Shopify-Access-Token": shop.accessToken,
            },
          },
        );

        if (!response.ok) {
          console.error(
            "Failed to cancel Shopify subscription:",
            response.status,
          );
        }
      }

      // Update local status
      await prisma.billingSubscription.update({
        where: { id: subscription.id },
        data: { status: "cancelled" },
      });

      return { success: true };
    } catch (error) {
      console.error("Error cancelling subscription:", error);
      return {
        success: false,
        error: "Failed to cancel subscription",
      };
    }
  }
}

// Export singleton instance
export const shopifyBillingService = new ShopifyBillingService();
