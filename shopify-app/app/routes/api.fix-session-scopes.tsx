import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { SessionScopeManager } from "../utils/session-scope-manager.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  try {
    console.log("🔧 Fix session scopes endpoint called");
    
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
    console.log(`🔧 Fixing scopes for shop: ${shopId}`);
    
    // Get current scope info
    const beforeInfo = await SessionScopeManager.getSessionScopeInfo(shopId);
    
    // Force update the scopes to the correct values
    const success = await SessionScopeManager.forceUpdateScopes(shopId);
    
    // Get updated scope info
    const afterInfo = await SessionScopeManager.getSessionScopeInfo(shopId);
    
    return json({
      success: true,
      shop: shopId,
      fixSuccess: success,
      before: beforeInfo,
      after: afterInfo,
      message: success 
        ? "Session scopes updated successfully" 
        : "Failed to update session scopes",
      note: "If orders API still fails, the merchant needs to re-authorize the app in Shopify admin"
    });
    
  } catch (error) {
    console.error("❌ Error fixing session scopes:", error);
    
    return json(
      {
        success: false,
        error: "Failed to fix session scopes",
        debug: {
          errorMessage: error instanceof Error ? error.message : String(error)
        }
      },
      { status: 500 },
    );
  }
};
