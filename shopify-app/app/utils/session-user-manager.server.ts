import { prisma } from "../core/database/prisma.server";

export class SessionUserManager {
  /**
   * Fetch user information from Shopify and update session
   */
  static async fetchAndUpdateUserInfo(shopDomain: string, accessToken: string): Promise<boolean> {
    try {
      console.log(`👤 Fetching user info for shop: ${shopDomain}`);
      
      // Fetch shop information from Shopify API
      const shopResponse = await fetch(`https://${shopDomain}/admin/api/2024-01/shop.json`, {
        headers: {
          'X-Shopify-Access-Token': accessToken,
          'Content-Type': 'application/json',
        },
      });

      if (!shopResponse.ok) {
        console.error(`❌ Failed to fetch shop info: ${shopResponse.status} ${shopResponse.statusText}`);
        return false;
      }

      const shopData = await shopResponse.json();
      const shop = shopData.shop;

      console.log(`📊 Shop data received:`, {
        name: shop.name,
        email: shop.email,
        domain: shop.domain,
        currency: shop.currency
      });

      // Update session with user information
      const sessionId = `offline_${shopDomain}`;
      const updatedSession = await prisma.session.update({
        where: { id: sessionId },
        data: {
          email: shop.email,
          firstName: shop.name?.split(' ')[0] || null,
          lastName: shop.name?.split(' ').slice(1).join(' ') || null,
        },
      });

      console.log(`✅ Session updated with user info:`, {
        email: updatedSession.email,
        firstName: updatedSession.firstName,
        lastName: updatedSession.lastName
      });

      // Also update the shop record with email if it doesn't have one
      const existingShop = await prisma.shop.findUnique({
        where: { shopDomain }
      });

      if (existingShop && !existingShop.email) {
        await prisma.shop.update({
          where: { shopDomain },
          data: { 
            email: shop.email,
            currencyCode: shop.currency,
            moneyFormat: shop.money_format
          }
        });
        console.log(`✅ Shop record updated with email and currency info`);
      }

      return true;

    } catch (error) {
      console.error(`❌ Error fetching user info:`, error);
      return false;
    }
  }

  /**
   * Check if session has user information
   */
  static async hasUserInfo(shopDomain: string): Promise<boolean> {
    try {
      const session = await prisma.session.findUnique({
        where: { id: `offline_${shopDomain}` },
        select: { email: true, firstName: true, lastName: true }
      });

      return !!(session?.email || session?.firstName || session?.lastName);
    } catch (error) {
      console.error(`❌ Error checking user info:`, error);
      return false;
    }
  }

  /**
   * Get user information from session
   */
  static async getUserInfo(shopDomain: string) {
    try {
      const session = await prisma.session.findUnique({
        where: { id: `offline_${shopDomain}` },
        select: { 
          email: true, 
          firstName: true, 
          lastName: true,
          userId: true,
          accountOwner: true,
          locale: true,
          collaborator: true,
          emailVerified: true
        }
      });

      return {
        found: !!session,
        userInfo: session ? {
          email: session.email,
          firstName: session.firstName,
          lastName: session.lastName,
          userId: session.userId,
          accountOwner: session.accountOwner,
          locale: session.locale,
          collaborator: session.collaborator,
          emailVerified: session.emailVerified
        } : null
      };
    } catch (error) {
      return {
        found: false,
        error: error instanceof Error ? error.message : String(error)
      };
    }
  }

  /**
   * Ensure user information is available in session
   */
  static async ensureUserInfo(shopDomain: string): Promise<boolean> {
    try {
      // Check if we already have user info
      const hasInfo = await this.hasUserInfo(shopDomain);
      if (hasInfo) {
        console.log(`✅ User info already available for ${shopDomain}`);
        return true;
      }

      // Get session to access token
      const session = await prisma.session.findUnique({
        where: { id: `offline_${shopDomain}` },
        select: { accessToken: true }
      });

      if (!session?.accessToken) {
        console.error(`❌ No access token found for ${shopDomain}`);
        return false;
      }

      // Fetch and update user info
      return await this.fetchAndUpdateUserInfo(shopDomain, session.accessToken);

    } catch (error) {
      console.error(`❌ Error ensuring user info:`, error);
      return false;
    }
  }
}
