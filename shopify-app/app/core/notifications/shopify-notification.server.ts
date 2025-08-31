import { prisma } from "../database/prisma.server";

export interface ShopifyNotificationData {
  title: string;
  message: string;
  actionUrl?: string;
  type?: "info" | "success" | "warning" | "error";
}

export class ShopifyNotificationService {
  /**
   * Send a native Shopify admin notification
   */
  static async sendShopifyNotification(
    shopDomain: string,
    notification: ShopifyNotificationData
  ) {
    try {
      // Get shop with access token
      const shop = await prisma.shop.findUnique({
        where: { shopDomain },
        select: { accessToken: true },
      });

      if (!shop) {
        console.error("❌ Shop not found for Shopify notification:", shopDomain);
        return;
      }

      // Create notification using Shopify Admin API
      const response = await fetch(`https://${shopDomain}/admin/api/2024-01/notifications.json`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Shopify-Access-Token": shop.accessToken,
        },
        body: JSON.stringify({
          notification: {
            title: notification.title,
            message: notification.message,
            action_url: notification.actionUrl,
            type: notification.type || "info",
          },
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        console.error("❌ Failed to send Shopify notification:", {
          status: response.status,
          statusText: response.statusText,
          error: errorText,
        });
        return;
      }

      const result = await response.json();
      console.log(`✅ Shopify notification sent to ${shopDomain}:`, result);
      return result;
    } catch (error) {
      console.error("❌ Error sending Shopify notification:", error);
    }
  }

  /**
   * Send analysis completion notification to Shopify admin
   */
  static async sendAnalysisCompleteNotification(
    shopDomain: string,
    jobId: string,
    success: boolean,
    error?: string
  ) {
    const notification: ShopifyNotificationData = {
      title: success ? "🎉 Bundle Analysis Complete!" : "❌ Bundle Analysis Failed",
      message: success
        ? "Your bundle analysis is complete. Check your dashboard for results!"
        : error
        ? `Your bundle analysis failed: ${error}`
        : "Your bundle analysis failed. Please try again.",
      actionUrl: `/admin/apps/${process.env.SHOPIFY_API_KEY}/dashboard`,
      type: success ? "success" : "error",
    };

    return this.sendShopifyNotification(shopDomain, notification);
  }

  /**
   * Send analysis started notification to Shopify admin
   */
  static async sendAnalysisStartedNotification(
    shopDomain: string,
    jobId: string
  ) {
    const notification: ShopifyNotificationData = {
      title: "🔄 Bundle Analysis Started",
      message: "Your bundle analysis is now processing. You'll be notified when it's complete.",
      actionUrl: `/admin/apps/${process.env.SHOPIFY_API_KEY}/dashboard`,
      type: "info",
    };

    return this.sendShopifyNotification(shopDomain, notification);
  }
}
