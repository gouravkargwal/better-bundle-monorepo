import type { ActionFunctionArgs } from "@remix-run/node";
import { NotificationService } from "../core/notifications/notification.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    const { shopId, jobId, success } = await request.json();

    if (!shopId || !jobId || success === undefined) {
      return Response.json(
        { error: "Missing required fields: shopId, jobId, success" },
        { status: 400 },
      );
    }

    // Send notification
    await NotificationService.sendAnalysisCompleteNotification(
      shopId,
      jobId,
      success,
    );

    return Response.json({ success: true });
  } catch (error) {
    console.error("❌ Error sending notification:", error);
    return Response.json(
      { error: "Failed to send notification" },
      { status: 500 },
    );
  }
};
