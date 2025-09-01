import { json, type ActionFunctionArgs } from "@remix-run/node";
import { shopifyBillingService } from "../services/shopify-billing.service";

/**
 * POST - Process monthly billing for all shops
 * This endpoint is designed to be called by GitHub Actions cron or external cron services
 */
export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    // Verify the request is from an authorized source
    const authHeader = request.headers.get("authorization");
    const expectedToken = process.env.CRON_SECRET_TOKEN;

    if (!expectedToken || authHeader !== `Bearer ${expectedToken}`) {
      return json({ error: "Unauthorized" }, { status: 401 });
    }

    // Process monthly billing
    const result = await shopifyBillingService.processMonthlyBilling();

    if (result.success) {
      console.log(
        `Monthly billing processed: ${result.processed} shops charged successfully`,
      );

      return json({
        success: true,
        message: "Monthly billing processed successfully",
        processed: result.processed,
        errors: result.errors,
      });
    } else {
      console.error("Monthly billing failed:", result.errors);

      return json(
        {
          success: false,
          message: "Monthly billing failed",
          processed: result.processed,
          errors: result.errors,
        },
        { status: 500 },
      );
    }
  } catch (error) {
    console.error("Monthly billing cron error:", error);
    return json(
      {
        error: "Internal server error",
        details: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
};

/**
 * GET - Health check for the billing cron endpoint
 */
export const loader = async () => {
  return json({
    status: "healthy",
    message: "Monthly billing cron endpoint is active",
    timestamp: new Date().toISOString(),
  });
};
