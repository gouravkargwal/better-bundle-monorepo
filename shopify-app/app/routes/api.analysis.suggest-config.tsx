import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { BundleAnalyticsService } from "../features/bundle-analysis";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  try {
    const { session } = await authenticate.admin(request);
    const shopId = session.shop;

    // Get configuration suggestions
    const analyticsService = new BundleAnalyticsService();

    return json({
      success: true,
      data: { message: "Configuration suggestions not implemented yet" },
    });
  } catch (error) {
    console.error("Error getting configuration suggestions:", error);

    return json(
      {
        success: false,
        error: "Failed to get configuration suggestions. Please try again.",
      },
      { status: 500 },
    );
  }
};
