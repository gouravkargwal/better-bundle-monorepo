import { BACKEND_URL } from "../constant";

// JWT Token Management for Apollo Extension
// Note: JWT tokens are short-lived (60 seconds) and should not be persisted
// Always fetch fresh tokens when needed
export class JWTManager {
  private refreshPromise: Promise<any> | null = null;
  private storage: any;

  // In-memory cache for current session only (tokens are short-lived)
  private memoryCache: {
    token?: string;
    expiresIn?: number;
    shopDomain?: string;
  } = {};

  constructor(storage: any) {
    // Apollo runs in post-purchase context
    this.storage = storage;
  }

  async getValidToken(
    shopDomain: string,
    customerId?: string | null,
  ): Promise<string | null> {
    // Check in-memory cache first (for current session only)
    if (this.memoryCache.token && this.memoryCache.shopDomain === shopDomain) {
      const isValid = this.isTokenNotExpired({
        expiresIn: this.memoryCache.expiresIn,
      });

      if (isValid) {
        return this.memoryCache.token;
      }
    }

    // Fetch new token
    try {
      return await this.refreshToken(shopDomain, customerId);
    } catch (error) {
      console.error("❌ Apollo: Error fetching new token:", error);
      return null;
    }
  }

  private async refreshToken(
    shopDomain: string,
    customerId?: string | null,
  ): Promise<string | null> {
    if (this.refreshPromise) {
      try {
        return (await this.refreshPromise).token;
      } catch (error) {
        return null;
      }
    }

    this.refreshPromise = this.fetchNewToken(shopDomain, customerId);

    try {
      const tokenInfo = await this.refreshPromise;

      // Store in memory cache only (not persistent)
      this.memoryCache = {
        token: tokenInfo.token,
        expiresIn: Math.floor(Date.now() / 1000) + tokenInfo.expiresIn,
        shopDomain: tokenInfo.shopDomain,
      };

      return tokenInfo.token;
    } catch (error) {
      console.error("❌ Apollo: Error in refreshToken:", error);
      return null;
    } finally {
      this.refreshPromise = null;
    }
  }

  private async fetchNewToken(shopDomain: string, customerId?: string | null) {
    const requestBody: any = { shop_domain: shopDomain };

    if (customerId) {
      requestBody.customer_id = customerId;
    }

    const response = await fetch(`${BACKEND_URL}/api/v1/auth/shop-token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      throw new Error(`Token generation failed: ${response.status}`);
    }

    const data = await response.json();

    return {
      token: data.token,
      expiresIn: data.expires_in,
      shopDomain: data.shop_domain,
      shopStatus: data.shop_status,
      permissions: data.permissions,
    };
  }

  private isTokenNotExpired(tokenInfo: any): boolean {
    if (!tokenInfo || !tokenInfo.expiresIn) return false;
    const now = Date.now() / 1000;
    const expiry = tokenInfo.expiresIn;
    const isValid = expiry - now > 60; // Valid if expires in more than 1 minute
    return isValid;
  }

  async makeAuthenticatedRequest(
    url: string,
    options: RequestInit & { shopDomain?: string; customerId?: string } = {},
  ): Promise<Response> {
    const { shopDomain, customerId, ...fetchOptions } = options;
    const token = await this.getValidToken(shopDomain || "", customerId);

    if (!token) {
      throw new Error("No valid JWT token available");
    }

    const headers = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...fetchOptions.headers,
    };

    return fetch(url, {
      ...fetchOptions,
      headers,
    });
  }
}
