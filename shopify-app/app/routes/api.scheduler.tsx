import type { LoaderFunctionArgs, ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { AnalysisScheduler } from "../core/scheduler/analysis-scheduler.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  try {
    const { session } = await authenticate.admin(request);
    const shopId = session.shop;
    const url = new URL(request.url);
    const action = url.searchParams.get("action");

    switch (action) {
      case "stats":
        // Get scheduler statistics
        const stats = await AnalysisScheduler.getSchedulerStats();
        return json({
          success: true,
          stats,
        });

      case "due":
        // Get shops due for analysis
        const shopsDue = await AnalysisScheduler.getShopsDueForAnalysis();
        return json({
          success: true,
          shopsDue,
        });

      case "upcoming":
        // Get upcoming scheduled analyses
        const limit = parseInt(url.searchParams.get("limit") || "10");
        const upcoming =
          await AnalysisScheduler.getUpcomingScheduledAnalyses(limit);
        return json({
          success: true,
          upcoming,
        });

      case "status":
        // Get scheduler status
        const status = AnalysisScheduler.getStatus();
        const scheduledAnalysisEnabled =
          AnalysisScheduler.isScheduledAnalysisEnabled();
        return json({
          success: true,
          status,
          scheduledAnalysisEnabled,
        });

      default:
        return json(
          {
            success: false,
            error: "Invalid action",
          },
          { status: 400 },
        );
    }
  } catch (error) {
    console.error("Error in scheduler API:", error);
    return json(
      {
        success: false,
        error: "Failed to get scheduler information",
      },
      { status: 500 },
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
      case "trigger":
        // Manually trigger analysis for current shop
        const triggerResult = await AnalysisScheduler.triggerAnalysis(shopId);
        return json(triggerResult);

      case "enable-auto":
        // Enable auto-analysis for current shop
        const enableResult = await AnalysisScheduler.setAutoAnalysisEnabled(
          shopId,
          true,
        );
        return json(enableResult);

      case "disable-auto":
        // Disable auto-analysis for current shop
        const disableResult = await AnalysisScheduler.setAutoAnalysisEnabled(
          shopId,
          false,
        );
        return json(disableResult);

      case "start-scheduler":
        // Start the scheduler (admin only)
        await AnalysisScheduler.start();
        return json({
          success: true,
          message: "Scheduler started successfully",
        });

      case "stop-scheduler":
        // Stop the scheduler (admin only)
        AnalysisScheduler.stop();
        return json({
          success: true,
          message: "Scheduler stopped successfully",
        });

      case "enable-scheduled-analysis":
        // Enable scheduled analysis
        AnalysisScheduler.enableScheduledAnalysis();
        return json({
          success: true,
          message: "Scheduled analysis enabled",
        });

      case "disable-scheduled-analysis":
        // Disable scheduled analysis
        AnalysisScheduler.disableScheduledAnalysis();
        return json({
          success: true,
          message: "Scheduled analysis disabled",
        });

      case "get-scheduled-analysis-status":
        // Get scheduled analysis status
        const isEnabled = AnalysisScheduler.isScheduledAnalysisEnabled();
        return json({
          success: true,
          scheduledAnalysisEnabled: isEnabled,
        });

      default:
        return json(
          {
            success: false,
            error: "Invalid action",
          },
          { status: 400 },
        );
    }
  } catch (error) {
    console.error("Error in scheduler action:", error);
    return json(
      {
        success: false,
        error: "Failed to perform scheduler action",
      },
      { status: 500 },
    );
  }
};
