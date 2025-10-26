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
    console.log("🔍 Apollo: Getting valid token for shop:", shopDomain);

    // Check in-memory cache first (for current session only)
    if (this.memoryCache.token && this.memoryCache.shopDomain === shopDomain) {
      const isValid = this.isTokenNotExpired({
        expiresIn: this.memoryCache.expiresIn,
      });

      if (isValid) {
        console.log("✅ Apollo: Using cached token from memory");
        return this.memoryCache.token;
      } else {
        console.log("❌ Apollo: Cached token expired, fetching new one");
      }
    }

    // Fetch new token
    try {
      return await this.refreshToken(shopDomain, customerId);
    } catch (error) {
      console.log("❌ Apollo: Error fetching new token:", error);
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
      console.log("🔄 Apollo: About to store token in memory:", tokenInfo);

      // Store in memory cache only (not persistent)
      this.memoryCache = {
        token: tokenInfo.token,
        expiresIn: Math.floor(Date.now() / 1000) + tokenInfo.expiresIn,
        shopDomain: tokenInfo.shopDomain,
      };

      console.log("✅ Apollo: Token stored in memory cache");
      return tokenInfo.token;
    } catch (error) {
      console.log("❌ Apollo: Error in refreshToken:", error);
      return null;
    } finally {
      this.refreshPromise = null;
    }
  }

  private async fetchNewToken(shopDomain: string, customerId?: string | null) {
    console.log("🌐 Apollo: Fetching new token from API for shop:", shopDomain);

    const requestBody: any = { shop_domain: shopDomain };

    if (customerId) {
      requestBody.customer_id = customerId;
    }

    console.log("📤 Apollo: Token request body:", requestBody);

    const response = await fetch(`${BACKEND_URL}/api/v1/auth/shop-token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      console.log("❌ Apollo: Token generation failed:", response.status);
      throw new Error(`Token generation failed: ${response.status}`);
    }

    const data = await response.json();
    console.log("✅ Apollo: New token received from API:", {
      hasToken: !!data.token,
      expiresIn: data.expires_in,
      shopDomain: data.shop_domain,
    });

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
    console.log("🕐 Apollo: Token expiry check:", {
      now,
      expiry,
      isValid,
      timeLeft: expiry - now,
    });
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
