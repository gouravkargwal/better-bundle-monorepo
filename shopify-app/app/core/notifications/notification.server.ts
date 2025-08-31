import { prisma } from "../database/prisma.server";

export interface NotificationData {
  id: string;
  shopId: string;
  type: "analysis_complete" | "analysis_failed" | "analysis_started";
  title: string;
  message: string;
  actionUrl?: string;
  isRead: boolean;
  createdAt: Date;
  metadata?: any;
}

export class NotificationService {
  /**
   * Send a notification to the shop when analysis completes
   */
  static async sendAnalysisCompleteNotification(
    shopId: string,
    jobId: string,
    success: boolean,
  ) {
    try {
      // Get shop info
      const shop = await prisma.shop.findUnique({
        where: { id: shopId },
        select: { shopId: true, shopDomain: true },
      });

      if (!shop) {
        console.error("❌ Shop not found for notification:", shopId);
        return;
      }

      // Create notification record
      await prisma.notification.create({
        data: {
          shopId,
          type: success ? "analysis_complete" : "analysis_failed",
          title: success ? "🎉 Analysis Complete!" : "❌ Analysis Failed",
          message: success
            ? "Your bundle analysis is complete. Check your dashboard for results!"
            : "Your bundle analysis failed. Please try again.",
          metadata: {
            jobId,
            success,
            timestamp: new Date().toISOString(),
          },
          isRead: false,
        },
      });

      console.log(
        `✅ Notification sent to shop ${shop.shopDomain} for job ${jobId}`,
      );
    } catch (error) {
      console.error("❌ Failed to send notification:", error);
    }
  }

  /**
   * Get unread notifications for a shop
   */
  static async getUnreadNotifications(shopId: string) {
    try {
      return await prisma.notification.findMany({
        where: {
          shopId,
          isRead: false,
        },
        orderBy: {
          createdAt: "desc",
        },
      });
    } catch (error) {
      console.error("❌ Failed to get notifications:", error);
      return [];
    }
  }

  /**
   * Mark notification as read
   */
  static async markAsRead(notificationId: string) {
    try {
      await prisma.notification.update({
        where: { id: notificationId },
        data: { isRead: true },
      });
    } catch (error) {
      console.error("❌ Failed to mark notification as read:", error);
    }
  }

  /**
   * Get unread count for a shop
   */
  static async getUnreadCount(shopId: string) {
    try {
      const count = await prisma.notification.count({
        where: {
          shopId,
          isRead: false,
        },
      });
      return count;
    } catch (error) {
      console.error("❌ Failed to get unread count:", error);
      return 0;
    }
  }

  /**
   * Get all notifications for a shop
   */
  static async getShopNotifications(shopId: string, limit: number = 20) {
    try {
      return await prisma.notification.findMany({
        where: {
          shopId,
        },
        orderBy: {
          createdAt: "desc",
        },
        take: limit,
      });
    } catch (error) {
      console.error("❌ Failed to get shop notifications:", error);
      return [];
    }
  }

  /**
   * Mark all notifications as read for a shop
   */
  static async markAllAsRead(shopId: string) {
    try {
      await prisma.notification.updateMany({
        where: {
          shopId,
          isRead: false,
        },
        data: {
          isRead: true,
        },
      });
    } catch (error) {
      console.error("❌ Failed to mark all notifications as read:", error);
    }
  }
}
