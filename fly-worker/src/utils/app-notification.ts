import axios from "axios";

export interface AppNotificationData {
  title: string;
  message: string;
  type?: "info" | "success" | "warning" | "error";
}

export class AppNotificationService {
  /**
   * Send notification through the app's API
   */
  static async sendAppNotification(
    shopifyAppUrl: string,
    shopId: string,
    jobId: string,
    success: boolean,
    error?: string
  ) {
    try {
      const response = await axios.post(
        `${shopifyAppUrl}/api/notifications/send`,
        {
          shopId,
          jobId,
          success,
          error,
          source: "worker",
        },
        {
          timeout: 10000,
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      console.log(`✅ App notification sent for job ${jobId}:`, response.data);
      return response.data;
    } catch (error) {
      console.error("❌ Error sending app notification:", error);
      throw error;
    }
  }

  /**
   * Send analysis completion notification
   */
  static async sendAnalysisCompleteNotification(
    shopifyAppUrl: string,
    shopId: string,
    jobId: string,
    success: boolean,
    error?: string
  ) {
    return this.sendAppNotification(
      shopifyAppUrl,
      shopId,
      jobId,
      success,
      error
    );
  }

  /**
   * Send analysis started notification
   */
  static async sendAnalysisStartedNotification(
    shopifyAppUrl: string,
    shopId: string,
    jobId: string
  ) {
    // For started notifications, we'll just log it since the app will handle the UI
    console.log(`🔄 Analysis started notification for job ${jobId}`);
    return { success: true };
  }
}
