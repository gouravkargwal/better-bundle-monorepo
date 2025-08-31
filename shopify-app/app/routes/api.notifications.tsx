import type { LoaderFunctionArgs, ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { NotificationService } from "../core/notifications/notification.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  try {
    const { session } = await authenticate.admin(request);
    const shopId = session.shop;
    const url = new URL(request.url);
    const action = url.searchParams.get("action");

    switch (action) {
      case "unread":
        // Get unread notifications
        const unreadNotifications = await NotificationService.getUnreadNotifications(shopId);
        return json({
          success: true,
          notifications: unreadNotifications,
        });

      case "count":
        // Get unread count
        const unreadCount = await NotificationService.getUnreadCount(shopId);
        return json({
          success: true,
          count: unreadCount,
        });

      default:
        // Get all notifications
        const allNotifications = await NotificationService.getShopNotifications(shopId);
        return json({
          success: true,
          notifications: allNotifications,
        });
    }
  } catch (error) {
    console.error("Error getting notifications:", error);
    return json(
      {
        success: false,
        error: "Failed to get notifications",
      },
      { status: 500 }
    );
  }
};

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    const { session } = await authenticate.admin(request);
    const shopId = session.shop;
    const formData = await request.formData();
    const action = formData.get("action") as string;

    switch (action) {
      case "mark-read":
        const notificationId = formData.get("notificationId") as string;
        if (!notificationId) {
          return json(
            {
              success: false,
              error: "Notification ID is required",
            },
            { status: 400 }
          );
        }

        await NotificationService.markAsRead(notificationId);
        return json({
          success: true,
          message: "Notification marked as read",
        });

      case "mark-all-read":
        await NotificationService.markAllAsRead(shopId);
        return json({
          success: true,
          message: "All notifications marked as read",
        });

      default:
        return json(
          {
            success: false,
            error: "Invalid action",
          },
          { status: 400 }
        );
    }
  } catch (error) {
    console.error("Error handling notification action:", error);
    return json(
      {
        success: false,
        error: "Failed to handle notification action",
      },
      { status: 500 }
    );
  }
};
