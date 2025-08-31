import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { SessionUserManager } from "../utils/session-user-manager.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  try {
    console.log("👤 Fetch user info endpoint called");
    
    const { session } = await authenticate.admin(request);
    
    if (!session?.shop) {
      return json(
        {
          success: false,
          error: "Authentication failed - no shop in session"
        },
        { status: 401 }
      );
    }
    
    const shopId = session.shop;
    console.log(`👤 Fetching user info for shop: ${shopId}`);
    
    // Get current user info
    const beforeInfo = await SessionUserManager.getUserInfo(shopId);
    
    // Fetch and update user info
    const success = await SessionUserManager.ensureUserInfo(shopId);
    
    // Get updated user info
    const afterInfo = await SessionUserManager.getUserInfo(shopId);
    
    return json({
      success: true,
      shop: shopId,
      fetchSuccess: success,
      before: beforeInfo,
      after: afterInfo,
      message: success 
        ? "User information fetched and updated successfully" 
        : "Failed to fetch user information"
    });
    
  } catch (error) {
    console.error("❌ Error fetching user info:", error);
    
    return json(
      {
        success: false,
        error: "Failed to fetch user information",
        debug: {
          errorMessage: error instanceof Error ? error.message : String(error)
        }
      },
      { status: 500 },
    );
  }
};
