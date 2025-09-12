import {
  json,
  type ActionFunctionArgs,
  type LoaderFunctionArgs,
} from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { getMultiThemeExtensionStatus } from "../services/extension-detection.service";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session, admin } = await authenticate.admin(request);

  try {
    // Use multi-theme detection for comprehensive status
    const status = await getMultiThemeExtensionStatus(
      session.shop,
      admin,
      session,
    );

    return json({
      success: true,
      status,
    });
  } catch (error) {
    console.error("❌ Error checking extension status:", error);
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
  const { session, admin } = await authenticate.admin(request);

  try {
    const formData = await request.formData();
    const action = formData.get("_action") as string;

    switch (action) {
      case "refresh": {
        // Force refresh the extension status

        // Multi-theme comprehensive call that handles everything internally
        const status = await getMultiThemeExtensionStatus(
          session.shop,
          admin,
          session,
        );

        return json({
          success: true,
          status,
          message: "Extension status refreshed successfully",
        });
      }

      case "check_installation": {
        // Detailed installation check using multi-theme status
        const installationStatus = await getMultiThemeExtensionStatus(
          session.shop,
          admin,
          session,
        );

        return json({
          success: true,
          installationStatus,
        });
      }

      default:
        return json(
          { success: false, error: "Invalid action" },
          { status: 400 },
        );
    }
  } catch (error) {
    console.error("❌ Error in extension status action:", error);
    return json(
      {
        success: false,
        error: error instanceof Error ? error.message : "Unknown error",
      },
      { status: 500 },
    );
  }
};
