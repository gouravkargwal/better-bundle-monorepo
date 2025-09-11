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

    console.log("🔧 API action called:", action);
    console.log("📋 Form data keys:", Array.from(formData.keys()));

    switch (action) {
      case "create":
      case "update": {
        // Only update fields that are actually being sent from the form
        const updateData: any = {};

        // Check if each field exists in form data before adding to updateData
        if (formData.has("productPageEnabled")) {
          updateData.productPageEnabled =
            formData.get("productPageEnabled") === "true";
        }
        if (formData.has("cartPageEnabled")) {
          updateData.cartPageEnabled =
            formData.get("cartPageEnabled") === "true";
        }
        if (formData.has("homepageEnabled")) {
          updateData.homepageEnabled =
            formData.get("homepageEnabled") === "true";
        }
        if (formData.has("collectionPageEnabled")) {
          updateData.collectionPageEnabled =
            formData.get("collectionPageEnabled") === "true";
        }

        console.log("📝 Update data:", updateData);

        const updatedConfig = await updateWidgetConfiguration(
          session.shop,
          updateData,
        );

        console.log("✅ Configuration updated successfully");

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
