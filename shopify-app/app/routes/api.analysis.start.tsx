import type { ActionFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { BundleAnalyticsService } from "../features/bundle-analysis";
import { PrivateAppDataCollectionService } from "../features/data-collection";

export const action = async ({ request }: ActionFunctionArgs) => {
  try {
    const { session } = await authenticate.admin(request);
    const shopId = session.shop;

    // Parse configuration from form data (if provided)
    const formData = await request.formData();
    const config = {
      // Let smart optimization calculate these values based on store data
      // Only use form values if explicitly provided
      minConfidence: formData.get("minConfidence") ? parseFloat(formData.get("minConfidence") as string) : undefined,
      minLift: formData.get("minLift") ? parseFloat(formData.get("minLift") as string) : undefined,
      minSupport: formData.get("minSupport") ? parseFloat(formData.get("minSupport") as string) : undefined,
      maxBundleSize: formData.get("maxBundleSize") ? parseInt(formData.get("maxBundleSize") as string) : 2,
    };

    console.log("Analysis configuration (will be optimized):", config);

    // Step 1: Collect data from Shopify using private app
    const dataCollectionService = new PrivateAppDataCollectionService();
    const dataCollectionResult =
      await dataCollectionService.initializeShopData();

    // Check if we have sufficient data
    if (!dataCollectionResult.success) {
      return json(
        {
          success: false,
          error: dataCollectionResult.error || "Failed to collect store data",
          errorType: dataCollectionResult.errorType || "api-error",
        },
        { status: 400 },
      );
    }

    // Step 2: Run bundle analysis with custom configuration
    const analyticsService = new BundleAnalyticsService(config);
    await analyticsService.analyzeShop(shopId);

    return json({
      success: true,
      message:
        "Bundle analysis and time-window analysis completed successfully",
      data: {
        ordersCollected: dataCollectionResult.ordersCollected || 0,
        productsCollected: dataCollectionResult.productsCollected || 0,
      },
    });
  } catch (error) {
    console.error("Error starting bundle analysis:", error);

    // Determine error type based on the error message
    let errorType = "api-error";
    if (error instanceof Error) {
      if (error.message.includes("No orders found")) {
        errorType = "no-orders";
      } else if (error.message.includes("insufficient data")) {
        errorType = "insufficient-data";
      }
    }

    return json(
      {
        success: false,
        error: "Failed to start bundle analysis. Please try again.",
        errorType,
      },
      { status: 500 },
    );
  }
};
