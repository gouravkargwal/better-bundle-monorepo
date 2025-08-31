import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { SessionManager } from "../utils/session-manager.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  try {
    console.log("🔧 Fix session endpoint called");
    
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
    console.log(`🔧 Fixing session for shop: ${shopId}`);
    
    // Get current session status
    const beforeStatus = await SessionManager.getSessionStatus(shopId);
    
    // Fix the session
    const fixResult = await SessionManager.validateAndFixSession(shopId);
    
    // Get updated session status
    const afterStatus = await SessionManager.getSessionStatus(shopId);
    
    return json({
      success: true,
      shop: shopId,
      fixResult: fixResult,
      before: beforeStatus,
      after: afterStatus,
      message: fixResult.success 
        ? "Session fixed successfully" 
        : "Session fix partially completed or failed"
    });
    
  } catch (error) {
    console.error("❌ Error fixing session:", error);
    
    return json(
      {
        success: false,
        error: "Failed to fix session",
        debug: {
          errorMessage: error instanceof Error ? error.message : String(error)
        }
      },
      { status: 500 },
    );
  }
};
