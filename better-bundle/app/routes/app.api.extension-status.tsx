import { json, type LoaderFunctionArgs } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { getExtensionStatus } from "../services/extension.service";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  const { session } = await authenticate.admin(request);

  try {
    const extensionStatus = await getExtensionStatus(session.shop);

    return json({
      success: true,
      status: extensionStatus,
    });
  } catch (error) {
    console.error("Error fetching extension status:", error);
    return json({
      success: false,
      error:
        error instanceof Error
          ? error.message
          : "Failed to fetch extension status",
    });
  }
};
