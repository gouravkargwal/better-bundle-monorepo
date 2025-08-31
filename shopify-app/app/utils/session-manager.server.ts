import { prisma } from "../core/database/prisma.server";
import { SessionScopeManager } from "./session-scope-manager.server";
import { SessionUserManager } from "./session-user-manager.server";

export class SessionManager {
  /**
   * Comprehensive session validation and fix
   */
  static async validateAndFixSession(shopDomain: string): Promise<{
    success: boolean;
    scopesFixed: boolean;
    userInfoFixed: boolean;
    details: any;
  }> {
    try {
      console.log(`🔧 Validating and fixing session for: ${shopDomain}`);
      
      const results = {
        success: false,
        scopesFixed: false,
        userInfoFixed: false,
        details: {}
      };

      // Check if session exists
      const session = await prisma.session.findUnique({
        where: { id: `offline_${shopDomain}` }
      });

      if (!session) {
        console.log(`❌ No session found for ${shopDomain}`);
        results.details.error = "No session found";
        return results;
      }

      console.log(`✅ Session found: ${session.id}`);

      // Fix scopes
      const scopesFixed = await SessionScopeManager.validateAndFixShopScopes(shopDomain);
      results.scopesFixed = scopesFixed;

      // Fix user info
      const userInfoFixed = await SessionUserManager.ensureUserInfo(shopDomain);
      results.userInfoFixed = userInfoFixed;

      // Get final state
      const finalScopeInfo = await SessionScopeManager.getSessionScopeInfo(shopDomain);
      const finalUserInfo = await SessionUserManager.getUserInfo(shopDomain);

      results.success = scopesFixed && userInfoFixed;
      results.details = {
        sessionId: session.id,
        scopeInfo: finalScopeInfo,
        userInfo: finalUserInfo,
        hasAccessToken: !!session.accessToken,
        isOnline: session.isOnline
      };

      console.log(`✅ Session validation completed:`, {
        success: results.success,
        scopesFixed: results.scopesFixed,
        userInfoFixed: results.userInfoFixed
      });

      return results;

    } catch (error) {
      console.error(`❌ Error in session validation:`, error);
      return {
        success: false,
        scopesFixed: false,
        userInfoFixed: false,
        details: {
          error: error instanceof Error ? error.message : String(error)
        }
      };
    }
  }

  /**
   * Get comprehensive session status
   */
  static async getSessionStatus(shopDomain: string) {
    try {
      const session = await prisma.session.findUnique({
        where: { id: `offline_${shopDomain}` }
      });

      if (!session) {
        return {
          found: false,
          message: `No session found for ${shopDomain}`
        };
      }

      const scopeInfo = await SessionScopeManager.getSessionScopeInfo(shopDomain);
      const userInfo = await SessionUserManager.getUserInfo(shopDomain);
      const shop = await prisma.shop.findUnique({
        where: { shopDomain },
        select: {
          id: true,
          shopId: true,
          shopDomain: true,
          email: true,
          currencyCode: true,
          moneyFormat: true,
          isActive: true,
          createdAt: true,
          updatedAt: true
        }
      });

      return {
        found: true,
        session: {
          id: session.id,
          shop: session.shop,
          isOnline: session.isOnline,
          scope: session.scope,
          expires: session.expires,
          hasAccessToken: !!session.accessToken,
          email: session.email,
          firstName: session.firstName,
          lastName: session.lastName
        },
        scopeValidation: scopeInfo,
        userInfoValidation: userInfo,
        shop: shop,
        status: {
          hasValidScopes: scopeInfo.found && scopeInfo.hasRequiredScopes,
          hasUserInfo: userInfo.found && !!userInfo.userInfo?.email,
          hasShopRecord: !!shop,
          isComplete: scopeInfo.found && scopeInfo.hasRequiredScopes && 
                     userInfo.found && !!userInfo.userInfo?.email && !!shop
        }
      };

    } catch (error) {
      return {
        found: false,
        error: error instanceof Error ? error.message : String(error)
      };
    }
  }

  /**
   * Force refresh session data from Shopify
   */
  static async refreshSessionData(shopDomain: string): Promise<boolean> {
    try {
      console.log(`🔄 Force refreshing session data for: ${shopDomain}`);
      
      const session = await prisma.session.findUnique({
        where: { id: `offline_${shopDomain}` },
        select: { accessToken: true }
      });

      if (!session?.accessToken) {
        console.error(`❌ No access token found for ${shopDomain}`);
        return false;
      }

      // Force refresh user info
      const userInfoSuccess = await SessionUserManager.fetchAndUpdateUserInfo(
        shopDomain, 
        session.accessToken
      );

      // Force refresh scopes
      const scopesSuccess = await SessionScopeManager.updateSessionScopes(
        `offline_${shopDomain}`
      );

      const success = userInfoSuccess && scopesSuccess;
      console.log(`✅ Session refresh completed:`, { success, userInfoSuccess, scopesSuccess });
      
      return success;

    } catch (error) {
      console.error(`❌ Error refreshing session data:`, error);
      return false;
    }
  }
}
