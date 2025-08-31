import { prisma } from "../core/database/prisma.server";

export class SessionScopeManager {
  static readonly REQUIRED_SCOPES = [
    "write_products",
    "read_products", 
    "read_orders",
    "write_orders"
  ];

  /**
   * Get the correct scopes string format
   */
  static getCorrectScopesString(): string {
    return this.REQUIRED_SCOPES.join(',');
  }

  /**
   * Check if session has all required scopes
   */
  static hasRequiredScopes(sessionScope: string | null): boolean {
    if (!sessionScope) return false;
    
    const sessionScopes = sessionScope.split(',').map(s => s.trim());
    return this.REQUIRED_SCOPES.every(scope => sessionScopes.includes(scope));
  }

  /**
   * Update session with correct scopes
   */
  static async updateSessionScopes(sessionId: string): Promise<boolean> {
    try {
      const correctScopes = this.getCorrectScopesString();
      
      await prisma.session.update({
        where: { id: sessionId },
        data: { scope: correctScopes }
      });
      
      console.log(`✅ Session ${sessionId} scopes updated to: ${correctScopes}`);
      return true;
    } catch (error) {
      console.error(`❌ Failed to update session scopes:`, error);
      return false;
    }
  }

  /**
   * Force update scopes for a shop (always updates regardless of current state)
   */
  static async forceUpdateScopes(shopDomain: string): Promise<boolean> {
    try {
      console.log(`🔄 Force updating scopes for shop: ${shopDomain}`);
      
      const session = await prisma.session.findUnique({
        where: { id: `offline_${shopDomain}` }
      });

      if (!session) {
        console.log(`⚠️ No session found for ${shopDomain}`);
        return false;
      }

      const correctScopes = this.getCorrectScopesString();
      console.log(`📋 Current scopes: ${session.scope}`);
      console.log(`📋 Setting scopes to: ${correctScopes}`);

      await prisma.session.update({
        where: { id: `offline_${shopDomain}` },
        data: { scope: correctScopes }
      });
      
      console.log(`✅ Force updated scopes for ${shopDomain}`);
      return true;
      
    } catch (error) {
      console.error(`❌ Error force updating scopes:`, error);
      return false;
    }
  }

  /**
   * Validate and fix session scopes for a shop
   */
  static async validateAndFixShopScopes(shopDomain: string): Promise<boolean> {
    try {
      console.log(`🔍 Validating scopes for shop: ${shopDomain}`);
      
      const session = await prisma.session.findUnique({
        where: { id: `offline_${shopDomain}` }
      });

      if (!session) {
        console.log(`⚠️ No session found for ${shopDomain}`);
        return false;
      }

      console.log(`📋 Current session scopes: ${session.scope}`);
      
      if (this.hasRequiredScopes(session.scope)) {
        console.log(`✅ Session already has correct scopes`);
        return true;
      }

      console.log(`🔄 Session missing required scopes, updating...`);
      return await this.updateSessionScopes(session.id);
      
    } catch (error) {
      console.error(`❌ Error validating shop scopes:`, error);
      return false;
    }
  }

  /**
   * Get session scope info for debugging
   */
  static async getSessionScopeInfo(shopDomain: string) {
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

      const hasRequired = this.hasRequiredScopes(session.scope);
      const correctScopes = this.getCorrectScopesString();

      return {
        found: true,
        sessionId: session.id,
        currentScopes: session.scope,
        correctScopes,
        hasRequiredScopes: hasRequired,
        missingScopes: hasRequired ? [] : this.REQUIRED_SCOPES.filter(scope => 
          !session.scope?.split(',').map(s => s.trim()).includes(scope)
        )
      };
    } catch (error) {
      return {
        found: false,
        error: error instanceof Error ? error.message : String(error)
      };
    }
  }
}
