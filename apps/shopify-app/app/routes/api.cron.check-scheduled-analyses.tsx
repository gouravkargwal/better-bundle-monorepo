import type { ActionFunctionArgs } from "@remix-run/node";
import { AnalysisScheduler } from "../core/scheduler/analysis-scheduler.server";

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    // Verify the request is from GitHub Actions (optional security)
    const authHeader = request.headers.get("Authorization");
    const expectedSecret = process.env.CRON_SECRET;

    if (expectedSecret && authHeader !== `Bearer ${expectedSecret}`) {
      console.log("❌ Unauthorized cron request");
      console.log(
        "🔐 Expected secret:",
        expectedSecret ? `${expectedSecret.substring(0, 10)}...` : "not set",
      );
      console.log(
        "🔑 Received header:",
        authHeader ? `${authHeader.substring(0, 20)}...` : "not set",
      );
      return Response.json({ error: "Unauthorized" }, { status: 401 });
    }

    console.log(" Cron job triggered - checking scheduled analyses...");
    console.log(`📅 Current time: ${new Date().toISOString()}`);

    // Run the scheduler logic
    await AnalysisScheduler.checkScheduledAnalyses();

    console.log("✅ Cron job completed successfully");

    return Response.json({
      success: true,
      message: "Scheduled analysis check completed",
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    console.error("❌ Cron job error:", error);

    return Response.json(
      {
        success: false,
        error: "Failed to check scheduled analyses",
        timestamp: new Date().toISOString(),
      },
      { status: 500 },
    );
  }
};
