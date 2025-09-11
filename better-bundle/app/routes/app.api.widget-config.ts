import {
  json,
  type ActionFunctionArgs,
  type LoaderFunctionArgs,
} from "@remix-run/node";
import { authenticate } from "../shopify.server";
import {
  getWidgetConfiguration,
  createDefaultConfiguration,
  updateWidgetConfiguration,
} from "../services/widget-config.service";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  try {
    // Get or create widget configuration for this shop
    let config = await getWidgetConfiguration(session.shop);
    if (!config) {
      config = await createDefaultConfiguration(session.shop);
    }

    return json({
      success: true,
      config,
      shopDomain: session.shop,
    });
  } catch (error) {
    console.error("Error loading widget configuration:", error);
    return json(
      {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
};

export const action = async ({ request }: ActionFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  try {
    const formData = await request.formData();
    const action = formData.get("_action") as string;

    switch (action) {
      case "create":
      case "update": {
        // Extract all form fields
        const updateData = {
          isActive: formData.get("isActive") === "true",
          layoutStyle: formData.get("layoutStyle") as string,
          gridColumns: parseInt(formData.get("gridColumns") as string) || 3,
          useThemeColors: formData.get("useThemeColors") === "true",

          // Product Page Settings
          productPageEnabled: formData.get("productPageEnabled") === "true",
          productPageTitle: formData.get("productPageTitle") as string,
          productPageLimit:
            parseInt(formData.get("productPageLimit") as string) || 6,
          productPageShowPrices:
            formData.get("productPageShowPrices") === "true",
          productPageShowReasons:
            formData.get("productPageShowReasons") === "true",

          // Cart Page Settings
          cartPageEnabled: formData.get("cartPageEnabled") === "true",
          cartPageTitle: formData.get("cartPageTitle") as string,
          cartPageLimit: parseInt(formData.get("cartPageLimit") as string) || 4,
          cartPageShowPrices: formData.get("cartPageShowPrices") === "true",
          cartPageShowReasons: formData.get("cartPageShowReasons") === "true",

          // Homepage Settings
          homepageEnabled: formData.get("homepageEnabled") === "true",
          homepageTitle: formData.get("homepageTitle") as string,
          homepageLimit: parseInt(formData.get("homepageLimit") as string) || 8,
          homepageShowPrices: formData.get("homepageShowPrices") === "true",
          homepageShowReasons: formData.get("homepageShowReasons") === "true",

          // Collection Page Settings
          collectionPageEnabled:
            formData.get("collectionPageEnabled") === "true",
          collectionPageTitle: formData.get("collectionPageTitle") as string,
          collectionPageLimit:
            parseInt(formData.get("collectionPageLimit") as string) || 6,
          collectionPageShowPrices:
            formData.get("collectionPageShowPrices") === "true",
          collectionPageShowReasons:
            formData.get("collectionPageShowReasons") === "true",

          // Search Results Settings
          searchPageEnabled: formData.get("searchPageEnabled") === "true",
          searchPageTitle: formData.get("searchPageTitle") as string,
          searchPageLimit:
            parseInt(formData.get("searchPageLimit") as string) || 6,
          searchPageShowPrices: formData.get("searchPageShowPrices") === "true",
          searchPageShowReasons:
            formData.get("searchPageShowReasons") === "true",

          // Blog Post Settings
          blogPageEnabled: formData.get("blogPageEnabled") === "true",
          blogPageTitle: formData.get("blogPageTitle") as string,
          blogPageLimit: parseInt(formData.get("blogPageLimit") as string) || 4,
          blogPageShowPrices: formData.get("blogPageShowPrices") === "true",
          blogPageShowReasons: formData.get("blogPageShowReasons") === "true",

          // Checkout Settings
          checkoutPageEnabled: formData.get("checkoutPageEnabled") === "true",
          checkoutPageTitle: formData.get("checkoutPageTitle") as string,
          checkoutPageLimit:
            parseInt(formData.get("checkoutPageLimit") as string) || 3,
          checkoutPageShowPrices:
            formData.get("checkoutPageShowPrices") === "true",
          checkoutPageShowReasons:
            formData.get("checkoutPageShowReasons") === "true",

          // Customer Account Settings
          accountPageEnabled: formData.get("accountPageEnabled") === "true",
          accountPageTitle: formData.get("accountPageTitle") as string,
          accountPageLimit:
            parseInt(formData.get("accountPageLimit") as string) || 6,
          accountPageShowPrices:
            formData.get("accountPageShowPrices") === "true",
          accountPageShowReasons:
            formData.get("accountPageShowReasons") === "true",

          // 404 Page Settings
          notFoundPageEnabled: formData.get("notFoundPageEnabled") === "true",
          notFoundPageTitle: formData.get("notFoundPageTitle") as string,
          notFoundPageLimit:
            parseInt(formData.get("notFoundPageLimit") as string) || 6,
          notFoundPageShowPrices:
            formData.get("notFoundPageShowPrices") === "true",
          notFoundPageShowReasons:
            formData.get("notFoundPageShowReasons") === "true",

          // Analytics
          analyticsEnabled: formData.get("analyticsEnabled") === "true",
        };

        const updatedConfig = await updateWidgetConfiguration(
          session.shop,
          updateData,
        );

        return json({
          success: true,
          config: updatedConfig,
          message: "Widget configuration updated successfully",
        });
      }

      case "reset": {
        // Reset to default configuration
        const defaultConfig = await createDefaultConfiguration(session.shop);

        return json({
          success: true,
          config: defaultConfig,
          message: "Widget configuration reset to defaults",
        });
      }

      default:
        return json(
          { success: false, error: "Invalid action" },
          { status: 400 },
        );
    }
  } catch (error) {
    console.error("Error updating widget configuration:", error);
    return json(
      {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
};
