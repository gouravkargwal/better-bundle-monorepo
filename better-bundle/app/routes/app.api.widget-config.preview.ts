import { json, type ActionFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import {
  getWidgetConfiguration,
  getContextSettings,
} from "../services/widget-config.service";

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  try {
    const formData = await request.formData();
    const configData = JSON.parse(formData.get("config") as string);
    const context = formData.get("context") as string;

    // Get context-specific settings
    const contextSettings = getContextSettings(configData, context as any);

    // Generate mock preview data
    const mockRecommendations = [
      {
        title: "Sample Product 1",
        handle: "sample-product-1",
        price: "29.99",
        currency: "USD",
        image: "https://via.placeholder.com/300x300?text=Product+1",
        imageAlt: "Sample Product 1",
        reason: contextSettings.showReasons ? "Similar products" : undefined,
      },
      {
        title: "Sample Product 2",
        handle: "sample-product-2",
        price: "39.99",
        currency: "USD",
        image: "https://via.placeholder.com/300x300?text=Product+2",
        imageAlt: "Sample Product 2",
        reason: contextSettings.showReasons ? "Recommended for you" : undefined,
      },
      {
        title: "Sample Product 3",
        handle: "sample-product-3",
        price: "19.99",
        currency: "USD",
        image: "https://via.placeholder.com/300x300?text=Product+3",
        imageAlt: "Sample Product 3",
        reason: contextSettings.showReasons ? "Popular choice" : undefined,
      },
    ].slice(0, contextSettings.limit);

    return json({
      success: true,
      preview: {
        context,
        settings: contextSettings,
        recommendations: mockRecommendations,
        layout: configData.layoutStyle || "grid",
        columns: configData.gridColumns || 3,
        useThemeColors: configData.useThemeColors !== false,
      },
    });
  } catch (error) {
    console.error("Error generating preview:", error);
    return json(
      {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
};
