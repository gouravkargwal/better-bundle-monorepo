import type { LoaderFunctionArgs } from "@remix-run/node";
import { json } from "@remix-run/node";
import { authenticate } from "../shopify.server";
import { prisma } from "../core/database/prisma.server";
import { SessionScopeManager } from "../utils/session-scope-manager.server";
import { SessionUserManager } from "../utils/session-user-manager.server";

export const loader = async ({ request }: LoaderFunctionArgs) => {
  try {
    console.log("🔍 Debug session endpoint called");
    
    const url = new URL(request.url);
    console.log("🔍 Request details:", {
      method: request.method,
      url: url.pathname,
      searchParams: Object.fromEntries(url.searchParams.entries()),
      headers: Object.fromEntries(request.headers.entries())
    });
    
    const { session } = await authenticate.admin(request);
    
    console.log("🔐 Session debug result:", {
      hasSession: !!session,
      shop: session?.shop,
      hasAccessToken: !!session?.accessToken,
      sessionId: session?.id,
      expires: session?.expires,
      isOnline: session?.isOnline,
      scope: session?.scope
    });
    
    if (!session?.shop) {
      console.error("❌ No shop in session - authentication failed");
      return json(
        {
          success: false,
          error: "Authentication failed - no shop in session",
          debug: {
            hasSession: !!session,
            sessionId: session?.id,
            expires: session?.expires,
            isOnline: session?.isOnline,
            scope: session?.scope
          }
        },
        { status: 401 }
      );
    }
    
    const shopId = session.shop;
    
    // Get shop from database
    const shop = await prisma.shop.findUnique({
      where: { shopDomain: shopId },
      select: { 
        id: true,
        shopId: true,
        shopDomain: true,
        isActive: true,
        email: true,
        currencyCode: true,
        moneyFormat: true,
        createdAt: true,
        updatedAt: true
      },
    });

    // Get all sessions for this shop
    const sessions = await prisma.session.findMany({
      where: { shop: shopId },
      select: {
        id: true,
        shop: true,
        state: true,
        isOnline: true,
        scope: true,
        expires: true,
        accessToken: true,
        userId: true,
        firstName: true,
        lastName: true,
        email: true,
        accountOwner: true,
        locale: true,
        collaborator: true,
        emailVerified: true,
      },
    });

    // Get scope validation info
    const scopeInfo = await SessionScopeManager.getSessionScopeInfo(shopId);

    // Get user info validation
    const userInfo = await SessionUserManager.getUserInfo(shopId);

    return json({
      success: true,
      session: {
        hasSession: !!session,
        shop: session?.shop,
        hasAccessToken: !!session?.accessToken,
        sessionId: session?.id,
        expires: session?.expires,
        isOnline: session?.isOnline,
        scope: session?.scope
      },
      shop: shop,
      allSessions: sessions,
      sessionCount: sessions.length,
      scopeValidation: scopeInfo,
      userInfoValidation: userInfo,
      requiredScopes: SessionScopeManager.REQUIRED_SCOPES,
      correctScopesString: SessionScopeManager.getCorrectScopesString()
    });
    
  } catch (error) {
    console.error("❌ Error in session debug:", error);
    
    return json(
      {
        success: false,
        error: "Failed to debug session",
        debug: {
          errorMessage: error instanceof Error ? error.message : String(error),
          errorStack: error instanceof Error ? error.stack : undefined
        }
      },
      { status: 500 },
    );
  }
};
