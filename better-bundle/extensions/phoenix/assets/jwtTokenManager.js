/**
 * JWT Token Manager for Phoenix Extension
 * Handles JWT token generation, validation, and storage
 */

class JWTTokenManager {
  constructor() {
    this.TOKEN_KEY = 'betterbundle_jwt_token';
    this.TOKEN_EXPIRY_KEY = 'betterbundle_jwt_expiry';
    this.SHOP_DOMAIN_KEY = 'betterbundle_shop_domain';
    this.BASE_URL = window.getBaseUrl ? window.getBaseUrl() : "https://nonconscientious-annette-saddeningly.ngrok-free.dev";
    this.refreshPromise = null;
  }


  /**
   * Get valid JWT token (refresh if needed)
   */
  async getValidToken(shopDomain) {
    const storedToken = this.getStoredToken();

    // Simple check: if we have a valid token for the right shop, use it
    if (storedToken &&
      storedToken.token &&
      storedToken.shopDomain === shopDomain &&
      this.isTokenNotExpired(storedToken)) {
      return storedToken.token;
    }

    // Only get new token if we don't have a valid one
    try {
      return await this.refreshToken(shopDomain);
    } catch (error) {
      // If refresh fails, return null instead of throwing
      return null;
    }
  }

  /**
   * Refresh JWT token
   */
  async refreshToken(shopDomain) {
    if (this.refreshPromise) {
      try {
        return (await this.refreshPromise).token;
      } catch (error) {
        return null;
      }
    }

    this.refreshPromise = this.fetchNewToken(shopDomain);

    try {
      const tokenInfo = await this.refreshPromise;
      this.storeToken(tokenInfo);
      return tokenInfo.token;
    } catch (error) {
      return null;
    } finally {
      this.refreshPromise = null;
    }
  }

  /**
   * Fetch new token from backend
   */
  async fetchNewToken(shopDomain) {
    try {
      const response = await fetch(`${this.BASE_URL}/api/v1/auth/shop-token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shop_domain: shopDomain }),
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
    } catch (error) {
      throw error;
    }
  }

  /**
   * Simple check if token is not expired
   */
  isTokenNotExpired(tokenInfo) {
    if (!tokenInfo || !tokenInfo.expiresIn) return false;

    const now = Date.now() / 1000;
    const expiry = tokenInfo.expiresIn;

    // Token is valid if it expires in more than 1 minute
    return (expiry - now) > 60;
  }

  /**
   * Get stored token from localStorage
   */
  getStoredToken() {
    try {
      const token = localStorage.getItem(this.TOKEN_KEY);
      const shopDomain = localStorage.getItem(this.SHOP_DOMAIN_KEY);

      if (!token || !shopDomain) return null;

      return {
        token,
        expiresIn: parseInt(localStorage.getItem(this.TOKEN_EXPIRY_KEY) || '0'),
        shopDomain,
        shopStatus: 'unknown',
        permissions: [],
      };
    } catch (error) {
      return null;
    }
  }

  /**
   * Store token in localStorage
   */
  storeToken(tokenInfo) {
    try {
      localStorage.setItem(this.TOKEN_KEY, tokenInfo.token);
      // Convert expires_in (seconds) to timestamp
      const expiryTimestamp = Math.floor(Date.now() / 1000) + tokenInfo.expiresIn;
      localStorage.setItem(this.TOKEN_EXPIRY_KEY, expiryTimestamp.toString());
      localStorage.setItem(this.SHOP_DOMAIN_KEY, tokenInfo.shopDomain);
    } catch (error) {
      // Silently fail
    }
  }

  /**
   * Clear stored token
   */
  clearToken() {
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.TOKEN_EXPIRY_KEY);
    localStorage.removeItem(this.SHOP_DOMAIN_KEY);
  }

  /**
   * Check if shop is suspended (disabled to prevent API calls)
   */
  async isShopSuspended(shopDomain) {
    // Always return false to prevent API calls
    return false;
  }

  /**
   * Make authenticated API request
   */
  async makeAuthenticatedRequest(url, options = {}) {
    const shopDomain = this.getShopDomain();

    // Get token once and reuse it
    const token = await this.getValidToken(shopDomain);

    return fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        ...options.headers,
      },
    });
  }

  /**
   * Get shop domain from context
   */
  getShopDomain() {
    if (typeof window !== 'undefined') {
      if (window.shopDomain) return window.shopDomain;
      if (window.shop && window.shop.myshopifyDomain) return window.shop.myshopifyDomain;
      if (window.location && window.location.hostname) {
        return window.location.hostname
      }
    }
    return null;
  }
}

// Export for use in Phoenix
window.JWTTokenManager = JWTTokenManager;
