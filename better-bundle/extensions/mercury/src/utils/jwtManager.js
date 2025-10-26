import { BACKEND_URL } from "../constant";

// JWT Token Management for Mercury Extension
export class JWTManager {
  constructor(storage) {
    this.storage = storage;
    this.TOKEN_KEY = "betterbundle_jwt_token";
    this.TOKEN_EXPIRY_KEY = "betterbundle_jwt_expiry";
    this.SHOP_DOMAIN_KEY = "betterbundle_shop_domain";
    this.refreshPromise = null;
  }

  async getValidToken(shopDomain, customerId = null) {
    const storedToken = await this.getStoredToken();

    // Use cached token if valid
    if (
      storedToken &&
      storedToken.token &&
      storedToken.shopDomain === shopDomain &&
      this.isTokenNotExpired(storedToken)
    ) {
      return storedToken.token;
    }

    // Fetch new token
    try {
      return await this.refreshToken(shopDomain, customerId);
    } catch (error) {
      return null;
    }
  }

  async refreshToken(shopDomain, customerId = null) {
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
      await this.storeToken(tokenInfo);
      return tokenInfo.token;
    } catch (error) {
      return null;
    } finally {
      this.refreshPromise = null;
    }
  }

  async fetchNewToken(shopDomain, customerId = null) {
    const requestBody = { shop_domain: shopDomain };

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

  isTokenNotExpired(tokenInfo) {
    if (!tokenInfo || !tokenInfo.expiresIn) return false;
    const now = Date.now() / 1000;
    const expiry = tokenInfo.expiresIn;
    return expiry - now > 60; // Valid if expires in more than 1 minute
  }

  async getStoredToken() {
    try {
      const token = await this.storage.read(this.TOKEN_KEY);
      const shopDomain = await this.storage.read(this.SHOP_DOMAIN_KEY);

      if (!token || !shopDomain) return null;

      return {
        token,
        expiresIn: parseInt((await this.storage.read(this.TOKEN_EXPIRY_KEY)) || "0"),
        shopDomain,
        shopStatus: "unknown",
        permissions: [],
      };
    } catch (error) {
      return null;
    }
  }

  async storeToken(tokenInfo) {
    try {
      await this.storage.write(this.TOKEN_KEY, tokenInfo.token);
      const expiryTimestamp = Math.floor(Date.now() / 1000) + tokenInfo.expiresIn;
      await this.storage.write(this.TOKEN_EXPIRY_KEY, expiryTimestamp.toString());
      await this.storage.write(this.SHOP_DOMAIN_KEY, tokenInfo.shopDomain);
    } catch (error) {
      // Silently fail
    }
  }

  async makeAuthenticatedRequest(url, options = {}) {
    const token = await this.getValidToken(options.shopDomain, options.customerId);

    if (!token) {
      throw new Error("No valid JWT token available");
    }

    const headers = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    };

    return fetch(url, {
      ...options,
      headers,
    });
  }
}
